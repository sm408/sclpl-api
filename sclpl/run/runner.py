"""The run: preflight, plan, schedule, report.

One function that everything else in the CLI calls. Keeping the assembly in one place
is what lets `run`, the launcher, and `runs replay` behave identically -- they differ
in how they gather the arguments, not in what happens afterwards.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sclpl.errors import (
    EXIT_INCOMPLETE,
    EXIT_INTERRUPTED,
    EXIT_STEP_FAILED,
    PolicyDenied,
    SclplError,
    ValidationError,
)
from sclpl.project import auth as auth_mod
from sclpl.project import context as project_context
from sclpl.project import outputs as outputs_mod
from sclpl.project import policy as policy_mod
from sclpl.render.events import RunFinished, RunStarted
from sclpl.render.reporter import Reporter
from sclpl.run import checkpoints as checkpoints_mod
from sclpl.run import lanes
from sclpl.run import resources as resources_mod
from sclpl.run import resume as resume_mod
from sclpl.run.compile_plan import hosts
from sclpl.run.execute import SKIPPED, Runtime, collect, run_injected, run_step
from sclpl.run.fixtures import Store as FixtureStore
from sclpl.run.ir import HttpConfig, WorkflowDoc
from sclpl.run.plan import Node, Plan
from sclpl.run.preflight import Report, preflight
from sclpl.run.publication import Ledger, discard, publish
from sclpl.run.schedule import JOIN_SUFFIX, ExpandSpec, Limits, Outcome, Scheduler
from sclpl.run.transport import Pool, TransportLimits
from sclpl.state import db, locking, safe_args
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
    #: Audited/resumable runs cannot begin unless their provenance row is durable.
    require_provenance: bool = False
    keep: int = db.KEEP_DEFAULT
    #: Decided before the run so the event log can be written *during* it. A log
    #: assembled afterwards from memory is a log that is missing whatever crashed.
    run_id: str = ""
    no_cache: bool = False
    refresh: bool = False
    offline: bool = False
    http_cache: bool = False
    #: F5: a run that otherwise succeeds but whose data completeness is
    #: `"partial"`/`"unknown"` fails with `EXIT_INCOMPLETE` instead of exit 0.
    require_complete: bool = False
    #: Persisted before scheduling so a killed run remains identifiable.
    started_at: str = ""
    fixture_root: Path | None = None
    record_fixture_root: Path | None = None
    strict_replay: bool = False
    #: Parent directory for temporary spill data; test execution supplies an isolated root.
    scratch_dir: Path | None = None
    #: How long to wait for exclusive ownership of a managed output another run holds.
    output_lock_timeout: float = 30.0
    #: Overrides a project policy's `overwrite = false` for this run only.
    overwrite: bool = False
    #: G3: resume from this run's checkpoints instead of starting fresh. The id of
    #: an existing history row, the same as `runs show`/`resume-plan` accept.
    resume_from: str | None = None
    #: G3: an explicit acknowledgment to rerun a step G2 would otherwise refuse --
    #: a non-idempotent write whose prior outcome was not confirmed successful.
    #: Rerunning it anyway is a deliberate operator decision; this only silences
    #: the refusal, it does not make the rerun itself any safer.
    force_resume: frozenset[str] = frozenset()
    #: Publish remote outputs beneath an immutable generation and advance latest.json last.
    remote_generation: bool = False
    #: Logical base URI of a remotely loaded workflow, if any.
    resource_base: str | None = None


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
    project_policy = _policy(options)

    report = preflight(
        doc,
        mode=options.mode,
        named_in=options.named_in,
        named_out=options.named_out,
        positional=options.positional,
        check_files=options.validate,
        policy=project_policy,
        resource_base=options.resource_base,
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

    if report.will_overwrite and not (options.overwrite or project_policy.overwrite):
        # Checked here rather than folded into `report.problems`: preflight itself
        # has no opinion on overwriting, since `validate`/`explain` call it without
        # ever intending to write anything. This is a `run`-specific decision, made
        # before the output lock, the pool, or a single step -- nothing has happened
        # yet that this denial needs to undo.
        existing = ", ".join(str(path) for path in report.will_overwrite)
        problem = PolicyDenied(
            f"refusing to overwrite existing output(s): {existing}",
            remedies=[
                "pass --overwrite to replace them",
                "or set [policy] overwrite = true in the project manifest",
            ],
        )
        reporter.log("error", str(problem))
        reporter.emit(
            RunFinished(
                status="failed", duration_ms=_ms(started), counts={}, exit_code=problem.exit_code
            )
        )
        return Result(report=report, exit_code=problem.exit_code)

    assert report.plan is not None and report.resolved is not None
    variables = {**doc.vars, **report.resolved.vars, **options.overrides}

    # G3: decided before anything else -- provenance, the scheduler, a single lock
    # or connection -- can begin, exactly like the overwrite check above. A refused
    # step is refused before any side effect, not partway through one.
    execution_plan = report.plan
    stubs = dict(report.resolved.stubs)
    resume_completeness: list[str] = []
    if options.resume_from:
        resumed = await _resume(doc, report, variables, options.resume_from, options.force_resume)
        if resumed.problem is not None:
            reporter.log("error", str(resumed.problem))
            reporter.emit(
                RunFinished(
                    status="failed",
                    duration_ms=_ms(started),
                    counts={},
                    exit_code=resumed.problem.exit_code,
                )
            )
            return Result(report=report, exit_code=resumed.problem.exit_code)
        execution_plan = resumed.plan
        stubs = resumed.stubs
        resume_completeness = resumed.completeness
        reporter.log(
            "info",
            f"resuming from {options.resume_from}: "
            f"{len(report.plan) - len(execution_plan)} reused, {len(execution_plan)} to run",
        )

    # A dry run has no scheduler or durable run outcome to resume, so retain the
    # established behavior of not creating a history row for it.
    if options.record and not options.dry_run:
        _remember_start(doc, options, report, started)

    reporter.emit(
        RunStarted(
            workflow=doc.name,
            version=doc.version,
            mode=report.resolved.name,
            steps_total=len(execution_plan),
            steps_pruned=len(report.resolved.pruned),
            hosts=hosts(doc),
        )
    )

    if options.dry_run:
        reporter.log("info", "dry run: nothing was executed")
        reporter.emit(
            RunFinished(
                status="ok", duration_ms=_ms(started), counts={"planned": len(execution_plan)}
            )
        )
        return Result(report=report, exit_code=0)

    assert report.bindings is not None
    resource_policy = cache.Policy.from_flags(
        no_cache=options.no_cache,
        refresh=options.refresh,
        offline=options.offline,
        http_cache=options.http_cache,
    )
    prepared_resources = None
    if any(binding.resources for binding in report.bindings.all()):
        try:
            prepared_resources = resources_mod.prepare(
                report.bindings,
                run_id=options.run_id or db.run_id(doc.name, started),
                root=options.scratch_dir,
                cache_read=resource_policy.read,
                cache_write=resource_policy.write,
                cache_require_hit=resource_policy.require_hit,
            )
        except SclplError as problem:
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

    limits = _limits(doc, options)
    store = ValueStore(keep_all=options.keep_all, scratch=Scratch(options.scratch_dir))

    transport = TransportLimits(
        timeout=options.timeout or doc.limits.timeout,
        max_connections=limits.concurrency * 2,
    )

    pools = lanes.Pools(max_processes=min(4, limits.concurrency))
    store_cache = None
    if resource_policy.enabled:
        store_cache = cache.Cache(cache.default_root(), policy=resource_policy)
    # G3: this run's own eligible step values, durably filed for a later resume.
    # Tied to `options.record`, not to `store_cache`/its policy -- a checkpoint
    # with no history row naming this run is never reachable by a future resume
    # regardless of whether *this* run's own HTTP response cache is enabled.
    checkpoint_store = checkpoints_mod.Store() if options.record else None
    fixtures = FixtureStore(options.fixture_root) if options.fixture_root else None
    outputs = _output_paths(report)
    output_settings = _output_settings(options)
    ledger = Ledger() if output_settings.publish == "validated" else None
    # C5: exclusive ownership of every managed destination for the run's whole
    # duration, acquired before any step -- including the first one -- can write.
    # Two runs targeting different files never wait on each other; two racing the
    # same one do, in a fixed order, so neither can deadlock the other.
    output_paths = [Path(path) for path in outputs.values() if path != STDIO]
    with locking.output_locks(output_paths, timeout=options.output_lock_timeout):
        async with Pool(
            transport,
            fixtures=fixtures,
            recorder=FixtureStore(options.record_fixture_root)
            if options.record_fixture_root
            else None,
            policy=project_policy if project_policy.restricts_hosts else None,
        ) as pool:
            runtime = Runtime(
                doc=doc,
                store=store,
                reporter=reporter,
                pool=pool,
                vars=variables,
                stubs=stubs,
                outputs=outputs,
                pools=pools,
                cache=store_cache,
                auth_profiles=_auth_profiles(doc, options),
                publication=ledger,
                checkpoint_store=checkpoint_store,
                run_id=options.run_id,
            )
            runtime.completeness.extend(resume_completeness)
            for name, value in stubs.items():
                # A stub stands in for a producer the mode pruned, or (G3) a step this
                # run reused from a checkpoint instead of redoing. Pinned either way,
                # because nothing in *this* run produced it and its refcount would
                # otherwise free it early.
                store.put(name, value, readers=report.plan.readers_of(name), pinned=True)

            async def runner(node: Node) -> Any:
                # Three kinds of node reach here. Most are steps someone wrote. The
                # rest the run grew for itself: a copy of a loop body, and the barrier
                # that gathers one. Only the first kind is in the document.
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

            scheduler = Scheduler(execution_plan, store, reporter, limits)

            def expand(
                parent: str, specs: list[ExpandSpec], tag_limit: tuple[str, int] | None
            ) -> None:
                scheduler.expand(parent, specs, tag_limit=tag_limit)

            runtime.expand = expand
            try:
                outcome = await scheduler.run(runner)
            finally:
                # Pools outlive the event loop unless closed, and a lingering process
                # pool keeps the interpreter alive after the CLI has printed its summary.
                pools.close()
            publication_state = "n/a"
            if ledger is not None:
                publication_state = _finish_publication(
                    ledger, doc, options, outcome, started, reporter
                )
            if (
                outcome.status == "ok"
                and prepared_resources is not None
                and prepared_resources.outputs
            ):
                if options.remote_generation:
                    resources_mod.publish_generation(prepared_resources, run_id=options.run_id)
                else:
                    resources_mod.publish(prepared_resources, overwrite=options.overwrite)
            if store_cache is not None:
                if store_cache.stats.hits or store_cache.stats.writes:
                    reporter.log("info", store_cache.stats.summary())
                store_cache.prune()
                store_cache.close()
            if checkpoint_store is not None:
                checkpoint_store.close()

    exit_code = _exit_code(outcome)
    # Only when nothing else already failed the run: EXIT_INCOMPLETE names a reason
    # of its own and must never paper over -- or be papered over by -- a real
    # failure that already has its own, more specific exit code.
    if (
        options.require_complete
        and exit_code == 0
        and _completeness_of(runtime, outcome) != "complete"
    ):
        exit_code = EXIT_INCOMPLETE
    if options.strict_replay and fixtures is not None and fixtures.unused():
        raise ValidationError("strict replay left unused fixtures")
    reporter.emit(
        RunFinished(
            status=outcome.status,  # type: ignore[arg-type]
            duration_ms=outcome.duration_ms,
            counts=outcome.counts(),
            exit_code=exit_code,
        )
    )
    if options.record:
        _remember(
            doc,
            options,
            report,
            outcome,
            exit_code,
            started,
            store_cache,
            reporter,
            runtime,
            publication_state,
        )
    return Result(outcome=outcome, report=report, store=store, exit_code=exit_code)


@dataclass(slots=True)
class _Resumed:
    """What `_resume` decided: either a refusal, or a plan to run instead of `report.plan`."""

    plan: Plan
    stubs: dict[str, Any]
    completeness: list[str]
    problem: SclplError | None = None


async def _resume(
    doc: WorkflowDoc,
    report: Report,
    variables: dict[str, Any],
    parent_run_id: str,
    force_resume: frozenset[str],
) -> _Resumed:
    """G3: turn G2's plan into what `run_workflow` needs to actually resume.

    Its own short-lived history/checkpoint/cache handles -- separate from the ones
    the real run opens afterward -- because nothing here is a side effect: a
    refusal at this point has touched nothing that needs undoing, and the plan
    itself does not outlive the decision of whether to proceed.
    """
    assert report.plan is not None and report.resolved is not None
    with (
        db.History() as history,
        checkpoints_mod.Store() as parent_store,
        cache.Cache(cache.default_root()) as planning_cache,
    ):
        plan = await resume_mod.plan_resume(
            doc,
            report,
            variables,
            parent_run_id,
            history=history,
            store=parent_store,
            cache=planning_cache,
        )
        refused = [
            entry
            for entry in plan.by_verdict(resume_mod.REFUSE)
            if entry.node_id not in force_resume
        ]
        if refused:
            detail = "; ".join(f"{entry.node_id} ({entry.reason})" for entry in refused)
            problem = PolicyDenied(
                f"resume refused for {len(refused)} step(s): {detail}",
                remedies=[
                    "pass --force-resume <step> for each one, to explicitly accept the risk "
                    "of repeating a side effect that may have already happened",
                ],
            )
            return _Resumed(plan=report.plan, stubs={}, completeness=[], problem=problem)

        reused = plan.by_verdict(resume_mod.REUSE)
        stubs = dict(report.resolved.stubs)
        for entry in reused:
            node = report.plan.nodes[entry.node_id]
            stubs[node.publishes] = parent_store.read(parent_run_id, entry.node_id)

        execution_plan = report.plan
        if reused:
            reused_ids = {entry.node_id for entry in reused}
            keep = {node_id for node_id in report.plan.nodes if node_id not in reused_ids}
            execution_plan = report.plan.subgraph(keep)

        completeness: list[str] = []
        if reused:
            # A reused value carries forward whatever the parent run itself knew
            # about its own completeness -- data this run never re-extracted
            # cannot become more complete just by being reused.
            parent_row = history.find(parent_run_id)
            if parent_row["completeness"] != "complete":
                completeness.append(parent_row["completeness"])

        return _Resumed(plan=execution_plan, stubs=stubs, completeness=completeness, problem=None)


def _remember(
    doc: WorkflowDoc,
    options: Options,
    report: Report,
    outcome: Outcome,
    exit_code: int,
    started: float,
    store_cache: cache.Cache | None,
    reporter: Reporter,
    runtime: Runtime,
    publication_state: str,
) -> None:
    """Write the run to history, and prune.

    Wrapped, because history is a convenience and a run that produced its files has
    succeeded whether or not it could also write a row about itself. A read-only home
    directory should not turn a good run into a failed one.
    """
    try:
        identifier = options.run_id or db.run_id(doc.name, started)
        bytes_in = sum(metric.bytes_in for metric in runtime.metrics.values())
        bytes_out = sum(metric.bytes_out for metric in runtime.metrics.values())
        retries = sum(max(0, metric.attempts - 1) for metric in runtime.metrics.values())
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
            retries=retries,
            cache_hits=store_cache.stats.hits if store_cache else 0,
            cache_misses=store_cache.stats.misses if store_cache else 0,
            peak_rss_bytes=governor.rss(),
            bytes_in=bytes_in,
            bytes_out=bytes_out,
            completeness=_completeness_of(runtime, outcome),
            publication=publication_state,
            parent_run_id=options.resume_from or "",
            env=options.env,
            tags=list(options.tags),
            argv=safe_args.render(sys.argv[1:]),
            steps=_step_records(outcome, runtime, reporter),
            ports=[
                (
                    binding.direction,
                    binding.name,
                    binding.describe(),
                    db.file_digest(binding.path) if binding.path else "",
                )
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


def _completeness_of(runtime: Runtime, outcome: Outcome) -> str:
    """F5: the run's overall data completeness, distinct from `status`/`exit_code`.

    `"unknown"` beats `"partial"` beats `"complete"`: any step whose own extraction
    could not tell what it left out makes the whole run's data completeness
    unknowable too, and a run cancelled mid-extraction is the same kind of unknown
    even with no paginated step involved at all. A run with no paginated steps, or
    where every one of them reached a bound something actually declared, is
    `"complete"` -- not a claim that a remote source has no more data, only that
    this run's own declared scope was fully covered.
    """
    if outcome.status == "cancelled":
        return "unknown"
    if "unknown" in runtime.completeness:
        return "unknown"
    if "partial" in runtime.completeness:
        return "partial"
    return "complete"


def _step_records(outcome: Outcome, runtime: Runtime, reporter: Reporter) -> list[db.StepRecord]:
    """F1: one persisted row per step, with the actual cost the live run measured."""

    def record(name: str, status: str, error: str = "") -> db.StepRecord:
        metric = runtime.metrics.get(name)
        return db.StepRecord(
            step_id=name,
            status=status,
            lane=outcome.step_lanes.get(name, "async"),
            duration_ms=outcome.step_durations.get(name, 0),
            attempts=max(1, metric.attempts) if metric else 1,
            error=error,
            cached=metric.cache_hit if metric else False,
            identity_key=runtime.identity_keys.get(name, ""),
        )

    return (
        [record(name, "ok") for name in outcome.succeeded]
        + [
            record(name, "failed", reporter.scrub(str(error)))
            for name, error in outcome.failed.items()
        ]
        + [record(name, "skipped") for name in outcome.skipped]
    )


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
                    parent_run_id=options.resume_from or "",
                    env=options.env,
                    argv=safe_args.render(sys.argv[1:]),
                    tags=list(options.tags),
                )
            )
    except Exception as error:  # noqa: BLE001 - storage implementations vary by platform
        if options.require_provenance:
            raise ValidationError(
                "cannot persist required run provenance",
                remedies=["repair writable history storage, then retry"],
            ) from error
        return


def _auth_profiles(doc: WorkflowDoc, options: Options) -> dict[str, auth_mod.Profile]:
    """Named auth profiles from the project manifest, or empty for a standalone run.

    A manifest that fails to load or parse only fails *this* run when the workflow
    actually names an auth profile. A standalone file sitting near an unrelated,
    broken `sclpl.toml` above it must keep running exactly as it did before this
    lookup existed (B1's "standalone execution works").
    """
    uses_auth = any(
        isinstance(step.config, HttpConfig) and step.config.auth for step in doc.all_steps()
    )
    try:
        context = project_context.load(env=options.env)
        if context is None:
            return {}
        return auth_mod.parse_profiles(context.manifest, default_env=context.environment)
    except ValidationError:
        if uses_auth:
            raise
        return {}


def _policy(options: Options) -> policy_mod.Policy:
    """The project's declared policy, or `DEFAULT` (unrestricted) for a standalone run.

    Unlike `_auth_profiles`, a broken `[policy]` table is never swallowed once a
    project has loaded: a project that opted into `hosts`/`output_roots`/`overwrite`
    and typo'd one is a project whose safety boundary silently would not apply,
    which is worse than refusing to run at all. A project that fails to *load* at
    all -- unrelated broken TOML near a standalone workflow -- still must not break
    standalone execution, so that case falls back to the default exactly as auth does.
    """
    try:
        context = project_context.load(env=options.env)
    except ValidationError:
        return policy_mod.DEFAULT
    if context is None:
        return policy_mod.DEFAULT
    return policy_mod.parse(context)


def _output_settings(options: Options) -> outputs_mod.OutputSettings:
    """The project's `[outputs]` publication mode, or `DEFAULT` ("immediate").

    Same reasoning as `_policy`: a project that opted into validated publication
    and typo'd the table should not silently fall back to immediate writes --
    that is the one setting this batch touches where "fail open" would be wrong.
    """
    try:
        context = project_context.load(env=options.env)
    except ValidationError:
        return outputs_mod.DEFAULT
    if context is None:
        return outputs_mod.DEFAULT
    return outputs_mod.parse(context)


def _finish_publication(
    ledger: Ledger,
    doc: WorkflowDoc,
    options: Options,
    outcome: Outcome,
    started: float,
    reporter: Reporter,
) -> str:
    """Publish every staged output together, or discard all of them together.

    The one rule that actually closes "an assertion branch outrun by a faster,
    independent export" (SPEC 3.5): reference dependencies say nothing about two
    branches with no data relationship, so the only safe default is the whole
    run, not just this output's own ancestors -- nothing publishes unless every
    step in the run succeeded.

    Returns F5's publication state for `state/db.py`'s `RunRecord.publication`:
    `"published"`, `"interrupted"` (a later file's replace itself failed, so some
    of this generation is staged and some is not), or `"withheld"` (nothing was
    ever eligible, or the run did not succeed).
    """
    if outcome.status == "ok" and not outcome.failed:
        run_id = options.run_id or db.run_id(doc.name, started)
        result = publish(ledger, workflow=doc.name, run_id=run_id)
        if result.published:
            reporter.log("info", f"published: {', '.join(result.published)}")
        if result.interrupted:
            reporter.log(
                "error",
                f"publication interrupted, left staged: {', '.join(result.interrupted)}",
            )
            return "interrupted"
        return "published" if result.published else "withheld"
    discarded = discard(ledger)
    if discarded:
        reporter.log(
            "info", f"run did not succeed; discarded staged output(s): {', '.join(discarded)}"
        )
    return "withheld"


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
