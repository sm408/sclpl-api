"""Extensibility: the function registry and the plugin loader."""

from __future__ import annotations

from sclpl.ext.functions import REGISTRY, Registered, function, lookup, names

__all__ = ["REGISTRY", "Registered", "function", "lookup", "names"]
