"""Run an ordinary Python file in the same interpreter as the SCLPL command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

from sclpl.errors import EXIT_USAGE


def register(app: typer.Typer) -> None:
    app.command(
        "python",
        help="Run a normal Python script. It can import sclpl from this environment.",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )(run)


def run(
    ctx: typer.Context,
    script: Annotated[Path, typer.Argument(help="Python source file to run.")],
) -> None:
    """Pass all arguments after SCRIPT directly to Python without invoking a shell."""
    if not script.is_file() or script.suffix.lower() != ".py":
        typer.echo(f"{script} is not a Python source file", err=True)
        raise typer.Exit(EXIT_USAGE)
    completed = subprocess.run([sys.executable, str(script), *ctx.args], check=False)
    if completed.returncode:
        raise typer.Exit(completed.returncode)
