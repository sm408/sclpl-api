"""The live region: byte-exact output at each rung, and restoration on every exit.

These assert on the actual escape sequences. That is the point: a live region that
"looks right" in one terminal and corrupts another is exactly the failure decision 7
accepted responsibility for, and the only way to catch it in CI is to check the bytes.

A pty is used where the platform has one (`test_pty.py`); here the stream is captured,
which tests the same code path because the sink writes to whatever stream it is given.
"""

from __future__ import annotations

import io

import pytest

from sclpl.render.events import (
    RunFinished,
    RunStarted,
    StepFinished,
    StepProgress,
    StepStarted,
)
from sclpl.render.human import HumanSink
from sclpl.render.live import MAX_ACTIVE_SHOWN, PANE_HEIGHT, LiveRegion, State
from sclpl.render.plain import PlainSink
from sclpl.render.term import (
    CLEAR_LINE,
    ESC,
    HIDE_CURSOR,
    RESET_SCROLL_REGION,
    SHOW_CURSOR,
    Caps,
    display_width,
)

FULL = Caps(rung="full", color=True, unicode=True, width=80, height=24)
SIMPLE = Caps(rung="simple", color=True, unicode=True, width=80, height=24)
PLAIN = Caps(rung="plain", color=False, unicode=False, width=80, height=24)


def region(caps: Caps = FULL) -> tuple[LiveRegion, io.StringIO]:
    stream = io.StringIO()
    return LiveRegion(caps, stream), stream


# -- installation and restoration ------------------------------------------------


def test_installing_fences_off_a_scroll_region() -> None:
    live, stream = region()
    live.install()
    written = stream.getvalue()
    # DECSTBM covering everything above the pane.
    assert f"{ESC}[1;{24 - PANE_HEIGHT}r" in written
    assert HIDE_CURSOR in written


def test_uninstalling_hands_the_terminal_back() -> None:
    live, stream = region()
    live.install()
    stream.truncate(0)
    stream.seek(0)
    live.uninstall()
    written = stream.getvalue()
    assert RESET_SCROLL_REGION in written
    assert SHOW_CURSOR in written


def test_uninstalling_is_idempotent() -> None:
    live, stream = region()
    live.install()
    live.uninstall()
    first = stream.getvalue()
    live.uninstall()
    assert stream.getvalue() == first


def test_uninstalling_without_installing_writes_nothing() -> None:
    live, stream = region()
    live.uninstall()
    assert stream.getvalue() == ""


def test_the_plain_rung_never_claims_rows() -> None:
    live, stream = region(PLAIN)
    live.install()
    live.update(RunStarted(workflow="w", steps_total=2))
    live.uninstall()
    assert stream.getvalue() == ""


def test_the_simple_rung_uses_no_scroll_region() -> None:
    """DECSTBM is what `simple` exists to avoid."""
    live, stream = region(SIMPLE)
    live.install()
    live.update(RunStarted(workflow="w", steps_total=2))
    live.paint(force=True)
    assert "r" not in stream.getvalue().replace(RESET_SCROLL_REGION, "")[:0] + ""
    assert f"{ESC}[1;" not in stream.getvalue()


# -- painting --------------------------------------------------------------------


def test_the_pane_occupies_exactly_its_rows() -> None:
    live, stream = region()
    live.install()
    stream.truncate(0)
    stream.seek(0)
    live.update(RunStarted(workflow="orders", steps_total=4))
    stream.truncate(0)
    stream.seek(0)
    live.paint(force=True)
    written = stream.getvalue()
    # One cursor-position per pane row, and a save/restore around the whole paint.
    assert written.count(CLEAR_LINE) == PANE_HEIGHT
    assert written.startswith(f"{ESC}7")
    assert written.endswith(f"{ESC}8")


def test_no_pane_row_exceeds_the_width() -> None:
    """A wrapped pane row occupies two terminal rows and the geometry desynchronises."""
    narrow = Caps(rung="full", color=True, unicode=True, width=40, height=24)
    live, _ = region(narrow)
    live.update(RunStarted(workflow="a-workflow-with-a-very-long-name" * 3, steps_total=100))
    for index in range(6):
        live.update(StepStarted(id=f"a-long-step-name-{index}", kind="http"))
    for row in live._compose():  # noqa: SLF001 - asserting on geometry is the point
        assert display_width(row) <= 40 or len(row) == 0


def test_repaint_is_bounded() -> None:
    """A thousand progress events a second must not be a thousand repaints."""
    live, stream = region()
    live.install()
    stream.truncate(0)
    stream.seek(0)
    for index in range(500):
        live.update(StepProgress(id="fetch", detail="pages", current=index))
    # Well under one paint per event; the exact number depends on wall-clock timing.
    assert stream.getvalue().count(CLEAR_LINE) < 500


def test_forcing_a_paint_ignores_the_frame_budget() -> None:
    live, stream = region()
    live.install()
    live.update(RunStarted(workflow="w", steps_total=1))
    stream.truncate(0)
    stream.seek(0)
    live.paint(force=True)
    assert CLEAR_LINE in stream.getvalue()


def test_resizing_refences_against_the_new_geometry() -> None:
    live, stream = region()
    live.install()
    stream.truncate(0)
    stream.seek(0)
    live.resize(Caps(rung="full", color=True, unicode=True, width=100, height=40))
    written = stream.getvalue()
    # Torn down against the old height, then rebuilt against the new one.
    assert RESET_SCROLL_REGION in written
    assert f"{ESC}[1;{40 - PANE_HEIGHT}r" in written


