"""A failed `assert` promises `-vv` shows the values it was checking.

Nothing ever made that true: `_assert` raised `AssertionFailed` with that remedy in
its text, but never emitted anything a `-vv` sink could actually show. A user running
workflows against a real project noticed the promise was empty. This pins the fix: a
failing assertion now logs a bounded, redaction-aware debug preview of the value it
checked, at exactly the level `-vv` (`verbosity=2`) unlocks.
"""

from __future__ import annotations

from typing import Any

import pytest

from sclpl.errors import AssertionFailed
from sclpl.render.events import Event, LogRecord
from sclpl.render.reporter import Reporter
from sclpl.run.execute import Runtime, _assert, _preview
from sclpl.run.ir import LetConfig, Step, WorkflowDoc
from sclpl.run.transport import Pool
from sclpl.values.store import ValueStore


class Recorder:
    """A sink that remembers what it was given."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def handle(self, event: Event) -> None:
        self.events.append(event)

    def close(self) -> None:
        pass


def _step(assert_: str) -> Step:
    return Step(id="fetch", kind="let", config=LetConfig(value=1), assert_=assert_)


def _runtime(doc: WorkflowDoc, reporter: Reporter) -> Runtime:
    return Runtime(doc=doc, store=ValueStore(), reporter=reporter, pool=Pool())


def _debug_records(recorder: Recorder) -> list[LogRecord]:
    return [
        event
        for event in recorder.events
        if isinstance(event, LogRecord) and event.level == "debug"
    ]


async def test_a_failed_assertion_logs_the_value_it_checked_at_debug_level() -> None:
    recorder = Recorder()
    doc = WorkflowDoc(name="orders")
    async with Reporter([recorder]) as reporter:
        with pytest.raises(AssertionFailed):
            await _assert(_step("false"), {"status": 500}, _runtime(doc, reporter))

    debug_records = _debug_records(recorder)
    assert len(debug_records) == 1
    assert debug_records[0].step == "fetch"
    assert "500" in debug_records[0].message


async def test_a_passing_assertion_logs_nothing() -> None:
    recorder = Recorder()
    doc = WorkflowDoc(name="orders")
    async with Reporter([recorder]) as reporter:
        await _assert(_step("true"), {"status": 200}, _runtime(doc, reporter))
    assert recorder.events == []


async def test_a_resolved_secret_in_the_checked_value_is_still_redacted() -> None:
    recorder = Recorder()
    doc = WorkflowDoc(name="orders")
    async with Reporter([recorder]) as reporter:
        reporter.secret("hunter2-distinctive")
        with pytest.raises(AssertionFailed):
            await _assert(_step("false"), {"token": "hunter2-distinctive"}, _runtime(doc, reporter))

    debug_records = _debug_records(recorder)
    assert len(debug_records) == 1
    assert "hunter2-distinctive" not in debug_records[0].message


def test_the_preview_is_bounded_for_a_large_value() -> None:
    huge: dict[str, Any] = {"rows": list(range(10_000))}
    text = _preview(huge)
    assert len(text) < 600
    assert text.endswith("... (truncated)")
