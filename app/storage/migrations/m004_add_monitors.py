"""Migration: Add monitors and monitor_events tables."""

from __future__ import annotations

from app.storage.migrations.base import Migration


class AddMonitors(Migration):
    @property
    def version(self) -> int:
        return 4

    @property
    def description(self) -> str:
        return "Add monitors and monitor_events tables"

    async def up(self, db) -> None:
        """Create monitors and monitor_events tables."""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS monitors (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                method TEXT DEFAULT 'GET',
                headers TEXT DEFAULT '{}',
                body TEXT,
                interval_seconds INTEGER DEFAULT 60,
                condition TEXT DEFAULT '',
                notification_on TEXT DEFAULT 'change',
                enabled INTEGER DEFAULT 1,
                status TEXT DEFAULT 'stopped',
                last_run TEXT,
                last_status_code INTEGER,
                last_body TEXT,
                last_error TEXT,
                last_changed TEXT,
                run_count INTEGER DEFAULT 0,
                trigger_count INTEGER DEFAULT 0,
                project_id TEXT DEFAULT '00000000-0000-0000-0000-000000000001',
                revision INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS monitor_events (
                id TEXT PRIMARY KEY,
                monitor_id TEXT NOT NULL,
                monitor_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                status_code INTEGER,
                body TEXT,
                condition_met INTEGER DEFAULT 0,
                changed INTEGER DEFAULT 0,
                error TEXT,
                duration_ms INTEGER DEFAULT 0,
                created_at TEXT,
                FOREIGN KEY (monitor_id) REFERENCES monitors(id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_monitor_events_monitor_id
            ON monitor_events(monitor_id)
        """)

        await db.commit()

    async def down(self, db) -> None:
        """Drop monitors and monitor_events tables."""
        await db.execute("DROP TABLE IF EXISTS monitor_events")
        await db.execute("DROP TABLE IF EXISTS monitors")
        await db.commit()
