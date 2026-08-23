"""Finding `@name` references in a string.

One place, because getting this wrong breaks invariant 3 silently. A missed reference
means a missing edge, which means a step runs before the value it reads exists -- and
the symptom appears in a different step, at a different time, on a different run
depending on scheduling.

A string in a workflow can be any of three things, and they need different treatment:

- an **interpolated string** -- `"{{base}}/orders"`
- a bare **expression** -- `count(@fetch.body.items)`, which is what a `let`, an
  `assert`, or a function argument holds
- **literal text** -- `out.csv`

Because a missed edge is a correctness bug while a spurious edge only costs some
parallelism, everything here errs toward finding a reference.
"""

from __future__ import annotations

import re

from sclpl.expr.parse import parse, parse_interpolated
from sclpl.run.errors import ValidationError

#: The fallback scan. Deliberately the same shape the lexer accepts for a `@ref`.
_REF = re.compile(r"@([A-Za-z_][A-Za-z0-9_-]*)")


def refs_in(text: str) -> frozenset[str]:
    """Every `@name` the string refers to."""
    if "@" not in text:
        return frozenset()

    if "{{" in text:
        try:
            return parse_interpolated(text).refs
        except ValidationError:
            return _scan(text)

    try:
        return parse(text).refs
    except ValidationError:
        # Not a whole expression -- a JSON body with a reference inside it, say. The
        # scan is coarser but never misses one, which is the direction to be wrong in.
        return _scan(text)


def _scan(text: str) -> frozenset[str]:
    return frozenset(_REF.findall(text))


def refs_in_value(value: object) -> frozenset[str]:
    """Every reference reachable in a config value, however deeply nested."""
    found: set[str] = set()
    _walk(value, found)
    return frozenset(found)


def _walk(value: object, found: set[str]) -> None:
    if isinstance(value, str):
        found.update(refs_in(value))
    elif isinstance(value, dict):
        for item in value.values():
            _walk(item, found)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _walk(item, found)
    elif hasattr(value, "model_dump"):
        _walk(value.model_dump(), found)
