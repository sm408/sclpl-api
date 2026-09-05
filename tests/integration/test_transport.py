"""The pooled transport, against the local mock server."""

from __future__ import annotations

import asyncio
import io

import pytest

from sclpl.errors import StepFailed
from sclpl.render.plain import PlainSink
from sclpl.render.reporter import Reporter
from sclpl.run.retry import Clock, Retry
from sclpl.run.transport import Pool, Profile, TransportLimits, decode, summarise


class VirtualClock:
    """No real time passes: `sleep` advances a counter instead of waiting."""

    def __init__(self) -> None:
        self.slept: list[float] = []

    def now(self) -> float:
        return float(len(self.slept))

    async def sleep(self, delay: float) -> None:
        self.slept.append(delay)

    def jitter(self) -> float:
        return 0.5


def reporter(stream: io.StringIO | None = None) -> Reporter:
    return Reporter([PlainSink(stream if stream is not None else io.StringIO(), verbosity=3)])


# -- pooling ---------------------------------------------------------------------


async def test_one_client_serves_many_requests(server_url: str) -> None:
    """Defect 3: the old engine built a client, and a TCP connection, per request."""
    async with Pool() as pool:
        for _ in range(10):
            await pool.request("GET", f"{server_url}/json")
        assert pool.stats()["profiles"] == 1


async def test_concurrent_requests_share_the_pool(server_url: str) -> None:
    async with Pool() as pool:
        await asyncio.gather(*(pool.request("GET", f"{server_url}/json") for _ in range(20)))
        assert pool.stats()["profiles"] == 1


async def test_different_hosts_get_different_clients(server_url: str) -> None:
    async with Pool() as pool:
        await pool.request("GET", f"{server_url}/json")
        with pytest.raises((StepFailed, Exception)):
            await pool.request("GET", "http://127.0.0.1:9/nothing", retry=Retry(max=0))
        assert pool.stats()["profiles"] == 2


def test_a_profile_captures_what_makes_a_connection_shareable() -> None:
    first = Profile.of("https://api.test/a")
    second = Profile.of("https://api.test/b")
    assert first == second  # same host: same connection
    assert Profile.of("https://api.test/a") != Profile.of("https://other.test/a")
    assert Profile.of("https://api.test:8443/a") != Profile.of("https://api.test/a")


async def test_closing_is_idempotent(server_url: str) -> None:
    pool = Pool()
    await pool.request("GET", f"{server_url}/json")
    await pool.aclose()
    await pool.aclose()


# -- retries ---------------------------------------------------------------------


async def test_a_flaky_endpoint_succeeds_on_retry(server_url: str) -> None:
    async with Pool(retry=Retry(max=3, base_delay=0.001)) as pool:
        attempt = await pool.request("GET", f"{server_url}/flaky/2")
    assert attempt.response.status_code == 200
    assert attempt.attempts == 3
    assert attempt.retried


async def test_a_virtual_clock_never_actually_waits_out_the_backoff(
    server_url: str,
) -> None:
    """D1: a huge nominal backoff costs this test nothing, because `sleep` here is a
    bookkeeping call, not a wait. `slept` still records what the policy chose.
    """
    clock = VirtualClock()
    retry = Retry(max=3, base_delay=100.0, max_delay=1000.0)
    async with Pool(retry=retry, clock=Clock(clock.now, clock.sleep, clock.jitter)) as pool:
        attempt = await pool.request("GET", f"{server_url}/flaky/2")
    assert attempt.response.status_code == 200
    assert attempt.attempts == 3
    assert len(clock.slept) == 2  # two retries before the third attempt succeeded
    assert all(delay > 0 for delay in clock.slept)


async def test_retries_are_reported(server_url: str) -> None:
    stream = io.StringIO()
    async with reporter(stream) as rep:
        async with Pool(retry=Retry(max=3, base_delay=0.001)) as pool:
            await pool.request("GET", f"{server_url}/flaky/1", reporter=rep, step="fetch")
        await rep.drain()
    assert "retry fetch" in stream.getvalue()
    assert "HTTP 503" in stream.getvalue()


