"""HTTP transport: one pooled client per host profile, for the process lifetime.

Defect 3 from the plan lives here. The engine this replaces constructed a new
`AsyncClient` for every request, which meant a new TCP connection and a new TLS
handshake for every request -- two round trips of pure overhead before any work, and no
HTTP/2 multiplexing ever. A pool keyed by host profile fixes both.

A *profile* is (scheme, host, port, auth mode, proxy, verify). Two requests that differ
in any of those cannot share a connection, and two that match in all of them always
should.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any

import httpx

from sclpl.errors import StepFailed
from sclpl.render.events import StepRetrying
from sclpl.render.reporter import Reporter
from sclpl.run.fixtures import Fixture
from sclpl.run.fixtures import Store as FixtureStore
from sclpl.run.retry import (
    REAL_CLOCK,
    Adaptive,
    Breaker,
    Clock,
    Retry,
    is_retryable_error,
    response_retry_after,
    summarise_reason,
)


@dataclass(frozen=True, slots=True)
class Profile:
    """What makes two requests able to share a connection."""

    scheme: str
    host: str
    port: int | None = None
    auth: str = ""
    proxy: str | None = None
    verify: bool = True

    @classmethod
    def of(
        cls, url: str, *, auth: str = "", proxy: str | None = None, verify: bool = True
    ) -> Profile:
        parsed = httpx.URL(url)
        return cls(
            scheme=parsed.scheme,
            host=parsed.host,
            port=parsed.port,
            auth=auth,
            proxy=proxy,
            verify=verify,
        )

    def __str__(self) -> str:
        port = f":{self.port}" if self.port else ""
        return f"{self.scheme}://{self.host}{port}"


def _http2_available() -> bool:
    """Whether `h2` is importable.

    It is a declared dependency (`httpx[http2]`), but an environment can end up with
    plain httpx -- an older lockfile, a partial install. Asking httpx for HTTP/2 then
    is an ImportError at the first request, which is a crash rather than an answer.
    Falling back to HTTP/1.1 costs multiplexing and nothing else.
    """
    try:
        import h2  # noqa: F401
    except ImportError:
        return False
    return True


HTTP2_AVAILABLE = _http2_available()


@dataclass(slots=True)
class TransportLimits:
    """Connection-pool sizing and timeouts."""

    max_connections: int = 32
    max_keepalive: int = 16
    keepalive_expiry: float = 30.0
    timeout: float = 30.0
    connect_timeout: float = 10.0
    http2: bool = True
    follow_redirects: bool = True
    verify: bool = True

    @property
    def use_http2(self) -> bool:
        return self.http2 and HTTP2_AVAILABLE


@dataclass(slots=True)
class Attempt:
    """One completed request, with what it cost."""

    response: httpx.Response
    attempts: int
    duration_ms: int
    retried: bool = False


@dataclass(slots=True)
class Streamed:
    """What a body written straight to disk cost, and what it turned out to be.

    No `httpx.Response` here: its body was never held in memory to hand back, only
    written to ``path`` in bounded chunks as it arrived.
    """

    status: int
    headers: dict[str, str]
    url: str
    path: Path
    bytes_written: int
    sha256: str
    attempts: int
    duration_ms: int


#: Streamed one chunk at a time, so a multi-gigabyte body never sits fully in memory
#: -- only this much of it does, at any one point.
STREAM_CHUNK_BYTES = 64 * 1024


class Pool:
    """Pooled clients, per-host breakers, and adaptive limits.

    Owned by the run and closed with it. `aclose` is idempotent and closes every client
    even if one of them raises, because a leaked connection outlives the process that
    made it only in the sense that the remote keeps it open waiting.
    """

    __slots__ = (
        "_clients",
        "_limits",
        "_breakers",
        "_adaptive",
        "_retry",
        "_lock",
        "_closed",
        "_adaptive_on",
        "_fixtures",
        "_recorder",
        "_occurrences",
        "_clock",
    )

    def __init__(
        self,
        limits: TransportLimits | None = None,
        retry: Retry | None = None,
        *,
        adaptive: bool = True,
        fixtures: FixtureStore | None = None,
        recorder: FixtureStore | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._limits = limits if limits is not None else TransportLimits()
        self._retry = retry if retry is not None else Retry()
        self._clients: dict[Profile, httpx.AsyncClient] = {}
        self._breakers: dict[str, Breaker] = {}
        self._adaptive: dict[str, Adaptive] = {}
        self._adaptive_on = adaptive
        self._lock = asyncio.Lock()
        self._closed = False
        self._fixtures = fixtures
        self._recorder = recorder
        self._occurrences: dict[tuple[str, str], int] = {}
        self._clock = clock if clock is not None else REAL_CLOCK

    async def client(self, profile: Profile) -> httpx.AsyncClient:
        """The client for this profile, created once."""
        existing = self._clients.get(profile)
        if existing is not None:
            return existing
        async with self._lock:
            # Re-check: another task may have created it while we waited.
            existing = self._clients.get(profile)
            if existing is not None:
                return existing
            created = httpx.AsyncClient(
                http2=self._limits.use_http2,
                # `profile.verify` is already the effective value -- the caller's
                # explicit choice, or the pool's default when it made none -- so it
                # is used as-is rather than ANDed with the pool default again, which
                # would let a globally-insecure pool silently override a step that
                # explicitly asked for verification.
                verify=profile.verify,
                follow_redirects=self._limits.follow_redirects,
                timeout=httpx.Timeout(
                    self._limits.timeout,
                    connect=self._limits.connect_timeout,
                ),
                limits=httpx.Limits(
                    max_connections=self._limits.max_connections,
                    max_keepalive_connections=self._limits.max_keepalive,
                    keepalive_expiry=self._limits.keepalive_expiry,
                ),
                proxy=profile.proxy,
            )
            self._clients[profile] = created
            return created

    def breaker(self, host: str) -> Breaker:
        existing = self._breakers.get(host)
        if existing is None:
            existing = Breaker(now=self._clock.now)
            self._breakers[host] = existing
        return existing

    def adaptive(self, host: str, ceiling: int) -> Adaptive:
        existing = self._adaptive.get(host)
        if existing is None:
            existing = Adaptive(ceiling=ceiling)
            self._adaptive[host] = existing
        return existing

    async def request(
        self,
        method: str,
        url: str,
        *,
        reporter: Reporter | None = None,
        step: str = "request",
        retry: Retry | None = None,
        auth: str = "",
        proxy: str | None = None,
        verify: bool | None = None,
        **kwargs: Any,
    ) -> Attempt:
        """Send a request, retrying per policy. Returns the final response.

        A non-2xx status is *not* an exception: an API that answers 404 has answered,
        and the workflow may well want to branch on it. Only exhausting the retries, or
        an open circuit, raises.

        ``auth``/``proxy``/``verify`` partition the connection pool (`Profile`), not
        just this one call: two steps naming different auth profiles against the same
        host never share a connection, so a proxy or TLS setting tied to one profile
        can never leak onto a request made under another.
        """
        policy = retry if retry is not None else self._retry
        occurrence_key = (method.upper(), url)
        occurrence = self._occurrences.get(occurrence_key, 0)
        self._occurrences[occurrence_key] = occurrence + 1
        if self._fixtures is not None:
            fixture = self._fixtures.replay(method, url, occurrence=occurrence)
            response = httpx.Response(
                fixture.status,
                headers=fixture.headers,
                content=fixture.body,
                request=httpx.Request(method, url),
            )
            if self._recorder is not None:
                self._recorder.record(
                    Fixture(
                        method,
                        url,
                        occurrence,
                        response.status_code,
                        dict(response.headers),
                        response.content,
                    )
                )
            return Attempt(response=response, attempts=1, duration_ms=0)
        effective_verify = verify if verify is not None else self._limits.verify
        profile = Profile.of(url, auth=auth, proxy=proxy, verify=effective_verify)
        breaker = self.breaker(profile.host)
        client = await self.client(profile)
        started = self._clock.now()

        if not breaker.allows():
            raise StepFailed(
                f"circuit open for {profile.host}: {breaker.threshold} consecutive failures",
                remedies=[
                    f"it will try again in about {breaker.reset_after:.0f}s",
                    "check the host is up, or raise --retries",
                ],
            )

        last_error: BaseException | None = None
        for attempt in range(policy.max + 1):
            attempt_started = self._clock.now()
            try:
                response = await client.request(method, url, **kwargs)
            except Exception as error:  # noqa: BLE001 - classified just below
                last_error = error
                breaker.record_failure()
                if (
                    attempt >= policy.max
                    or not is_retryable_error(error, policy)
                    or not policy.allows_transport_retry(method)
                ):
                    raise self._exhausted(method, url, attempt, error, None) from error
                await self._wait(reporter, step, attempt, policy, None, error, None)
                continue

            latency = self._clock.now() - attempt_started
            self._observe(profile.host, latency, response.status_code)

            if policy.should_retry_status(response.status_code) and attempt < policy.max:
                breaker.record_failure()
                await self._wait(
                    reporter,
                    step,
                    attempt,
                    policy,
                    response.status_code,
                    None,
                    response_retry_after(response),
                )
                continue

            if response.status_code >= 500:
                breaker.record_failure()
            else:
                breaker.record_success()
            if self._recorder is not None:
                self._recorder.record(
                    Fixture(
                        method,
                        url,
                        occurrence,
                        response.status_code,
                        dict(response.headers),
                        response.content,
                    )
                )
            return Attempt(
                response=response,
                attempts=attempt + 1,
                duration_ms=int((self._clock.now() - started) * 1000),
                retried=attempt > 0,
            )

        raise self._exhausted(method, url, policy.max, last_error, None)

    async def stream_to_file(
        self,
        method: str,
        url: str,
        destination: Path,
        *,
        reporter: Reporter | None = None,
        step: str = "request",
        retry: Retry | None = None,
        auth: str = "",
        proxy: str | None = None,
        verify: bool | None = None,
        **kwargs: Any,
    ) -> Streamed:
        """Write a response body straight to ``destination``, one chunk at a time.

        The body never accumulates in memory: each chunk is written and hashed as it
        arrives, so this holds roughly `STREAM_CHUNK_BYTES` regardless of whether the
        body is a kilobyte or a hundred gigabytes. Written beside the destination and
        renamed atomically only on complete success, so a crash, a cancellation, or a
        checksum caller later rejects can never leave a partial file at a name the
        rest of the workflow trusts as done.
        """
        policy = retry if retry is not None else self._retry
        effective_verify = verify if verify is not None else self._limits.verify
        profile = Profile.of(url, auth=auth, proxy=proxy, verify=effective_verify)
        breaker = self.breaker(profile.host)
        client = await self.client(profile)
        started = self._clock.now()

        if not breaker.allows():
            raise StepFailed(
                f"circuit open for {profile.host}: {breaker.threshold} consecutive failures",
                remedies=[
                    f"it will try again in about {breaker.reset_after:.0f}s",
                    "check the host is up, or raise --retries",
                ],
            )

        last_error: BaseException | None = None
        for attempt in range(policy.max + 1):
            scratch = destination.with_name(f"{destination.name}.partial-{os.getpid()}")
            done = False
            try:
                async with client.stream(method, url, **kwargs) as response:
                    if policy.should_retry_status(response.status_code) and attempt < policy.max:
                        # `async with` closes the streamed response on the way out,
                        # whether that is this `continue` or the exception below.
                        breaker.record_failure()
                        await self._wait(
                            reporter,
                            step,
                            attempt,
                            policy,
                            response.status_code,
                            None,
                            response_retry_after(response),
                        )
                        continue

                    hasher = hashlib.sha256()
                    total = 0
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with open(scratch, "wb") as handle:
                        async for chunk in response.aiter_bytes(STREAM_CHUNK_BYTES):
                            handle.write(chunk)
                            hasher.update(chunk)
                            total += len(chunk)
                    os.replace(scratch, destination)
                    done = True

                    if response.status_code >= 500:
                        breaker.record_failure()
                    else:
                        breaker.record_success()
                    return Streamed(
                        status=response.status_code,
                        headers=dict(response.headers),
                        url=str(response.url),
                        path=destination,
                        bytes_written=total,
                        sha256=hasher.hexdigest(),
                        attempts=attempt + 1,
                        duration_ms=int((self._clock.now() - started) * 1000),
                    )
            except Exception as error:  # noqa: BLE001 - classified just below
                last_error = error
                breaker.record_failure()
                if (
                    attempt >= policy.max
                    or not is_retryable_error(error, policy)
                    or not policy.allows_transport_retry(method)
                ):
                    raise self._exhausted(method, url, attempt, error, None) from error
                await self._wait(reporter, step, attempt, policy, None, error, None)
                continue
            finally:
                # Reached on the happy path (nothing left to clean up: `scratch` was
                # already renamed away), on a caught `Exception` above, and -- the
                # part `except Exception` alone would miss -- on cancellation, which
                # is a `BaseException` in this Python and propagates straight through
                # both `except` clauses here without either one seeing it.
                if not done:
                    scratch.unlink(missing_ok=True)

        raise self._exhausted(method, url, policy.max, last_error, None)

    def _observe(self, host: str, latency: float, status: int) -> None:
        if not self._adaptive_on:
            return
        self.adaptive(host, self._limits.max_connections).record(latency, status)

    async def _wait(
        self,
        reporter: Reporter | None,
        step: str,
        attempt: int,
        policy: Retry,
        status: int | None,
        error: BaseException | None,
        retry_after: float | None,
    ) -> None:
        delay = policy.delay_for(attempt, retry_after, jitter=self._clock.jitter())
        if reporter is not None:
            reporter.emit(
                StepRetrying(
                    id=step,
                    attempt=attempt + 1,
                    max=policy.max,
                    reason=summarise_reason(error, status),
                    delay_s=delay,
                )
            )
        await self._clock.sleep(delay)

    def _exhausted(
        self,
        method: str,
        url: str,
        attempts: int,
        error: BaseException | None,
        status: int | None,
    ) -> StepFailed:
        reason = summarise_reason(error, status)
        remedies = ["raise --retries, or --timeout if it is timing out"]
        if isinstance(error, httpx.ConnectError):
            remedies = ["check the host name and that it is reachable"]
        elif isinstance(error, httpx.TimeoutException):
            remedies = ["raise --timeout, or lower --concurrency if you are saturating it"]
        return StepFailed(
            f"{method} {url} failed after {attempts + 1} attempt"
            f"{'' if attempts == 0 else 's'}: {reason}",
            remedies=remedies,
        )

    def stats(self) -> dict[str, Any]:
        return {
            "profiles": len(self._clients),
            "hosts": sorted({profile.host for profile in self._clients}),
            "breakers": {host: breaker.state for host, breaker in self._breakers.items()},
            "limits": {host: control.limit for host, control in self._adaptive.items()},
        }

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        for client in list(self._clients.values()):
            # Close every one even if one of them fails.
            with contextlib.suppress(Exception):
                await client.aclose()
        self._clients.clear()

    async def __aenter__(self) -> Pool:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()


@dataclass(slots=True)
class Request:
    """A request as a workflow describes it, before variables are resolved."""

    method: str = "GET"
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    query: dict[str, Any] = field(default_factory=dict)
    body: Any = None
    json_body: Any = None
    timeout: float | None = None

    def kwargs(self) -> dict[str, Any]:
        """The httpx keyword arguments for this request."""
        out: dict[str, Any] = {}
        if self.headers:
            out["headers"] = self.headers
        if self.query:
            out["params"] = self.query
        if self.json_body is not None:
            out["json"] = self.json_body
        elif self.body is not None:
            out["content"] = self.body
        if self.timeout is not None:
            out["timeout"] = self.timeout
        return out


def decode(response: httpx.Response) -> Any:
    """Turn a response body into a typed value.

    JSON becomes real Python objects, which is what the whole engine is built on. A
    body that claims to be JSON and is not raises rather than silently arriving as a
    string, because a downstream `@a.body.items` would then fail somewhere much less
    obvious.
    """
    content_type = response.headers.get("content-type", "")
    if "json" in content_type:
        try:
            return response.json()
        except ValueError as error:
            raise StepFailed(
                f"{response.request.url} claimed {content_type} but the body is not JSON",
                remedies=[
                    "look at the raw body with -vvv",
                    "the server may be returning an error page with the wrong header",
                ],
            ) from error
    if content_type.startswith("text/") or not content_type:
        return response.text
    return response.content


def summarise(response: httpx.Response, attempts: int) -> str:
    """The step-line summary for a completed request."""
    from sclpl.render.plain import format_bytes

    size = format_bytes(len(response.content))
    tail = f" after {attempts} attempts" if attempts > 1 else ""
    return f"{response.status_code} {response.reason_phrase} {size}{tail}"
