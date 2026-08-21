from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.storage.migrations.base import Migration


class AddExportPresets(Migration):
    @property
    def version(self) -> int:
        return 4

    @property
    def description(self) -> str:
        return "Add export_presets table with sample presets"

    async def up(self, db) -> None:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS export_presets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                format TEXT NOT NULL,
                field_mappings TEXT DEFAULT '[]',
                filters TEXT DEFAULT '{}',
                created_at TEXT NOT NULL
            )"""
        )

        now = datetime.now(UTC).isoformat()
        presets = [
            {
                "id": str(uuid.uuid4()),
                "name": "full_backup",
                "format": "json",
                "field_mappings": '["*"]',
                "filters": "{}",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "workflow_only",
                "format": "json",
                "field_mappings": '["workflows"]',
                "filters": '{"exclude_history": true}',
            },
            {
                "id": str(uuid.uuid4()),
                "name": "history_only",
                "format": "json",
                "field_mappings": '["history"]',
                "filters": "{}",
            },
        ]
        for preset in presets:
            existing = await db.fetch_one(
                "SELECT id FROM export_presets WHERE name = ?", (preset["name"],)
            )
            if not existing:
                await db.execute(
                    "INSERT INTO export_presets (id, name, format, field_mappings, filters, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (preset["id"], preset["name"], preset["format"], preset["field_mappings"], preset["filters"], now),
                )

    async def down(self, db) -> None:
        await db.execute("DROP TABLE IF EXISTS export_presets")
