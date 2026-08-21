"""Shared option types, exit codes, and the resolved global option set.

Every command reads its global flags from one `GlobalOptions` on the Typer context, so
`-v` means the same thing everywhere and a new command cannot quietly invent its own
verbosity scale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import typer

# Exit codes are part of the CLI contract (SPEC §15) — scripts depend on them.
EXIT_OK = 0
EXIT_STEP_FAILED = 1
EXIT_USAGE = 2
EXIT_VALIDATION = 3
EXIT_ASSERTION = 4
EXIT_CACHE_MISS = 5
EXIT_UNKNOWN_TARGET = 6
EXIT_INTERRUPTED = 130

#: `-qq` .. `-vvv`. Below `-2` and above `3` nothing further changes, so clamp rather
#: than let `-vvvvv` imply a level no sink implements.
MIN_VERBOSITY = -2
MAX_VERBOSITY = 3


@dataclass(frozen=True, slots=True)
class GlobalOptions:
    """Flags that apply to every command, resolved once on the root callback."""

    verbosity: int = 0
    json_mode: bool = False
    plain: bool = False
    no_color: bool = False


def resolve_verbosity(quiet: int, verbose: int) -> int:
    """`-q` counts down, `-v` counts up. Both given is the user's problem, not ours."""
    return max(MIN_VERBOSITY, min(MAX_VERBOSITY, verbose - quiet))


QuietOption = Annotated[
    int,
    typer.Option(
        "--quiet",
        "-q",
        count=True,
        help="Errors and summary only; repeat (-qq) for silence.",
    ),
]

VerboseOption = Annotated[
    int,
    typer.Option(
        "--verbose",
        "-v",
        count=True,
        help="More detail; repeat up to -vvv.",
    ),
]

JsonOption = Annotated[
    bool,
    typer.Option(
        "--json",
        help="Emit NDJSON events on stderr and suppress the human view.",
    ),
]

PlainOption = Annotated[
    bool,
    typer.Option("--plain", help="Force the plain renderer: one line per event, no escapes."),
]

NoColorOption = Annotated[
    bool,
    typer.Option("--no-color", help="Disable colour. NO_COLOR in the environment does the same."),
]


def options_of(ctx: typer.Context) -> GlobalOptions:
    """The resolved globals for this invocation.

    Falls back to defaults so a command remains callable in tests without going through
    the root callback.
    """
    resolved = ctx.find_object(GlobalOptions)
    return resolved if resolved is not None else GlobalOptions()
