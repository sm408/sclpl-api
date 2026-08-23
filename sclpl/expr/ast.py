"""Expression AST.

Our own node types, not Python's (invariant 7). Nothing here is ever handed to `eval`
or `compile`; the evaluator walks these and dispatches through an explicit table, so
the set of things an expression can do is exactly the set of registered operators.

Infix is sugar. `a.total > 500` parses straight to `Call("gt", [...])` — the parser
does the lowering, so the evaluator has one shape to handle instead of two.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypeAlias


@dataclass(frozen=True, slots=True)
class Literal:
    value: Any


@dataclass(frozen=True, slots=True)
class Ref:
    """`@name` — a reference to a step output or a bound value.

    Every `Ref` in a workflow becomes an edge in the DAG (invariant 3).
    """

    name: str


@dataclass(frozen=True, slots=True)
class Var:
    """A bare identifier: a workflow var, a `let` name, or a loop variable."""

    name: str


@dataclass(frozen=True, slots=True)
class Attr:
    obj: Node
    name: str


@dataclass(frozen=True, slots=True)
class Index:
    obj: Node
    index: Node


@dataclass(frozen=True, slots=True)
class Slice:
    obj: Node
    start: Node | None
    stop: Node | None


@dataclass(frozen=True, slots=True)
class Projection:
    """`[*]` — every element, flattened one level."""

    obj: Node


@dataclass(frozen=True, slots=True)
class Filter:
    """`[?(pred)]` — the elements for which `pred` holds.

    Inside `pred`, bare identifiers resolve against the element, so
    `items[?(price > 10)]` reads the way it looks.
    """

    obj: Node
    predicate: Node


@dataclass(frozen=True, slots=True)
class Call:
    name: str
    args: tuple[Node, ...] = ()
    kwargs: tuple[tuple[str, Node], ...] = ()


@dataclass(frozen=True, slots=True)
class And:
    """Kept out of `Call` because it must short-circuit."""

    left: Node
    right: Node


@dataclass(frozen=True, slots=True)
class Or:
    left: Node
    right: Node


@dataclass(frozen=True, slots=True)
class Not:
    operand: Node


@dataclass(frozen=True, slots=True)
class Ternary:
    condition: Node
    then: Node
    otherwise: Node


@dataclass(frozen=True, slots=True)
class ListLit:
    items: tuple[Node, ...] = ()


@dataclass(frozen=True, slots=True)
class DictLit:
    pairs: tuple[tuple[Node, Node], ...] = ()


@dataclass(frozen=True, slots=True)
class Interpolation:
    """A string with `{{expr}}` holes.

    The only place a value is stringified (invariant 2). Literal segments are `str`;
    holes are nodes.
    """

    parts: tuple[str | Node, ...] = ()


@dataclass(frozen=True, slots=True)
class Pipe:
    """`a | f(b)` — sugar for `f(a, b)`, so a chain of transforms reads left to right."""

    value: Node
    call: Call


Node: TypeAlias = (
    Literal
    | Ref
    | Var
    | Attr
    | Index
    | Slice
    | Projection
    | Filter
    | Call
    | And
    | Or
    | Not
    | Ternary
    | ListLit
    | DictLit
    | Interpolation
    | Pipe
)


@dataclass(slots=True)
class Expr:
    """A parsed expression plus the source it came from.

    The source text is kept so a diagnostic can quote what the user actually wrote
    rather than a reconstruction of it.
    """

    node: Node
    source: str
    refs: frozenset[str] = field(default_factory=frozenset)

    def __str__(self) -> str:
        return self.source


def collect_refs(node: Node) -> frozenset[str]:
    """Every `@name` reachable in ``node``.

    This is where the DAG comes from (invariant 3): a step that mentions `@orders`
    depends on `orders`, and no hand-written list is consulted.
    """
    found: set[str] = set()
    _walk_refs(node, found)
    return frozenset(found)


def _walk_refs(node: Node, found: set[str]) -> None:
    match node:
        case Ref(name=name):
            found.add(name)
        case Attr(obj=obj) | Index(obj=obj) | Projection(obj=obj):
            _walk_refs(obj, found)
            if isinstance(node, Index):
                _walk_refs(node.index, found)
        case Slice(obj=obj, start=start, stop=stop):
            _walk_refs(obj, found)
            if start is not None:
                _walk_refs(start, found)
            if stop is not None:
                _walk_refs(stop, found)
        case Filter(obj=obj, predicate=predicate):
            _walk_refs(obj, found)
            _walk_refs(predicate, found)
        case Call(args=args, kwargs=kwargs):
            for arg in args:
                _walk_refs(arg, found)
            for _, value in kwargs:
                _walk_refs(value, found)
        case And(left=left, right=right) | Or(left=left, right=right):
            _walk_refs(left, found)
            _walk_refs(right, found)
        case Not(operand=operand):
            _walk_refs(operand, found)
        case Ternary(condition=condition, then=then, otherwise=otherwise):
            _walk_refs(condition, found)
            _walk_refs(then, found)
            _walk_refs(otherwise, found)
        case ListLit(items=items):
            for item in items:
                _walk_refs(item, found)
        case DictLit(pairs=pairs):
            for key, value in pairs:
                _walk_refs(key, found)
                _walk_refs(value, found)
        case Interpolation(parts=parts):
            for part in parts:
                if not isinstance(part, str):
                    _walk_refs(part, found)
        case Pipe(value=value, call=call):
            _walk_refs(value, found)
            _walk_refs(call, found)
        case _:
            return


def unparse(node: Node) -> str:
    """Render a node back to source. Used by `explain` and by error messages."""
    match node:
        case Literal(value=value):
            return (
                "null" if value is None else repr(value) if isinstance(value, str) else str(value)
            )
        case Ref(name=name):
            return f"@{name}"
        case Var(name=name):
            return name
        case Attr(obj=obj, name=name):
            return f"{unparse(obj)}.{name}"
        case Index(obj=obj, index=index):
            return f"{unparse(obj)}[{unparse(index)}]"
        case Slice(obj=obj, start=start, stop=stop):
            left = unparse(start) if start is not None else ""
            right = unparse(stop) if stop is not None else ""
            return f"{unparse(obj)}[{left}:{right}]"
        case Projection(obj=obj):
            return f"{unparse(obj)}[*]"
        case Filter(obj=obj, predicate=predicate):
            return f"{unparse(obj)}[?({unparse(predicate)})]"
        case Call(name=name, args=args, kwargs=kwargs):
            rendered = [unparse(arg) for arg in args]
            rendered.extend(f"{key}={unparse(value)}" for key, value in kwargs)
            return f"{name}({', '.join(rendered)})"
        case And(left=left, right=right):
            return f"({unparse(left)} and {unparse(right)})"
        case Or(left=left, right=right):
            return f"({unparse(left)} or {unparse(right)})"
        case Not(operand=operand):
            return f"not {unparse(operand)}"
        case Ternary(condition=condition, then=then, otherwise=otherwise):
            return f"({unparse(condition)} ? {unparse(then)} : {unparse(otherwise)})"
        case ListLit(items=items):
            return f"[{', '.join(unparse(item) for item in items)}]"
        case DictLit(pairs=pairs):
            body = ", ".join(f"{unparse(key)}: {unparse(value)}" for key, value in pairs)
            return f"{{{body}}}"
        case Interpolation(parts=parts):
            body = "".join(
                part if isinstance(part, str) else f"{{{{{unparse(part)}}}}}" for part in parts
            )
            return f'"{body}"'
        case Pipe(value=value, call=call):
            return f"{unparse(value)} | {unparse(call)}"
