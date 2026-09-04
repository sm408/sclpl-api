"""Text utilities as a bundled plugin, using only the public API."""

from __future__ import annotations

import re
from string import Formatter
from typing import Any

from sclpl.ext.api import ValidationError, connector, records_of


def register() -> None:
    """Called once at load. The decorators below have already run on import."""


@connector("text.slug")
def slug(value: Any, *, lower: bool = True) -> str:
    """Turn text into a URL- and filename-friendly slug."""
    text = str(value).strip()
    if lower:
        text = text.lower()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text)
    return text.strip("-")


@connector("text.split")
def split(value: Any, *, sep: str = ",", strip: bool = True) -> list[str]:
    """Split text into parts."""
    parts = str(value).split(sep)
    return [part.strip() for part in parts] if strip else parts


@connector("text.join")
def join(values: Any, *, sep: str = ", ") -> str:
    """Join values into text."""
    if isinstance(values, (list, tuple, set)):
        return sep.join(str(value) for value in values)
    return str(values)


@connector("text.template")
def template(pattern: str, data: Any) -> Any:
    """Format one record, or each record, with `{field}` placeholders."""
    rows = records_of(data)
    if rows:
        return [_format(pattern, row) for row in rows]
    if isinstance(data, dict):
        return _format(pattern, data)
    raise ValidationError(
        "text.template needs an object or records",
        remedies=["pass a dict, a list of dicts, or a Table"],
    )


@connector("text.extract")
def extract(
    data: Any,
    field: str,
    pattern: str,
    *,
    group: int | str = 1,
    into: str | None = None,
) -> Any:
    """Extract a regex group from text or from a field in each record."""
    regex = re.compile(pattern)
    if isinstance(data, str):
        match = regex.search(data)
        return match.group(group) if match else None

    target = into or field
    out: list[dict[str, Any]] = []
    for row in records_of(data):
        copied = dict(row)
        match = regex.search(str(row.get(field, "")))
        copied[target] = match.group(group) if match else None
        out.append(copied)
    return out


def _format(pattern: str, row: dict[str, Any]) -> str:
    missing = [name for _, name, _, _ in Formatter().parse(pattern) if name and name not in row]
    if missing:
        raise ValidationError(
            f"text.template has no field {missing[0]!r}",
            remedies=[f"available: {', '.join(row) or 'none'}"],
        )
    return pattern.format_map(row)
