"""`sclpl plugin` — what is installed, what it contributes, and how to write one."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from sclpl.errors import EXIT_USAGE, ValidationError
from sclpl.ext import plugins as ext

app = typer.Typer(no_args_is_help=True, help="Inspect and scaffold plugins.")


def register(root: typer.Typer) -> None:
    root.add_typer(app, name="plugin")


NameArg = Annotated[str, typer.Argument(help="Plugin name.")]


@app.command("list")
def list_plugins(
    refused: Annotated[
        bool, typer.Option("--refused", help="Only the ones that did not load.")
    ] = False,
) -> None:
    """What is installed, where it came from, and what it may do."""
    registry = ext.discover()
    found = registry.refused() if refused else list(registry.plugins.values())

    if not found:
        typer.echo("no plugins" if not refused else "nothing was refused", err=True)
        return

    width = max(len(plugin.name) for plugin in found)
    for plugin in sorted(found, key=lambda item: item.name):
        mark = " " if plugin.loaded else "!"
        caps = ", ".join(sorted(plugin.capabilities)) or "-"
        typer.echo(f"{mark} {plugin.name:<{width}} {plugin.version:<8} {plugin.source:<12} {caps}")
        if plugin.refused:
            typer.echo(f"  {' ' * width}   {plugin.refused}")

    for name, first, second in registry.shadowed:
        # Two plugins claiming one name is a thing to know about, not a coin toss.
        typer.echo(f"! {name}: also provided by {second}; using the one from {first}", err=True)


@app.command()
def describe(name: NameArg) -> None:
    """Everything a plugin declares, and everything it registered."""
    from sclpl.ext.functions import REGISTRY as FUNCTIONS

    registry = ext.discover()
    plugin = registry.get(name)

    typer.echo(f"{plugin.name} {plugin.version}")
    if plugin.description:
        typer.echo(f"  {plugin.description}")
    typer.echo(f"\n  api          {plugin.api}")
    typer.echo(f"  source       {plugin.source}")
    if plugin.path:
        typer.echo(f"  path         {plugin.path}")
    typer.echo(f"  module       {plugin.module}")
    typer.echo(f"  capabilities {', '.join(sorted(plugin.capabilities)) or 'none'}")
    typer.echo(f"  status       {'loaded' if plugin.loaded else 'refused'}")
    if plugin.refused:
        typer.echo(f"               {plugin.refused}")

    if plugin.contributes:
        typer.echo("\n  declares")
        for item in plugin.contributes:
            lane = f" [{item.lane}]" if item.lane else ""
            typer.echo(f"    {item.kind:<10} {item.name}{lane}")
            if item.summary:
                typer.echo(f"    {'':<10} {item.summary}")

    # What it *declared* and what it *registered* can differ, and the difference is
    # worth seeing: a manifest naming a connector the code forgot is a bug in the plugin.
    registered = sorted(entry for entry in FUNCTIONS if entry.startswith(f"{plugin.name}."))
    if registered:
        typer.echo("\n  registered")
        for entry in registered:
            typer.echo(f"    {entry:<24} {FUNCTIONS[entry].signature()}")


@app.command()
def scaffold(
    name: NameArg,
    into: Annotated[Path, typer.Option("--into", help="Where to write it.")] = Path("plugins"),
) -> None:
    """Write a working plugin you can edit.

    Working, not a sketch: it loads, it registers, and `sclpl fn list` shows what it
    added the moment it is written. A scaffold that needs three fixes before it runs
    teaches the wrong thing about how hard this is.
    """
    if not name.isidentifier():
        raise ValidationError(
            f"{name!r} is not a usable plugin name",
            remedies=["letters, digits, and underscores; it becomes a Python module"],
        )

    target = into / name
    if target.exists():
        raise ValidationError(
            f"{target} already exists",
            remedies=["pick another name, or delete it first"],
        )

    target.mkdir(parents=True)
    (target / "plugin.toml").write_text(_MANIFEST.format(name=name), encoding="utf-8")
    (target / "__init__.py").write_text(_MODULE.format(name=name), encoding="utf-8")

    typer.echo(f"wrote {target}", err=True)
    typer.echo(f"  {target / 'plugin.toml'}", err=True)
    typer.echo(f"  {target / '__init__.py'}", err=True)
    typer.echo(f"\ntry it:\n  sclpl plugin describe {name}\n  sclpl fn list", err=True)


@app.command()
def install(
    source: Annotated[str, typer.Argument(help="A pip requirement, or a directory.")],
) -> None:
    """How to install a plugin. It does not run pip for you.

    Deliberately. `sclpl` running `pip install` would guess at the environment, the
    index, and whether you meant `--user` -- and be wrong in a way that is hard to
    unpick. Printing the command respects that you have a package manager and know how
    you like to use it.
    """
    typer.echo(f"  pip install {source}", err=True)
    typer.echo("\nfor one you are writing, no install is needed:", err=True)
    typer.echo("  put it in ./plugins/ or ~/.sclpl/plugins/", err=True)
    typer.echo("  sclpl plugin list", err=True)
    raise typer.Exit(EXIT_USAGE)


_MANIFEST = """[plugin]
name = "{name}"
version = "0.1.0"
api = "sclpl/1"
module = "{name}"
description = "What this plugin is for."

# What it needs to be allowed to do. Shown by `sclpl plugin list`, and refused by
# `--deny-capability`. Declare the least that is true.
# One of: network, fs:read, fs:write, secrets:read, subprocess
capabilities = []

[[function]]
name = "{name}_hello"
summary = "One line, shown in `sclpl fn list`."

[[connector]]
name = "{name}.echo"
summary = "A namespaced callable."
"""

_MODULE = '''"""The {name} plugin."""

from __future__ import annotations

from typing import Any

from sclpl.ext.api import connector, function


def register() -> None:
    """Called once when the plugin loads.

    The decorators below have already run -- importing the module is what registers
    them. Use this for anything needing the engine to exist first.
    """


@function("{name}_hello")
def hello(name: str) -> str:
    """One line, shown in `sclpl fn list` and in `--help`."""
    return f"Hello from {name}, {{name}}."


@connector("{name}.echo")
def echo(value: Any, *, times: int = 1) -> list[Any]:
    """Return what it was given, `times` times.

    Note what is not here: no argument parsing, no validation, no help text. The
    signature generates all three, so annotate everything.
    """
    return [value] * times
'''
