from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.core.models.context import ExecutionContext
from app.core.models.history import HistoryEntry
from app.core.models.request import RequestDef


@dataclass
class ResponseResult:
    status_code: int
    headers: dict[str, str]
    body: str
    duration_ms: int
    error: str | None = None


class RequestExecutor(ABC):
    @abstractmethod
    async def execute(
        self,
        request: RequestDef,
        ctx: ExecutionContext,
    ) -> ResponseResult:
        ...

    @abstractmethod
    async def execute_with_history(
        self,
        request: RequestDef,
        ctx: ExecutionContext,
    ) -> tuple[ResponseResult, HistoryEntry]:
        ...
