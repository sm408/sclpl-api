"""What the human and plain sinks actually put on the screen."""

from __future__ import annotations

import io

from sclpl.render.events import (
    LogRecord,
    RunFinished,
    RunStarted,
    StepFinished,
    StepProgress,
    StepRetrying,
)
from sclpl.render.human import HumanSink
from sclpl.render.plain import PlainSink, format_bytes, format_duration, plural
from sclpl.render.term import ESC, Caps, display_width


def test_plural_agrees() -> None:
    assert plural(1, "step") == "1 step"
    assert plural(3, "step") == "3 steps"


def test_duration_scales_by_magnitude() -> None:
    assert format_duration(42) == "42ms"
    assert format_duration(1500) == "1.5s"
    assert format_duration(65_000) == "1m05.0s"


def test_bytes_scale_by_magnitude() -> None:
    assert format_bytes(429) == "429B"
    assert format_bytes(2048) == "2.0KB"


def test_plain_sink_emits_no_escape_sequences() -> None:
    stream = io.StringIO()
    sink = PlainSink(stream, verbosity=3)
    for event in (
        RunStarted(workflow="orders", mode="partial", steps_total=2),
        StepProgress(id="fetch", detail="pages", current=3, total=40),
        StepRetrying(id="fetch", attempt=2, max=5, reason="429", delay_s=1.5),
        StepFinished(id="fetch", status="ok", duration_ms=1200, summary="200 OK"),
        RunFinished(status="ok", duration_ms=1300, counts={"steps": 2}),
    ):
        sink.handle(event)
    assert ESC not in stream.getvalue()


def test_plain_sink_reports_the_mode_and_step_count() -> None:
    stream = io.StringIO()
    PlainSink(stream).handle(RunStarted(workflow="orders", mode="partial", steps_total=12))
    assert "orders [partial]" in stream.getvalue()
    assert "12 steps" in stream.getvalue()


def test_human_sink_colours_when_it_can() -> None:
    stream = io.StringIO()
    sink = HumanSink(Caps(rung="full", color=True, width=100), stream)
    sink.handle(StepFinished(id="fetch", status="ok", duration_ms=12))
    assert ESC in stream.getvalue()


def test_human_sink_stays_plain_when_colour_is_off() -> None:
    stream = io.StringIO()
    sink = HumanSink(Caps(rung="full", color=False, width=100), stream)
    sink.handle(StepFinished(id="fetch", status="ok", duration_ms=12))
    assert ESC not in stream.getvalue()


def test_human_sink_never_exceeds_the_terminal_width() -> None:
    """A wrapped line occupies two rows and desynchronises every later cursor move."""
    stream = io.StringIO()
    sink = HumanSink(Caps(rung="full", color=True, width=40), stream)
    sink.handle(
        StepFinished(
            id="a-very-long-step-identifier" * 4,
            status="ok",
            duration_ms=1,
            summary="x" * 200,
        )
    )
    for line in stream.getvalue().splitlines():
        assert display_width(line) <= 40


def test_human_sink_falls_back_to_ascii_glyphs() -> None:
    stream = io.StringIO()
    sink = HumanSink(Caps(rung="full", color=False, unicode=False, width=80), stream)
    sink.handle(StepFinished(id="a", status="ok", duration_ms=1))
    written = stream.getvalue()
    assert "+" in written
    assert "✔" not in written


def test_human_sink_descends_to_plain_from_simple() -> None:
    sink = HumanSink(Caps(rung="simple", color=True, width=80), io.StringIO())
    assert isinstance(sink.descend(), PlainSink)


def test_human_sink_descends_full_to_simple() -> None:
    sink = HumanSink(Caps(rung="full", color=True, width=80), io.StringIO())
    lowered = sink.descend()
    assert isinstance(lowered, HumanSink)


def test_failed_steps_are_marked() -> None:
    stream = io.StringIO()
    PlainSink(stream).handle(
        StepFinished(id="fetch", status="failed", duration_ms=30, summary="500 Server Error")
    )
    assert "FAIL" in stream.getvalue()
    assert "500 Server Error" in stream.getvalue()


def test_cached_steps_say_so() -> None:
    stream = io.StringIO()
    PlainSink(stream).handle(StepFinished(id="fetch", status="ok", duration_ms=0, cached=True))
    assert "cached" in stream.getvalue()


def test_log_records_name_their_step() -> None:
    stream = io.StringIO()
    PlainSink(stream).handle(LogRecord(level="warning", message="slow", step="fetch"))
    assert "[fetch]" in stream.getvalue()
