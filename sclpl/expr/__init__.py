"""The expression language: lexer, parser, AST, path resolution, and dispatch.

Importing this package registers the built-in operators, so `dispatch.resolve` works
without a caller having to know which module an operator lives in.
"""

from __future__ import annotations

from sclpl.expr import ops as _ops  # noqa: F401 - the import is the registration
from sclpl.expr.ast import Expr, Node, collect_refs, unparse
from sclpl.expr.eval import Context, evaluate, stringify
from sclpl.expr.parse import is_expression, parse, parse_interpolated

__all__ = [
    "Context",
    "Expr",
    "Node",
    "collect_refs",
    "evaluate",
    "is_expression",
    "parse",
    "parse_interpolated",
    "stringify",
    "unparse",
]
