"""Retry policy: backoff with full jitter, `Retry-After`, and a circuit breaker.

Two things here are not negotiable when talking to someone else's server.

**`Retry-After` is obeyed exactly.** When a server says how long to wait, waiting less
is not an optimisation, it is ignoring the only signal that will make the next attempt
succeed.

**Backoff is fully jittered.** Exponential backoff without jitter synchronises every
client that failed at the same moment into retrying at the same moment, which is how a
recovering server gets knocked back down. `random() * base * 2**attempt` spreads them.
"""

from __future__ import annotations

import asyncio
import email.utils
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

#: Statuses worth trying again. 429 is rate limiting; 5xx are the server's problem, not
#: the request's. 4xx otherwise means the request was wrong and will stay wrong.
RETRY_STATUSES: frozenset[int] = frozenset({408, 425, 429, 500, 502, 503, 504})

#: Beyond this a "retry" is really a hang. A server asking for an hour needs a
#: scheduled run, not a held connection.
MAX_RETRY_AFTER_SECONDS = 300.0

#: Safe to repeat without asking: HTTP itself defines these as idempotent, so a
#: connection error or timeout that leaves the first attempt's outcome unknown is not
#: a reason to withhold a second one. POST and PATCH are not here on purpose --
#: resending a POST after a timeout can create the order twice, not zero or one times,
#: because a timeout does not tell you whether the server ever saw the request.
IDEMPOTENT_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE", "TRACE"})


@dataclass(frozen=True, slots=True)
class Clock:
    """Time, sleep, and randomness, gathered so a test can replace all three at once.

    D1: the transport used to reach directly for `time.perf_counter`, `asyncio.sleep`,
    and `random.random`, which means testing backoff timing or breaker recovery meant
    either a real wait or monkeypatching a stdlib module out from under every other
    test in the process. Real time and real randomness by default; a test builds its
    own `Clock` with a controllable `now`/`sleep`/`jitter` instead.
    """

    now: Callable[[], float] = time.monotonic
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    jitter: Callable[[], float] = random.random


REAL_CLOCK = Clock()


@dataclass(slots=True)
class Retry:
    """How many times, how long between, and on what."""

    max: int = 3
    base_delay: float = 0.5
    max_delay: float = 30.0
    statuses: frozenset[int] = RETRY_STATUSES
    #: Retry on connection errors and timeouts as well as statuses.
    on_transport_error: bool = True
    #: Explicit opt-in: retry a transport-level failure even for POST/PATCH, because
    #: the caller knows the operation is idempotent (an upsert keyed by a client-
    #: supplied id, say) even though its HTTP method does not promise it.
    idempotent: bool = False

    def allows_transport_retry(self, method: str) -> bool:
        """Whether a connection error or timeout on ``method`` may be retried at all.

        A received response -- even a 500 -- already completed the HTTP exchange, so
        `should_retry_status` governs that case regardless of method. This method
        answers a narrower question: after a failure with no response at all, is a
        second attempt safe without being told so explicitly?
        """
        return self.idempotent or method.upper() in IDEMPOTENT_METHODS

    def delay_for(
        self, attempt: int, retry_after: float | None = None, *, jitter: float | None = None
    ) -> float:
        """How long to wait before ``attempt``, honouring the server if it spoke.

        ``jitter`` is a spread factor in ``[0, 1)``; the caller supplies one already
        drawn (from a `Clock`, ordinarily) rather than this method drawing its own, so
        a deterministic test can pin the exact delay instead of asserting a range.
        """
        if retry_after is not None:
            return min(max(0.0, retry_after), MAX_RETRY_AFTER_SECONDS)
        # `2 ** attempt` types as Any (it is float for a negative exponent), so pin it.
        growth: float = float(2**attempt)
        ceiling = min(self.max_delay, self.base_delay * growth)
        drawn = jitter if jitter is not None else random.random()  # noqa: S311 - spreading load
        return drawn * ceiling

    def should_retry_status(self, status: int) -> bool:
        return status in self.statuses


