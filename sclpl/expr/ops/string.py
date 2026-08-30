"""String operators."""

from __future__ import annotations

import re
from typing import Any

from sclpl.expr.dispatch import generic, overload
from sclpl.run.errors import TypeDispatchError

#: Compiled patterns are cached: a `matches` inside a filter runs once per element, and
#: recompiling the same pattern a thousand times is pure waste.
_PATTERNS: dict[str, re.Pattern[str]] = {}
_PATTERN_CACHE_MAX = 256


def _pattern(source: str) -> re.Pattern[str]:
    compiled = _PATTERNS.get(source)
    if compiled is None:
        try:
            compiled = re.compile(source)
        except re.error as error:
            raise TypeDispatchError(
                f"invalid regular expression {source!r}: {error}",
                remedies=["escape special characters, or use contains() for plain text"],
            ) from error
        if len(_PATTERNS) >= _PATTERN_CACHE_MAX:
            _PATTERNS.clear()
        _PATTERNS[source] = compiled
    return compiled


@overload("lower", str, summary="Lowercases a string.")
def lower(value: str) -> str:
    """Lowercases a string."""
    return value.lower()


@overload("upper", str, summary="Uppercases a string.")
def upper(value: str) -> str:
    """Uppercases a string."""
    return value.upper()


@overload("trim", str, summary="Removes leading and trailing whitespace.")
def trim(value: str, chars: str | None = None) -> str:
    """Removes leading and trailing whitespace."""
    return value.strip(chars)


@overload("split", str, summary="Splits a string into a list.")
def split(value: str, separator: str = ",", limit: int = -1) -> list[str]:
    """Splits a string into a list."""
    return value.split(separator, limit)


@overload("replace", str, summary="Replaces every occurrence of one substring.")
def replace(value: str, old: str, new: str, count: int = -1) -> str:
    """Replaces every occurrence of one substring."""
    return value.replace(old, new, count)


@overload("starts_with", str, summary="True when the string begins with a prefix.")
def starts_with(value: str, prefix: str) -> bool:
    """True when the string begins with a prefix."""
    return value.startswith(prefix)


@overload("ends_with", str, summary="True when the string ends with a suffix.")
def ends_with(value: str, suffix: str) -> bool:
    """True when the string ends with a suffix."""
    return value.endswith(suffix)


@overload("matches", str, summary="True when a regular expression matches anywhere.")
def matches(value: str, pattern: str) -> bool:
    """True when a regular expression matches anywhere."""
    return _pattern(pattern).search(value) is not None


@overload("extract", str, summary="The first regex match, or a capture group.")
def extract(value: str, pattern: str, group: int = 0) -> str | None:
    """The first regex match, or a capture group."""
    found = _pattern(pattern).search(value)
    if found is None:
        return None
    try:
        return found.group(group)
    except (IndexError, re.error) as error:
        raise TypeDispatchError(f"the pattern has no capture group {group}") from error


@overload("extract_all", str, summary="Every regex match in the string.")
def extract_all(value: str, pattern: str) -> list[Any]:
    """Every regex match in the string."""
    return _pattern(pattern).findall(value)


@overload("pad_left", str, summary="Pads a string on the left to a given width.")
def pad_left(value: str, width: int, fill: str = " ") -> str:
    """Pads a string on the left to a given width."""
    return value.rjust(width, fill)


@overload("pad_right", str, summary="Pads a string on the right to a given width.")
def pad_right(value: str, width: int, fill: str = " ") -> str:
    """Pads a string on the right to a given width."""
    return value.ljust(width, fill)


@overload("slug", str, summary="A lowercase, dash-separated form safe for filenames.")
def slug(value: str) -> str:
    """A lowercase, dash-separated form safe for filenames."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return cleaned.strip("-")


def join_text(values: Any, separator: str = ",") -> str:
    """Joins a list into a string with a separator.

    Not registered here. `join` is one name over two shapes -- a list into a string,
    and two tables on a key -- and the first argument is a list either way, so the
    dispatch table cannot tell them apart. The built-in catalogue owns the name and
    calls this for the string shape.
    """
    from sclpl.expr.eval import stringify

    if isinstance(values, str):
        return values
    if not isinstance(values, (list, tuple, set)):
        raise TypeDispatchError(f"join() needs a list, not {type(values).__name__}")
    return separator.join(stringify(item) for item in values)


@generic("text", summary="Converts any value to its string form.")
def text(value: Any) -> str:
    """Converts any value to its string form."""
    from sclpl.expr.eval import stringify

    return stringify(value)


@generic("format", summary="Fills {} placeholders in a template, positionally.")
def format_string(template: Any, *args: Any) -> str:
    """Fills {} placeholders in a template, positionally."""
    from sclpl.expr.eval import stringify

    if not isinstance(template, str):
        raise TypeDispatchError("format() needs a string template")
    out = template
    for value in args:
        out = out.replace("{}", stringify(value), 1)
    return out


@generic("url_encode", summary="Percent-encodes a value for use in a URL.")
def url_encode(value: Any) -> str:
    """Percent-encodes a value for use in a URL."""
    from urllib.parse import quote

    from sclpl.expr.eval import stringify

    return quote(stringify(value), safe="")


@generic("json_parse", summary="Parses a JSON string into a value.")
def json_parse(value: Any) -> Any:
    """Parses a JSON string into a value."""
    import json

    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", "replace")
    if not isinstance(value, str):
        raise TypeDispatchError(f"json_parse() needs a string, not {type(value).__name__}")
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        raise TypeDispatchError(
            f"not valid JSON: {error.msg} at position {error.pos}",
            remedies=["check the response really is JSON -- print it with -vvv"],
        ) from error


@generic("json_encode", summary="Renders a value as a JSON string.")
def json_encode(value: Any, indent: int | None = None) -> str:
    """Renders a value as a JSON string."""
    import json

    separators = None if indent else (",", ":")
    return json.dumps(value, indent=indent, separators=separators, default=str)
