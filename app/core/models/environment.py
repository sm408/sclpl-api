from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class VariableScope(StrEnum):
    GLOBAL = "global"
    ENVIRONMENT = "environment"


@dataclass
class Variable:
    key: str
    value: str
    scope: VariableScope = VariableScope.ENVIRONMENT
    is_secret: bool = False
    enabled: bool = True


@dataclass
class Environment:
    id: str
    name: str
    variables: list[Variable] = field(default_factory=list)
    is_active: bool = False
    created_at: str | None = None
    updated_at: str | None = None
