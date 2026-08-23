"""The evaluator: walks our AST, dispatches through the operator table.

Two rules shape everything here.

Invariant 2 -- values keep their type. `@a.count + 1` is integer arithmetic because
`@a.count` arrives as an `int`. The only place a value becomes a string is
`Interpolation`, which is the interpolation boundary the invariant names.

Invariant 7 -- nothing is `eval`'d. Every operation goes through `dispatch.apply`, so
the reachable surface is exactly what has been registered.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sclpl.expr import dispatch, path
from sclpl.expr.ast import (
    And,
    Attr,
    Call,
    DictLit,
    Expr,
    Filter,
    Index,
    Interpolation,
    ListLit,
    Literal,
    Node,
    Not,
    Or,
    Pipe,
    Projection,
    Ref,
    Slice,
    Ternary,
    Var,
    unparse,
)
from sclpl.run.errors import ExpressionError, PathError, UnknownReference, did_you_mean
from sclpl.values.store import Frame, ValueStore


@dataclass(slots=True)
class Context:
    """What names an expression can see.

    ``store`` holds step outputs, reached with `@name`. ``frame`` holds locals -- `let`
    bindings, the loop variable, and inside a filter, the element under test. ``vars``
    holds workflow-level variables, which are the outermost scope.
    """

    store: ValueStore | None = None
    frame: Frame | None = None
    vars: dict[str, Any] | None = None
    #: The element a filter predicate is testing, if we are inside one. Bare
    #: identifiers resolve against it first, so `items[?(price > 10)]` reads naturally.
    element: Any = None
    has_element: bool = False

    def with_element(self, element: Any) -> Context:
        return Context(
            store=self.store,
            frame=self.frame,
            vars=self.vars,
            element=element,
            has_element=True,
        )

    def with_frame(self, frame: Frame) -> Context:
        return Context(
            store=self.store,
            frame=frame,
            vars=self.vars,
            element=self.element,
            has_element=self.has_element,
        )


async def evaluate(expr: Expr | Node, context: Context | None = None) -> Any:
    """Evaluate an expression to a Python value of its natural type."""
    node = expr.node if isinstance(expr, Expr) else expr
    return await _eval(node, context if context is not None else Context())


async def _eval(node: Node, ctx: Context) -> Any:
    match node:
        case Literal(value=value):
            return value

        case Ref(name=name):
            return _lookup_ref(name, ctx)

        case Var(name=name):
            return _lookup_var(name, ctx)

        case Attr(obj=obj, name=name):
            target = await _eval(obj, ctx)
            return path.get_attr(target, name, path=unparse(node))

        case Index(obj=obj, index=index_node):
            target = await _eval(obj, ctx)
            index = await _eval(index_node, ctx)
            return path.get_index(target, index, path=unparse(node))

        case Slice(obj=obj, start=start_node, stop=stop_node):
            target = await _eval(obj, ctx)
            start = await _eval(start_node, ctx) if start_node is not None else None
            stop = await _eval(stop_node, ctx) if stop_node is not None else None
            return path.get_slice(target, start, stop, path=unparse(node))

        case Projection(obj=obj):
            target = await _eval(obj, ctx)
            return path.project(target, path=unparse(node))

        case Filter(obj=obj, predicate=predicate):
            target = await _eval(obj, ctx)
            kept: list[Any] = []
            for item in path.elements(target, path=unparse(node)):
                if _truthy(await _eval(predicate, ctx.with_element(item))):
                    kept.append(item)
            return kept

        case Call(name=name, args=args, kwargs=kwargs):
            values = [await _eval(arg, ctx) for arg in args]
            keywords = {key: await _eval(value, ctx) for key, value in kwargs}
            return await dispatch.apply(name, values, keywords)

        case Pipe(value=value, call=call):
            piped = await _eval(value, ctx)
            values = [piped] + [await _eval(arg, ctx) for arg in call.args]
            keywords = {key: await _eval(item, ctx) for key, item in call.kwargs}
            return await dispatch.apply(call.name, values, keywords)

        case And(left=left, right=right):
            first = await _eval(left, ctx)
            return await _eval(right, ctx) if _truthy(first) else first

        case Or(left=left, right=right):
            first = await _eval(left, ctx)
            return first if _truthy(first) else await _eval(right, ctx)

        case Not(operand=operand):
            return not _truthy(await _eval(operand, ctx))

        case Ternary(condition=condition, then=then, otherwise=otherwise):
            chosen = then if _truthy(await _eval(condition, ctx)) else otherwise
            return await _eval(chosen, ctx)

        case ListLit(items=items):
            return [await _eval(item, ctx) for item in items]

        case DictLit(pairs=pairs):
            return {await _eval(key, ctx): await _eval(value, ctx) for key, value in pairs}

        case Interpolation(parts=parts):
            # The interpolation boundary -- the one place a value becomes text.
            out: list[str] = []
            for part in parts:
                if isinstance(part, str):
                    out.append(part)
                else:
                    out.append(stringify(await _eval(part, ctx)))
            return "".join(out)

        case _:
            raise ExpressionError(f"cannot evaluate {type(node).__name__}")


def stringify(value: Any) -> str:
    """Render a value for interpolation into a string.

    JSON-ish rather than Python-ish: `true`, not `True`; no quotes around a string that
    is being spliced into a URL; compact JSON for anything structured.
    """
    match value:
        case None:
            return ""
        case bool():
            return "true" if value else "false"
        case str():
            return value
        case int() | float():
            return str(value)
        case bytes() | bytearray():
            return value.decode("utf-8", "replace")
        case list() | tuple() | dict():
            import json

            return json.dumps(value, separators=(",", ":"), default=str)
        case _:
            return str(value)


def _truthy(value: Any) -> bool:
    """Python truthiness, except that a Table is truthy when it has rows.

    A DataFrame raises on `bool()`, which would turn a reasonable `when` clause into a
    crash, so decide it here rather than letting it surface from pandas.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    empty = getattr(value, "empty", None)
    if isinstance(empty, bool):
        return not empty
    rows = getattr(value, "row_count", None)
    if isinstance(rows, int):
        return rows > 0
    try:
        return bool(value)
    except (ValueError, TypeError):
        return True


