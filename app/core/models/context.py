from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.models.environment import Environment
from app.core.models.request import RequestDef


@dataclass
class ResolvedVariable:
    key: str
    value: str
    source: str


@dataclass
class ExecutionContext:
    request: RequestDef | None = None
    environment: Environment | None = None
    variables: dict[str, str] = field(default_factory=dict)
    resolved_variables: list[ResolvedVariable] = field(default_factory=list)
    step_outputs: dict[str, Any] = field(default_factory=dict)
    batch_row: dict[str, str] = field(default_factory=dict)
    workflow_variables: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
