from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.core.models.context import ExecutionContext


@dataclass
class FunctionResult:
    name: str
    success: bool
    return_value: Any = None
    error: str | None = None
    duration_ms: int = 0


class FunctionRunner(ABC):
    @abstractmethod
    def discover(self, directory: str) -> list[dict[str, str]]:
        ...

    @abstractmethod
    async def run(
        self,
        name: str,
        ctx: ExecutionContext,
    ) -> FunctionResult:
        ...
