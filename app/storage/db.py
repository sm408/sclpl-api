from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data") / "sclplapi.db"

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS collections (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS requests (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    method TEXT NOT NULL,
    url TEXT NOT NULL,
    headers TEXT DEFAULT '[]',
    query_params TEXT DEFAULT '[]',
    body TEXT,
    body_type TEXT,
    auth_type TEXT,
    auth_config TEXT DEFAULT '{}',
    collection_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS environments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    is_active INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS variables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    environment_id TEXT,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    scope TEXT DEFAULT 'environment',
    is_secret INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1,
    FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS history (
    id TEXT PRIMARY KEY,
    request_id TEXT,
    request_name TEXT NOT NULL,
    method TEXT NOT NULL,
    url TEXT NOT NULL,
    status TEXT NOT NULL,
    status_code INTEGER,
    response_body TEXT,
    response_headers TEXT DEFAULT '{}',
    duration_ms INTEGER DEFAULT 0,
    error_message TEXT,
    environment_id TEXT,
    variables_used TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workflows (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    steps TEXT DEFAULT '[]',
    variables TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS export_presets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    format TEXT NOT NULL,
    field_mappings TEXT DEFAULT '[]',
    filters TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self._path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._path))
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    async def initialize(self) -> None:
        if not self._db:
            await self.connect()
        await self._db.executescript(SCHEMA_SQL)
        await self._db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        await self._db.commit()
        logger.info("Database initialized at %s (version %d)", self._path, SCHEMA_VERSION)

    @property
    def connection(self) -> aiosqlite.Connection:
        if not self._db:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._db

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        return await self.connection.execute(sql, params)

    async def fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        cursor = await self.connection.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        cursor = await self.connection.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def commit(self) -> None:
        await self.connection.commit()
