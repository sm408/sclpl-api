"""Casts and temporal operators.

Casts are explicit because implicit coercion is how the old engine ended up comparing
`"50"` to `50`. `number("12")` says what it means; `"12" > 5` does not, and raises.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sclpl.errors import TypeDispatchError
from sclpl.expr.dispatch import generic

#: Tried in order. ISO 8601 first, since that is what an API returns.
_FORMATS: tuple[str, ...] = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%b-%Y",
    "%Y%m%d",
)


#: Distinguishes "no fallback given" from a fallback of None, which is a legitimate
#: thing to want back from a failed cast.
_MISSING: Any = object()


@generic("number", summary="Converts a value to a number.")
def to_number(value: Any, fallback: Any = _MISSING) -> Any:
    """Converts a value to a number."""
    match value:
        case bool():
            return 1 if value else 0
        case int() | float():
            return value
        case str():
            cleaned = value.strip().replace(",", "").replace("_", "")
            if cleaned.endswith("%"):
                try:
                    return float(cleaned[:-1]) / 100
                except ValueError:
                    pass
            cleaned = cleaned.lstrip("$£€")
            try:
                return int(cleaned)
            except ValueError:
                pass
            try:
                return float(cleaned)
            except ValueError:
                pass
        case None:
            pass
    if fallback is not _MISSING:
        return fallback
    raise TypeDispatchError(
        f"cannot read {value!r} as a number",
        remedies=["supply a fallback: number(@x, 0)"],
    )


@generic("int", summary="Converts a value to a whole number.")
def to_int(value: Any, fallback: Any = _MISSING) -> Any:
    """Converts a value to a whole number."""
    result = to_number(value, fallback)
    if isinstance(result, float):
        return int(result)
    return result


@generic("bool", summary="Converts a value to true or false.")
def to_bool(value: Any) -> bool:
    """Converts a value to true or false."""
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "yes", "y", "1", "on"):
            return True
        if lowered in ("false", "no", "n", "0", "off", ""):
            return False
    from sclpl.expr.eval import _truthy

    return _truthy(value)


@generic("list", summary="Wraps a value in a list, or leaves a list alone.")
def to_list(value: Any) -> list[Any]:
    """Wraps a value in a list, or leaves a list alone."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set, frozenset)):
        return list(value)
    if isinstance(value, dict):
        return [value]
    records = getattr(value, "to_records", None)
    if callable(records):
        return list(records())
    return [value]


@generic("date", summary="Parses a value as a date and time.")
def to_date(value: Any, format: str | None = None) -> datetime:
    """Parses a value as a date and time."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # Distinguish seconds from milliseconds: anything past year 5138 is millis.
        seconds = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(seconds, tz=UTC)
    if not isinstance(value, str):
        raise TypeDispatchError(f"cannot read {type(value).__name__} as a date")

    text = value.strip()
    if format is not None:
        try:
            return datetime.strptime(text, format)
        except ValueError as error:
            raise TypeDispatchError(f"{text!r} does not match the format {format!r}") from error

    normalised = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        return datetime.fromisoformat(normalised)
    except ValueError:
        pass
    for candidate in _FORMATS:
        try:
            return datetime.strptime(text, candidate)
        except ValueError:
            continue
    raise TypeDispatchError(
        f"cannot read {text!r} as a date",
        remedies=["supply the layout: date(@x, '%d/%m/%Y')"],
    )


@generic("date_format", summary="Renders a date using a format string.")
def date_format(value: Any, format: str = "%Y-%m-%d") -> str:
    """Renders a date using a format string."""
    return to_date(value).strftime(format)


@generic("date_add", summary="Shifts a date by a number of days, hours, or minutes.")
def date_add(value: Any, days: float = 0, hours: float = 0, minutes: float = 0) -> datetime:
    """Shifts a date by a number of days, hours, or minutes."""
    return to_date(value) + timedelta(days=days, hours=hours, minutes=minutes)


@generic("date_diff", summary="The gap between two dates, in days by default.")
def date_diff(left: Any, right: Any, unit: str = "days") -> float:
    """The gap between two dates, in days by default."""
    delta = to_date(left) - to_date(right)
    seconds = delta.total_seconds()
    divisors = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400, "weeks": 604800}
    if unit not in divisors:
        raise TypeDispatchError(
            f"unknown unit {unit!r}",
            remedies=[f"use one of: {', '.join(divisors)}"],
        )
    return seconds / divisors[unit]


@generic("now", summary="The current UTC time.")
def now() -> datetime:
    """The current UTC time."""
    return datetime.now(tz=UTC)


@generic("today", summary="Midnight UTC today.")
def today() -> datetime:
    """Midnight UTC today."""
    moment = datetime.now(tz=UTC)
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


@generic("timestamp", summary="A date as seconds since the epoch.")
def timestamp(value: Any) -> float:
    """A date as seconds since the epoch."""
    return to_date(value).timestamp()


@generic("type_of", summary="The name of a value's type.")
def type_of(value: Any) -> str:
    """The name of a value's type."""
    match value:
        case None:
            return "null"
        case bool():
            return "boolean"
        case int() | float():
            return "number"
        case str():
            return "string"
        case list() | tuple():
            return "list"
        case dict():
            return "object"
        case _:
            return type(value).__name__
