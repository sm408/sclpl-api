"""Transactional schema migration for the local run-history database."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from sclpl.errors import ValidationError

SCHEMA_VERSION = 4


def migrate(path: Path, schema: str, upgrades: dict[int, str] | None = None) -> None:
    """Apply known migrations once, keeping a backup before the first upgrade.

    ``schema`` is the full base schema -- idempotent `CREATE TABLE`/`CREATE INDEX
    ... IF NOT EXISTS` statements -- always re-applied. ``upgrades`` names additive
    changes beyond that base, keyed by the version they bring the database *to*:
    for a table that already exists, `IF NOT EXISTS` cannot add a column the base
    schema grew after the table was first created, so those go here instead, each
    applied at most once, in version order. A brand-new database still runs every
    entry in ``upgrades`` after the base schema creates its tables -- the base
    schema is never grown a new column an upgrade is also responsible for; it is
    one or the other, never both, so nothing can apply twice.
    """
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
            for version in range(max(current, 1) + 1, SCHEMA_VERSION + 1):
                addition = (upgrades or {}).get(version, "")
                for statement in (item.strip() for item in addition.split(";")):
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
