"""The Typer root: global flags, the bare shorthand, and subcommand registration.

Commands are registered by the module that owns them, so a milestone adds its surface
in one place. Nothing is stubbed: if `--help` lists a command, that command works.
"""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from sclpl import __version__, bootstrap
from sclpl.cli import (
    admin_cmd,
    catalog_cmd,
    contract_cmd,
    docs_cmd,
    launcher,
    plugin_cmd,
    project_cmd,
    resource_cmd,
    test_cmd,
    workflow_cmd,
    workflow_project_cmd,
)
from sclpl.cli import run as call_cmd
from sclpl.cli.options import (
    GlobalOptions,
    JsonOption,
    NoColorOption,
    PlainOption,
    QuietOption,
    VerboseOption,
    resolve_verbosity,
)
from sclpl.errors import EXIT_USAGE, SclplError, ValidationError
from sclpl.ext.configuration import set_plugin_settings
from sclpl.ext.plugins import parse_capabilities
from sclpl.project import context as project_context
from sclpl.project import policy as policy_mod


def _denied_capabilities() -> list[str]:
    """`--deny-capability` values, read from `sys.argv` rather than from the parser.

    Loading a plugin *runs* its module, so a capability refused after parsing has
    already been exercised. The denial has to precede the import, and the import
    precedes the parser -- so this reads the flag itself. It is validated properly by
    `plugins.parse_capabilities` once the registry has it, so a typo is still an error
    and not a silent no-op.
    """
    wanted: list[str] = []
    argv = sys.argv[1:]
    for index, item in enumerate(argv):
        if item == "--deny-capability" and index + 1 < len(argv):
            wanted.append(argv[index + 1])
        elif item.startswith("--deny-capability="):
            wanted.append(item.split("=", 1)[1])
    return wanted


def _project_denied_capabilities() -> frozenset[str]:
    """A project's own declared capability denials, or empty for a standalone run.

    A project that fails to load at all -- no manifest, or one broken for reasons
    unrelated to policy -- denies nothing extra here, exactly like a workflow run
    falls back to `policy.DEFAULT` when no project is found. A project that loads
    but declares an unparsable `[policy]` table is different: this runs before any
    subcommand's own error handling exists to report it well, so it is swallowed
    here too and left for that subcommand -- `project check` or `run` -- to raise
    with a proper diagnostic once it actually loads the project itself.
    """
    try:
        context = project_context.load()
    except ValidationError:
        return frozenset()
    if context is None:
        return frozenset()
    try:
        return policy_mod.parse(context).deny_capabilities
    except ValidationError:
        return frozenset()


def _is_static_plugin_inspection() -> bool:
    """Whether the requested command promises not to import plugin modules."""
    argv = sys.argv[1:]
    return len(argv) >= 2 and argv[:2] == ["plugin", "list"] and "--static" in argv[2:]


# Commands and help only need built-ins to route. Plugin activation follows policy
# resolution in the root callback, preventing project code from running at import time.
bootstrap.load(plugins=False)

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
contract_cmd.register(app)
plugin_cmd.register(app)
project_cmd.register(app)
resource_cmd.register(app)
test_cmd.register(app)
workflow_project_cmd.register(app)
admin_cmd.register(app)
docs_cmd.register(app)


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
    deny_capability: Annotated[
        list[str] | None,
        typer.Option(
            "--deny-capability",
            metavar="NAME",
            help="Refuse to load any plugin declaring this. Repeatable.",
        ),
    ] = None,
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version,
        is_eager=True,
        help="Print the version and exit.",
    ),
) -> None:
    # Validate policy before plugin activation, so a typo is not a silent no-op.
    # A project's own `[policy] deny_capabilities` is folded in here too: activation
    # happens once, at process startup, before any subcommand -- including `--project`
    # -- has been parsed, so this can only see a project discoverable from the
    # current directory. That is the same constraint auth profiles and output policy
    # already accept for a standalone run; it is not a new limitation.
    denied = frozenset(deny_capability or ()) | _project_denied_capabilities()
    parse_capabilities(denied)
    if not _is_static_plugin_inspection():
        loaded_project = project_context.load()
        set_plugin_settings(loaded_project.plugin_settings if loaded_project is not None else {})
        bootstrap.activate_plugins(denied=denied)

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

    try:
        app()
    except SclplError as error:
        # A diagnostic reaching here came from somewhere no command wraps -- the root
        # callback, or an option parsed before routing. It was written to be read, so
        # it is printed rather than shown as a traceback with the message buried in it.
        typer.echo(str(error), err=True)
        # `sys.exit`, not `typer.Exit`: we are outside `app()`, so Click's handler is
        # no longer on the stack to turn that into an exit code.
        sys.exit(error.exit_code)


def _command_names() -> list[str]:
    return [
        command.name or (command.callback.__name__ if command.callback else "")
        for command in app.registered_commands
    ]
