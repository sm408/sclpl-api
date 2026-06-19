import pytest

from app.storage.db import Database


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
    assert row["version"] == 4


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
