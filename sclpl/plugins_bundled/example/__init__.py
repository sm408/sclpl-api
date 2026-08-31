"""A plugin that does almost nothing, correctly.

This is what `sclpl plugin scaffold` writes. It is also loaded on every run like any
other bundled plugin, which means it cannot quietly stop working -- a scaffold that no
longer runs is worse than no scaffold, because it costs an hour before you suspect it.

Copy the directory, rename it, delete what you do not need.

Three things to know:

1. **Import from `sclpl.ext.api` only.** That module is the promise; everything else may
   be rearranged between versions without warning.
2. **A dot makes it a connector.** `greet` is a function, `example.echo` is a connector,
   and the only difference is the namespace -- which is what lets two plugins both offer
   `query` without either having to be renamed.
3. **Type hints are load-bearing.** The signature generates the JSON Schema, the help
   text, the shell completions, and the coercion that turns `"3"` from a workflow file
   into the `int` you declared. Annotate everything.
"""

from __future__ import annotations

from typing import Any

from sclpl.ext.api import connector, function


def register() -> None:
    """Called once when the plugin loads.

    The decorators below have already run by the time this is reached -- importing the
    module is what registers them. Use this for anything that needs to happen *after*
    the engine exists: replacing the table backend, registering a rehydrator, reading
    configuration.

    An exception here is caught and turned into a refusal, so a broken plugin is listed
    as broken rather than taking the run down with it.
    """


@function("greet")
def greet(name: str, *, excited: bool = False) -> str:
    """Say hello. The smallest thing a plugin can contribute.

    The first line of this docstring becomes the summary in `sclpl fn list` and in
    `--help`, so write it as one.
    """
    return f"Hello, {name}!" if excited else f"Hello, {name}."


@connector("example.echo")
def echo(value: Any, *, times: int = 1) -> list[Any]:
    """Return what it was given, `times` times.

    Note what is *not* here: no argument validation, no type coercion, no help text.
    All three come from the signature.
    """
    return [value] * times
