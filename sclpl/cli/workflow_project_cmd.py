"""Project-aware workflow subcommands."""

from __future__ import annotations

import typer

from sclpl.catalog import resolve
from sclpl.project import context


def register(root: typer.Typer) -> None:
    app = typer.Typer(no_args_is_help=True, help="Project workflow operations.")
    app.command("list", help="List workflows declared by the project.")(list_workflows)
    root.add_typer(app, name="workflow")


def list_workflows() -> None:
    loaded = context.load()
    found = resolve.available(loaded.workflow_dirs if loaded else None)
    if not found:
        typer.echo("no workflows found", err=True)
        return
    for name, path in sorted(found.items()):
        typer.echo(f"{name}\t{path}")
