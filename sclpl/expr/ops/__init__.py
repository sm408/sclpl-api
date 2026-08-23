"""Operator families.

Importing this module registers every operator in the dispatch table. The imports look
unused and are not: the decorators run on import, which is the registration.

Later milestones add families here -- `rel` and `shape` over tables in M5 -- without
any other module changing.
"""

from __future__ import annotations

from sclpl.expr.ops import arith, cast, coll, compare, string

__all__ = ["arith", "cast", "coll", "compare", "string"]