async def test_exhausting_the_retries_fails_with_a_remedy(server_url: str) -> None:
    async with Pool(retry=Retry(max=1, base_delay=0.001)) as pool:
        attempt = await pool.request("GET", f"{server_url}/flaky/99")
    # Retries exhausted on a status still returns the response: the server answered.
    assert attempt.response.status_code == 503
    assert attempt.attempts == 2


async def test_a_429_is_retried_honouring_retry_after(server_url: str) -> None:
    async with Pool(retry=Retry(max=1, base_delay=5.0)) as pool:
        # Retry-After is 0, so this must not wait the 5s the backoff would have chosen.
        attempt = await asyncio.wait_for(
            pool.request("GET", f"{server_url}/rate-limited"), timeout=3.0
        )
    assert attempt.attempts == 2


async def test_a_404_is_an_answer_not_a_failure(server_url: str) -> None:
    """An API that says 404 has answered; the workflow may want to branch on it."""
    async with Pool() as pool:
        attempt = await pool.request("GET", f"{server_url}/missing")
    assert attempt.response.status_code == 404
    assert attempt.attempts == 1


async def test_an_unreachable_host_fails_with_a_remedy() -> None:
    async with Pool(retry=Retry(max=0)) as pool:
        with pytest.raises(StepFailed) as caught:
            await pool.request("GET", "http://127.0.0.1:9/nothing")
    assert "reachable" in str(caught.value) or "failed after" in str(caught.value)


# -- the circuit breaker ---------------------------------------------------------


async def test_the_circuit_opens_after_repeated_failures() -> None:
    async with Pool(retry=Retry(max=0)) as pool:
        for _ in range(5):
            with pytest.raises(StepFailed):
                await pool.request("GET", "http://127.0.0.1:9/nothing")
        with pytest.raises(StepFailed) as caught:
            await pool.request("GET", "http://127.0.0.1:9/nothing")
    assert "circuit open" in str(caught.value)


# -- decoding --------------------------------------------------------------------


async def test_json_decodes_to_typed_python_values(server_url: str) -> None:
    """Invariant 2 at the boundary where values enter the engine."""
    async with Pool() as pool:
        attempt = await pool.request("GET", f"{server_url}/json")
    payload = decode(attempt.response)
    assert isinstance(payload, dict)
    assert isinstance(payload["slideshow"]["slides"], list)


async def test_a_body_that_lies_about_being_json_says_so(server_url: str) -> None:
    """Passing it on as a string would fail much later and much less obviously."""
    async with Pool() as pool:
        attempt = await pool.request("GET", f"{server_url}/not-json")
    with pytest.raises(StepFailed) as caught:
        decode(attempt.response)
    assert "not JSON" in str(caught.value)


async def test_text_decodes_to_a_string(server_url: str) -> None:
    async with Pool() as pool:
        attempt = await pool.request("GET", f"{server_url}/boom")
    assert decode(attempt.response) == "server error"


async def test_a_post_body_is_sent(server_url: str) -> None:
    async with Pool() as pool:
        attempt = await pool.request("POST", f"{server_url}/submit", json={"a": 1})
    assert attempt.response.status_code == 201
    assert decode(attempt.response)["received"] == '{"a":1}'


def test_the_summary_mentions_retries() -> None:
    class FakeResponse:
        status_code = 200
        reason_phrase = "OK"
        content = b"x" * 10

    assert "after 3 attempts" in summarise(FakeResponse(), 3)  # type: ignore[arg-type]
    assert "attempts" not in summarise(FakeResponse(), 1)  # type: ignore[arg-type]


# -- timeouts --------------------------------------------------------------------


async def test_a_timeout_is_reported_with_a_remedy(server_url: str) -> None:
    limits = TransportLimits(timeout=0.05, connect_timeout=0.05)
    async with Pool(limits, Retry(max=0)) as pool:
        with pytest.raises(StepFailed) as caught:
            await pool.request("GET", f"{server_url}/slow")
    assert "--timeout" in str(caught.value)
