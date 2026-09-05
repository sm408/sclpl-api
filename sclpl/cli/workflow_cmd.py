"""Workflow commands: run, validate, explain, fmt, convert.

`run` is the one that matters; the other four are all ways of looking at a workflow
without executing it, and they share the same resolution and preflight so what they
report is what `run` would actually do.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from sclpl.catalog import resolve as catalog
from sclpl.cli.options import options_of
from sclpl.errors import EXIT_INTERRUPTED, EXIT_USAGE, EXIT_VALIDATION, SclplError
from sclpl.project import context as project_context
from sclpl.project import identity, lock
from sclpl.render.reporter import build_reporter
from sclpl.run import compile_json
from sclpl.run.ir import WorkflowDoc
from sclpl.run.preflight import preflight
from sclpl.run.runner import Options, run_workflow
from sclpl.run.sclpll import emit as emit_sclpll
from sclpl.state import db


def register(app: typer.Typer) -> None:
    app.command("run", help="Run a workflow by name or path.")(run)
    app.command("validate", help="Check a workflow without running it.")(validate)
    app.command("explain", help="Show the execution plan.")(explain)
    app.command("fmt", help="Rewrite a workflow in canonical form.")(fmt)
    app.command("convert", help="Convert between the JSON and SCLPLL surfaces.")(convert)


WorkflowArg = Annotated[str, typer.Argument(help="Workflow name or path.")]
ModeOpt = Annotated[str | None, typer.Option("--mode", "-m", help="Named subset to run.")]


def run(
    ctx: typer.Context,
    workflow: WorkflowArg,
    files: Annotated[
        list[str] | None,
        typer.Argument(help="Positional port bindings: inputs then outputs."),
    ] = None,
    mode: ModeOpt = None,
    in_: Annotated[list[str] | None, typer.Option("--in", help="Bind an input: name=path.")] = None,
    out: Annotated[
        list[str] | None, typer.Option("--out", help="Bind an output: name=path.")
    ] = None,
    var: Annotated[
        list[str] | None, typer.Option("--var", help="Override a variable: key=value.")
    ] = None,
    concurrency: Annotated[int | None, typer.Option("--concurrency")] = None,
    host_concurrency: Annotated[int | None, typer.Option("--host-concurrency")] = None,
    timeout: Annotated[float | None, typer.Option("--timeout")] = None,
    retries: Annotated[int | None, typer.Option("--retries")] = None,
    keep_going: Annotated[
        bool, typer.Option("--keep-going", help="Do not stop at the first failure.")
    ] = False,
    no_validate: Annotated[
        bool, typer.Option("--no-validate", help="Skip preflight. Not recommended.")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Plan and validate, but execute nothing.")
    ] = False,
    keep_all: Annotated[
        bool, typer.Option("--keep-all", help="Do not free intermediate values.")
    ] = False,
    no_cache: Annotated[
        bool, typer.Option("--no-cache", help="Neither read nor write the cache.")
    ] = False,
    refresh: Annotated[
        bool, typer.Option("--refresh", help="Ignore what is cached; replace it.")
    ] = False,
    offline: Annotated[
        bool,
        typer.Option("--offline", help="Read the cache only. A miss exits 5."),
    ] = False,
    http_cache: Annotated[
        bool,
        typer.Option("--http-cache", help="Revalidate with ETag; a 304 counts as a hit."),
    ] = False,
    replay: Annotated[
        Path | None,
        typer.Option("--replay", help="Serve HTTP requests from this fixture directory offline."),
    ] = None,
    record_fixture: Annotated[
        Path | None,
        typer.Option("--record", help="Record HTTP responses into this fixture directory."),
    ] = None,
    locked: Annotated[
        bool,
        typer.Option("--locked", help="Require the project workflow lock before running."),
    ] = False,
    name: Annotated[
        str | None, typer.Option("--name", help="Call this run something in the history.")
    ] = None,
    tag: Annotated[list[str] | None, typer.Option("--tag", help="Tag it. Repeatable.")] = None,
    no_record: Annotated[
        bool, typer.Option("--no-record", help="Do not write it to the history.")
    ] = False,
    require_provenance: Annotated[
        bool,
        typer.Option(
            "--require-provenance", help="Refuse to start unless run provenance is stored."
        ),
    ] = False,
    memory_budget: Annotated[
        str | None,
        typer.Option(
            "--memory-budget",
            metavar="SIZE",
            help="Spill intermediates past this, e.g. 4G. Default: half the machine.",
        ),
    ] = None,
) -> None:
    located = _locate(workflow)
    doc = located.doc
    if locked:
        resolved_project = project_context.load()
        if resolved_project is None:
            typer.echo("--locked requires a project; run sclpl init first", err=True)
            raise typer.Exit(EXIT_VALIDATION)
        try:
            lock.verify(
                resolved_project,
                identity.identify(doc.name, located.path, resolved_project),
            )
        except SclplError as error:
            typer.echo(str(error), err=True)
            raise typer.Exit(error.exit_code) from error
    options = Options(
        mode=mode,
        named_in=_pairs(in_, "--in"),
        named_out=_pairs(out, "--out"),
        positional=list(files or []),
        overrides=_typed_pairs(var, "--var"),
        concurrency=concurrency,
        host_concurrency=host_concurrency,
        timeout=timeout,
        retries=retries,
        keep_going=keep_going,
        validate=not no_validate,
        dry_run=dry_run,
        keep_all=keep_all,
        memory_budget=memory_budget,
        name=name,
        tags=list(tag or []),
        record=not no_record,
        require_provenance=require_provenance,
        run_id=_new_run_id(),
        no_cache=no_cache,
        refresh=refresh,
        offline=offline,
        http_cache=http_cache,
        fixture_root=replay,
        record_fixture_root=record_fixture,
    )
    globals_ = options_of(ctx)
    reporter = build_reporter(
        verbosity=globals_.verbosity,
        json_mode=globals_.json_mode,
        plain=globals_.plain,
        no_color=globals_.no_color,
        # Written *during* the run, not assembled from memory afterwards: a log put
        # together at the end is a log that is missing whatever crashed.
        log_path=db.default_root() / "logs" / f"{options.run_id}.ndjson"
        if options.record
        else None,
    )

    async def go() -> int:
        async with reporter:
            result = await run_workflow(doc, options, reporter)
            return result.exit_code

    try:
        code = asyncio.run(go())
    except KeyboardInterrupt:
        raise typer.Exit(EXIT_INTERRUPTED) from None
    if code:
        raise typer.Exit(code)


def validate(
    ctx: typer.Context,
    workflow: WorkflowArg,
    mode: ModeOpt = None,
) -> None:
    """Preflight only: parse, resolve, check the graph and the ports."""
    doc = _load(workflow)
    report = preflight(doc, mode=mode, check_files=False, require_ports=False)
    del ctx

    if report.ok:
        typer.echo(f"{doc.name}: ok — {report.summary()}", err=True)
        for note in report.notes:
            typer.echo(f"  note: {note}", err=True)
        return

    for problem in report.problems:
        typer.echo(str(problem), err=True)
    raise typer.Exit(report.problems[0].exit_code)


def explain(
    ctx: typer.Context,
    workflow: WorkflowArg,
    mode: ModeOpt = None,
    memory: Annotated[
        bool,
        typer.Option("--memory", help="Show where each value is freed."),
    ] = False,
) -> None:
    """Print the plan: order, dependencies, and the critical path."""
    doc = _load(workflow)
    report = preflight(doc, mode=mode, check_files=False, require_ports=False)
    del ctx
    if not report.ok:
        for problem in report.problems:
            typer.echo(str(problem), err=True)
        raise typer.Exit(report.problems[0].exit_code)

    plan = report.plan
    assert plan is not None and report.resolved is not None

    header = f"{doc.name}"
    if report.resolved.name:
        header += f" [{report.resolved.name}]"
    typer.echo(header)
    if report.resolved.pruned:
        typer.echo(f"  pruned: {', '.join(sorted(report.resolved.pruned))}")

    typer.echo(f"\n  {'step':<24} {'depends on':<28} {'host':<20} cost")
    typer.echo(f"  {'-' * 24} {'-' * 28} {'-' * 20} ----")
    for step_id in plan.topological():
        node = plan.nodes[step_id]
        needs = ", ".join(sorted(node.needs)) or "-"
        typer.echo(
            f"  {step_id:<24} {needs[:28]:<28} {(node.host or '-')[:20]:<20} "
            f"{node.critical_path:.1f}"
        )

    if memory:
        released = plan.release_points()
        typer.echo(f"\n  {'value':<24} {'read by':<8} freed after")
        typer.echo(f"  {'-' * 24} {'-' * 8} {'-' * 24}")
        for step_id in plan.topological():
            # A leaf is what the run produced. Freeing it on arrival saves nothing and
            # throws away the answer, so it is held to the end.
            after = released.get(step_id) or "held (nothing reads it)"
            typer.echo(f"  {step_id:<24} {plan.readers_of(step_id):<8} {after}")

    typer.echo(f"\n  critical path: {plan.critical_path_length():.1f}")
    typer.echo(f"  parallel roots: {len(plan.roots())}")
    if report.bindings:
        for binding in report.bindings.all():
            typer.echo(f"  {binding.direction}: {binding.name} -> {binding.describe()}")


def fmt(
    ctx: typer.Context,
    path: Annotated[Path, typer.Argument(help="Workflow file to rewrite.")],
    check: Annotated[
        bool, typer.Option("--check", help="Exit 3 if it is not already canonical.")
    ] = False,
) -> None:
    """Rewrite a workflow in canonical form, in place."""
    del ctx
    if not path.is_file():
        typer.echo(f"{path} does not exist", err=True)
        raise typer.Exit(EXIT_USAGE)

    doc = catalog.load(path)
    formatted = compile_json.dumps(doc) if path.suffix == ".json" else emit_sclpll(doc)
    current = path.read_text(encoding="utf-8")

    if formatted == current:
        typer.echo(f"{path}: already canonical", err=True)
        return
    if check:
        typer.echo(f"{path}: not canonical", err=True)
        raise typer.Exit(EXIT_VALIDATION)
    path.write_text(formatted, encoding="utf-8")
    typer.echo(f"{path}: rewritten", err=True)


def convert(
    ctx: typer.Context,
    source: Annotated[Path, typer.Argument(help="Workflow to read.")],
    target: Annotated[
        Path | None, typer.Argument(help="Where to write it. Omit for stdout.")
    ] = None,
) -> None:
    """Convert between the JSON and SCLPLL surfaces.

    Both are surfaces over the same IR, so a conversion is lossless in either
    direction -- `fmt` then `convert` round-trips byte-identically.
    """
    del ctx
    if not source.is_file():
        typer.echo(f"{source} does not exist", err=True)
        raise typer.Exit(EXIT_USAGE)

    doc = catalog.load(source)
    suffix = (
        target.suffix.lower() if target else (".json" if source.suffix == ".sclpll" else ".sclpll")
    )
    rendered = compile_json.dumps(doc) if suffix == ".json" else emit_sclpll(doc)

    if target is None:
        sys.stdout.write(rendered)
        return
    target.write_text(rendered, encoding="utf-8")
    typer.echo(f"{source} -> {target}", err=True)


# -- helpers ---------------------------------------------------------------------


def _new_run_id() -> str:
    """A fresh id for this run, decided before it starts rather than after."""
    import time

    return db.run_id("run", time.perf_counter())


def _load(target: str) -> WorkflowDoc:
    return _locate(target).doc


def _locate(target: str) -> catalog.Located:
    try:
        resolved_project = project_context.load()
        return catalog.resolve(
            target,
            extra_dirs=resolved_project.workflow_dirs if resolved_project is not None else None,
        )
    except SclplError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(error.exit_code) from error


def _pairs(items: list[str] | None, flag: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items or []:
        name, separator, value = item.partition("=")
        if not separator or not name:
            typer.echo(f"{flag} expects name=value, got {item!r}", err=True)
            raise typer.Exit(EXIT_USAGE)
        out[name] = value
    return out


def _typed_pairs(items: list[str] | None, flag: str) -> dict[str, Any]:
    """`--var` values keep their obvious type: `--var limit=10` is the number 10."""
    from sclpl.run.sclpll.parse import _literal

    return {name: _literal(value) for name, value in _pairs(items, flag).items()}
