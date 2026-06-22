from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data") / "sclplapi.db"

SCHEMA_VERSION = 5

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    root_path TEXT DEFAULT '',
    is_default INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collections (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    project_id TEXT DEFAULT '00000000-0000-0000-0000-000000000001',
    revision INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
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
    project_id TEXT DEFAULT '00000000-0000-0000-0000-000000000001',
    revision INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE SET NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS environments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    is_active INTEGER DEFAULT 0,
    project_id TEXT DEFAULT '00000000-0000-0000-0000-000000000001',
    revision INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
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
    project_id TEXT DEFAULT '00000000-0000-0000-0000-000000000001',
    revision INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS workflows (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    steps TEXT DEFAULT '[]',
    variables TEXT DEFAULT '{}',
    project_id TEXT DEFAULT '00000000-0000-0000-0000-000000000001',
    revision INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS export_presets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    format TEXT NOT NULL,
    field_mappings TEXT DEFAULT '[]',
    filters TEXT DEFAULT '{}',
    project_id TEXT DEFAULT '00000000-0000-0000-0000-000000000001',
    revision INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

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
    updated_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

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
);

CREATE TABLE IF NOT EXISTS plugins (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT DEFAULT '',
    author TEXT DEFAULT '',
    status TEXT DEFAULT 'inactive',
    manifest_json TEXT DEFAULT '{}',
    project_id TEXT DEFAULT '00000000-0000-0000-0000-000000000001',
    revision INTEGER DEFAULT 1,
    installed_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS plugin_variables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    FOREIGN KEY (plugin_id) REFERENCES plugins(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workflow_versions (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    sclpll_source TEXT DEFAULT '',
    json_source TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

-- Note: project_id indexes (idx_*_project_id) are created by migration m005
-- after it ensures the project_id columns exist on all tables.  They are
-- deliberately omitted here so that existing databases (created before the
-- project model) do not fail when SCHEMA_SQL runs against tables that lack
-- the project_id column.
CREATE INDEX IF NOT EXISTS idx_monitor_events_monitor_id ON monitor_events(monitor_id);
"""


def get_all_migrations():
    from app.storage.migrations.m001_add_plugin_tables import AddPluginTables
    from app.storage.migrations.m002_add_workflow_versioning import AddWorkflowVersioning
    from app.storage.migrations.m003_add_export_presets import AddExportPresets
    from app.storage.migrations.m004_add_monitors import AddMonitors
    from app.storage.migrations.m005_add_projects import AddProjects
    return [AddPluginTables(), AddWorkflowVersioning(), AddExportPresets(), AddMonitors(), AddProjects()]


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
        await self._db.commit()
        await self._run_migrations()
        current = await self.fetch_one(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        )
        if not current:
            await self._db.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            await self._db.commit()
        logger.info("Database initialized at %s (version %d)", self._path, SCHEMA_VERSION)

    async def _run_migrations(self) -> None:
        from app.storage.migrations.runner import MigrationRunner
        migrations = get_all_migrations()
        runner = MigrationRunner(self, migrations)
        applied = await runner.run_pending()
        if applied:
            logger.info("Applied migrations: %s", applied)

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
