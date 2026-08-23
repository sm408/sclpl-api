"""Path resolution into a value.

The critical rule: **a missing path is an error**. The engine this replaces returned the
literal text `{{orders.id}}` when it could not resolve, which then went out in a URL,
and the request that arrived at the remote was one nobody meant to send. So every
failure here raises, and every failure carries three things: the path, the value that
was actually present, and the nearest valid key.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from sclpl.run.errors import PathError, nearest

#: Beyond this, listing the available keys stops being help and starts being noise.
MAX_KEYS_SHOWN = 8


def get_attr(obj: Any, name: str, *, path: str = "") -> Any:
    """Read field ``name`` from ``obj``.

    Mappings are read by key, objects by attribute, and a list of mappings maps the
    read over its elements -- so `@users.email` works without an explicit `[*]`, which
    is what people write and expect.
    """
    if isinstance(obj, dict):
        if name in obj:
            return obj[name]
        raise _missing_key(obj, name, path)

    if isinstance(obj, (list, tuple)):
        if all(isinstance(item, dict) for item in obj):
            return [get_attr(item, name, path=path) for item in obj]
        raise PathError(
            f"cannot read {name!r} from a list of {_type_name(obj[0]) if obj else 'nothing'}",
            where=path or name,
            remedies=[
                f"index it first: [0].{name}",
                f"project over it: [*].{name}",
            ],
        )

    if obj is None:
        raise PathError(
            f"cannot read {name!r}: the value is null",
            where=path or name,
            remedies=["check the step that produced it returned what you expect"],
        )

    if hasattr(obj, name):
        return getattr(obj, name)

    columns = getattr(obj, "columns", None)
    if columns is not None and name in list(columns):
        return obj[name]

    raise PathError(
        f"cannot read {name!r} from {_type_name(obj)}",
        where=path or name,
        remedies=_suggest(name, _available(obj)),
    )


def get_index(obj: Any, index: Any, *, path: str = "") -> Any:
    """Read ``obj[index]``, whether that is a list position or a mapping key."""
    if isinstance(obj, dict):
        if index in obj:
            return obj[index]
        raise _missing_key(obj, index, path)

    if isinstance(obj, (list, tuple, str)):
        if not isinstance(index, int) or isinstance(index, bool):
            raise PathError(
                f"a list index must be a whole number, not {_type_name(index)}",
                where=path or str(index),
                remedies=["use [0] for the first element, or [*] for all of them"],
            )
        length = len(obj)
        if -length <= index < length:
            return obj[index]
        raise PathError(
            f"index {index} is out of range: there {'is' if length == 1 else 'are'} "
            f"{length} element{'' if length == 1 else 's'}",
            where=path or str(index),
            remedies=(
                ["the collection is empty -- check the step that produced it"]
                if length == 0
                else [f"valid indices are 0 to {length - 1}, or -1 for the last"]
            ),
        )

    if obj is None:
        raise PathError(
            f"cannot index into null with [{index!r}]",
            where=path or str(index),
            remedies=["check the step that produced it returned what you expect"],
        )

    try:
        return obj[index]
    except (KeyError, IndexError, TypeError) as error:
        raise PathError(
            f"cannot index {_type_name(obj)} with {index!r}",
            where=path or str(index),
            remedies=_suggest(str(index), _available(obj)),
        ) from error


def get_slice(obj: Any, start: int | None, stop: int | None, *, path: str = "") -> Any:
    if isinstance(obj, (list, tuple, str)):
        return obj[start:stop]
    head = getattr(obj, "head", None)
    if callable(head) and start in (None, 0) and stop is not None:
        return head(stop)
    raise PathError(
        f"cannot slice {_type_name(obj)}",
        where=path or "slice",
        remedies=["slicing works on lists, strings, and tables"],
    )


def project(obj: Any, *, path: str = "") -> list[Any]:
    """`[*]` -- every element, flattening one level of nesting.

    Flattening is what makes chained projections behave: `@a[*].tags[*]` gives one flat
    list of tags rather than a list of lists, which is what a filter downstream needs.
    """
    if isinstance(obj, (list, tuple)):
        out: list[Any] = []
        for item in obj:
            if isinstance(item, (list, tuple)):
                out.extend(item)
            else:
                out.append(item)
        return out
    if isinstance(obj, dict):
        return list(obj.values())
    rows = getattr(obj, "to_records", None)
    if callable(rows):
        result = rows()
        return list(result) if isinstance(result, Iterable) else [result]
    if obj is None:
        raise PathError(
            "cannot project [*] over null",
            where=path or "[*]",
            remedies=["check the step that produced it returned a collection"],
        )
    raise PathError(
        f"cannot project [*] over {_type_name(obj)}",
        where=path or "[*]",
        remedies=["[*] works on lists, objects, and tables"],
    )


def elements(obj: Any, *, path: str = "") -> Sequence[Any]:
    """The elements of ``obj`` for a filter to test, without flattening."""
    if isinstance(obj, (list, tuple)):
        return obj
    if isinstance(obj, dict):
        return list(obj.values())
    rows = getattr(obj, "to_records", None)
    if callable(rows):
        return list(rows())
    raise PathError(
        f"cannot filter {_type_name(obj)}",
        where=path or "[?(...)]",
        remedies=["a filter needs a list, an object, or a table"],
    )


def _missing_key(mapping: dict[Any, Any], key: Any, path: str) -> PathError:
    keys = [str(item) for item in mapping]
    return PathError(
        f"no field {key!r} in this object",
        where=path or str(key),
        remedies=_suggest(str(key), keys),
    )


def _suggest(name: str, available: list[str]) -> list[str]:
    """The three remedies a missing path always offers, when they apply."""
    if not available:
        return ["the value has no fields to read"]
    remedies: list[str] = []
    matches = nearest(name, available)
    if matches:
        if len(matches) == 1:
            remedies.append(f"did you mean {matches[0]!r}?")
        else:
            remedies.append("did you mean " + ", ".join(repr(match) for match in matches) + "?")
    shown = available[:MAX_KEYS_SHOWN]
    listing = ", ".join(repr(key) for key in shown)
    if len(available) > MAX_KEYS_SHOWN:
        listing += f", … ({len(available)} total)"
    remedies.append(f"available: {listing}")
    return remedies


def _available(obj: Any) -> list[str]:
    if isinstance(obj, dict):
        return [str(key) for key in obj]
    columns = getattr(obj, "columns", None)
    if columns is not None:
        return [str(column) for column in columns]
    if hasattr(obj, "__dict__"):
        return [name for name in vars(obj) if not name.startswith("_")]
    if hasattr(obj, "__slots__"):
        return [name for name in obj.__slots__ if not name.startswith("_")]
    return []


def _type_name(value: Any) -> str:
    """A name the user will recognise. `dict` is 'an object', not 'a dict'."""
    match value:
        case None:
            return "null"
        case bool():
            return "a boolean"
        case int() | float():
            return "a number"
        case str():
            return "a string"
        case dict():
            return "an object"
        case list() | tuple():
            return "a list"
        case _:
            return f"a {type(value).__name__}"
