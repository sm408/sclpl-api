from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.models.project import DEFAULT_PROJECT_ID
from app.storage.db import Database


class EnvironmentRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, name: str, project_id: str | None = None) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        eid = str(uuid.uuid4())
        pid = project_id or DEFAULT_PROJECT_ID
        await self._db.execute(
            "INSERT INTO environments (id, name, is_active, project_id, created_at, updated_at) VALUES (?, ?, 0, ?, ?, ?)",
            (eid, name, pid, now, now),
        )
        await self._db.commit()
        return {"id": eid, "name": name, "is_active": False, "created_at": now, "project_id": pid}

    async def list_all(self, project_id: str | None = None) -> list[dict]:
        if project_id:
            envs = await self._db.fetch_all(
                "SELECT * FROM environments WHERE project_id = ? ORDER BY name",
                (project_id,),
            )
        else:
            envs = await self._db.fetch_all("SELECT * FROM environments ORDER BY name")
        for env in envs:
            env["variables"] = await self._db.fetch_all(
                "SELECT * FROM variables WHERE environment_id = ?", (env["id"],)
            )
        return envs

    async def get(self, env_id: str) -> dict | None:
        env = await self._db.fetch_one(
            "SELECT * FROM environments WHERE id = ?", (env_id,)
        )
        if env:
            env["variables"] = await self._db.fetch_all(
                "SELECT * FROM variables WHERE environment_id = ?", (env_id,)
            )
        return env

    async def get_active(self, project_id: str | None = None) -> dict | None:
        if project_id:
            env = await self._db.fetch_one(
                "SELECT * FROM environments WHERE is_active = 1 AND project_id = ?",
                (project_id,),
            )
        else:
            env = await self._db.fetch_one(
                "SELECT * FROM environments WHERE is_active = 1"
            )
        if env:
            env["variables"] = await self._db.fetch_all(
                "SELECT * FROM variables WHERE environment_id = ?", (env["id"],)
            )
        return env

    async def set_active(self, env_id: str, project_id: str | None = None) -> None:
        if project_id:
            await self._db.execute(
                "UPDATE environments SET is_active = 0 WHERE project_id = ?", (project_id,)
            )
            await self._db.execute(
                "UPDATE environments SET is_active = 1 WHERE id = ? AND project_id = ?", (env_id, project_id)
            )
        else:
            await self._db.execute("UPDATE environments SET is_active = 0")
            await self._db.execute(
                "UPDATE environments SET is_active = 1 WHERE id = ?", (env_id,)
            )
        await self._db.commit()

    async def delete(self, env_id: str) -> bool:
        cursor = await self._db.execute(
            "DELETE FROM environments WHERE id = ?", (env_id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def update(self, env_id: str, data: dict) -> dict | None:
        """Update environment name. Returns updated dict or None if not found."""
        existing = await self._db.fetch_one(
            "SELECT * FROM environments WHERE id = ?", (env_id,)
        )
        if not existing:
            return None
        now = datetime.now(timezone.utc).isoformat()
        fields = []
        values = []
        if "name" in data and data["name"] is not None:
            fields.append("name = ?")
            values.append(data["name"])
        if fields:
            new_rev = (existing.get("revision", 1) or 1) + 1
            fields.append("revision = ?")
            values.append(new_rev)
            fields.append("updated_at = ?")
            values.append(now)
            values.append(env_id)
            sql = f"UPDATE environments SET {', '.join(fields)} WHERE id = ?"
            await self._db.execute(sql, tuple(values))
            await self._db.commit()
        return await self.get(env_id)

    async def set_variables(self, env_id: str, variables: list[dict]) -> None:
        """Replace all variables for an environment."""
        await self._db.execute(
            "DELETE FROM variables WHERE environment_id = ?", (env_id,)
        )
        for var in variables:
            await self._db.execute(
                "INSERT INTO variables (environment_id, key, value, scope, is_secret) VALUES (?, ?, ?, 'environment', ?)",
                (env_id, var["key"], var["value"], int(var.get("is_secret", False))),
            )
        await self._db.commit()

    async def set_variable(
        self, env_id: str, key: str, value: str, is_secret: bool = False
    ) -> None:
        existing = await self._db.fetch_one(
            "SELECT id FROM variables WHERE environment_id = ? AND key = ?",
            (env_id, key),
        )
        if existing:
            await self._db.execute(
                "UPDATE variables SET value = ?, is_secret = ? WHERE id = ?",
                (value, int(is_secret), existing["id"]),
            )
        else:
            await self._db.execute(
                "INSERT INTO variables (environment_id, key, value, scope, is_secret) VALUES (?, ?, ?, 'environment', ?)",
                (env_id, key, value, int(is_secret)),
            )
        await self._db.commit()

    async def delete_variable(self, env_id: str, key: str) -> bool:
        cursor = await self._db.execute(
            "DELETE FROM variables WHERE environment_id = ? AND key = ?",
            (env_id, key),
        )
        await self._db.commit()
        return cursor.rowcount > 0
