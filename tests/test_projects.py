"""Tests for project-scoped workspace model.

Covers:
- Migration m005 (fresh DB, populated DB, idempotency, rollback)
- ProjectRepository CRUD and Default project resolution
- Project-scoped queries across collection, environment, history, monitor services
"""

from __future__ import annotations

import pytest

from app.core.models.project import DEFAULT_PROJECT_ID, Project
from app.services.collection_service import CollectionRepository, RequestRepository
from app.services.environment_service import EnvironmentRepository
from app.services.history_service import HistoryRepository
from app.services.monitor_service import MonitorService
from app.services.project_service import ProjectRepository
from app.storage.db import Database

# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
async def db():
    """A fresh in-memory database with all migrations applied."""
    database = Database(":memory:")
    await database.connect()
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def populated_db(db):
    """A database with some collections, requests, and environments
    all belonging to the Default project (as migrated)."""
    now = "2026-01-01T00:00:00Z"
    await db.execute(
        "INSERT INTO collections (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("col-1", "API Tests", "Test collection", now, now),
    )
    await db.execute(
        """INSERT INTO requests (id, name, method, url, headers, query_params, body, body_type, auth_type, auth_config, collection_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("req-1", "Get Users", "GET", "https://api.example.com/users", "[]", "[]", None, None, None, "{}", "col-1", now, now),
    )
    await db.execute(
        "INSERT INTO environments (id, name, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("env-1", "Development", 1, now, now),
    )
    await db.execute(
        """INSERT INTO history (id, request_id, request_name, method, url, status, status_code, response_body, response_headers, duration_ms, error_message, environment_id, variables_used, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("hist-1", "req-1", "Get Users", "GET", "https://api.example.com/users", "success", 200, '{"users":[]}', "{}", 150, None, "env-1", "{}", now),
    )
    await db.execute(
        "INSERT INTO workflows (id, name, description, steps, variables, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("wf-1", "Test Workflow", "A test", "[]", "{}", now, now),
    )
    await db.commit()
    return db


# ── Migration Tests ────────────────────────────────────────────────────

class TestMigrationFreshDB:
    """Migration on a brand-new database (tables created by SCHEMA_SQL)."""

    async def test_projects_table_created(self, db):
        tables = await db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='projects'"
        )
        assert len(tables) == 1

    async def test_default_project_seeded(self, db):
        row = await db.fetch_one(
            "SELECT * FROM projects WHERE id = ?", (DEFAULT_PROJECT_ID,)
        )
        assert row is not None
        assert row["name"] == "Default"
        assert row["is_default"] == 1

    async def test_project_id_column_on_collections(self, db):
        cols = await db.fetch_all("PRAGMA table_info(collections)")
        names = {c["name"] for c in cols}
        assert "project_id" in names
        assert "revision" in names

    async def test_project_id_column_on_requests(self, db):
        cols = await db.fetch_all("PRAGMA table_info(requests)")
        names = {c["name"] for c in cols}
        assert "project_id" in names

    async def test_project_id_column_on_environments(self, db):
        cols = await db.fetch_all("PRAGMA table_info(environments)")
        names = {c["name"] for c in cols}
        assert "project_id" in names

    async def test_project_id_column_on_history(self, db):
        cols = await db.fetch_all("PRAGMA table_info(history)")
        names = {c["name"] for c in cols}
        assert "project_id" in names

    async def test_project_id_column_on_workflows(self, db):
        cols = await db.fetch_all("PRAGMA table_info(workflows)")
        names = {c["name"] for c in cols}
        assert "project_id" in names

    async def test_indexes_created(self, db):
        indexes = await db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%_project_id'"
        )
        idx_names = {i["name"] for i in indexes}
        expected = {
            "idx_collections_project_id",
            "idx_requests_project_id",
            "idx_environments_project_id",
            "idx_history_project_id",
            "idx_workflows_project_id",
            "idx_export_presets_project_id",
        }
        assert expected.issubset(idx_names)


