from __future__ import annotations

from app.storage.migrations.base import Migration


class AddWorkflowVersioning(Migration):
    @property
    def version(self) -> int:
        return 3

    @property
    def description(self) -> str:
        return "Add workflow_versions table for change tracking"

    async def up(self, db) -> None:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS workflow_versions (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                sclpll_source TEXT DEFAULT '',
                json_source TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
            )"""
        )

    async def down(self, db) -> None:
        await db.execute("DROP TABLE IF EXISTS workflow_versions")