def parse_retry_after(value: str | None) -> float | None:
    """`Retry-After` as seconds, from either the delta or the HTTP-date form."""
    if not value:
        return None
    text = value.strip()
    try:
        return float(text)
    except ValueError:
        pass
    try:
        when = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    delta = when.timestamp() - time.time()
    return max(0.0, delta)


@dataclass(slots=True)
class Breaker:
    """A per-host circuit breaker.

    After ``threshold`` consecutive failures the circuit opens and further requests to
    that host fail immediately instead of queueing behind a dead server. It half-opens
    on a timer: one request is let through, and its result decides whether to close.
    """

    threshold: int = 5
    reset_after: float = 30.0
    #: Monotonic time source. Real by default; a test injects one it controls so a
    #: reset window does not mean an actual wait.
    now: Callable[[], float] = time.monotonic
    _failures: int = 0
    _opened_at: float | None = None
    _probing: bool = False

    @property
    def state(self) -> str:
        if self._opened_at is None:
            return "closed"
        return "half-open" if self._probing else "open"

    def allows(self) -> bool:
        if self._opened_at is None:
            return True
        if self.now() - self._opened_at >= self.reset_after:
            self._probing = True
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._probing = False

    def record_failure(self) -> None:
        self._failures += 1
        if self._probing:
            # The probe failed: back to fully open, and start the timer again.
            self._probing = False
            self._opened_at = self.now()
            return
        if self._failures >= self.threshold:
            self._opened_at = self.now()


@dataclass(slots=True)
class Adaptive:
    """AIMD concurrency control, per host.

    Additive increase while latency is flat, multiplicative decrease on a 429 or 503.
    Never exceeds the static cap: adaptation tunes *down* from a ceiling the user set,
    it does not discover a higher one.
    """

    ceiling: int
    current: float = field(init=False)
    minimum: int = 1
    #: p95 samples, newest last. Bounded so an hour-long run does not accumulate.
    latencies: list[float] = field(default_factory=list)
    window: int = 32

    def __post_init__(self) -> None:
        self.current = float(self.ceiling)

    @property
    def limit(self) -> int:
        return max(self.minimum, min(self.ceiling, int(self.current)))

    def record(self, latency: float, status: int | None = None) -> bool:
        """Feed one result back. Returns True when the limit changed."""
        before = self.limit
        self.latencies.append(latency)
        if len(self.latencies) > self.window:
            del self.latencies[0]

        if status in (429, 503):
            self.current = max(self.minimum, self.current / 2)
        elif self._latency_is_flat():
            self.current = min(self.ceiling, self.current + 1)
        return self.limit != before

    def _latency_is_flat(self) -> bool:
        """True when recent p95 is no worse than the earlier half of the window."""
        if len(self.latencies) < self.window:
            return False
        half = len(self.latencies) // 2
        return _p95(self.latencies[half:]) <= _p95(self.latencies[:half]) * 1.2


def _p95(samples: list[float]) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    index = min(len(ordered) - 1, int(len(ordered) * 0.95))
    return ordered[index]


def summarise_reason(error: BaseException | None, status: int | None) -> str:
    """A short reason for the retry line the user sees."""
    if status is not None:
        return f"HTTP {status}"
    if error is not None:
        return type(error).__name__
    return "unknown"


def is_retryable_error(error: BaseException, policy: Retry) -> bool:
    """Whether a transport-level failure is worth another attempt.

    Timeouts and connection errors are; a malformed URL or an SSL certificate that does
    not match will fail identically every time, and retrying only delays the message.
    """
    if not policy.on_transport_error:
        return False
    import httpx

    if isinstance(error, (httpx.ConnectError, httpx.ReadError, httpx.WriteError)):
        return True
    if isinstance(error, httpx.TimeoutException):
        return True
    # A protocol error is usually a connection the server closed mid-response.
    return isinstance(error, httpx.RemoteProtocolError)


def response_retry_after(response: Any) -> float | None:
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    return parse_retry_after(headers.get("Retry-After"))
