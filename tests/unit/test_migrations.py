"""History migrations preserve old data and fail safely for newer databases."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from sclpl.errors import ValidationError
from sclpl.state import db, migrations


def test_first_history_open_versions_the_database(tmp_path: Path) -> None:
    with db.History(tmp_path):
        pass
    with sqlite3.connect(tmp_path / "history.db") as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == migrations.SCHEMA_VERSION


def test_existing_unversioned_database_is_backed_up_before_upgrade(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE preserved (value TEXT)")
        connection.execute("INSERT INTO preserved VALUES ('keep')")

    migrations.migrate(path, "CREATE TABLE added (id INTEGER);")

    backup = tmp_path / "history.db.v0.bak"
    assert backup.is_file()
    with sqlite3.connect(backup) as connection:
        assert connection.execute("SELECT value FROM preserved").fetchone()[0] == "keep"


def test_newer_history_database_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    with sqlite3.connect(path) as connection:
        connection.execute(f"PRAGMA user_version = {migrations.SCHEMA_VERSION + 1}")

    with pytest.raises(ValidationError, match="newer"):
        migrations.migrate(path, "")
