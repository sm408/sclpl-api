"""Retry policy, the circuit breaker, and adaptive concurrency."""

from __future__ import annotations

import time
from email.utils import formatdate

import pytest

from sclpl.run.retry import (
    MAX_RETRY_AFTER_SECONDS,
    Adaptive,
    Breaker,
    Retry,
    parse_retry_after,
    summarise_reason,
)

# -- backoff ---------------------------------------------------------------------


def test_backoff_grows_with_the_attempt() -> None:
    policy = Retry(base_delay=1.0, max_delay=100.0)
    # Jittered, so compare ceilings over many samples rather than single values.
    early = max(policy.delay_for(0) for _ in range(200))
    late = max(policy.delay_for(4) for _ in range(200))
    assert late > early


def test_backoff_is_jittered() -> None:
    """Without jitter every client that failed together retries together."""
    policy = Retry(base_delay=10.0)
    samples = {policy.delay_for(3) for _ in range(50)}
    assert len(samples) > 40


def test_backoff_is_capped() -> None:
    policy = Retry(base_delay=1.0, max_delay=5.0)
    assert all(policy.delay_for(20) <= 5.0 for _ in range(100))


def test_retry_after_overrides_the_backoff_exactly() -> None:
    """When a server says how long to wait, waiting less is ignoring the only signal."""
    policy = Retry(base_delay=0.001, max_delay=0.002)
    assert policy.delay_for(0, retry_after=7.5) == 7.5


def test_an_absurd_retry_after_is_capped() -> None:
    policy = Retry()
    assert policy.delay_for(0, retry_after=99999) == MAX_RETRY_AFTER_SECONDS


@pytest.mark.parametrize(
    ("status", "expected"),
    [(429, True), (503, True), (500, True), (404, False), (200, False), (401, False)],
)
def test_which_statuses_are_worth_retrying(status: int, expected: bool) -> None:
    assert Retry().should_retry_status(status) is expected


# -- Retry-After parsing ---------------------------------------------------------


def test_retry_after_as_seconds() -> None:
    assert parse_retry_after("120") == 120.0


def test_retry_after_as_an_http_date() -> None:
    when = formatdate(time.time() + 60, usegmt=True)
    parsed = parse_retry_after(when)
    assert parsed is not None
    assert 50 <= parsed <= 70


def test_a_retry_after_in_the_past_is_zero() -> None:
    when = formatdate(time.time() - 600, usegmt=True)
    assert parse_retry_after(when) == 0.0


@pytest.mark.parametrize("value", [None, "", "not a date"])
def test_unparseable_retry_after_is_ignored(value: str | None) -> None:
    assert parse_retry_after(value) is None


# -- idempotency policy (D2) -------------------------------------------------------


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS", "PUT", "DELETE", "TRACE", "get"])
def test_idempotent_methods_allow_a_transport_retry(method: str) -> None:
    assert Retry().allows_transport_retry(method)


@pytest.mark.parametrize("method", ["POST", "PATCH", "post"])
def test_unsafe_methods_refuse_a_transport_retry_by_default(method: str) -> None:
    assert not Retry().allows_transport_retry(method)


@pytest.mark.parametrize("method", ["POST", "PATCH"])
def test_the_idempotent_override_allows_any_method(method: str) -> None:
    assert Retry(idempotent=True).allows_transport_retry(method)


# -- injected clock and randomness (D1) -------------------------------------------


def test_an_injected_jitter_makes_the_delay_deterministic() -> None:
    policy = Retry(base_delay=1.0, max_delay=100.0)
    assert policy.delay_for(3, jitter=0.5) == policy.delay_for(3, jitter=0.5)
    assert policy.delay_for(3, jitter=0.0) == 0.0
    assert policy.delay_for(3, jitter=1.0) == min(100.0, 1.0 * 2**3)


def test_an_injected_jitter_does_not_disturb_the_uninjected_default() -> None:
    """Existing callers that never pass `jitter` still get real randomness."""
    policy = Retry(base_delay=1.0, max_delay=100.0)
    samples = {policy.delay_for(3) for _ in range(20)}
    assert len(samples) > 1


# -- circuit breaker -------------------------------------------------------------


def test_the_circuit_opens_after_consecutive_failures() -> None:
    breaker = Breaker(threshold=3)
    assert breaker.allows()
    for _ in range(3):
        breaker.record_failure()
    assert not breaker.allows()
    assert breaker.state == "open"


def test_a_success_resets_the_count() -> None:
    breaker = Breaker(threshold=3)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()
    assert breaker.allows()


def test_the_circuit_half_opens_on_a_timer() -> None:
    breaker = Breaker(threshold=1, reset_after=0.0)
    breaker.record_failure()
    assert breaker.allows()
    assert breaker.state == "half-open"


def test_a_failed_probe_reopens_the_circuit() -> None:
    breaker = Breaker(threshold=1, reset_after=0.0)
    breaker.record_failure()
    breaker.allows()  # half-open
    breaker.record_failure()
    assert breaker.state == "open"


def test_a_successful_probe_closes_the_circuit() -> None:
    breaker = Breaker(threshold=1, reset_after=0.0)
    breaker.record_failure()
    breaker.allows()
    breaker.record_success()
    assert breaker.state == "closed"


def test_an_injected_clock_governs_the_reset_window_exactly() -> None:
    """No `reset_after=0.0` trick needed: a virtual clock proves the exact boundary."""
    ticks = iter([0.0, 29.9, 30.0])
    breaker = Breaker(threshold=1, reset_after=30.0, now=lambda: next(ticks))
    breaker.record_failure()  # opens at t=0
    assert not breaker.allows()  # checked at t=29.9: still open
    assert breaker.allows()  # checked at t=30.0: exactly at the boundary, half-open
    assert breaker.state == "half-open"


# -- adaptive concurrency --------------------------------------------------------


def test_a_429_halves_the_limit() -> None:
    control = Adaptive(ceiling=16)
    control.record(0.1, 429)
    assert control.limit == 8


def test_repeated_pressure_keeps_reducing_but_never_below_one() -> None:
    control = Adaptive(ceiling=16)
    for _ in range(20):
        control.record(0.1, 429)
    assert control.limit == 1


def test_adaptation_never_exceeds_the_static_cap() -> None:
    """Adaptation tunes down from a ceiling the user set; it does not discover a higher one."""
    control = Adaptive(ceiling=4)
    for _ in range(200):
        control.record(0.01, 200)
    assert control.limit <= 4


def test_it_recovers_when_latency_is_flat() -> None:
    control = Adaptive(ceiling=16)
    control.record(0.1, 429)
    lowered = control.limit
    for _ in range(control.window * 2):
        control.record(0.1, 200)
    assert control.limit > lowered


def test_a_503_is_treated_like_a_429() -> None:
    control = Adaptive(ceiling=8)
    control.record(0.1, 503)
    assert control.limit == 4


def test_reasons_are_short_enough_for_a_step_line() -> None:
    assert summarise_reason(None, 429) == "HTTP 429"
    assert summarise_reason(TimeoutError(), None) == "TimeoutError"
    assert summarise_reason(None, None) == "unknown"
