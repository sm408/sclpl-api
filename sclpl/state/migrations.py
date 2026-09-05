"""Transactional schema migration for the local run-history database."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from sclpl.errors import ValidationError

SCHEMA_VERSION = 1


def migrate(path: Path, schema: str) -> None:
    """Apply known migrations once, keeping a backup before the first upgrade."""
    existed = path.exists() and path.stat().st_size > 0
    connection = sqlite3.connect(path)
    try:
        current = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if current > SCHEMA_VERSION:
            raise ValidationError(
                f"history database schema {current} is newer than this sclpl build",
                remedies=["upgrade sclpl", "use a separate SCLPL_HOME for the older build"],
            )
        if current == SCHEMA_VERSION:
            return
        if existed:
            _backup(path, current)
        connection.execute("BEGIN IMMEDIATE")
        try:
            for statement in (item.strip() for item in schema.split(";")):
                if statement:
                    connection.execute(statement)
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    finally:
        connection.close()


def _backup(path: Path, version: int) -> Path:
    """Keep the pre-migration bytes until an operator chooses to remove them."""
    backup = path.with_name(f"{path.name}.v{version}.bak")
    if not backup.exists():
        shutil.copy2(path, backup)
    return backup
