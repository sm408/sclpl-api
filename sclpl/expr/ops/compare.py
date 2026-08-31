"""Comparison and logic operators.

Comparison is generic: `eq` on two values of any type is meaningful, and refusing to
compare an int with a float would be pedantry rather than safety. Ordering is stricter
-- comparing a string to a number is almost always a mistake in a workflow, and the
error naming both types is more useful than a silent False.
"""

from __future__ import annotations

from typing import Any

from sclpl.errors import TypeDispatchError
from sclpl.expr.dispatch import generic

_NUMERIC = (int, float)


@generic("eq", summary="True when both sides are equal.")
def eq(left: Any, right: Any) -> bool:
    """True when both sides are equal."""
    return bool(_coerced(left) == _coerced(right))


@generic("ne", summary="True when the two sides differ.")
def ne(left: Any, right: Any) -> bool:
    """True when the two sides differ."""
    return not eq(left, right)


@generic("lt", summary="True when the left side is smaller.")
def lt(left: Any, right: Any) -> bool:
    """True when the left side is smaller."""
    first, second = _ordered(left, right, "<")
    return bool(first < second)


@generic("le", summary="True when the left side is smaller or equal.")
def le(left: Any, right: Any) -> bool:
    """True when the left side is smaller or equal."""
    first, second = _ordered(left, right, "<=")
    return bool(first <= second)


@generic("gt", summary="True when the left side is larger.")
def gt(left: Any, right: Any) -> bool:
    """True when the left side is larger."""
    first, second = _ordered(left, right, ">")
    return bool(first > second)


@generic("ge", summary="True when the left side is larger or equal.")
def ge(left: Any, right: Any) -> bool:
    """True when the left side is larger or equal."""
    first, second = _ordered(left, right, ">=")
    return bool(first >= second)


@generic("is_null", summary="True when the value is null.")
def is_null(value: Any) -> bool:
    """True when the value is null."""
    return value is None


@generic("is_empty", summary="True when the value is null, empty, or blank.")
def is_empty(value: Any) -> bool:
    """True when the value is null, empty, or blank."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return not value
    rows = getattr(value, "row_count", None)
    if isinstance(rows, int):
        return rows == 0
    return False


@generic("coalesce", summary="The first argument that is not null.")
def coalesce(*values: Any) -> Any:
    """The first argument that is not null."""
    for value in values:
        if value is not None:
            return value
    return None


@generic("default", summary="The value, or a fallback when it is null or empty.")
def default(value: Any, fallback: Any) -> Any:
    """The value, or a fallback when it is null or empty."""
    return fallback if is_empty(value) else value


def _coerced(value: Any) -> Any:
    """Make equality behave the way a workflow author expects.

    A bool is not silently a number here: `true == 1` being True has surprised more
    people than it has helped.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    return value


def _ordered(left: Any, right: Any, symbol: str) -> tuple[Any, Any]:
    """Check that two values can be ordered, and return them ready to compare."""
    if isinstance(left, bool) or isinstance(right, bool):
        raise TypeDispatchError(
            f"cannot order booleans with '{symbol}'",
            remedies=["compare with == or != instead"],
        )
    if isinstance(left, _NUMERIC) and isinstance(right, _NUMERIC):
        return left, right
    if isinstance(left, str) and isinstance(right, str):
        return left, right
    if type(left) is type(right):
        try:
            left < right  # noqa: B015 - probing whether the type is orderable at all
        except TypeError as error:
            raise TypeDispatchError(
                f"{type(left).__name__} values cannot be ordered with '{symbol}'"
            ) from error
        return left, right
    if left is None or right is None:
        raise TypeDispatchError(
            f"cannot compare null with '{symbol}'",
            remedies=[
                "guard it first: is_null(@x) or @x > 10",
                "supply a fallback: default(@x, 0) > 10",
            ],
        )
    raise TypeDispatchError(
        f"cannot compare {type(left).__name__} with {type(right).__name__} using '{symbol}'",
        remedies=[
            f"cast one side: number(@x) {symbol} 10",
            "check the step produced the type you expect",
        ],
    )
