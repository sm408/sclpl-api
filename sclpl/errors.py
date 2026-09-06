"""Typed diagnostics, and the exit codes that go with them.

Lives at the top of the package rather than inside `run/` because every package raises
these -- `expr/`, `tables/`, `values/`, `ext/`, `functions/`, `catalog/`, and `cli/` all
import from here. It is the project's shared vocabulary for going wrong, not a part of
the engine, and having it inside `run/` made `run/` look like something everything
depended on when what everything depended on was this one leaf.

The exit codes live here too, for the same reason in the other direction. An exit code
is a property of a *kind of failure*, not of the surface that reports it; keeping them
in `cli/options.py` meant the engine imported the command line to know what number to
fail with.

**Every diagnostic carries remedies.** A message that says what went wrong and not what
to do about it is a message that sends the reader to the source.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

EXIT_OK = 0
EXIT_STEP_FAILED = 1
EXIT_USAGE = 2
EXIT_VALIDATION = 3
EXIT_ASSERTION = 4
EXIT_CACHE_MISS = 5
EXIT_UNKNOWN_TARGET = 6
EXIT_INTERRUPTED = 130


@dataclass(slots=True)
class Diagnostic:
    """The structured half of an error: everything but the class."""

    message: str
    where: str | None = None
    #: Concrete things the user can do. Rendered as a bulleted list under the message.
    remedies: list[str] = field(default_factory=list)

    def render(self) -> str:
        head = f"{self.where}: {self.message}" if self.where else self.message
        if not self.remedies:
            return head
        lines = [head]
        lines.extend(f"  - {remedy}" for remedy in self.remedies)
        return "\n".join(lines)


class SclplError(Exception):
    """Base for everything the user is meant to see rather than a traceback."""

    exit_code = EXIT_STEP_FAILED

    def __init__(
        self,
        message: str,
        *,
        where: str | None = None,
        remedies: list[str] | None = None,
    ) -> None:
        self.diagnostic = Diagnostic(message, where, remedies or [])
        super().__init__(self.diagnostic.render())


class ValidationError(SclplError):
    """The workflow is not runnable as written. Found before anything executes."""

    exit_code = EXIT_VALIDATION


class PolicyDenied(ValidationError):
    """A declared project policy blocked something before it could happen.

    Deliberately a `ValidationError`: like an unresolved reference or a broken
    graph, this is a reason the run cannot proceed as configured, found and
    reported before any side effect -- not a step that ran and failed.
    """


class ExpressionError(ValidationError):
    """A malformed expression, or one that cannot resolve."""


class PathError(ExpressionError):
    """A reference into a value that is not there.

    Never returns the literal text of the reference as a fallback: a request built from
    an unresolved `{{...}}` goes out to a URL nobody meant to call.
    """


class UnknownReference(ExpressionError):
    """`@name` where nothing produces `name`."""


class TypeDispatchError(ExpressionError):
    """No overload of an operator accepts the runtime type it was given."""


class StepFailed(SclplError):
    """A step ran and did not succeed."""

    exit_code = EXIT_STEP_FAILED


class AssertionFailed(SclplError):
    """An `assert` rule was false."""

    exit_code = EXIT_ASSERTION


class CacheMiss(SclplError):
    """`--offline` and the value is not in the cache."""

    exit_code = EXIT_CACHE_MISS


class UnknownTarget(SclplError):
    """No such workflow, mode, function, or plugin."""

    exit_code = EXIT_UNKNOWN_TARGET


def nearest(name: str, candidates: Iterable[object], *, limit: int = 3) -> list[str]:
    """Candidate names closest to ``name``, best first.

    Used everywhere a user can mistype an identifier. Damerau-Levenshtein, with a
    budget that grows in steps with the length of the *shorter* of the two words:
    one edit up to four characters, two up to eight, three beyond.

    Counting a transposition as one edit rather than two is what makes this work at a
    tight budget. Transpositions are the most common typo there is -- 'stpe' for
    'step', 'itmes' for 'items' -- and under plain Levenshtein they cost two, which
    forces a budget loose enough to also admit 'lane' for 'tags'. A suggestion the user
    has to stop and dismiss is worse than no suggestion.
    """
    names = [str(item) for item in candidates]
    if not names:
        return []
    scored: list[tuple[int, str]] = []
    for candidate in names:
        shorter = min(len(name), len(candidate))
        ceiling = 1 if shorter <= 4 else 2 if shorter <= 8 else 3
        distance = _damerau(name.lower(), candidate.lower())
        if distance <= ceiling:
            scored.append((distance, candidate))
    scored.sort(key=lambda pair: (pair[0], pair[1]))
    return [candidate for _, candidate in scored[:limit]]


def _damerau(left: str, right: str) -> int:
    """Optimal string alignment distance: insert, delete, substitute, or transpose."""
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    rows, columns = len(left) + 1, len(right) + 1
    grid = [[0] * columns for _ in range(rows)]
    for i in range(rows):
        grid[i][0] = i
    for j in range(columns):
        grid[0][j] = j

    for i in range(1, rows):
        for j in range(1, columns):
            cost = 0 if left[i - 1] == right[j - 1] else 1
            grid[i][j] = min(
                grid[i - 1][j] + 1,  # delete
                grid[i][j - 1] + 1,  # insert
                grid[i - 1][j - 1] + cost,  # substitute
            )
            if i > 1 and j > 1 and left[i - 1] == right[j - 2] and left[i - 2] == right[j - 1]:
                grid[i][j] = min(grid[i][j], grid[i - 2][j - 2] + 1)  # transpose
    return grid[-1][-1]


def did_you_mean(name: str, candidates: Iterable[object]) -> str | None:
    """A ready-made remedy line, or None when nothing is close enough."""
    matches = nearest(name, candidates)
    if not matches:
        return None
    if len(matches) == 1:
        return f"did you mean {matches[0]!r}?"
    quoted = ", ".join(repr(match) for match in matches)
    return f"did you mean one of {quoted}?"
