"""Catalogue commands: import, list, show, remove."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from sclpl.catalog import resolve as resolver
from sclpl.catalog import store
from sclpl.errors import SclplError
from sclpl.run.preflight import preflight

app = typer.Typer(help="Register and inspect workflows.", no_args_is_help=True)


def register(root: typer.Typer) -> None:
    root.command("import", help="Register a workflow file.")(import_workflow)
    root.command("list", help="List registered and local workflows.")(list_workflows)
    root.command("show", help="Show a workflow's ports, modes, and steps.")(show)
    root.command("remove", help="Unregister a workflow.")(remove)


ScopeOpt = Annotated[
    str,
    typer.Option("--scope", help="Where to register it: project or user."),
]


def import_workflow(
    source: Annotated[Path, typer.Argument(help="Workflow file to register.")],
    name: Annotated[str | None, typer.Option("--as", help="Register under this name.")] = None,
    scope: ScopeOpt = "project",
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Replace without keeping the previous version.")
    ] = False,
) -> None:
    if scope not in ("project", "user"):
        typer.echo(f"unknown scope {scope!r}: expected 'project' or 'user'", err=True)
        raise typer.Exit(2)
    try:
        entry = store.import_workflow(source, scope=scope, name=name, overwrite=overwrite)
    except SclplError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(error.exit_code) from error
    typer.echo(f"registered {entry.name} ({entry.steps} steps) at {entry.path}", err=True)


def list_workflows(
    scope: Annotated[str | None, typer.Option("--scope", help="project or user.")] = None,
) -> None:
    """Everything resolvable, registered or local.

    Local files are listed too: they are what `sclpl <name>` would actually run, and a
    listing that only showed the registered ones would be misleading.
    """
    registered = {entry.name: entry for entry in store.entries(scope)}
    local = resolver.available()

    if not registered and not local:
        typer.echo("no workflows found", err=True)
        typer.echo("import one:  sclpl import <file.sclpll>", err=True)
        return

    typer.echo(f"{'name':<24} {'steps':>5}  {'where':<10} description")
    typer.echo(f"{'-' * 24} {'-' * 5}  {'-' * 10} {'-' * 30}")
    for name in sorted(set(registered) | set(local)):
        entry = registered.get(name)
        if entry is not None and name not in local:
            typer.echo(f"{name:<24} {entry.steps:>5}  {entry.scope:<10} {entry.description[:30]}")
        else:
            path = local.get(name)
            steps = entry.steps if entry else _count(path)
            typer.echo(f"{name:<24} {steps:>5}  {'local':<10} {path}")


def _count(path: Path | None) -> int:
    if path is None:
        return 0
    try:
        return len(resolver.load(path).all_steps())
    except Exception:  # noqa: BLE001 - a broken file still belongs in the listing
        return 0


def show(
    workflow: Annotated[str, typer.Argument(help="Workflow name or path.")],
) -> None:
    try:
        located = resolver.resolve(workflow)
    except SclplError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(error.exit_code) from error

    doc = located.doc
    typer.echo(f"{doc.name}  ({located.source}: {located.path})")
    if doc.description:
        typer.echo(f"  {doc.description}")

    if doc.inputs or doc.outputs:
        typer.echo("\nports:")
        for port in doc.inputs:
            flag = "" if port.required else "  (optional)"
            typer.echo(f"  in   {port.name:<20} {port.format}{flag}")
        for port in doc.outputs:
            flag = "" if port.required else "  (optional)"
            typer.echo(f"  out  {port.name:<20} {port.format}{flag}")

    if doc.modes:
        typer.echo("\nmodes:")
        for name, mode in doc.modes.items():
            marker = " (default)" if name == doc.default_mode else ""
            detail = mode.description or ("all steps" if mode.all else ", ".join(mode.include))
            typer.echo(f"  {name:<20} {detail[:44]}{marker}")

    typer.echo(f"\nsteps ({len(doc.all_steps())}):")
    for step in doc.all_steps():
        needs = f" <- {', '.join(step.needs)}" if step.needs else ""
        tags = f"  [{', '.join(step.tags)}]" if step.tags else ""
        typer.echo(f"  {step.id:<24} {step.kind:<10}{needs}{tags}")

    report = preflight(doc, check_files=False, require_ports=False)
    if report.ok:
        typer.echo(f"\nvalidates: {report.summary()}")
    else:
        typer.echo(f"\ndoes not validate: {report.problems[0].diagnostic.message}")


def remove(
    workflow: Annotated[str, typer.Argument(help="Registered workflow name.")],
    scope: ScopeOpt = "project",
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Do not ask.")] = False,
) -> None:
    try:
        entry = store.find(workflow, scope)
    except SclplError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(error.exit_code) from error

    # Nothing destructive without naming the target (SPEC section 15).
    if not yes and not typer.confirm(f"remove {entry.name} ({entry.path})?", default=False):
        typer.echo("cancelled", err=True)
        raise typer.Exit(0)

    path = store.remove(workflow, scope)
    typer.echo(
        f"removed {path} (a copy is kept under {store.root(scope) / store.VERSIONS})", err=True
    )
