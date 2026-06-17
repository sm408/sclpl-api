from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.models.export import ExportFormat


@dataclass
class ExportResult:
    path: str
    format: ExportFormat
    record_count: int
    success: bool
    error: str | None = None


class ExportPipeline(ABC):
    @abstractmethod
    async def export_json(self, data: list[dict], output_path: str) -> ExportResult:
        ...

    @abstractmethod
    async def export_csv(self, data: list[dict], output_path: str) -> ExportResult:
        ...