class TestMigrationPopulatedDB:
    """Migration on a database that already has rows (the default project
    should be assigned to all existing rows)."""

    async def test_existing_collections_assigned_to_default(self, populated_db):
        rows = await populated_db.fetch_all("SELECT project_id FROM collections")
        for row in rows:
            assert row["project_id"] == DEFAULT_PROJECT_ID

    async def test_existing_requests_assigned_to_default(self, populated_db):
        rows = await populated_db.fetch_all("SELECT project_id FROM requests")
        for row in rows:
            assert row["project_id"] == DEFAULT_PROJECT_ID

    async def test_existing_environments_assigned_to_default(self, populated_db):
        rows = await populated_db.fetch_all("SELECT project_id FROM environments")
        for row in rows:
            assert row["project_id"] == DEFAULT_PROJECT_ID

    async def test_existing_history_assigned_to_default(self, populated_db):
        rows = await populated_db.fetch_all("SELECT project_id FROM history")
        for row in rows:
            assert row["project_id"] == DEFAULT_PROJECT_ID

    async def test_existing_workflows_assigned_to_default(self, populated_db):
        rows = await populated_db.fetch_all("SELECT project_id FROM workflows")
        for row in rows:
            assert row["project_id"] == DEFAULT_PROJECT_ID

    async def test_row_counts_preserved(self, populated_db):
        cols = await populated_db.fetch_all("SELECT COUNT(*) as cnt FROM collections")
        assert cols[0]["cnt"] == 1
        reqs = await populated_db.fetch_all("SELECT COUNT(*) as cnt FROM requests")
        assert reqs[0]["cnt"] == 1
        envs = await populated_db.fetch_all("SELECT COUNT(*) as cnt FROM environments")
        assert envs[0]["cnt"] == 1
        hist = await populated_db.fetch_all("SELECT COUNT(*) as cnt FROM history")
        assert hist[0]["cnt"] == 1


class TestMigrationIdempotency:
    """Running initialize() twice should not fail or duplicate data."""

    async def test_double_init_does_not_duplicate_default_project(self):
        database = Database(":memory:")
        await database.connect()
        await database.initialize()
        await database.initialize()  # second time
        rows = await database.fetch_all("SELECT * FROM projects WHERE is_default = 1")
        assert len(rows) == 1
        await database.close()

    async def test_double_init_preserves_row_counts(self):
        database = Database(":memory:")
        await database.connect()
        await database.initialize()
        now = "2026-01-01T00:00:00Z"
        await database.execute(
            "INSERT INTO collections (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("c1", "Test", "", now, now),
        )
        await database.commit()
        await database.initialize()  # second time
        cols = await database.fetch_all("SELECT COUNT(*) as cnt FROM collections")
        assert cols[0]["cnt"] == 1
        await database.close()


class TestMigrationRollback:
    """Rollback m005 should remove the projects table but leave columns
    (SQLite < 3.35 does not support DROP COLUMN)."""

    async def test_rollback_removes_projects_table(self):
        from app.storage.migrations.m005_add_projects import AddProjects
        from app.storage.migrations.runner import MigrationRunner

        database = Database(":memory:")
        await database.connect()
        await database.initialize()

        runner = MigrationRunner(database, [AddProjects()])
        rolled = await runner.rollback_to(4)
        assert 5 in rolled

        tables = await database.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='projects'"
        )
        assert len(tables) == 0
        await database.close()

    async def test_rollback_then_reapply(self):
        from app.storage.migrations.m005_add_projects import AddProjects
        from app.storage.migrations.runner import MigrationRunner

        database = Database(":memory:")
        await database.connect()
        await database.initialize()

        runner = MigrationRunner(database, [AddProjects()])
        await runner.rollback_to(4)

        # Re-apply
        applied = await runner.run_pending()
        assert 5 in applied

        row = await database.fetch_one(
            "SELECT * FROM projects WHERE id = ?", (DEFAULT_PROJECT_ID,)
        )
        assert row is not None
        await database.close()


# ── ProjectRepository Tests ────────────────────────────────────────────

class TestProjectRepositoryCRUD:
    async def test_create_project(self, db):
        repo = ProjectRepository(db)
        proj = await repo.create("My Project", "A test project")
        assert proj.name == "My Project"
        assert proj.description == "A test project"
        assert proj.is_default is False
        assert proj.id != DEFAULT_PROJECT_ID

    async def test_list_all_returns_default_first(self, db):
        repo = ProjectRepository(db)
        await repo.create("Z Project")
        await repo.create("A Project")
        all_projects = await repo.list_all()
        assert all_projects[0].is_default is True
        assert all_projects[0].name == "Default"

    async def test_get_by_id(self, db):
        repo = ProjectRepository(db)
        proj = await repo.create("Findable")
        found = await repo.get(proj.id)
        assert found is not None
        assert found.name == "Findable"

    async def test_get_returns_none_for_missing(self, db):
        repo = ProjectRepository(db)
        found = await repo.get("nonexistent-id")
        assert found is None

    async def test_update_project(self, db):
        repo = ProjectRepository(db)
        proj = await repo.create("Old Name")
        updated = await repo.update(proj.id, {"name": "New Name"})
        assert updated is True
        found = await repo.get(proj.id)
        assert found.name == "New Name"

    async def test_cannot_update_default_project(self, db):
        repo = ProjectRepository(db)
        updated = await repo.update(DEFAULT_PROJECT_ID, {"name": "Hacked"})
        assert updated is False
        default = await repo.get_default()
        assert default.name == "Default"

    async def test_delete_project(self, db):
        repo = ProjectRepository(db)
        proj = await repo.create("Deletable")
        deleted = await repo.delete(proj.id)
        assert deleted is True
        assert await repo.get(proj.id) is None

    async def test_cannot_delete_default_project(self, db):
        repo = ProjectRepository(db)
        deleted = await repo.delete(DEFAULT_PROJECT_ID)
        assert deleted is False
        default = await repo.get_default()
        assert default is not None


