"""The reporter: single-writer discipline, sink selection, and failure handling."""

from __future__ import annotations

import io
import json

import pytest

from sclpl.render.events import Event, LogRecord, RunFinished, RunStarted, StepFinished
from sclpl.render.human import HumanSink
from sclpl.render.jsonl import JsonlSink
from sclpl.render.plain import PlainSink, QuietSink
from sclpl.render.reporter import Reporter, build_reporter
from sclpl.render.term import Caps


class Recorder:
    """A sink that remembers what it was given."""

    def __init__(self) -> None:
        self.events: list[Event] = []
        self.closed = False

    def handle(self, event: Event) -> None:
        self.events.append(event)

    def close(self) -> None:
        self.closed = True


class Exploder:
    """A sink that fails the way a resized-away terminal does."""

    def __init__(self) -> None:
        self.calls = 0

    def handle(self, event: Event) -> None:
        self.calls += 1
        raise OSError("terminal went away")

    def close(self) -> None:
        pass


async def test_events_reach_the_sink_in_order() -> None:
    recorder = Recorder()
    async with Reporter([recorder]) as reporter:
        reporter.emit(RunStarted(workflow="w"))
        reporter.emit(StepFinished(id="a", status="ok", duration_ms=3))
        reporter.emit(RunFinished(status="ok", duration_ms=4))
    assert [type(event).__name__ for event in recorder.events] == [
        "RunStarted",
        "StepFinished",
        "RunFinished",
    ]
    assert recorder.closed


async def test_secrets_are_scrubbed_before_any_sink_sees_them() -> None:
    """Redaction lives in the reporter so a new sink cannot introduce a leak."""
    recorder = Recorder()
    async with Reporter([recorder]) as reporter:
        reporter.secret("top-secret-key")
        reporter.log("info", "using top-secret-key now")
    message = recorder.events[0]
    assert isinstance(message, LogRecord)
    assert "top-secret-key" not in message.message


async def test_emit_after_close_is_dropped_not_raised() -> None:
    recorder = Recorder()
    reporter = Reporter([recorder])
    await reporter.__aenter__()
    await reporter.aclose()
    reporter.emit(RunStarted(workflow="late"))
    assert not recorder.events


async def test_a_failing_sink_drops_out_rather_than_failing_the_run() -> None:
    exploder = Exploder()
    recorder = Recorder()
    async with Reporter([exploder, recorder]) as reporter:
        reporter.emit(RunStarted(workflow="w"))
        reporter.emit(RunFinished(status="ok", duration_ms=1))
    # It raised once, was removed, and the surviving sink saw everything.
    assert exploder.calls == 1
    assert len(recorder.events) == 2


async def test_a_failing_human_sink_descends_instead_of_disappearing() -> None:
    stream = io.StringIO()
    human = HumanSink(Caps(rung="full", color=True, width=80), stream)
    reporter = Reporter([human])
    async with reporter:
        stream.close()  # writing now raises, as a vanished terminal would
        reporter.emit(RunStarted(workflow="w"))
    # It dropped a rung rather than going silent.
    assert reporter._sinks  # noqa: SLF001 - asserting on the ladder is the point


async def test_drain_waits_for_everything_queued() -> None:
    recorder = Recorder()
    async with Reporter([recorder]) as reporter:
        for index in range(50):
            reporter.emit(StepFinished(id=str(index), status="ok", duration_ms=1))
        await reporter.drain()
        assert len(recorder.events) == 50


@pytest.mark.parametrize(
    ("verbosity", "json_mode", "expected"),
    [
        (0, False, PlainSink),
        (-1, False, QuietSink),
        (-2, False, QuietSink),
        (0, True, JsonlSink),
        (-2, True, JsonlSink),  # machine output wins over quiet
    ],
)
def test_sink_selection(verbosity: int, json_mode: bool, expected: type) -> None:
    reporter = build_reporter(
        verbosity=verbosity,
        json_mode=json_mode,
        stream=io.StringIO(),  # not a tty, so the human rung is off the table
    )
    assert isinstance(reporter._sinks[0], expected)  # noqa: SLF001


def test_plain_flag_forces_the_bottom_rung() -> None:
    reporter = build_reporter(
        plain=True,
        stream=io.StringIO(),
        caps=Caps(rung="full", color=True, width=80),
    )
    assert isinstance(reporter._sinks[0], PlainSink)  # noqa: SLF001


def test_jsonl_writes_one_object_per_line() -> None:
    stream = io.StringIO()
    sink = JsonlSink(stream)
    sink.handle(RunStarted(workflow="orders", mode="partial", steps_total=3))
    sink.handle(RunFinished(status="ok", duration_ms=12, counts={"steps": 3}))
    lines = stream.getvalue().strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["event"] == "run_started"
    assert first["workflow"] == "orders"
    assert "ts" in first
    assert json.loads(lines[1])["counts"] == {"steps": 3}


def test_quiet_stays_silent_until_something_fails() -> None:
    stream = io.StringIO()
    sink = QuietSink(stream)
    sink.handle(RunStarted(workflow="w"))
    sink.handle(StepFinished(id="a", status="ok", duration_ms=1))
    assert stream.getvalue() == ""
    sink.handle(StepFinished(id="b", status="failed", duration_ms=1, summary="500"))
    assert "FAIL b" in stream.getvalue()


def test_silent_says_nothing_even_on_failure() -> None:
    stream = io.StringIO()
    sink = QuietSink(stream, silent=True)
    sink.handle(StepFinished(id="b", status="failed", duration_ms=1))
    sink.handle(RunFinished(status="failed", duration_ms=1))
    assert stream.getvalue() == ""
