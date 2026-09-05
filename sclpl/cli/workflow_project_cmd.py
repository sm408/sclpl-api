"""Project-aware workflow subcommands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from sclpl.catalog import resolve
from sclpl.cli import workflow_cmd
from sclpl.project import context, identity, lock


def register(root: typer.Typer) -> None:
    app = typer.Typer(no_args_is_help=True, help="Project workflow operations.")
    app.command("list", help="List workflows declared by the project.")(list_workflows)
    app.command("lock", help="Write or verify project workflow identities.")(lock_workflows)
    app.command("replay", help="Run a workflow using recorded fixtures offline.")(replay)
    root.add_typer(app, name="workflow")


def list_workflows() -> None:
    loaded = context.load()
    found = resolve.available(loaded.workflow_dirs if loaded else None)
    if not found:
        typer.echo("no workflows found", err=True)
        return
    for name, path in sorted(found.items()):
        typer.echo(f"{name}\t{path}")


def lock_workflows(
    name: str | None = typer.Argument(None, help="One workflow; omit for all project workflows."),
    check: bool = typer.Option(False, "--check", help="Verify without rewriting the lock."),
) -> None:
    loaded = context.load()
    if loaded is None:
        raise typer.BadParameter("workflow locks require a project; run sclpl init first")
    available = resolve.available(loaded.workflow_dirs)
    selected = [name] if name else sorted(available)
    if not selected:
        raise typer.BadParameter("no project workflows found")
    identified = []
    for target in selected:
        located = resolve.resolve(target, extra_dirs=loaded.workflow_dirs)
        identified.append(identity.identify(located.doc.name, located.path, loaded))
    if check:
        for item in identified:
            lock.verify(loaded, item)
        typer.echo(f"{len(identified)} workflow lock{'s' if len(identified) != 1 else ''}: valid")
        return
    path = lock.write(loaded, identified)
    typer.echo(f"wrote {path}")


def replay(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Project workflow name or path.")],
    fixture: Annotated[Path, typer.Option("--fixture", help="Recorded fixture directory.")],
) -> None:
    """Delegate to the normal workflow runner with its live transport replaced."""
    workflow_cmd.run(ctx, name, replay=fixture)
