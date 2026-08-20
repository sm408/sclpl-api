from __future__ import annotations

from app.storage.migrations.base import Migration


class AddPluginTables(Migration):
    @property
    def version(self) -> int:
        return 2

    @property
    def description(self) -> str:
        return "Add plugins and plugin_variables tables"

    async def up(self, db) -> None:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS plugins (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                description TEXT DEFAULT '',
                author TEXT DEFAULT '',
                status TEXT DEFAULT 'inactive',
                manifest_json TEXT DEFAULT '{}',
                project_id TEXT DEFAULT '00000000-0000-0000-0000-000000000001',
                revision INTEGER DEFAULT 1,
                installed_at TEXT NOT NULL
            )"""
        )
        await db.execute(
            """CREATE TABLE IF NOT EXISTS plugin_variables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plugin_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                FOREIGN KEY (plugin_id) REFERENCES plugins(id) ON DELETE CASCADE
            )"""
        )

    async def down(self, db) -> None:
        await db.execute("DROP TABLE IF EXISTS plugin_variables")
        await db.execute("DROP TABLE IF EXISTS plugins")
