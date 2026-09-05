"""The run: preflight, plan, schedule, report.

One function that everything else in the CLI calls. Keeping the assembly in one place
is what lets `run`, the launcher, and `runs replay` behave identically -- they differ
in how they gather the arguments, not in what happens afterwards.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Any

from sclpl.errors import EXIT_INTERRUPTED, EXIT_STEP_FAILED, SclplError
from sclpl.render.events import RunFinished, RunStarted
from sclpl.render.reporter import Reporter
from sclpl.run import lanes
from sclpl.run.compile_plan import hosts
from sclpl.run.execute import SKIPPED, Runtime, collect, run_injected, run_step
from sclpl.run.ir import WorkflowDoc
from sclpl.run.plan import Node
from sclpl.run.preflight import Report, preflight
from sclpl.run.schedule import JOIN_SUFFIX, ExpandSpec, Limits, Outcome, Scheduler
from sclpl.run.transport import Pool, TransportLimits
from sclpl.state import db, safe_args
from sclpl.tables.io import STDIO
from sclpl.values import cache, governor
from sclpl.values.governor import parse_budget
from sclpl.values.ref import Scratch
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
    memory_budget: str | None = None
    #: What to call this run in the history. Defaults to `workflow-mode-MMDD-HHMM`.
    name: str | None = None
    tags: list[str] = field(default_factory=list)
    env: str | None = None
    #: History is written unless this is off, which is for tests and one-off `call`s.
    record: bool = True
    keep: int = db.KEEP_DEFAULT
    #: Decided before the run so the event log can be written *during* it. A log
    #: assembled afterwards from memory is a log that is missing whatever crashed.
    run_id: str = ""
    no_cache: bool = False
    refresh: bool = False
    offline: bool = False
    http_cache: bool = False
    #: Persisted before scheduling so a killed run remains identifiable.
    started_at: str = ""


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
    if options.record:
        _remember_start(doc, options, report, started)

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
    store = ValueStore(keep_all=options.keep_all, scratch=Scratch())
    variables = {**doc.vars, **report.resolved.vars, **options.overrides}

    transport = TransportLimits(
        timeout=options.timeout or doc.limits.timeout,
        max_connections=limits.concurrency * 2,
    )

    pools = lanes.Pools(max_processes=min(4, limits.concurrency))
    policy = cache.Policy.from_flags(
        no_cache=options.no_cache,
        refresh=options.refresh,
        offline=options.offline,
        http_cache=options.http_cache,
    )
    store_cache = cache.Cache(cache.default_root(), policy=policy) if policy.enabled else None
    async with Pool(transport) as pool:
        runtime = Runtime(
            doc=doc,
            store=store,
            reporter=reporter,
            pool=pool,
            vars=variables,
            stubs=dict(report.resolved.stubs),
            outputs=_output_paths(report),
            pools=pools,
            cache=store_cache,
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

        def expand(parent: str, specs: list[ExpandSpec], tag_limit: tuple[str, int] | None) -> None:
            scheduler.expand(parent, specs, tag_limit=tag_limit)

        runtime.expand = expand
        try:
            outcome = await scheduler.run(runner)
        finally:
            # Pools outlive the event loop unless closed, and a lingering process pool
            # keeps the interpreter alive after the CLI has printed its summary.
            pools.close()
            if store_cache is not None:
                if store_cache.stats.hits or store_cache.stats.writes:
                    reporter.log("info", store_cache.stats.summary())
                store_cache.prune()
                store_cache.close()

    exit_code = _exit_code(outcome)
    reporter.emit(
        RunFinished(
            status=outcome.status,  # type: ignore[arg-type]
            duration_ms=outcome.duration_ms,
            counts=outcome.counts(),
            exit_code=exit_code,
        )
    )
    if options.record:
        _remember(doc, options, report, outcome, exit_code, started, store_cache)
    return Result(outcome=outcome, report=report, store=store, exit_code=exit_code)


def _remember(
    doc: WorkflowDoc,
    options: Options,
    report: Report,
    outcome: Outcome,
    exit_code: int,
    started: float,
    store_cache: cache.Cache | None,
) -> None:
    """Write the run to history, and prune.

    Wrapped, because history is a convenience and a run that produced its files has
    succeeded whether or not it could also write a row about itself. A read-only home
    directory should not turn a good run into a failed one.
    """
    try:
        identifier = options.run_id or db.run_id(doc.name, started)
        record = db.RunRecord(
            id=identifier,
            name=options.name or db.default_name(doc.name, options.mode),
            workflow=doc.name,
            workflow_version=doc.version,
            mode=report.resolved.name if report.resolved else options.mode,
            started_at=options.started_at or db.now(),
            finished_at=db.now(),
            duration_ms=outcome.duration_ms,
            status=outcome.status,
            exit_code=exit_code,
            steps_run=len(outcome.succeeded),
            steps_skipped=len(outcome.skipped),
            steps_failed=len(outcome.failed),
            cache_hits=store_cache.stats.hits if store_cache else 0,
            cache_misses=store_cache.stats.misses if store_cache else 0,
            peak_rss_bytes=governor.rss(),
            env=options.env,
            tags=list(options.tags),
            argv=safe_args.render(sys.argv[1:]),
            steps=[db.StepRecord(step_id=name, status="ok") for name in outcome.succeeded]
            + [
                db.StepRecord(step_id=name, status="failed", error=str(error))
                for name, error in outcome.failed.items()
            ]
            + [db.StepRecord(step_id=name, status="skipped") for name in outcome.skipped],
            ports=[
                (binding.direction, binding.name, binding.describe(), "")
                for binding in (report.bindings.all() if report.bindings else [])
            ],
        )
        with db.History() as history:
            log = history.log_path(identifier)
            record.log_path = str(log) if log.exists() else None
            history.record(record)
            history.prune(options.keep)
    except Exception:  # noqa: BLE001 - history is a convenience, never the run's verdict
        return


def _remember_start(doc: WorkflowDoc, options: Options, report: Report, started: float) -> None:
    """Persist safe run provenance before any scheduled side effects begin."""
    try:
        identifier = options.run_id or db.run_id(doc.name, started)
        options.run_id = identifier
        options.started_at = db.now()
        with db.History() as history:
            history.record(
                db.RunRecord(
                    id=identifier,
                    name=options.name or db.default_name(doc.name, options.mode),
                    workflow=doc.name,
                    workflow_version=doc.version,
                    mode=report.resolved.name if report.resolved else options.mode,
                    started_at=options.started_at,
                    status="running",
                    env=options.env,
                    argv=safe_args.render(sys.argv[1:]),
                    tags=list(options.tags),
                )
            )
    except Exception:  # noqa: BLE001 - ordinary history remains best effort
        return


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
    # There is always a budget. SPEC section 12 makes it a share of system memory when
    # nobody says otherwise, and a governor that only exists when asked for is a
    # governor that is missing exactly when a run turns out to be bigger than expected.
    budget = options.memory_budget or doc.limits.memory_budget
    return Limits(
        concurrency=options.concurrency or doc.limits.concurrency,
        host_concurrency=options.host_concurrency or doc.limits.host_concurrency,
        tags=dict(doc.limits.tags),
        keep_going=options.keep_going,
        memory_budget=parse_budget(budget),
    )


def _exit_code(outcome: Outcome) -> int:
    """The first failure's own exit code, so an assertion is distinguishable from a 500."""
    if outcome.status == "cancelled":
        return EXIT_INTERRUPTED
    if not outcome.failed:
        return 0
    for error in outcome.failed.values():
        if isinstance(error, SclplError):
            return error.exit_code

    return EXIT_STEP_FAILED


def _ms(since: float) -> int:
    return int((time.perf_counter() - since) * 1000)
