from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.storage.db import Database


class EnvironmentRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, name: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        eid = str(uuid.uuid4())
        await self._db.execute(
            "INSERT INTO environments (id, name, is_active, created_at, updated_at) VALUES (?, ?, 0, ?, ?)",
            (eid, name, now, now),
        )
        await self._db.commit()
        return {"id": eid, "name": name, "is_active": False, "created_at": now}

    async def list_all(self) -> list[dict]:
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

    async def get_active(self) -> dict | None:
        env = await self._db.fetch_one(
            "SELECT * FROM environments WHERE is_active = 1"
        )
        if env:
            env["variables"] = await self._db.fetch_all(
                "SELECT * FROM variables WHERE environment_id = ?", (env["id"],)
            )
        return env

    async def set_active(self, env_id: str) -> None:
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
