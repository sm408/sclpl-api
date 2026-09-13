"""Project test-manifest inspection commands."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated

import typer

from sclpl.errors import EXIT_STEP_FAILED, SclplError
from sclpl.project import context
from sclpl.testing import Manifest, discover, load, select
from sclpl.testing import report as report_mod
from sclpl.testing import run as run_manifest

app = typer.Typer(no_args_is_help=True, help="Discover and validate project test manifests.")


def register(root: typer.Typer) -> None:
    root.add_typer(app, name="test")


def _project(project: Path | None) -> context.ProjectContext:
    loaded = context.load(project=project)
    if loaded is None:
        raise typer.BadParameter("a project manifest is required", param_hint="--project")
    return loaded


@app.command("list")
def list_tests(
    project: Annotated[
        Path | None, typer.Option("--project", help="Project root or manifest.")
    ] = None,
) -> None:
    """List discovered project test manifests without executing workflows."""
    loaded = _project(project)
    for path in discover(loaded):
        typer.echo(path.relative_to(loaded.root))


@app.command("validate")
def validate(
    path: Annotated[Path, typer.Argument(help="Test manifest path.")],
    project: Annotated[
        Path | None, typer.Option("--project", help="Project root or manifest.")
    ] = None,
) -> None:
    """Validate one declaration before it is eligible for isolated offline execution."""
    loaded = _project(project)
    manifest = load(path, loaded)
    typer.echo(f"{manifest.path}: valid", err=True)


@app.command("run")
def run(
    path: Annotated[
        Path | None, typer.Argument(help="One test manifest; every discovered one when omitted.")
    ] = None,
    project: Annotated[
        Path | None, typer.Option("--project", help="Project root or manifest.")
    ] = None,
    changed: Annotated[
        bool,
        typer.Option("--changed", help="Only manifests a git diff against --base could affect."),
    ] = False,
    base: Annotated[
        str,
        typer.Option("--base", help="Git ref --changed diffs against."),
    ] = "HEAD",
    update_snapshots: Annotated[
        bool,
        typer.Option(
            "--update-snapshots", help="Rewrite expected-output files instead of failing on them."
        ),
    ] = False,
    junit: Annotated[
        Path | None, typer.Option("--junit", help="Write a JUnit XML report to this path.")
    ] = None,
    json_report: Annotated[
        Path | None, typer.Option("--json", help="Write a stable JSON report to this path.")
    ] = None,
    report_html: Annotated[
        Path | None, typer.Option("--html", help="Write a self-contained HTML report to this path.")
    ] = None,
) -> None:
    """Run project test manifests with fixtures offline, state isolated below `.sclpl/tests`."""
    loaded = _project(project)
    if changed and path is not None:
        raise typer.BadParameter("--changed selects manifests itself; do not also name one")

    targets = [path] if path is not None else discover(loaded)
    manifests: list[Manifest] = []
    failed = 0
    cases: list[report_mod.CaseResult] = []
    for target in targets:
        try:
            manifests.append(load(target, loaded))
        except SclplError as error:
            typer.echo(f"{target}: {error}", err=True)
            failed += 1
            cases.append(report_mod.CaseResult(str(target), str(target), False, 0.0, str(error)))

    if changed:
        manifests = select(manifests, loaded, base=base)
    if not manifests and not failed:
        typer.echo("no test manifests to run", err=True)
        return

    for manifest in manifests:
        started = time.perf_counter()
        try:
            outcome = run_manifest(manifest, loaded, update_snapshots=update_snapshots)
        except SclplError as error:
            typer.echo(f"{manifest.path}: {error}", err=True)
            failed += 1
            cases.append(
                report_mod.CaseResult(
                    manifest.workflow,
                    str(manifest.path),
                    False,
                    time.perf_counter() - started,
                    str(error),
                )
            )
            continue
        duration = time.perf_counter() - started
        if outcome.updated:
            for path_written in outcome.updated:
                typer.echo(f"{manifest.path}: updated {path_written}", err=True)
            cases.append(
                report_mod.CaseResult(manifest.workflow, str(manifest.path), True, duration)
            )
        elif outcome.result.ok:
            typer.echo(f"{manifest.path}: passed", err=True)
            cases.append(
                report_mod.CaseResult(manifest.workflow, str(manifest.path), True, duration)
            )
        else:
            failed += 1
            typer.echo(f"{manifest.path}: failed (exit {outcome.result.exit_code})", err=True)
            cases.append(
                report_mod.CaseResult(
                    manifest.workflow,
                    str(manifest.path),
                    False,
                    duration,
                    f"exit {outcome.result.exit_code}",
                )
            )

    _write_reports(cases, junit=junit, json_path=json_report, html_path=report_html)
    if failed:
        raise typer.Exit(EXIT_STEP_FAILED)


def _write_reports(
    cases: list[report_mod.CaseResult],
    *,
    junit: Path | None,
    json_path: Path | None,
    html_path: Path | None,
) -> None:
    for path, render in (
        (junit, report_mod.to_junit_xml),
        (json_path, report_mod.to_json),
        (html_path, report_mod.to_html),
    ):
        if path is None:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(cases), encoding="utf-8")
        typer.echo(f"wrote {path}", err=True)
