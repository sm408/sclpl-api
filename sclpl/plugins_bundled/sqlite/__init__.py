"""SQLite as a plugin, using only `sclpl.ext.api`.

This is the proof that the plugin API is sufficient (locked decision 8). Nothing here
reaches into the engine; it imports from `sclpl.ext.api` exactly as an external plugin
would. If SQLite needed something that is not there, the API would be missing something.

`sqlite3` is in the standard library, so this adds no dependency.

**Everything runs in the thread lane.** `sqlite3` blocks, and blocking on the event loop
stalls every other step -- including ones whose HTTP responses have already arrived. The
manifest declares the lane; the engine honours it.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from sclpl.ext.api import ValidationError, connector, records_of

#: SQLite's own affinities, chosen from what a value looks like. `REAL` for a float and
#: `INTEGER` for an int matters: a column typed `TEXT` sorts "10" before "9".
_AFFINITY = {
    bool: "INTEGER",
    int: "INTEGER",
    float: "REAL",
    bytes: "BLOB",
}


def register() -> None:
    """Called once at load. The decorators below have already run on import."""


def _connect(path: str, *, create: bool) -> sqlite3.Connection:
    target = Path(path)
    if not create and not target.exists():
        raise ValidationError(
            f"{target} does not exist",
            remedies=[
                "check the path, or the step that was meant to write it",
                "sqlite.write creates a database; sqlite.query does not",
            ],
        )
    if create:
        target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target)
    connection.row_factory = sqlite3.Row
    return connection


def _identifier(name: str) -> str:
    """Quote a table or column name.

    SQLite has no placeholder for an identifier, so this is the one place a name is
    interpolated into SQL. Doubling the quote is the escape; refusing a name containing
    a null byte is the rest of it.
    """
    if "\x00" in name:
        raise ValidationError(f"{name!r} is not a usable name")
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


@connector("sqlite.query", lane="thread")
def query(database: str, sql: str, *params: Any) -> list[dict[str, Any]]:
    """Run a SELECT and return the rows as objects.

    Parameters are bound, never formatted: `sqlite.query db.sqlite "select * from t
    where id = ?" 4`. That is not only about injection -- a bound parameter also keeps
    its type, which is invariant 2 reaching all the way into the database.
    """
    with _connect(database, create=False) as connection:
        cursor = connection.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


@connector("sqlite.exec", lane="thread")
def execute(database: str, sql: str, *params: Any) -> dict[str, Any]:
    """Run a statement that returns no rows. Reports what it changed."""
    with _connect(database, create=True) as connection:
        cursor = connection.execute(sql, params)
        connection.commit()
        return {"changed": cursor.rowcount, "last_id": cursor.lastrowid}


@connector("sqlite.write", lane="thread")
def write(
    data: Any,
    database: str,
    table: str,
    *,
    mode: str = "replace",
    key: str | None = None,
) -> dict[str, Any]:
    """Write records into a table, creating it from the first row if it is not there.

    `mode` is `replace` (drop and recreate), `append`, or `upsert` -- which needs `key`,
    the column that decides whether a row is new.

    The columns come from the **union** of the records, not the first one. An API that
    omits a null field on some rows would otherwise silently drop that column for
    everybody.
    """
    if mode not in ("replace", "append", "upsert"):
        raise ValidationError(
            f"unknown write mode {mode!r}",
            remedies=["use one of: replace, append, upsert"],
        )
    if mode == "upsert" and not key:
        raise ValidationError(
            "upsert needs to know which column identifies a row",
            remedies=["add key=<column>", "or use mode=append if duplicates are fine"],
        )

    rows = records_of(data)
    if not rows:
        return {"written": 0, "table": table}

    columns: list[str] = []
    for row in rows:
        for name in row:
            if name not in columns:
                columns.append(name)

    quoted = _identifier(table)
    with _connect(database, create=True) as connection:
        if mode == "replace":
            connection.execute(f"DROP TABLE IF EXISTS {quoted}")
        connection.execute(
            f"CREATE TABLE IF NOT EXISTS {quoted} ("
            + ", ".join(
                f"{_identifier(name)} {_column_type(rows, name)}"
                + (" PRIMARY KEY" if key == name else "")
                for name in columns
            )
            + ")"
        )
        _add_missing_columns(connection, quoted, columns, rows)

        verb = "INSERT OR REPLACE INTO" if mode == "upsert" else "INSERT INTO"
        statement = (
            f"{verb} {quoted} ({', '.join(_identifier(name) for name in columns)})"
            f" VALUES ({', '.join('?' for _ in columns)})"
        )
        connection.executemany(
            statement, [[_bindable(row.get(name)) for name in columns] for row in rows]
        )
        connection.commit()
    return {"written": len(rows), "table": table, "columns": columns}


@connector("sqlite.schema", lane="thread")
def schema(database: str, table: str | None = None) -> dict[str, Any]:
    """The tables in a database and their columns, or just one table's."""
    with _connect(database, create=False) as connection:
        names = (
            [table]
            if table
            else [
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                    " AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
        )
        found: dict[str, Any] = {}
        for name in names:
            columns = connection.execute(f"PRAGMA table_info({_identifier(name)})").fetchall()
            if not columns and table:
                raise ValidationError(
                    f"no table named {name!r} in {database}",
                    remedies=["run sqlite.schema without a table name to see what is there"],
                )
            found[name] = {row["name"]: row["type"] for row in columns}
        return found


def _column_type(rows: list[dict[str, Any]], name: str) -> str:
    """The affinity for a column, from the first row that has a value for it."""
    for row in rows:
        value = row.get(name)
        if value is not None:
            return _AFFINITY.get(type(value), "TEXT")
    return "TEXT"


def _add_missing_columns(
    connection: sqlite3.Connection,
    quoted: str,
    columns: list[str],
    rows: list[dict[str, Any]],
) -> None:
    """Widen an existing table rather than failing on a new field.

    An API adding a field should not break an append into a table that predates it --
    the same reasoning as `assert_schema` allowing extra columns by default.
    """
    existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({quoted})")}
    for name in columns:
        if name not in existing:
            connection.execute(
                f"ALTER TABLE {quoted} ADD COLUMN {_identifier(name)} {_column_type(rows, name)}"
            )


def _bindable(value: Any) -> Any:
    """SQLite binds five types. Anything else goes in as its JSON form.

    Not as `str(value)`: a dict rendered with `repr` is not readable by anything, while
    JSON can be read back by `json_parse` on the way out.
    """
    if value is None or isinstance(value, (str, int, float, bytes)):
        return value
    import json

    return json.dumps(value, default=str)