class TestProjectDefaultResolution:
    async def test_get_or_default_returns_default_when_none(self, db):
        repo = ProjectRepository(db)
        proj = await repo.get_or_default(None)
        assert proj.id == DEFAULT_PROJECT_ID
        assert proj.is_default is True

    async def test_get_or_default_returns_specific_project(self, db):
        repo = ProjectRepository(db)
        created = await repo.create("Specific")
        proj = await repo.get_or_default(created.id)
        assert proj.id == created.id

    async def test_get_or_default_falls_back_for_missing_id(self, db):
        repo = ProjectRepository(db)
        proj = await repo.get_or_default("nonexistent")
        assert proj.id == DEFAULT_PROJECT_ID

    async def test_get_default_always_returns_project(self, db):
        repo = ProjectRepository(db)
        default = await repo.get_default()
        assert default.id == DEFAULT_PROJECT_ID
        assert default.name == "Default"


# ── Project-Scoped Service Tests ──────────────────────────────────────

class TestProjectScopedCollections:
    """Verify that the same collection name can exist in separate projects
    and that list_all filters by project."""

    async def test_create_collection_in_specific_project(self, db):
        proj_repo = ProjectRepository(db)
        proj = await repo_create_project(proj_repo, "Project A")
        col_repo = CollectionRepository(db)
        col = await col_repo.create("My Collection", project_id=proj.id)
        assert col["project_id"] == proj.id

    async def test_list_all_filters_by_project(self, db):
        proj_repo = ProjectRepository(db)
        proj_a = await repo_create_project(proj_repo, "A")
        proj_b = await repo_create_project(proj_repo, "B")
        col_repo = CollectionRepository(db)
        await col_repo.create("Only In A", project_id=proj_a.id)
        await col_repo.create("Only In B", project_id=proj_b.id)

        cols_a = await col_repo.list_all(project_id=proj_a.id)
        cols_b = await col_repo.list_all(project_id=proj_b.id)
        assert len(cols_a) == 1
        assert cols_a[0]["name"] == "Only In A"
        assert len(cols_b) == 1
        assert cols_b[0]["name"] == "Only In B"

    async def test_same_name_in_different_projects(self, db):
        proj_repo = ProjectRepository(db)
        proj_a = await repo_create_project(proj_repo, "A")
        proj_b = await repo_create_project(proj_repo, "B")
        col_repo = CollectionRepository(db)
        await col_repo.create("Shared Name", project_id=proj_a.id)
        await col_repo.create("Shared Name", project_id=proj_b.id)

        cols_a = await col_repo.list_all(project_id=proj_a.id)
        cols_b = await col_repo.list_all(project_id=proj_b.id)
        assert len(cols_a) == 1
        assert len(cols_b) == 1

    async def test_list_all_without_project_returns_everything(self, db):
        proj_repo = ProjectRepository(db)
        proj = await repo_create_project(proj_repo, "P")
        col_repo = CollectionRepository(db)
        await col_repo.create("Default Col")
        await col_repo.create("Project Col", project_id=proj.id)
        all_cols = await col_repo.list_all()
        assert len(all_cols) == 2


class TestProjectScopedRequests:
    async def test_create_request_with_project(self, db):
        proj_repo = ProjectRepository(db)
        proj = await repo_create_project(proj_repo, "P")
        req_repo = RequestRepository(db)
        req = await req_repo.create({
            "name": "Test",
            "method": "GET",
            "url": "https://example.com",
            "project_id": proj.id,
        })
        assert req["project_id"] == proj.id

    async def test_list_all_filters_by_project(self, db):
        proj_repo = ProjectRepository(db)
        proj_a = await repo_create_project(proj_repo, "A")
        proj_b = await repo_create_project(proj_repo, "B")
        req_repo = RequestRepository(db)
        await req_repo.create({"name": "Req A", "method": "GET", "url": "https://a.com", "project_id": proj_a.id})
        await req_repo.create({"name": "Req B", "method": "GET", "url": "https://b.com", "project_id": proj_b.id})

        reqs_a = await req_repo.list_all(project_id=proj_a.id)
        reqs_b = await req_repo.list_all(project_id=proj_b.id)
        assert len(reqs_a) == 1
        assert reqs_a[0]["name"] == "Req A"
        assert len(reqs_b) == 1


