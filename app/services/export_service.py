from __future__ import annotations

import csv
import json
import uuid
from pathlib import Path

from app.core.contracts.export_pipeline import ExportPipeline, ExportResult
from app.core.models.export import ExportFormat


class DefaultExportPipeline(ExportPipeline):
    async def export_json(self, data: list[dict], output_path: str) -> ExportResult:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return ExportResult(
            path=str(path),
            format=ExportFormat.JSON,
            record_count=len(data),
            success=True,
        )

    async def export_csv(self, data: list[dict], output_path: str) -> ExportResult:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not data:
            return ExportResult(
                path=str(path),
                format=ExportFormat.CSV,
                record_count=0,
                success=True,
            )
        fieldnames = list(data[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        return ExportResult(
            path=str(path),
            format=ExportFormat.CSV,
            record_count=len(data),
            success=True,
        )
