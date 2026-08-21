"""Redaction — invariant 9. A leak here is the failure mode with no recovery."""

from __future__ import annotations

import pytest

from sclpl.render.events import LogRecord, RunStarted, StepFinished
from sclpl.render.redact import MASK, Redactor, TooShortToRedact


def test_secret_is_masked_in_a_message() -> None:
    redactor = Redactor(["s3cret-token-value"])
    event = redactor.apply(LogRecord(level="info", message="auth with s3cret-token-value ok"))
    assert isinstance(event, LogRecord)
    assert "s3cret-token-value" not in event.message
    assert MASK in event.message


def test_longest_secret_wins() -> None:
    """A key that contains a shorter secret must be masked whole, not in pieces."""
    redactor = Redactor(["abcd", "abcd-efgh-ijkl"])
    assert redactor.scrub("token=abcd-efgh-ijkl") == f"token={MASK}"


def test_nested_containers_are_scrubbed() -> None:
    redactor = Redactor(["hunter2!"])
    event = redactor.apply(RunStarted(workflow="w", hosts=("api.test/hunter2!",)))
    assert isinstance(event, RunStarted)
    assert event.hosts == (f"api.test/{MASK}",)


def test_untouched_events_are_returned_unchanged() -> None:
    redactor = Redactor(["hunter2!"])
    original = StepFinished(id="a", status="ok", duration_ms=5, summary="200 OK")
    assert redactor.apply(original) is original


def test_no_secrets_is_a_passthrough() -> None:
    redactor = Redactor()
    original = LogRecord(level="info", message="anything at all")
    assert redactor.apply(original) is original


def test_short_secrets_are_refused_not_silently_ignored() -> None:
    """Substituting a 2-character secret would shred every message instead."""
    with pytest.raises(TooShortToRedact):
        Redactor(["ab"])


def test_empty_secret_is_dropped() -> None:
    redactor = Redactor([""])
    assert not redactor
