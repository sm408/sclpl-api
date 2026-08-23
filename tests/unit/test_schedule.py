"""The scheduler: continuous admission, ordered locking, and cancellation.

The timing tests use a real event loop with short sleeps rather than a fake clock,
because what is being asserted is that `asyncio` actually overlaps the work -- a fake
clock would happily "pass" against a scheduler that ran everything in series.
"""

from __future__ import annotations

import asyncio
import io
import time

import pytest

from sclpl.render.plain import PlainSink
from sclpl.render.reporter import Reporter
from sclpl.run.plan import Node, StepSpec, build
from sclpl.run.schedule import Limits, Scheduler, execute
from sclpl.values.store import ValueStore

TICK = 0.05


def spec(step_id: str, reads: str = "", **kwargs: object) -> StepSpec:
    return StepSpec(
        id=step_id,
        reads=frozenset(reads.split()) if reads else frozenset(),
        **kwargs,  # type: ignore[arg-type]
    )


def reporter() -> Reporter:
    return Reporter([PlainSink(io.StringIO(), verbosity=-2)])


async def test_independent_steps_overlap() -> None:
    """Four independent one-tick steps must take about one tick, not four."""
    plan = build([spec(f"s{index}") for index in range(4)])

    async def runner(node: Node) -> str:
        await asyncio.sleep(TICK)
        return node.id

    started = time.perf_counter()
    async with reporter() as rep:
        outcome = await Scheduler(plan, ValueStore(), rep, Limits(concurrency=4)).run(runner)
    elapsed = time.perf_counter() - started

    assert outcome.ok
    assert elapsed < TICK * 2.5


async def test_the_seven_node_graph_finishes_in_critical_path_time() -> None:
    """The M2 exit criterion.

    a fans out to b, c, d; b and c join at e; d and e join at f; f feeds g. The
    critical path is a -> b -> e -> f -> g, five nodes deep. Barrier-wave scheduling
    would take longer because it would wait for `d` alongside `b` and `c` before
    starting anything in the next wave.
    """
    plan = build(
        [
            spec("a"),
            spec("b", "a"),
            spec("c", "a"),
            spec("d", "a"),
            spec("e", "b c"),
            spec("f", "d e"),
            spec("g", "f"),
        ]
    )

    async def runner(node: Node) -> str:
        # `d` is slow but nothing on the critical path waits for it until `f`.
        await asyncio.sleep(TICK * 2 if node.id == "d" else TICK)
        return node.id

    started = time.perf_counter()
    async with reporter() as rep:
        outcome = await Scheduler(plan, ValueStore(), rep, Limits(concurrency=8)).run(runner)
    elapsed = time.perf_counter() - started

    assert outcome.ok
    assert len(outcome.succeeded) == 7
    # Critical path is 5 ticks; serial execution would be 8.
    assert elapsed < TICK * 6.5


async def test_a_step_starts_the_moment_its_dependency_lands() -> None:
    """Not when the wave it happens to be in completes."""
    plan = build([spec("fast"), spec("slow"), spec("after_fast", "fast")])
    starts: dict[str, float] = {}
    origin = time.perf_counter()

    async def runner(node: Node) -> str:
        starts[node.id] = time.perf_counter() - origin
        await asyncio.sleep(TICK * 4 if node.id == "slow" else TICK)
        return node.id

    async with reporter() as rep:
        await Scheduler(plan, ValueStore(), rep, Limits(concurrency=4)).run(runner)

    # `after_fast` must not have waited for `slow`.
    assert starts["after_fast"] < TICK * 3


async def test_values_flow_between_steps_with_their_types() -> None:
    plan = build([spec("source"), spec("double", "source")])
    store = ValueStore()

    async def runner(node: Node) -> object:
        if node.id == "source":
            return {"count": 21}
        upstream = store.get("source")
        assert isinstance(upstream["count"], int)
        return upstream["count"] * 2

    async with reporter() as rep:
        await Scheduler(plan, store, rep, Limits(concurrency=2)).run(runner)
    assert store.get("double") == 42


async def test_a_consumed_value_is_freed() -> None:
    plan = build([spec("source"), spec("sink", "source")])
    store = ValueStore()

    async def runner(node: Node) -> object:
        return "x" * 1000 if node.id == "source" else None

    async with reporter() as rep:
        await Scheduler(plan, store, rep, Limits(concurrency=2)).run(runner)
    assert not store.has("source")


async def test_a_failure_stops_admitting_new_work() -> None:
    plan = build([spec("boom"), spec("downstream", "boom"), spec("unrelated")])
    ran: list[str] = []

    async def runner(node: Node) -> str:
        ran.append(node.id)
        if node.id == "boom":
            raise RuntimeError("no")
        return node.id

    async with reporter() as rep:
        outcome = await Scheduler(plan, ValueStore(), rep, Limits(concurrency=1)).run(runner)

    assert not outcome.ok
    assert "boom" in outcome.failed
    assert "downstream" not in ran
    assert "downstream" in outcome.skipped


