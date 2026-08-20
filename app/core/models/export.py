from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ExportFormat(StrEnum):
    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"


@dataclass
class ExportFieldMapping:
    source: str
    target: str
    transform: str | None = None


@dataclass
class ExportPreset:
    id: str
    name: str
    format: ExportFormat
    field_mappings: list[ExportFieldMapping] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None


@dataclass
class ExportJob:
    id: str
    preset_id: str | None = None
    format: ExportFormat = ExportFormat.JSON
    history_ids: list[str] = field(default_factory=list)
    output_path: str | None = None
    status: str = "pending"
    created_at: str | None = None
