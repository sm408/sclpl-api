"""Arithmetic.

This family is the clearest demonstration of invariant 2. In the engine this replaces,
every value was stringified between steps, so `@a.count + 1` concatenated two strings
and produced `"51"` where the author meant `51`. Here the value arrives as an `int` and
`add` is integer addition.

`add` is also the string and list concatenation operator, dispatched on the first
argument's type -- which is exactly what the dispatch table is for.
"""

from __future__ import annotations

from typing import Any

from sclpl.expr.dispatch import generic, overload
from sclpl.run.errors import TypeDispatchError

_NUMERIC = (int, float)


@overload("add", int, summary="Adds numbers, joins strings, or concatenates lists.")
@overload("add", float)
def add_number(left: float, right: Any) -> Any:
    """Adds numbers, joins strings, or concatenates lists."""
    if isinstance(right, bool) or not isinstance(right, _NUMERIC):
        raise _mismatch("add", left, right)
    return left + right


@overload("add", str)
def add_str(left: str, right: Any) -> str:
    """Joins two strings."""
    if not isinstance(right, str):
        raise _mismatch("add", left, right, hint="use text(...) to make it a string")
    return left + right


@overload("add", list)
def add_list(left: list[Any], right: Any) -> list[Any]:
    """Concatenates two lists."""
    if not isinstance(right, (list, tuple)):
        return [*left, right]
    return [*left, *right]


@overload("add", dict)
def add_dict(left: dict[Any, Any], right: Any) -> dict[Any, Any]:
    """Merges two objects; the right side wins on a shared key."""
    if not isinstance(right, dict):
        raise _mismatch("add", left, right)
    return {**left, **right}


@overload("sub", int, summary="Subtracts the right side from the left.")
@overload("sub", float)
def sub(left: float, right: Any) -> Any:
    """Subtracts the right side from the left."""
    _require_number("sub", left, right)
    return left - right


@overload("sub", list)
def sub_list(left: list[Any], right: Any) -> list[Any]:
    """Removes every element of the right list from the left."""
    removed = (
        set(_hashable(item) for item in right)
        if isinstance(right, (list, tuple))
        else {_hashable(right)}
    )
    return [item for item in left if _hashable(item) not in removed]


@overload("mul", int, summary="Multiplies two numbers, or repeats a sequence.")
@overload("mul", float)
def mul(left: float, right: Any) -> Any:
    """Multiplies two numbers, or repeats a sequence."""
    if isinstance(right, (str, list)):
        repeated: Any = right * int(left)
        return repeated
    _require_number("mul", left, right)
    return left * right


@overload("div", int, summary="Divides; division by zero is an error, not infinity.")
@overload("div", float)
def div(left: float, right: Any) -> float:
    """Divides; division by zero is an error, not infinity."""
    _require_number("div", left, right)
    if right == 0:
        raise TypeDispatchError(
            "division by zero",
            remedies=["guard it: @b != 0 and @a / @b", "or use div_safe(@a, @b, 0)"],
        )
    quotient: float = left / right
    return quotient


@generic("div_safe", summary="Divides, returning a fallback instead of failing on zero.")
def div_safe(left: Any, right: Any, fallback: Any = None) -> Any:
    """Divides, returning a fallback instead of failing on zero."""
    if not isinstance(left, _NUMERIC) or not isinstance(right, _NUMERIC) or right == 0:
        return fallback
    return left / right


@overload("floordiv", int, summary="Divides and rounds down to a whole number.")
@overload("floordiv", float)
def floordiv(left: float, right: Any) -> Any:
    """Divides and rounds down to a whole number."""
    _require_number("floordiv", left, right)
    if right == 0:
        raise TypeDispatchError("division by zero")
    return left // right


@overload("mod", int, summary="The remainder after division.")
@overload("mod", float)
def mod(left: float, right: Any) -> Any:
    """The remainder after division."""
    _require_number("mod", left, right)
    if right == 0:
        raise TypeDispatchError("division by zero")
    return left % right


@overload("pow", int, summary="Raises the left side to the power of the right.")
@overload("pow", float)
def power(left: float, right: Any) -> Any:
    """Raises the left side to the power of the right."""
    _require_number("pow", left, right)
    return left**right


@overload("neg", int, summary="Negates a number.")
@overload("neg", float)
def neg(value: float) -> float:
    """Negates a number."""
    return -value


@generic("abs", summary="The magnitude of a number, ignoring its sign.")
def absolute(value: Any) -> Any:
    """The magnitude of a number, ignoring its sign."""
    if not isinstance(value, _NUMERIC) or isinstance(value, bool):
        raise _not_a_number("abs", value)
    return abs(value)


@generic("round", summary="Rounds to the given number of decimal places.")
def round_to(value: Any, places: int = 0) -> Any:
    """Rounds to the given number of decimal places."""
    if not isinstance(value, _NUMERIC) or isinstance(value, bool):
        raise _not_a_number("round", value)
    result = round(value, places)
    return int(result) if places <= 0 else result


@generic("floor", summary="Rounds down to a whole number.")
def floor(value: Any) -> int:
    """Rounds down to a whole number."""
    import math

    if not isinstance(value, _NUMERIC) or isinstance(value, bool):
        raise _not_a_number("floor", value)
    return math.floor(value)


@generic("ceil", summary="Rounds up to a whole number.")
def ceil(value: Any) -> int:
    """Rounds up to a whole number."""
    import math

    if not isinstance(value, _NUMERIC) or isinstance(value, bool):
        raise _not_a_number("ceil", value)
    return math.ceil(value)


@generic("clamp", summary="Constrains a number to a range.")
def clamp(value: Any, low: Any, high: Any) -> Any:
    """Constrains a number to a range."""
    if not isinstance(value, _NUMERIC) or isinstance(value, bool):
        raise _not_a_number("clamp", value)
    return max(low, min(high, value))


def _require_number(name: str, left: Any, right: Any) -> None:
    if isinstance(right, bool) or not isinstance(right, _NUMERIC):
        raise _mismatch(name, left, right)


def _mismatch(name: str, left: Any, right: Any, *, hint: str | None = None) -> TypeDispatchError:
    remedies = [hint] if hint else []
    remedies.append("cast it: number(@x) or text(@x)")
    return TypeDispatchError(
        f"{name}() cannot combine {type(left).__name__} with {type(right).__name__}",
        remedies=remedies,
    )


def _not_a_number(name: str, value: Any) -> TypeDispatchError:
    return TypeDispatchError(
        f"{name}() needs a number, not {type(value).__name__}",
        remedies=["cast it: number(@x)"],
    )


def _hashable(value: Any) -> Any:
    """A stand-in key for values that cannot go in a set."""
    try:
        hash(value)
    except TypeError:
        return repr(value)
    return value