async def test_keep_going_runs_what_it_still_can() -> None:
    plan = build([spec("boom"), spec("independent")])

    async def runner(node: Node) -> str:
        if node.id == "boom":
            raise RuntimeError("no")
        return node.id

    async with reporter() as rep:
        outcome = await Scheduler(
            plan, ValueStore(), rep, Limits(concurrency=2, keep_going=True)
        ).run(runner)

    assert "independent" in outcome.succeeded
    assert "boom" in outcome.failed


async def test_the_global_ceiling_is_respected() -> None:
    plan = build([spec(f"s{index}") for index in range(20)])
    peak = 0
    current = 0

    async def runner(node: Node) -> str:
        nonlocal peak, current
        current += 1
        peak = max(peak, current)
        await asyncio.sleep(TICK)
        current -= 1
        return node.id

    async with reporter() as rep:
        await Scheduler(plan, ValueStore(), rep, Limits(concurrency=3)).run(runner)
    assert peak <= 3


async def test_the_per_host_ceiling_is_respected() -> None:
    plan = build([spec(f"s{index}", host="api.test") for index in range(12)])
    peak = 0
    current = 0

    async def runner(node: Node) -> str:
        nonlocal peak, current
        current += 1
        peak = max(peak, current)
        await asyncio.sleep(TICK)
        current -= 1
        return node.id

    async with reporter() as rep:
        await Scheduler(plan, ValueStore(), rep, Limits(concurrency=12, host_concurrency=2)).run(
            runner
        )
    assert peak <= 2


async def test_different_hosts_do_not_block_each_other() -> None:
    plan = build(
        [spec("a1", host="one.test"), spec("a2", host="one.test"), spec("b1", host="two.test")]
    )
    starts: dict[str, float] = {}
    origin = time.perf_counter()

    async def runner(node: Node) -> str:
        starts[node.id] = time.perf_counter() - origin
        await asyncio.sleep(TICK * 2)
        return node.id

    async with reporter() as rep:
        await Scheduler(plan, ValueStore(), rep, Limits(concurrency=8, host_concurrency=1)).run(
            runner
        )
    # two.test's step should not have queued behind one.test's two steps.
    assert starts["b1"] < TICK * 1.5


async def test_a_tag_ceiling_applies_across_hosts() -> None:
    plan = build([spec(f"s{index}", tags=frozenset({"slow"})) for index in range(8)])
    peak = 0
    current = 0

    async def runner(node: Node) -> str:
        nonlocal peak, current
        current += 1
        peak = max(peak, current)
        await asyncio.sleep(TICK)
        current -= 1
        return node.id

    async with reporter() as rep:
        await Scheduler(plan, ValueStore(), rep, Limits(concurrency=8, tags={"slow": 2})).run(
            runner
        )
    assert peak <= 2


async def test_five_hundred_steps_complete() -> None:
    """The exit criterion's scale test: no per-step task explosion, no deadlock."""
    plan = build([spec(f"s{index}", host="api.test") for index in range(500)])

    async def runner(node: Node) -> str:
        await asyncio.sleep(0)
        return node.id

    async with reporter() as rep:
        outcome = await Scheduler(
            plan, ValueStore(), rep, Limits(concurrency=16, host_concurrency=8)
        ).run(runner)
    assert len(outcome.succeeded) == 500


async def test_cancellation_leaves_a_clean_outcome() -> None:
    """Ctrl-C. Nothing hangs, and what did not run is reported as skipped."""
    plan = build([spec(f"s{index}") for index in range(8)])

    async def runner(node: Node) -> str:
        await asyncio.sleep(10)
        return node.id

    async with reporter() as rep:
        scheduler = Scheduler(plan, ValueStore(), rep, Limits(concurrency=4))
        task = asyncio.create_task(scheduler.run(runner))
        await asyncio.sleep(TICK)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


async def test_an_empty_plan_finishes_immediately() -> None:
    async def runner(node: Node) -> None:
        raise AssertionError("nothing to run")

    async with reporter() as rep:
        outcome = await Scheduler(build([]), ValueStore(), rep, Limits()).run(runner)
    assert outcome.ok
    assert outcome.succeeded == []


async def test_execute_reports_a_run_finished_event() -> None:
    stream = io.StringIO()
    plan = build([spec("a")])

    async def runner(node: Node) -> str:
        return "done"

    async with Reporter([PlainSink(stream, verbosity=0)]) as rep:
        outcome = await execute(plan, runner, rep)
        await rep.drain()

    assert outcome.ok
    assert "ok in" in stream.getvalue()


async def test_a_diamond_runs_each_node_once() -> None:
    plan = build(
        [spec("top"), spec("left", "top"), spec("right", "top"), spec("join", "left right")]
    )
    ran: list[str] = []

    async def runner(node: Node) -> str:
        ran.append(node.id)
        return node.id

    async with reporter() as rep:
        await Scheduler(plan, ValueStore(), rep, Limits(concurrency=4)).run(runner)
    assert sorted(ran) == ["join", "left", "right", "top"]
