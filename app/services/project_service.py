"""Project repository for CRUD operations and Default project resolution."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.models.project import DEFAULT_PROJECT_ID, Project, ensure_project_dirs
from app.storage.db import Database


class ProjectRepository:
    """Manage projects and resolve the Default project for backward compatibility."""

    def __init__(self, db: Database, data_root: Path | str = "data") -> None:
        self._db = db
        self._data_root = Path(data_root)

    # ── CRUD ──────────────────────────────────────────────────────────

    async def create(
        self,
        name: str,
        description: str = "",
        project_id: str | None = None,
    ) -> Project:
        """Create a new project.  Returns the created Project."""
        now = datetime.now(timezone.utc).isoformat()
        pid = project_id or str(uuid.uuid4())
        root_path = f"data/projects/{pid}"

        await self._db.execute(
            """INSERT INTO projects
            (id, name, description, root_path, is_default, created_at, updated_at)
            VALUES (?, ?, ?, ?, 0, ?, ?)""",
            (pid, name, description, root_path, now, now),
        )
        await self._db.commit()

        # Create on-disk directories for the new project.
        ensure_project_dirs(self._data_root / "projects" / pid)

        return Project(
            id=pid,
            name=name,
            description=description,
            root_path=root_path,
            is_default=False,
            created_at=now,
            updated_at=now,
        )

    async def list_all(self) -> list[Project]:
        """Return every project, Default first."""
        rows = await self._db.fetch_all(
            "SELECT * FROM projects ORDER BY is_default DESC, name"
        )
        return [self._row_to_project(r) for r in rows]

    async def get(self, project_id: str) -> Project | None:
        row = await self._db.fetch_one(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        )
        return self._row_to_project(row) if row else None

    async def get_or_default(self, project_id: str | None) -> Project:
        """Return *project_id* if given, otherwise the Default project.

        This is the primary entry-point for services that want to
        scope their queries — callers can always pass ``None`` and
        get back the Default project transparently.
        """
        if project_id:
            proj = await self.get(project_id)
            if proj:
                return proj
        return await self.get_default()

    async def get_default(self) -> Project:
        """Return the well-known Default project, creating it if missing."""
        row = await self._db.fetch_one(
            "SELECT * FROM projects WHERE id = ?", (DEFAULT_PROJECT_ID,)
        )
        if row:
            return self._row_to_project(row)

        # First-run on an existing DB before m005 ran — create it now.
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            """INSERT OR IGNORE INTO projects
            (id, name, description, root_path, is_default, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (DEFAULT_PROJECT_ID, "Default", "Default workspace", "", 1, now, now),
        )
        await self._db.commit()
        return Project(
            id=DEFAULT_PROJECT_ID,
            name="Default",
            description="Default workspace",
            root_path="",
            is_default=True,
            created_at=now,
            updated_at=now,
        )

    async def update(self, project_id: str, data: dict) -> bool:
        """Update project name and/or description.  Cannot change is_default."""
        now = datetime.now(timezone.utc).isoformat()
        fields = []
        values = []
        for key in ("name", "description"):
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        if not fields:
            return False
        fields.append("updated_at = ?")
        values.append(now)
        values.append(project_id)
        sql = f"UPDATE projects SET {', '.join(fields)} WHERE id = ? AND is_default = 0"
        cursor = await self._db.execute(sql, tuple(values))
        await self._db.commit()
        return cursor.rowcount > 0

    async def delete(self, project_id: str) -> bool:
        """Delete a non-default project.  Returns False for the Default project."""
        if project_id == DEFAULT_PROJECT_ID:
            return False
        cursor = await self._db.execute(
            "DELETE FROM projects WHERE id = ? AND is_default = 0",
            (project_id,),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    # ── Helpers ───────────────────────────────────────────────────────

    def _row_to_project(self, row: dict) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            description=row.get("description", ""),
            root_path=row.get("root_path", ""),
            is_default=bool(row.get("is_default", 0)),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
