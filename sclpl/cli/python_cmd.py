"""Run an ordinary Python file in the same interpreter as the SCLPL command."""

from __future__ import annotations

import subprocess
import sys
from typing import Annotated

import typer

from sclpl.errors import EXIT_USAGE
from sclpl.project import context as project_context
from sclpl.project import scripts


def register(app: typer.Typer) -> None:
    app.command(
        "python",
        help="Run a registered Python script. It can import sclpl from this environment.",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )(run)


def run(
    ctx: typer.Context,
    script: Annotated[str, typer.Argument(help="Registered script name from sclpl.toml.")],
) -> None:
    """Run a digest-pinned project script without accepting an arbitrary path."""
    project = project_context.load()
    if project is None:
        typer.echo("sclpl python requires a project with [python.scripts]", err=True)
        raise typer.Exit(EXIT_USAGE)
    path = scripts.materialize(project, script)
    completed = subprocess.run([sys.executable, str(path), *ctx.args], check=False)
    if completed.returncode:
        raise typer.Exit(completed.returncode)
