"""Typed diagnostics.

Every user-facing failure is one of these. They carry enough structure that the
reporter can render them and the CLI can pick an exit code without re-parsing a
message string.

The rule for messages: say what was wrong, where, and what to do instead. A diagnostic
that only says what was wrong makes the user guess.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from sclpl.cli.options import (
    EXIT_ASSERTION,
    EXIT_CACHE_MISS,
    EXIT_STEP_FAILED,
    EXIT_UNKNOWN_TARGET,
    EXIT_VALIDATION,
)


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

    Used everywhere a user can mistype an identifier. Levenshtein, with the cap derived
    from *both* lengths: 'pric' and 'id' are three edits apart, which is within budget
    for a four-character typo but well outside it for a two-character name. Judging on
    the typo alone lets short unrelated names in, and a suggestion the user has to
    dismiss is worse than no suggestion.
    """
    names = [str(item) for item in candidates]
    if not names:
        return []
    scored: list[tuple[int, str]] = []
    for candidate in names:
        ceiling = max(1, min(len(name), len(candidate)) // 2 + 1)
        distance = _levenshtein(name.lower(), candidate.lower())
        if distance <= ceiling:
            scored.append((distance, candidate))
    scored.sort(key=lambda pair: (pair[0], pair[1]))
    return [candidate for _, candidate in scored[:limit]]


def _levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for i, lchar in enumerate(left, start=1):
        current = [i]
        for j, rchar in enumerate(right, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (lchar != rchar),
                )
            )
        previous = current
    return previous[-1]


def did_you_mean(name: str, candidates: Iterable[object]) -> str | None:
    """A ready-made remedy line, or None when nothing is close enough."""
    matches = nearest(name, candidates)
    if not matches:
        return None
    if len(matches) == 1:
        return f"did you mean {matches[0]!r}?"
    quoted = ", ".join(repr(match) for match in matches)
    return f"did you mean one of {quoted}?"
