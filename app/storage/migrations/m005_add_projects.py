"""Migration: Add project-scoped workspace model.

Creates the ``projects`` table and adds ``project_id`` / ``revision``
columns to every top-level resource table.  All existing rows are
assigned to the well-known Default project so that every current
CLI / TUI workflow continues to work without changes.
"""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.models.project import DEFAULT_PROJECT_ID, PROJECT_SUBDIRS
from app.storage.migrations.base import Migration


# Tables that receive project_id and revision columns.
_TOP_LEVEL_TABLES = (
    "collections",
    "requests",
    "environments",
    "workflows",
    "history",
    "monitors",
    "plugins",
    "export_presets",
)

_BACKUP_DIR = Path("data") / "migration_backups"


async def _column_exists(db, table: str, column: str) -> bool:
    """Return True if *table* already has *column*."""
    rows = await db.fetch_all(f"PRAGMA table_info({table})")
    return any(row["name"] == column for row in rows)


class AddProjects(Migration):
    @property
    def version(self) -> int:
        return 5

    @property
    def description(self) -> str:
        return "Add project-scoped workspace model"

    async def up(self, db) -> None:
        now = datetime.now(timezone.utc).isoformat()

        # ── 1. Create projects table ─────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                root_path TEXT DEFAULT '',
                is_default INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # ── 2. Seed the Default project ──────────────────────────────
        existing = await db.fetch_one(
            "SELECT id FROM projects WHERE id = ?", (DEFAULT_PROJECT_ID,)
        )
        if not existing:
            await db.execute(
                """INSERT INTO projects
                (id, name, description, root_path, is_default, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    DEFAULT_PROJECT_ID,
                    "Default",
                    "Default workspace — existing resources live here",
                    "",
                    1,
                    now,
                    now,
                ),
            )

        # ── 3. Add project_id + revision to each top-level table ─────
        for table in _TOP_LEVEL_TABLES:
            if not await _column_exists(db, table, "project_id"):
                await db.execute(
                    f"ALTER TABLE {table} ADD COLUMN project_id TEXT DEFAULT '{DEFAULT_PROJECT_ID}'"
                )
            if not await _column_exists(db, table, "revision"):
                await db.execute(
                    f"ALTER TABLE {table} ADD COLUMN revision INTEGER DEFAULT 1"
                )
            # Backfill any rows that were inserted before the column existed
            # (should only matter for the first run of this migration).
            await db.execute(
                f"UPDATE {table} SET project_id = ? WHERE project_id IS NULL",
                (DEFAULT_PROJECT_ID,),
            )

        # ── 4. Indexes for fast project-scoped queries ───────────────
        for table in _TOP_LEVEL_TABLES:
            idx_name = f"idx_{table}_project_id"
            await db.execute(
                f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}(project_id)"
            )

        await db.commit()

    async def down(self, db) -> None:
        # Drop indexes first.
        for table in _TOP_LEVEL_TABLES:
            idx_name = f"idx_{table}_project_id"
            await db.execute(f"DROP INDEX IF EXISTS {idx_name}")

        # SQLite < 3.35 does not support DROP COLUMN; we simply
        # leave the columns in place (they are harmless) rather than
        # risk a full table recreation.
        await db.execute("DROP TABLE IF EXISTS projects")
        await db.commit()


def backup_database(db_path: Path) -> Path | None:
    """Create a timestamped backup of the database file.

    Returns the backup path, or ``None`` if the source does not exist.
    """
    if not db_path.exists():
        return None

    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = _BACKUP_DIR / f"{db_path.stem}_{stamp}{db_path.suffix}"
    shutil.copy2(db_path, backup)
    return backup


def create_project_root(base: Path, project_id: str) -> Path:
    """Create ``data/projects/<project_id>/`` with standard subdirs."""
    root = base / "projects" / project_id
    for subdir in PROJECT_SUBDIRS:
        (root / subdir).mkdir(parents=True, exist_ok=True)
    return root
