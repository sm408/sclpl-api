import pytest

from app.storage.db import SCHEMA_VERSION, Database


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    await database.initialize()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_initialize_creates_tables(db):
    tables = await db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    table_names = [t["name"] for t in tables]
    assert "projects" in table_names
    assert "collections" in table_names
    assert "requests" in table_names
    assert "environments" in table_names
    assert "variables" in table_names
    assert "history" in table_names
    assert "workflows" in table_names
    assert "export_presets" in table_names
    assert "schema_version" in table_names
    assert "plugins" in table_names
    assert "plugin_variables" in table_names
    assert "workflow_versions" in table_names


@pytest.mark.asyncio
async def test_schema_version(db):
    row = await db.fetch_one("SELECT MAX(version) as version FROM schema_version")
    assert row["version"] == SCHEMA_VERSION


@pytest.mark.asyncio
async def test_default_project_exists(db):
    row = await db.fetch_one("SELECT * FROM projects WHERE is_default = 1")
    assert row is not None
    assert row["id"] == "00000000-0000-0000-0000-000000000001"
    assert row["name"] == "Default"


@pytest.mark.asyncio
async def test_collections_have_project_id_column(db):
    cols = await db.fetch_all("PRAGMA table_info(collections)")
    col_names = [c["name"] for c in cols]
    assert "project_id" in col_names
    assert "revision" in col_names


@pytest.mark.asyncio
async def test_requests_have_project_id_column(db):
    cols = await db.fetch_all("PRAGMA table_info(requests)")
    col_names = [c["name"] for c in cols]
    assert "project_id" in col_names
    assert "revision" in col_names


@pytest.mark.asyncio
async def test_environments_have_project_id_column(db):
    cols = await db.fetch_all("PRAGMA table_info(environments)")
    col_names = [c["name"] for c in cols]
    assert "project_id" in col_names
    assert "revision" in col_names


@pytest.mark.asyncio
async def test_history_has_project_id_column(db):
    cols = await db.fetch_all("PRAGMA table_info(history)")
    col_names = [c["name"] for c in cols]
    assert "project_id" in col_names
    assert "revision" in col_names


@pytest.mark.asyncio
async def test_workflows_have_project_id_column(db):
    cols = await db.fetch_all("PRAGMA table_info(workflows)")
    col_names = [c["name"] for c in cols]
    assert "project_id" in col_names
    assert "revision" in col_names


@pytest.mark.asyncio
async def test_project_id_indexes_exist(db):
    indexes = await db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%_project_id'"
    )
    idx_names = {i["name"] for i in indexes}
    assert "idx_collections_project_id" in idx_names
    assert "idx_requests_project_id" in idx_names
    assert "idx_environments_project_id" in idx_names
    assert "idx_history_project_id" in idx_names
    assert "idx_workflows_project_id" in idx_names
    assert "idx_export_presets_project_id" in idx_names


@pytest.mark.asyncio
async def test_insert_and_fetch_collection(db):
    await db.execute(
        "INSERT INTO collections (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("c1", "Test Collection", "A test", "2024-01-01", "2024-01-01"),
    )
    await db.commit()
    row = await db.fetch_one("SELECT * FROM collections WHERE id = ?", ("c1",))
    assert row["name"] == "Test Collection"


@pytest.mark.asyncio
async def test_insert_request_with_collection(db):
    await db.execute(
        "INSERT INTO collections (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("c1", "Test", "", "2024-01-01", "2024-01-01"),
    )
    await db.execute(
        """INSERT INTO requests (id, name, method, url, headers, query_params, body, body_type, auth_type, auth_config, collection_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("r1", "Test Request", "GET", "https://example.com", "[]", "[]", None, None, None, "{}", "c1", "2024-01-01", "2024-01-01"),
    )
    await db.commit()
    row = await db.fetch_one("SELECT * FROM requests WHERE id = ?", ("r1",))
    assert row["method"] == "GET"
    assert row["collection_id"] == "c1"


@pytest.mark.asyncio
async def test_insert_and_fetch_environment(db):
    await db.execute(
        "INSERT INTO environments (id, name, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("e1", "Development", 1, "2024-01-01", "2024-01-01"),
    )
    await db.execute(
        "INSERT INTO variables (environment_id, key, value, scope, is_secret, enabled) VALUES (?, ?, ?, ?, ?, ?)",
        ("e1", "host", "dev.example.com", "environment", 0, 1),
    )
    await db.commit()
    env = await db.fetch_one("SELECT * FROM environments WHERE id = ?", ("e1",))
    assert env["name"] == "Development"
    vars_rows = await db.fetch_all(
        "SELECT * FROM variables WHERE environment_id = ?", ("e1",)
    )
    assert len(vars_rows) == 1
    assert vars_rows[0]["key"] == "host"
