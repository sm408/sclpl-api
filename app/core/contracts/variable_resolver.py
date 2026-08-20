from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.models.context import ExecutionContext, ResolvedVariable


class VariableResolver(ABC):
    @abstractmethod
    def resolve(self, text: str, ctx: ExecutionContext) -> str:
        ...

    @abstractmethod
    def resolve_all(self, ctx: ExecutionContext) -> list[ResolvedVariable]:
        ...

    @abstractmethod
    def extract_variable_keys(self, text: str) -> list[str]:
        ...
