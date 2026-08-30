"""The run: preflight, plan, schedule, report.

One function that everything else in the CLI calls. Keeping the assembly in one place
is what lets `run`, the launcher, and `runs replay` behave identically -- they differ
in how they gather the arguments, not in what happens afterwards.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from sclpl.render.events import RunFinished, RunStarted
from sclpl.render.reporter import Reporter
from sclpl.run.compile_plan import hosts
from sclpl.run.errors import SclplError
from sclpl.run.execute import SKIPPED, Runtime, collect, run_injected, run_step
from sclpl.run.ir import WorkflowDoc
from sclpl.run.plan import Node
from sclpl.run.ports import STDIO
from sclpl.run.preflight import Report, preflight
from sclpl.run.schedule import JOIN_SUFFIX, Limits, Outcome, Scheduler
from sclpl.run.transport import Pool, TransportLimits
from sclpl.values.store import ValueStore


@dataclass(slots=True)
class Options:
    """Everything a run can be told, gathered from flags and config."""

    mode: str | None = None
    named_in: dict[str, str] = field(default_factory=dict)
    named_out: dict[str, str] = field(default_factory=dict)
    positional: list[str] = field(default_factory=list)
    overrides: dict[str, Any] = field(default_factory=dict)
    concurrency: int | None = None
    host_concurrency: int | None = None
    timeout: float | None = None
    retries: int | None = None
    keep_going: bool = False
    validate: bool = True
    dry_run: bool = False
    keep_all: bool = False


@dataclass(slots=True)
class Result:
    """What a finished run produced."""

    outcome: Outcome | None = None
    report: Report | None = None
    store: ValueStore | None = None
    exit_code: int = 0

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


async def run_workflow(doc: WorkflowDoc, options: Options, reporter: Reporter) -> Result:
    """Validate, plan, and execute a workflow."""
    started = time.perf_counter()

    report = preflight(
        doc,
        mode=options.mode,
        named_in=options.named_in,
        named_out=options.named_out,
        positional=options.positional,
        check_files=options.validate,
    )
    for note in report.notes:
        reporter.log("info", note)

    if not report.ok:
        problem = report.problems[0]
        reporter.log("error", str(problem))
        reporter.emit(
            RunFinished(
                status="failed",
                duration_ms=_ms(started),
                counts={},
                exit_code=problem.exit_code,
            )
        )
        return Result(report=report, exit_code=problem.exit_code)

    assert report.plan is not None and report.resolved is not None

    reporter.emit(
        RunStarted(
            workflow=doc.name,
            version=doc.version,
            mode=report.resolved.name,
            steps_total=len(report.plan),
            steps_pruned=len(report.resolved.pruned),
            hosts=hosts(doc),
        )
    )

    if options.dry_run:
        reporter.log("info", "dry run: nothing was executed")
        reporter.emit(
            RunFinished(status="ok", duration_ms=_ms(started), counts={"planned": len(report.plan)})
        )
        return Result(report=report, exit_code=0)

    limits = _limits(doc, options)
    store = ValueStore(keep_all=options.keep_all)
    variables = {**doc.vars, **report.resolved.vars, **options.overrides}

    transport = TransportLimits(
        timeout=options.timeout or doc.limits.timeout,
        max_connections=limits.concurrency * 2,
    )

    async with Pool(transport) as pool:
        runtime = Runtime(
            doc=doc,
            store=store,
            reporter=reporter,
            pool=pool,
            vars=variables,
            stubs=dict(report.resolved.stubs),
            outputs=_output_paths(report),
        )
        for name, value in report.resolved.stubs.items():
            # A stub stands in for a producer the mode pruned. It is pinned, because
            # nothing produced it and its refcount would otherwise free it early.
            store.put(name, value, readers=report.plan.readers_of(name), pinned=True)

        async def runner(node: Node) -> Any:
            # Three kinds of node reach here. Most are steps someone wrote. The rest the
            # run grew for itself: a copy of a loop body, and the barrier that gathers
            # one. Only the first kind is in the document.
            if node.id.endswith(JOIN_SUFFIX):
                return collect(node.id[: -len(JOIN_SUFFIX)], runtime)
            if node.id in runtime.injected:
                value = await run_injected(node.id, runtime)
                return None if value is SKIPPED else value

            step = doc.step(node.id)
            if step is None:  # pragma: no cover - the plan is built from these steps
                raise SclplError(f"no such step {node.id!r}")
            value = await run_step(step, node, runtime)
            return None if value is SKIPPED else value

        scheduler = Scheduler(report.plan, store, reporter, limits)
        runtime.expand = scheduler.expand
        outcome = await scheduler.run(runner)

    exit_code = _exit_code(outcome)
    reporter.emit(
        RunFinished(
            status=outcome.status,  # type: ignore[arg-type]
            duration_ms=outcome.duration_ms,
            counts=outcome.counts(),
            exit_code=exit_code,
        )
    )
    return Result(outcome=outcome, report=report, store=store, exit_code=exit_code)


def _output_paths(report: Report) -> dict[str, str]:
    """Where each bound output port points, for the steps that declare `-> port`.

    `-` is a destination like any other here; `tables/io.py` is the one place that knows
    it means stdout.
    """
    if report.bindings is None:
        return {}
    paths: dict[str, str] = {}
    for name, binding in report.bindings.outputs.items():
        if binding.is_stdio:
            paths[name] = STDIO
        elif binding.path is not None:
            paths[name] = str(binding.path)
    return paths


def _limits(doc: WorkflowDoc, options: Options) -> Limits:
    """Flags beat the mode's limits, which beat the workflow's (SPEC section 15)."""
    return Limits(
        concurrency=options.concurrency or doc.limits.concurrency,
        host_concurrency=options.host_concurrency or doc.limits.host_concurrency,
        tags=dict(doc.limits.tags),
        keep_going=options.keep_going,
    )


def _exit_code(outcome: Outcome) -> int:
    """The first failure's own exit code, so an assertion is distinguishable from a 500."""
    if outcome.status == "cancelled":
        from sclpl.cli.options import EXIT_INTERRUPTED

        return EXIT_INTERRUPTED
    if not outcome.failed:
        return 0
    for error in outcome.failed.values():
        if isinstance(error, SclplError):
            return error.exit_code
    from sclpl.cli.options import EXIT_STEP_FAILED

    return EXIT_STEP_FAILED


def _ms(since: float) -> int:
    return int((time.perf_counter() - since) * 1000)
