"""Project test-manifest inspection commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from sclpl.project import context
from sclpl.testing import discover, load

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
