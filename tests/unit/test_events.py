"""Event protocol: naming, serialisation, and the verbosity policy."""

from __future__ import annotations

import pytest

from sclpl.render.events import (
    Event,
    LogRecord,
    RunFinished,
    RunStarted,
    StepFinished,
    StepProgress,
    StepStarted,
    as_dict,
    event_name,
    visible_at,
)


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        (RunStarted(workflow="w"), "run_started"),
        (StepStarted(id="a", kind="http"), "step_started"),
        (StepFinished(id="a", status="ok", duration_ms=1), "step_finished"),
        (LogRecord(level="info", message="m"), "log_record"),
        (RunFinished(status="ok", duration_ms=1), "run_finished"),
    ],
)
def test_event_name_is_snake_case(event: Event, expected: str) -> None:
    assert event_name(event) == expected


def test_as_dict_carries_every_field_and_unpacks_tuples() -> None:
    payload = as_dict(RunStarted(workflow="orders", mode="partial", hosts=("a.test", "b.test")))
    assert payload["workflow"] == "orders"
    assert payload["mode"] == "partial"
    # JSON has no tuple; the sink must not have to know that.
    assert payload["hosts"] == ["a.test", "b.test"]
    assert isinstance(payload["hosts"], list)


def test_errors_survive_quiet() -> None:
    """A failure the user cannot see is a silent wrong answer."""
    failure = StepFinished(id="a", status="failed", duration_ms=1)
    assert visible_at(failure, -1)
    assert visible_at(LogRecord(level="error", message="boom"), -1)


def test_routine_events_are_hidden_when_quiet() -> None:
    assert not visible_at(StepFinished(id="a", status="ok", duration_ms=1), -1)
    assert not visible_at(StepProgress(id="a", detail="pages", current=2), -1)


def test_step_started_needs_verbose() -> None:
    started = StepStarted(id="a", kind="http")
    assert not visible_at(started, 0)
    assert visible_at(started, 1)


def test_debug_logs_need_double_verbose() -> None:
    record = LogRecord(level="debug", message="admission")
    assert not visible_at(record, 1)
    assert visible_at(record, 2)
