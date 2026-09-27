"""The governor's CPU and loop-lag signals (ADR 0016).

The samplers are injected: what is under test is the decision -- one step fewer, half,
back up one -- and burning a real core to get there would make the suite slow and the
result depend on whatever else the machine is doing. The one exception is the blocked
loop, where a synchronous sleep is the thing being detected and is cheap to cause.
"""

from __future__ import annotations

import asyncio
import io
import sys
import time
from collections.abc import Callable

import pytest
from pydantic import ValidationError

from sclpl.render.events import Event, LogRecord, ResourceWarning
from sclpl.render.plain import PlainSink
from sclpl.render.reporter import Reporter
from sclpl.run.plan import Node, StepSpec, build
from sclpl.run.schedule import Limits, Scheduler
from sclpl.run.sclpll import emit, parse
from sclpl.values import governor as gov
from sclpl.values.store import ValueStore

MB = 1024 * 1024


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class Recorder:
    """A sink that keeps every event, so a test can read what the run said."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def handle(self, event: Event) -> None:
        self.events.append(event)

    def close(self) -> None:
        pass

    def logs(self) -> list[str]:
        return [event.message for event in self.events if isinstance(event, LogRecord)]

    def warnings(self) -> list[ResourceWarning]:
        return [event for event in self.events if isinstance(event, ResourceWarning)]


def governor(
    cpu: Callable[[], float | None],
    cpu_soft: float | None = None,
    cpu_hard: float | None = None,
) -> gov.Governor:
    load = gov.Load(cpu_soft=cpu_soft, cpu_hard=cpu_hard, cpu_probe=cpu, window=0.0)
    return gov.Governor(budget=0, load=load)


# -- parsing -----------------------------------------------------------------------


@pytest.mark.parametrize(("text", "expected"), [("70%", 70.0), (70, 70.0), ("12.5%", 12.5)])
def test_a_cpu_threshold_is_a_percentage(text: str | float, expected: float) -> None:
    assert gov.parse_percent(text) == expected


@pytest.mark.parametrize("text", ["0%", "101%", "lots"])
def test_a_cpu_threshold_outside_the_machine_is_refused(text: str) -> None:
    with pytest.raises(ValueError):
        gov.parse_percent(text)


@pytest.mark.parametrize(("text", "expected"), [("250ms", 0.25), ("0.5s", 0.5), ("1S", 1.0)])
def test_a_lag_threshold_is_read_with_its_unit(text: str, expected: float) -> None:
    assert gov.parse_lag(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", ["250", "0ms", "fast"])
def test_a_lag_threshold_without_a_unit_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match="unit"):
        gov.parse_lag(text)


def test_nothing_set_is_no_load_at_all() -> None:
    assert gov.parse_load() is None
    load = gov.parse_load(cpu_hard="90%", loop_lag_hard="250ms")
    assert load is not None
    assert (load.cpu_soft, load.cpu_hard, load.lag_soft, load.lag_hard) == (None, 90.0, None, 0.25)


def test_limits_accept_the_thresholds_and_round_trip() -> None:
    source = "@workflow w\n\n@limits cpu_soft=70% cpu_hard=90% loop_lag_hard=250ms\n"
    doc = parse(source)
    assert doc.limits.cpu_soft == "70%"
    assert doc.limits.loop_lag_hard == "250ms"
    assert emit(parse(emit(doc))) == emit(doc)


def test_a_bad_threshold_is_a_validation_error_not_a_failed_run() -> None:
    with pytest.raises(ValidationError, match="needs a unit"):
        parse("@workflow w\n\n@limits loop_lag_hard=250\n")


# -- the policy --------------------------------------------------------------------


def test_no_thresholds_changes_nothing() -> None:
    calls: list[int] = []

    def probe() -> float:
        calls.append(1)
        return 100.0

    plain = gov.Governor(budget=100 * MB)
    assert plain.pace(16) == []
    assert plain.admits(16) == 16
    idle = gov.Governor(budget=100 * MB, load=gov.Load(cpu_probe=probe))
    assert idle.pace(16) == []
    assert calls == []


def test_soft_takes_one_step_and_hard_halves_never_below_one() -> None:
    reading = [75.0]
    g = governor(lambda: reading[0], cpu_soft=70.0, cpu_hard=90.0)
    (soft,) = g.pace(16)
    assert (soft.level, soft.before, soft.after) == ("soft", 16, 15)
    assert g.admits(16) == 15
    reading[0] = 95.0
    assert [d.after for d in g.pace(16)] == [7]
    assert [d.after for d in (g.pace(16) + g.pace(16) + g.pace(16))] == [3, 1]
    assert g.pace(16) == []  # already at the floor: nothing to decide
    assert g.admits(16) == 1


def test_recovery_climbs_one_step_at_a_time_back_to_the_ceiling() -> None:
    reading = [95.0]
    g = governor(lambda: reading[0], cpu_hard=90.0)
    g.pace(4)
    assert g.admits(4) == 2
    reading[0] = 10.0
    (up,) = g.pace(4)
    assert (up.level, up.before, up.after, up.severity) == ("ok", 2, 3, "info")
    assert "below 90%" in up.describe()
    g.pace(4)
    assert g.cap is None
    assert g.pace(4) == []


def test_the_worst_signal_decides_once() -> None:
    load = gov.Load(
        cpu_soft=70.0, lag_hard=0.1, cpu_probe=lambda: 80.0, lag_probe=lambda: 0.3, window=0.0
    )
    (decision,) = gov.Governor(budget=0, load=load).pace(16)
    assert (decision.signal, decision.level, decision.after) == ("loop_lag", "hard", 8)
    assert decision.describe() == "loop lag at 300ms (hard 100ms); concurrency 16 -> 8"


def test_the_window_keeps_a_blip_from_re_pacing() -> None:
    clock = Clock()
    load = gov.Load(cpu_hard=90.0, cpu_probe=lambda: 95.0, clock=clock, window=0.5)
    g = gov.Governor(budget=0, load=load)
    assert [d.after for d in g.pace(16)] == [8]
    clock.now = 0.2
    assert g.pace(16) == []
    clock.now = 0.6
    assert [d.after for d in g.pace(16)] == [4]


def test_memory_can_lower_the_ceiling_below_the_load_cap() -> None:
    g = governor(lambda: 95.0, cpu_hard=90.0)
    g.pace(16)
    assert g.admits(16) == 8
    assert g.admits(4) == 4


def test_without_psutil_cpu_is_unwatched_and_says_so_once() -> None:
    g = governor(lambda: None, cpu_hard=90.0)
    (note,) = g.pace(16)
    assert note.level == "unavailable"
    assert note.severity == "warning"
    assert "sclpl[monitor]" in note.describe()
    assert g.pace(16) == []
    assert g.admits(16) == 16


def test_the_default_cpu_probe_is_none_without_psutil(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "psutil", None)
    assert gov.cpu_percent() is None


# -- in a run ----------------------------------------------------------------------


async def test_cpu_pressure_lowers_admissions_and_logs_why() -> None:
    """Process-lane steps saturating the machine, as the sampler would report it."""
    plan = build(
        [StepSpec(id=f"s{index}", reads=frozenset(), lane="process") for index in range(12)]
    )
    active = 0
    seen: dict[str, int] = {}

    async def runner(node: Node) -> str:
        nonlocal active
        active += 1
        seen[node.id] = active
        await asyncio.sleep(0.01)
        active -= 1
        return node.id

    load = gov.Load(cpu_soft=70.0, cpu_hard=90.0, cpu_probe=lambda: 95.0, window=0.0)
    recorder = Recorder()
    async with Reporter([recorder]) as rep:
        outcome = await Scheduler(plan, ValueStore(), rep, Limits(concurrency=8, load=load)).run(
            runner
        )

    assert outcome.ok
    assert "cpu at 95% (hard 90%); concurrency 8 -> 4" in recorder.logs()
    assert "cpu at 95% (hard 90%); concurrency 2 -> 1" in recorder.logs()
    assert recorder.warnings()[0] == ResourceWarning(kind="cpu", current=95, budget=90)
    # The first eight were admitted before any sample; the rest ran one at a time.
    assert [seen[f"s{index}"] for index in range(8, 12)] == [1, 1, 1, 1]


async def test_a_blocked_loop_trips_the_lag_signal() -> None:
    """A synchronous sleep inside an async step: the timer cannot fire, and says so."""
    plan = build([StepSpec(id=f"s{index}", reads=frozenset()) for index in range(3)])

    async def runner(node: Node) -> str:
        if node.id == "s0":
            time.sleep(0.3)  # the bug being detected, on purpose
        return node.id

    load = gov.Load(lag_hard=0.1)
    recorder = Recorder()
    async with Reporter([recorder]) as rep:
        outcome = await Scheduler(plan, ValueStore(), rep, Limits(concurrency=4, load=load)).run(
            runner
        )

    assert outcome.ok
    tripped = [line for line in recorder.logs() if line.startswith("loop lag at ")]
    assert tripped
    assert "(hard 100ms); concurrency 4 -> 2" in tripped[0]
    (warning,) = recorder.warnings()
    assert warning.kind == "loop_lag"
    assert warning.current >= 150
    assert warning.budget == 100


async def test_without_thresholds_a_run_says_nothing_new() -> None:
    plan = build([StepSpec(id=f"s{index}", reads=frozenset()) for index in range(6)])

    async def runner(node: Node) -> str:
        await asyncio.sleep(0)
        return node.id

    recorder = Recorder()
    async with Reporter([recorder, PlainSink(io.StringIO())]) as rep:
        outcome = await Scheduler(
            plan, ValueStore(), rep, Limits(concurrency=4, memory_budget=1024**4)
        ).run(runner)

    assert outcome.ok
    assert recorder.logs() == []
    assert recorder.warnings() == []
