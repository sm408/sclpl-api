"""Collection and aggregate operators.

These are the ones a filter or a summary line reaches for. They work on lists and
objects here; M5 registers the same names over `Table`, and because dispatch is on the
runtime type, `count(@x)` keeps working when `@x` becomes a dataframe.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from sclpl.errors import TypeDispatchError
from sclpl.expr.dispatch import generic, overload

_NUMERIC = (int, float)


@generic("count", summary="How many elements a collection holds.")
def count(value: Any) -> int:
    """How many elements a collection holds."""
    if value is None:
        return 0
    rows = getattr(value, "row_count", None)
    if isinstance(rows, int):
        return rows
    if isinstance(value, (list, tuple, dict, set, str)):
        return len(value)
    raise TypeDispatchError(f"count() needs a collection, not {type(value).__name__}")


@generic("contains", summary="True when a collection holds a value.")
def contains(container: Any, item: Any) -> bool:
    """True when a collection holds a value."""
    if container is None:
        return False
    if isinstance(container, str):
        from sclpl.expr.eval import stringify

        return stringify(item) in container
    if isinstance(container, dict):
        return item in container
    if isinstance(container, (list, tuple, set, frozenset)):
        return item in container
    try:
        return bool(item in container)
    except TypeError as error:
        raise TypeDispatchError(f"cannot test membership in {type(container).__name__}") from error


@generic("contains_by", summary="True when the left side is inside the right.")
def contains_by(item: Any, container: Any) -> bool:
    """True when the left side is inside the right."""
    return contains(container, item)


@overload("first", list, summary="The first element, or null when empty.")
def first(values: list[Any], fallback: Any = None) -> Any:
    """The first element, or null when empty."""
    return values[0] if values else fallback


@overload("last", list, summary="The last element, or null when empty.")
def last(values: list[Any], fallback: Any = None) -> Any:
    """The last element, or null when empty."""
    return values[-1] if values else fallback


@overload("take", list, summary="The first n elements.")
def take(values: list[Any], n: int) -> list[Any]:
    """The first n elements."""
    return values[:n]


@overload("drop", list, summary="Everything after the first n elements.")
def drop(values: list[Any], n: int) -> list[Any]:
    """Everything after the first n elements."""
    return values[n:]


@overload("reverse", list, summary="The elements in reverse order.")
def reverse(values: list[Any]) -> list[Any]:
    """The elements in reverse order."""
    return list(reversed(values))


def flatten_lists(values: list[Any], depth: int = 1) -> list[Any]:
    """Collapses nested lists into one.

    Not registered here. `flatten` also means "nested objects into underscore columns",
    and both shapes arrive as a list, so the catalogue owns the name and picks by what
    the list holds.
    """
    if depth <= 0:
        return list(values)
    out: list[Any] = []
    for item in values:
        if isinstance(item, (list, tuple)):
            out.extend(flatten_lists(list(item), depth - 1))
        else:
            out.append(item)
    return out


@overload("unique", list, summary="The distinct elements, in first-seen order.")
def unique(values: list[Any], by: str | None = None) -> list[Any]:
    """The distinct elements, in first-seen order."""
    seen: set[Any] = set()
    out: list[Any] = []
    for item in values:
        key = _key_of(item, by)
        marker = _hashable(key)
        if marker not in seen:
            seen.add(marker)
            out.append(item)
    return out


@overload("sort", list, summary="The elements sorted, optionally by a field.")
def sort(values: list[Any], by: str | None = None, descending: bool = False) -> list[Any]:
    """The elements sorted, optionally by a field."""
    try:
        return sorted(values, key=lambda item: _sort_key(item, by), reverse=descending)
    except TypeError as error:
        raise TypeDispatchError(
            "cannot sort a list of mixed types",
            remedies=["sort by a field: sort(@xs, by='name')"],
        ) from error


@overload("pluck", list, summary="One field from every element.")
def pluck(values: list[Any], field: str) -> list[Any]:
    """One field from every element."""
    from sclpl.expr.path import get_attr

    return [get_attr(item, field) for item in values]


@overload("group_by", list, summary="Groups elements into an object keyed by a field.")
def group_by(values: list[Any], field: str) -> dict[Any, list[Any]]:
    """Groups elements into an object keyed by a field."""
    groups: dict[Any, list[Any]] = {}
    for item in values:
        key = _hashable(_key_of(item, field))
        groups.setdefault(key, []).append(item)
    return groups


@overload("chunk", list, summary="Splits a list into batches of a given size.")
def chunk(values: list[Any], size: int) -> list[list[Any]]:
    """Splits a list into batches of a given size."""
    if size <= 0:
        raise TypeDispatchError("chunk() needs a size of at least 1")
    return [values[index : index + size] for index in range(0, len(values), size)]


@overload("zip", list, summary="Pairs elements of two lists positionally.")
def zip_lists(left: list[Any], right: Any) -> list[list[Any]]:
    """Pairs elements of two lists positionally."""
    if not isinstance(right, (list, tuple)):
        raise TypeDispatchError("zip() needs two lists")
    return [[a, b] for a, b in zip(left, right, strict=False)]


@overload("keys", dict, summary="The field names of an object.")
def keys(value: dict[Any, Any]) -> list[Any]:
    """The field names of an object."""
    return list(value)


@overload("values", dict, summary="The values of an object.")
def values_of(value: dict[Any, Any]) -> list[Any]:
    """The values of an object."""
    return list(value.values())


@overload("entries", dict, summary="An object as a list of key/value pairs.")
def entries(value: dict[Any, Any]) -> list[list[Any]]:
    """An object as a list of key/value pairs."""
    return [[key, item] for key, item in value.items()]


@overload("pick", dict, summary="An object with only the named fields.")
def pick(value: dict[Any, Any], *fields: str) -> dict[Any, Any]:
    """An object with only the named fields."""
    wanted = _flatten_names(fields)
    return {key: value[key] for key in wanted if key in value}


@overload("omit", dict, summary="An object without the named fields.")
def omit(value: dict[Any, Any], *fields: str) -> dict[Any, Any]:
    """An object without the named fields."""
    unwanted = set(_flatten_names(fields))
    return {key: item for key, item in value.items() if key not in unwanted}


def merge_objects(first_value: dict[Any, Any], *rest: Any) -> dict[Any, Any]:
    """Merges objects; later ones win.

    Not registered here; the catalogue's `merge` covers objects and record sets alike.
    """
    out = dict(first_value)
    for item in rest:
        if not isinstance(item, dict):
            raise TypeDispatchError("merge() needs objects")
        out.update(item)
    return out


# -- aggregates ------------------------------------------------------------------


@generic("sum", summary="The total of a list of numbers.")
def total(values: Any, by: str | None = None) -> float:
    """The total of a list of numbers."""
    numbers = _numbers("sum", values, by)
    return sum(numbers)


@generic("avg", summary="The mean of a list of numbers.")
def average(values: Any, by: str | None = None) -> float | None:
    """The mean of a list of numbers."""
    numbers = _numbers("avg", values, by)
    return sum(numbers) / len(numbers) if numbers else None


@generic("min", summary="The smallest value.")
def minimum(values: Any, by: str | None = None) -> Any:
    """The smallest value."""
    return _extreme("min", values, by, min)


@generic("max", summary="The largest value.")
def maximum(values: Any, by: str | None = None) -> Any:
    """The largest value."""
    return _extreme("max", values, by, max)


@generic("median", summary="The middle value of a list of numbers.")
def median(values: Any, by: str | None = None) -> float | None:
    """The middle value of a list of numbers."""
    numbers = sorted(_numbers("median", values, by))
    if not numbers:
        return None
    middle = len(numbers) // 2
    if len(numbers) % 2:
        return numbers[middle]
    return (numbers[middle - 1] + numbers[middle]) / 2


@generic("any", summary="True when any element is truthy.")
def any_of(values: Any) -> bool:
    """True when any element is truthy."""
    from sclpl.expr.eval import _truthy

    return any(_truthy(item) for item in _sequence("any", values))


@generic("all", summary="True when every element is truthy.")
def all_of(values: Any) -> bool:
    """True when every element is truthy."""
    from sclpl.expr.eval import _truthy

    return all(_truthy(item) for item in _sequence("all", values))


# -- helpers ---------------------------------------------------------------------


def _sequence(name: str, values: Any) -> list[Any]:
    if values is None:
        return []
    if isinstance(values, (list, tuple, set)):
        return list(values)
    if isinstance(values, dict):
        return list(values.values())
    records = getattr(values, "to_records", None)
    if callable(records):
        result = records()
        if isinstance(result, Iterable):
            return list(result)
    raise TypeDispatchError(f"{name}() needs a collection, not {type(values).__name__}")


def _numbers(name: str, values: Any, by: str | None) -> list[float]:
    out: list[float] = []
    for item in _sequence(name, values):
        candidate = _key_of(item, by)
        if candidate is None:
            continue
        if isinstance(candidate, bool) or not isinstance(candidate, _NUMERIC):
            raise TypeDispatchError(
                f"{name}() found {type(candidate).__name__} where it needed a number",
                remedies=[
                    "select a numeric field: sum(@rows, by='total')",
                    "cast first: sum(pluck(@rows, 'total') | map(number))",
                ],
            )
        out.append(candidate)
    return out


def _extreme(name: str, values: Any, by: str | None, chooser: Callable[..., Any]) -> Any:
    items = _sequence(name, values)
    if not items:
        return None
    if by is None:
        return chooser(items)
    return chooser(items, key=lambda item: _key_of(item, by))


def _key_of(item: Any, field: str | None) -> Any:
    if field is None:
        return item
    from sclpl.expr.path import get_attr

    return get_attr(item, field)


def _sort_key(item: Any, field: str | None) -> Any:
    value = _key_of(item, field)
    # None sorts first rather than raising, which is what a partly-filled column needs.
    return (value is not None, value) if value is not None else (False, "")


def _hashable(value: Any) -> Any:
    try:
        hash(value)
    except TypeError:
        return repr(value)
    return value


def _flatten_names(fields: tuple[Any, ...]) -> list[str]:
    """Accept both `pick(o, 'a', 'b')` and `pick(o, ['a', 'b'])`."""
    if len(fields) == 1 and isinstance(fields[0], (list, tuple)):
        return [str(name) for name in fields[0]]
    return [str(name) for name in fields]