def _lookup_ref(name: str, ctx: Context) -> Any:
    if ctx.store is not None and ctx.store.has(name):
        return ctx.store.get(name)
    if ctx.frame is not None and ctx.frame.has(name):
        return ctx.frame.get(name)
    available: list[str] = []
    if ctx.store is not None:
        available.extend(ctx.store.names())
    if ctx.frame is not None:
        available.extend(ctx.frame.names())
    remedies = []
    suggestion = did_you_mean(name, available)
    if suggestion:
        remedies.append(suggestion)
    if available:
        remedies.append(f"available: {', '.join(sorted(set(available))[:8])}")
    else:
        remedies.append("no step has produced a value yet at this point in the graph")
    raise UnknownReference(f"nothing produces @{name}", remedies=remedies)


def _lookup_var(name: str, ctx: Context) -> Any:
    if ctx.has_element:
        element = ctx.element
        if isinstance(element, dict) and name in element:
            return element[name]
        if not isinstance(element, (dict, list, tuple)) and hasattr(element, name):
            return getattr(element, name)
    if ctx.frame is not None and ctx.frame.has(name):
        return ctx.frame.get(name)
    if ctx.vars is not None and name in ctx.vars:
        return ctx.vars[name]
    if ctx.store is not None and ctx.store.has(name):
        return ctx.store.get(name)

    if ctx.has_element and isinstance(ctx.element, dict):
        raise PathError(
            f"no field {name!r} on this element",
            where=name,
            remedies=_element_remedies(name, ctx.element),
        )

    available: list[str] = []
    if ctx.frame is not None:
        available.extend(ctx.frame.names())
    if ctx.vars is not None:
        available.extend(ctx.vars)
    remedies = []
    suggestion = did_you_mean(name, available)
    if suggestion:
        remedies.append(suggestion)
    remedies.append(f"use @{name} if you meant a step's output")
    raise UnknownReference(f"unknown name {name!r}", remedies=remedies)


def _element_remedies(name: str, element: dict[str, Any]) -> list[str]:
    keys = [str(key) for key in element]
    remedies: list[str] = []
    suggestion = did_you_mean(name, keys)
    if suggestion:
        remedies.append(suggestion)
    remedies.append(f"available: {', '.join(repr(key) for key in keys[:8])}")
    return remedies