class TestProjectScopedEnvironments:
    async def test_create_environment_in_project(self, db):
        proj_repo = ProjectRepository(db)
        proj = await repo_create_project(proj_repo, "P")
        env_repo = EnvironmentRepository(db)
        env = await env_repo.create("Staging", project_id=proj.id)
        assert env["project_id"] == proj.id

    async def test_list_all_filters_by_project(self, db):
        proj_repo = ProjectRepository(db)
        proj_a = await repo_create_project(proj_repo, "A")
        proj_b = await repo_create_project(proj_repo, "B")
        env_repo = EnvironmentRepository(db)
        await env_repo.create("Env A", project_id=proj_a.id)
        await env_repo.create("Env B", project_id=proj_b.id)

        envs_a = await env_repo.list_all(project_id=proj_a.id)
        envs_b = await env_repo.list_all(project_id=proj_b.id)
        assert len(envs_a) == 1
        assert envs_a[0]["name"] == "Env A"
        assert len(envs_b) == 1

    async def test_get_active_scoped_to_project(self, db):
        proj_repo = ProjectRepository(db)
        proj_a = await repo_create_project(proj_repo, "A")
        proj_b = await repo_create_project(proj_repo, "B")
        env_repo = EnvironmentRepository(db)
        env_a = await env_repo.create("Active A", project_id=proj_a.id)
        env_b = await env_repo.create("Active B", project_id=proj_b.id)
        await env_repo.set_active(env_a["id"], project_id=proj_a.id)
        await env_repo.set_active(env_b["id"], project_id=proj_b.id)

        active_a = await env_repo.get_active(project_id=proj_a.id)
        active_b = await env_repo.get_active(project_id=proj_b.id)
        assert active_a["id"] == env_a["id"]
        assert active_b["id"] == env_b["id"]


class TestProjectScopedHistory:
    async def test_save_and_list_filtered_by_project(self, db):
        from app.core.models.history import HistoryEntry, RunStatus

        proj_repo = ProjectRepository(db)
        proj = await repo_create_project(proj_repo, "P")
        hist_repo = HistoryRepository(db)

        entry = HistoryEntry(
            id="h1",
            request_id="r1",
            request_name="Test",
            method="GET",
            url="https://example.com",
            status=RunStatus.SUCCESS,
            status_code=200,
        )
        await hist_repo.save(entry, project_id=proj.id)

        # List scoped to project
        scoped = await hist_repo.list_recent(project_id=proj.id)
        assert len(scoped) == 1
        assert scoped[0]["id"] == "h1"

        # List scoped to different project should be empty
        other = await hist_repo.list_recent(project_id="other-project")
        assert len(other) == 0

    async def test_clear_scoped_to_project(self, db):
        from app.core.models.history import HistoryEntry, RunStatus

        proj_repo = ProjectRepository(db)
        proj_a = await repo_create_project(proj_repo, "A")
        proj_b = await repo_create_project(proj_repo, "B")
        hist_repo = HistoryRepository(db)

        for pid, hid in [(proj_a.id, "h-a"), (proj_b.id, "h-b")]:
            entry = HistoryEntry(
                id=hid, request_id="r1", request_name="T",
                method="GET", url="https://x.com", status=RunStatus.SUCCESS,
            )
            await hist_repo.save(entry, project_id=pid)

        cleared = await hist_repo.clear(project_id=proj_a.id)
        assert cleared == 1
        assert len(await hist_repo.list_recent(project_id=proj_a.id)) == 0
        assert len(await hist_repo.list_recent(project_id=proj_b.id)) == 1


class TestProjectScopedMonitors:
    async def test_create_monitor_in_project(self, db):
        proj_repo = ProjectRepository(db)
        proj = await repo_create_project(proj_repo, "P")
        mon_repo = MonitorService(db)
        monitor = await mon_repo.create("Test Monitor", "https://example.com", project_id=proj.id)
        assert monitor.id is not None

    async def test_list_monitors_filtered_by_project(self, db):
        proj_repo = ProjectRepository(db)
        proj_a = await repo_create_project(proj_repo, "A")
        proj_b = await repo_create_project(proj_repo, "B")
        mon_repo = MonitorService(db)
        await mon_repo.create("Mon A", "https://a.com", project_id=proj_a.id)
        await mon_repo.create("Mon B", "https://b.com", project_id=proj_b.id)

        mons_a = await mon_repo.list_all(project_id=proj_a.id)
        mons_b = await mon_repo.list_all(project_id=proj_b.id)
        assert len(mons_a) == 1
        assert mons_a[0].name == "Mon A"
        assert len(mons_b) == 1


# ── Helpers ────────────────────────────────────────────────────────────

async def repo_create_project(repo: ProjectRepository, name: str) -> Project:
    """Shorthand for tests that just need a project quickly."""
    return await repo.create(name)