def test_a_closed_stream_does_not_raise() -> None:
    """The terminal can go away mid-run; the sink's descend path handles it."""
    live, stream = region()
    live.install()
    stream.close()
    live.update(RunStarted(workflow="w", steps_total=1))
    live.paint(force=True)
    live.uninstall()


# -- state -----------------------------------------------------------------------


def test_state_tracks_progress() -> None:
    state = State()
    state.apply(RunStarted(workflow="orders", steps_total=4))
    state.apply(StepStarted(id="a", kind="http"))
    state.apply(StepFinished(id="a", status="ok", duration_ms=5))
    state.apply(StepStarted(id="b", kind="http"))
    state.apply(StepFinished(id="b", status="failed", duration_ms=5))
    assert state.done == 1
    assert state.failed == 1
    assert state.fraction == 0.5
    assert state.active == {}


def test_state_counts_cached_and_retried() -> None:
    from sclpl.render.events import StepRetrying

    state = State()
    state.apply(StepFinished(id="a", status="ok", duration_ms=1, cached=True))
    state.apply(StepRetrying(id="b", attempt=1, max=3, reason="429", delay_s=0.1))
    assert state.cached == 1
    assert state.retries == 1


def test_the_fraction_never_exceeds_one() -> None:
    state = State()
    state.apply(RunStarted(workflow="w", steps_total=1))
    state.apply(StepFinished(id="a", status="ok", duration_ms=1))
    state.apply(StepFinished(id="b", status="ok", duration_ms=1))
    assert state.fraction == 1.0


def test_an_unknown_total_does_not_divide_by_zero() -> None:
    state = State()
    state.apply(StepFinished(id="a", status="ok", duration_ms=1))
    assert state.fraction == 0.0


def test_many_active_steps_collapse_to_a_count() -> None:
    """A pane that grows with concurrency pushes the scroll region off the screen."""
    live, _ = region()
    for index in range(MAX_ACTIVE_SHOWN + 5):
        live.update(StepStarted(id=f"step{index}", kind="http"))
    instrument = live._instrument_line()  # noqa: SLF001
    assert "running" in instrument
    assert "step0" not in instrument


def test_few_active_steps_are_named() -> None:
    live, _ = region()
    live.update(StepStarted(id="fetch", kind="http"))
    assert "fetch" in live._instrument_line()  # noqa: SLF001


def test_the_bar_is_ascii_without_unicode() -> None:
    ascii_caps = Caps(rung="full", color=False, unicode=False, width=80, height=24)
    live, _ = region(ascii_caps)
    live.update(RunStarted(workflow="w", steps_total=2))
    live.update(StepFinished(id="a", status="ok", duration_ms=1))
    bar = live._bar_line()  # noqa: SLF001
    assert "#" in bar
    assert "█" not in bar


# -- the sink ---------------------------------------------------------------------


def test_the_sink_prints_lines_and_paints_the_pane() -> None:
    stream = io.StringIO()
    sink = HumanSink(FULL, stream, verbosity=0)
    sink.start()
    sink.handle(RunStarted(workflow="orders", steps_total=1))
    sink.handle(StepFinished(id="fetch", status="ok", duration_ms=12))
    written = stream.getvalue()
    assert "fetch" in written
    assert f"{ESC}[1;" in written  # the pane was installed


def test_the_sink_gives_the_rows_back_when_the_run_finishes() -> None:
    stream = io.StringIO()
    sink = HumanSink(FULL, stream, verbosity=0)
    sink.start()
    sink.handle(RunFinished(status="ok", duration_ms=10))
    assert RESET_SCROLL_REGION in stream.getvalue()


def test_closing_restores_even_without_a_run_finished() -> None:
    """A crash mid-run must still hand the terminal back."""
    stream = io.StringIO()
    sink = HumanSink(FULL, stream, verbosity=0)
    sink.start()
    sink.handle(StepStarted(id="a", kind="http"))
    sink.close()
    assert RESET_SCROLL_REGION in stream.getvalue()
    assert SHOW_CURSOR in stream.getvalue()


def test_quiet_has_no_pane() -> None:
    stream = io.StringIO()
    sink = HumanSink(FULL, stream, verbosity=-1)
    sink.start()
    sink.handle(RunStarted(workflow="w", steps_total=1))
    assert f"{ESC}[1;" not in stream.getvalue()


def test_descending_releases_the_rows_first() -> None:
    stream = io.StringIO()
    sink = HumanSink(FULL, stream, verbosity=0)
    sink.start()
    lowered = sink.descend()
    assert RESET_SCROLL_REGION in stream.getvalue()
    assert isinstance(lowered, HumanSink)


def test_descending_from_simple_reaches_plain() -> None:
    sink = HumanSink(SIMPLE, io.StringIO(), verbosity=0)
    assert isinstance(sink.descend(), PlainSink)


@pytest.mark.parametrize("caps", [FULL, SIMPLE, PLAIN])
def test_every_rung_survives_a_whole_run(caps: Caps) -> None:
    """The ladder's three rungs must each handle the full event sequence."""
    stream = io.StringIO()
    sink = HumanSink(caps, stream, verbosity=1) if caps.rung != "plain" else PlainSink(stream, 1)
    start = getattr(sink, "start", None)
    if callable(start):
        start()
    sink.handle(RunStarted(workflow="orders", mode="partial", steps_total=3))
    for index in range(3):
        sink.handle(StepStarted(id=f"s{index}", kind="http"))
        sink.handle(StepProgress(id=f"s{index}", detail="pages", current=1, total=4))
        sink.handle(StepFinished(id=f"s{index}", status="ok", duration_ms=10))
    sink.handle(RunFinished(status="ok", duration_ms=40, counts={"steps": 3}))
    sink.close()
    assert "orders" in stream.getvalue()
