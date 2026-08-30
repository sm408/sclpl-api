"""The Typer root: global flags, the bare shorthand, and subcommand registration.

Commands are registered by the module that owns them, so a milestone adds its surface
in one place. Nothing is stubbed: if `--help` lists a command, that command works.
"""

from __future__ import annotations

import sys

import typer

from sclpl import __version__, bootstrap
from sclpl.cli import catalog_cmd, launcher, workflow_cmd
from sclpl.cli import run as call_cmd
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

# Built-ins and plugins register before any command can be routed, so `--help`,
# completion, and preflight all see the same set a run would.
bootstrap.load()

app = typer.Typer(
    name="sclpl",
    help="A command-line pipeline runner for HTTP APIs.",
    add_completion=False,
    no_args_is_help=False,
    pretty_exceptions_enable=False,
)

call_cmd.register(app)
workflow_cmd.register(app)
catalog_cmd.register(app)


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
    # Bare `sclpl`: the launcher on a terminal, help and exit 2 otherwise.
    if launcher.is_interactive():
        raise typer.Exit(launcher.launch())
    typer.echo(ctx.get_help())
    raise typer.Exit(EXIT_USAGE)


def entrypoint() -> None:
    """The console script.

    The bare shorthand is resolved here rather than inside Typer, because Typer has to
    see a subcommand to route at all. Rewriting `sclpl orders partial in.csv` into
    `sclpl run orders --mode partial in.csv` before Typer parses keeps one code path
    for both spellings.
    """
    argv = sys.argv[1:]
    known = set(app.registered_commands and _command_names())
    if argv and not argv[0].startswith("-") and argv[0] not in known:
        rewritten = launcher.bare_shorthand(argv)
        if rewritten is not None:
            sys.argv = [sys.argv[0], *rewritten]
    app()


def _command_names() -> list[str]:
    return [
        command.name or (command.callback.__name__ if command.callback else "")
        for command in app.registered_commands
    ]
