"""The operator table.

One dict, keyed by `(name, type)`, resolved on the runtime type of the first argument
with an MRO walk-up. That is the whole mechanism: adding `filter` over a `Table` in M5
is a registration, not a change to the evaluator.

Registration:

    @overload("filter", list)
    def _(xs: list, where: Callable) -> list: ...

A missing overload is an error that names the type it was given and lists the types
that *are* registered, because "unsupported operand" tells the user nothing about what
to do next.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, TypeVar

from sclpl.run.errors import TypeDispatchError, did_you_mean

F = TypeVar("F", bound=Callable[..., Any])

#: (operator name, first-argument type) -> implementation.
TABLE: dict[tuple[str, type], Callable[..., Any]] = {}

#: Operators that accept any first argument. Checked after the typed table.
FALLBACK: dict[str, Callable[..., Any]] = {}

#: One-line summaries, for `docs/reference/expressions.md` and `--help`.
SUMMARY: dict[str, str] = {}


def overload(name: str, first: type, *, summary: str = "") -> Callable[[F], F]:
    """Register an implementation of ``name`` for a first argument of ``first``."""

    def register(function: F) -> F:
        key = (name, first)
        if key in TABLE:
            raise RuntimeError(f"duplicate overload for {name}/{first.__name__}")
        TABLE[key] = function
        if summary or name not in SUMMARY:
            SUMMARY[name] = summary or _first_line(function)
        return function

    return register


def generic(name: str, *, summary: str = "") -> Callable[[F], F]:
    """Register an implementation of ``name`` that accepts any first argument.

    For operators where the type genuinely does not matter -- `eq`, `coalesce`,
    `is_null`. Reaching for this because a typed overload is inconvenient is how a
    dispatch table becomes a pile of isinstance checks.
    """

    def register(function: F) -> F:
        if name in FALLBACK:
            raise RuntimeError(f"duplicate generic for {name}")
        FALLBACK[name] = function
        if summary or name not in SUMMARY:
            SUMMARY[name] = summary or _first_line(function)
        return function

    return register


def resolve(name: str, first: Any) -> Callable[..., Any]:
    """The implementation of ``name`` for this runtime type.

    MRO walk-up means an overload registered for `dict` also serves an `OrderedDict`,
    and one registered for `object` serves anything -- which is what `generic` is for.
    """
    for candidate in type(first).__mro__:
        implementation = TABLE.get((name, candidate))
        if implementation is not None:
            return implementation
    fallback = FALLBACK.get(name)
    if fallback is not None:
        return fallback
    raise _no_overload(name, first)


def has(name: str) -> bool:
    return name in FALLBACK or any(key[0] == name for key in TABLE)


def names() -> list[str]:
    """Every registered operator, sorted. Used by completion and the docs builder."""
    found = {key[0] for key in TABLE} | set(FALLBACK)
    return sorted(found)


def types_for(name: str) -> list[str]:
    return sorted({key[1].__name__ for key in TABLE if key[0] == name})


async def apply(name: str, args: list[Any], kwargs: dict[str, Any]) -> Any:
    """Resolve and invoke, awaiting the result when the overload is async.

    Both `def` and `async def` overloads are supported (SPEC section 10). Keeping the
    await here means no call site has to know which kind it got.
    """
    if not args:
        implementation = FALLBACK.get(name)
        if implementation is None:
            raise _no_overload(name, None)
    else:
        implementation = resolve(name, args[0])
    result = implementation(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _no_overload(name: str, first: Any) -> TypeDispatchError:
    if not has(name):
        remedies = []
        suggestion = did_you_mean(name, names())
        if suggestion:
            remedies.append(suggestion)
        remedies.append("run 'sclpl fn list' to see everything available")
        return TypeDispatchError(f"no such function or operator {name!r}", remedies=remedies)
    registered = types_for(name)
    return TypeDispatchError(
        f"{name}() does not accept {type(first).__name__}",
        remedies=[f"it accepts: {', '.join(registered)}"],
    )


def _first_line(function: Callable[..., Any]) -> str:
    doc = inspect.getdoc(function) or ""
    return doc.splitlines()[0] if doc else ""
