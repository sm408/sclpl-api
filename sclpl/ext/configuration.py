"""Plugin-scoped, non-secret configuration supplied by an embedding host."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_SETTINGS: dict[str, dict[str, Any]] = {}


def set_plugin_settings(settings: Mapping[str, Mapping[str, Any]]) -> None:
    """Replace the current process's non-secret settings before plugin activation."""
    global _SETTINGS
    _SETTINGS = {name: dict(value) for name, value in settings.items()}


def plugin_settings(name: str) -> dict[str, Any]:
    """Return a defensive copy of one plugin's opaque configuration table."""
    return dict(_SETTINGS.get(name, {}))
