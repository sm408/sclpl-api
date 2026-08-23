"""Typed values: the store, refcounted disposal, digests, and spill references."""

from __future__ import annotations

from sclpl.values.digest import digest
from sclpl.values.ref import Scratch, ValueRef, size_of, spill
from sclpl.values.store import Binding, Frame, StoreStats, ValueStore

__all__ = [
    "Binding",
    "Frame",
    "Scratch",
    "StoreStats",
    "ValueRef",
    "ValueStore",
    "digest",
    "size_of",
    "spill",
]
