from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StepType(StrEnum):
    REQUEST = "request"
    FUNCTION = "function"
    TRANSFORMER = "transformer"
    EXPORT = "export"
    DELAY = "delay"


class RetryStrategy(StrEnum):
    NONE = "none"
    FIXED = "fixed"
    EXPONENTIAL = "exponential"


@dataclass
class RetryConfig:
    max_retries: int = 0
    strategy: RetryStrategy = RetryStrategy.NONE
    delay_ms: int = 1000
    retry_on_status: list[int] = field(default_factory=list)


@dataclass
class WorkflowStep:
    id: str
    name: str
    step_type: StepType
    request_id: str | None = None
    function_name: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    retry: RetryConfig = field(default_factory=RetryConfig)
    condition: str | None = None
    output_variable: str | None = None


@dataclass
class WorkflowDef:
    id: str
    name: str
    description: str = ""
    steps: list[WorkflowStep] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None
