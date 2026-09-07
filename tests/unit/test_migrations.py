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


# -- F5: incremental upgrades (an ALTER TABLE a fresh CREATE cannot do) --------------


def test_a_version_1_database_gains_the_new_columns_without_losing_its_row(
    tmp_path: Path,
) -> None:
    """An existing database, from before `completeness`/`publication` existed, must
    reach the current schema version with the new columns present and its own data
    untouched -- even though only version 2's own upgrade is supplied here, since a
    later batch's own upgrades (unrelated to this test) are free to bring the module
    to a higher `SCHEMA_VERSION` without invalidating what this test actually checks.
    """
    path = tmp_path / "history.db"
    v1_schema = """
        CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, name TEXT NOT NULL);
    """
    with sqlite3.connect(path) as connection:
        for statement in v1_schema.split(";"):
            if statement.strip():
                connection.execute(statement)
        connection.execute("INSERT INTO runs (id, name) VALUES ('r1', 'kept')")
        connection.execute("PRAGMA user_version = 1")

    migrations.migrate(
        path,
        v1_schema,
        {2: "ALTER TABLE runs ADD COLUMN completeness TEXT NOT NULL DEFAULT 'unknown';"},
    )

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == migrations.SCHEMA_VERSION
        row = connection.execute("SELECT name, completeness FROM runs WHERE id = 'r1'").fetchone()
        assert row == ("kept", "unknown")


def test_an_upgrade_for_a_version_the_database_already_has_does_not_reapply(
    tmp_path: Path,
) -> None:
    """Idempotent by construction: a database already at `SCHEMA_VERSION` returns
    before any upgrade statement runs, so `ALTER TABLE ADD COLUMN` never fires
    twice and fails with "duplicate column".
    """
    path = tmp_path / "history.db"
    with db.History(tmp_path):
        pass
    # A second open must not attempt to re-add the columns the first one just did.
    with db.History(tmp_path):
        pass
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == migrations.SCHEMA_VERSION


def test_db_module_upgrades_are_exercised_by_a_real_history_open(tmp_path: Path) -> None:
    """The actual `db._UPGRADES` this project ships, not a stand-in schema."""
    with db.History(tmp_path) as history:
        record = db.RunRecord(id="r1", name="run", workflow="orders", started_at=db.now())
        history.record(record)
    with sqlite3.connect(tmp_path / "history.db") as connection:
        row = connection.execute(
            "SELECT completeness, publication FROM runs WHERE id = 'r1'"
        ).fetchone()
        assert row == ("unknown", "n/a")
