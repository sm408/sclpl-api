from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class PluginStatus(StrEnum):
    DISCOVERED = "discovered"
    LOADED = "loaded"
    ACTIVE = "active"
    ERROR = "error"


@dataclass
class PluginManifest:
    name: str
    version: str
    description: str = ""
    author: str = ""
    functions: list[str] = field(default_factory=list)
    workflows: list[str] = field(default_factory=list)
    hooks: dict[str, str] = field(default_factory=dict)
    variables: dict[str, str] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    path: str = ""


@dataclass
class PluginInfo:
    manifest: PluginManifest
    status: PluginStatus = PluginStatus.DISCOVERED
    functions: list[dict[str, str]] = field(default_factory=list)
    workflows: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
