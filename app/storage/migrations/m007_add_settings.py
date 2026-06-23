"""Migration m007: Add settings table.

Creates a key-value ``settings`` table so that application settings
persist across server restarts.
"""

from __future__ import annotations

from app.storage.migrations.base import Migration


class AddSettings(Migration):
    @property
    def version(self) -> int:
        return 7

    @property
    def description(self) -> str:
        return "Add settings table for persistent application settings"

    async def up(self, db) -> None:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

    async def down(self, db) -> None:
        await db.execute("DROP TABLE IF EXISTS settings")
