"""The JSON surface: text in, IR out, and back again.

Thin by design. Pydantic does the validation; this module's job is to turn a pydantic
error into a diagnostic that names the field and says what to do, and to write the
canonical form back out byte-stably.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError as PydanticError

from sclpl.errors import ValidationError, did_you_mean
from sclpl.run.ir import WorkflowDoc

#: Two spaces, keys in model order, trailing newline. The formatting `fmt` produces and
#: the round-trip property depends on.
INDENT = 2


def loads(source: str, *, origin: str = "<json>") -> WorkflowDoc:
    """Parse JSON text into the IR."""
    try:
        raw = json.loads(source)
    except json.JSONDecodeError as error:
        raise ValidationError(
            f"not valid JSON: {error.msg}",
            where=f"{origin}:{error.lineno}:{error.colno}",
            remedies=_json_remedies(error, source),
        ) from error
    return from_dict(raw, origin=origin)


def from_dict(raw: Any, *, origin: str = "<dict>") -> WorkflowDoc:
    if not isinstance(raw, dict):
        raise ValidationError(
            f"a workflow must be an object, not {type(raw).__name__}",
            where=origin,
            remedies=["the top level needs at least a 'name' and 'steps'"],
        )
    try:
        return WorkflowDoc.model_validate(raw)
    except PydanticError as error:
        raise _translate(error, raw, origin) from error


def load(path: Path) -> WorkflowDoc:
    return loads(path.read_text(encoding="utf-8"), origin=str(path))


def dumps(doc: WorkflowDoc) -> str:
    """The canonical JSON form. Stable enough to diff and to hash."""
    return json.dumps(doc.canonical(), indent=INDENT, ensure_ascii=False) + "\n"


def dump(doc: WorkflowDoc, path: Path) -> None:
    path.write_text(dumps(doc), encoding="utf-8")


def _translate(error: PydanticError, raw: Any, origin: str) -> ValidationError:
    """Turn pydantic's report into one diagnostic a person can act on.

    Pydantic reports every failure; the first is almost always the cause and the rest
    are consequences, so lead with it and count the others.
    """
    problems = error.errors()
    first = problems[0]
    location = ".".join(str(part) for part in first["loc"]) or "(root)"
    message = first.get("msg", "invalid")
    remedies: list[str] = []

    if first["type"] == "extra_forbidden":
        field = str(first["loc"][-1])
        siblings = _siblings(raw, first["loc"])
        suggestion = did_you_mean(field, siblings)
        message = f"unknown field {field!r}"
        if suggestion:
            remedies.append(suggestion)
        remedies.append("unknown fields are refused so a typo cannot silently do nothing")
    elif first["type"] == "missing":
        message = f"missing required field {str(first['loc'][-1])!r}"

    if len(problems) > 1:
        remedies.append(f"({len(problems) - 1} more problem(s) after this one)")

    return ValidationError(message, where=f"{origin}: {location}", remedies=remedies)


def _siblings(raw: Any, location: tuple[Any, ...]) -> list[str]:
    """The keys available where the bad key was, for a suggestion."""
    node = raw
    for part in location[:-1]:
        if (
            isinstance(node, dict)
            and part in node
            or isinstance(node, list)
            and isinstance(part, int)
            and part < len(node)
        ):
            node = node[part]
        else:
            return []
    known = _known_fields(location)
    if known:
        return known
    return [str(key) for key in node] if isinstance(node, dict) else []


def _known_fields(location: tuple[Any, ...]) -> list[str]:
    """Field names of the model at ``location``, when we can identify it."""
    from sclpl.run.ir import Port, Step
    from sclpl.run.ir import WorkflowDoc as Doc

    if not location:
        return list(Doc.model_fields)
    head = str(location[0])
    if head == "steps":
        return list(Step.model_fields)
    if head in ("inputs", "outputs"):
        return list(Port.model_fields)
    if len(location) == 1:
        return list(Doc.model_fields)
    return []


def _json_remedies(error: json.JSONDecodeError, source: str) -> list[str]:
    """Guess at the usual JSON mistakes, from the message and the offending line."""
    remedies: list[str] = []
    lines = source.splitlines()
    if 0 < error.lineno <= len(lines):
        line = lines[error.lineno - 1]
        remedies.append(f"line {error.lineno}: {line.strip()[:60]}")
    if "Expecting ',' delimiter" in error.msg:
        remedies.append("a comma is probably missing at the end of the previous line")
    elif "Expecting property name" in error.msg:
        remedies.append("there may be a trailing comma before this closing brace")
    elif "Expecting value" in error.msg:
        remedies.append("check for a trailing comma, or an unquoted string")
    remedies.append("JSON has no comments and no trailing commas; SCLPLL has both")
    return remedies
