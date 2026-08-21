"""The Typer root: global flags, version, and subcommand registration.

Commands are registered by the module that owns them, so a milestone adds its surface
in one place. Nothing is stubbed: if `--help` lists a command, that command works.
"""

from __future__ import annotations

import typer

from sclpl import __version__
from sclpl.cli import run
from sclpl.cli.options import (
    EXIT_USAGE,
    GlobalOptions,
    JsonOption,
    NoColorOption,
    PlainOption,
    QuietOption,
    VerboseOption,
    resolve_verbosity,
)

app = typer.Typer(
    name="sclpl",
    help="A command-line pipeline runner for HTTP APIs.",
    add_completion=False,
    no_args_is_help=False,
    pretty_exceptions_enable=False,
)

run.register(app)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"sclpl {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    quiet: QuietOption = 0,
    verbose: VerboseOption = 0,
    json_mode: JsonOption = False,
    plain: PlainOption = False,
    no_color: NoColorOption = False,
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version,
        is_eager=True,
        help="Print the version and exit.",
    ),
) -> None:
    ctx.obj = GlobalOptions(
        verbosity=resolve_verbosity(quiet, verbose),
        json_mode=json_mode,
        plain=plain,
        no_color=no_color,
    )
    if ctx.invoked_subcommand is not None:
        return
    # Bare invocation. The interactive launcher (SPEC §15) arrives in M4; until then a
    # bare `sclpl` does the documented non-TTY thing — help, and exit 2.
    typer.echo(ctx.get_help())
    raise typer.Exit(EXIT_USAGE)
