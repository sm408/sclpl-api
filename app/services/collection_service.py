from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.core.models.project import DEFAULT_PROJECT_ID
from app.storage.db import Database


class CollectionRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, name: str, description: str = "", project_id: str | None = None) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        cid = str(uuid.uuid4())
        pid = project_id or DEFAULT_PROJECT_ID
        await self._db.execute(
            "INSERT INTO collections (id, name, description, project_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (cid, name, description, pid, now, now),
        )
        await self._db.commit()
        return {"id": cid, "name": name, "description": description, "created_at": now, "project_id": pid}

    async def list_all(self, project_id: str | None = None) -> list[dict]:
        if project_id:
            return await self._db.fetch_all(
                "SELECT * FROM collections WHERE project_id = ? ORDER BY name",
                (project_id,),
            )
        return await self._db.fetch_all("SELECT * FROM collections ORDER BY name")

    async def get(self, collection_id: str) -> dict | None:
        return await self._db.fetch_one(
            "SELECT * FROM collections WHERE id = ?", (collection_id,)
        )

    async def delete(self, collection_id: str) -> bool:
        cursor = await self._db.execute(
            "DELETE FROM collections WHERE id = ?", (collection_id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0


class RequestRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, data: dict) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        rid = data.get("id", str(uuid.uuid4()))
        project_id = data.get("project_id") or DEFAULT_PROJECT_ID
        await self._db.execute(
            """INSERT INTO requests
            (id, name, method, url, headers, query_params, body, body_type, auth_type, auth_config, collection_id, project_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rid,
                data["name"],
                data["method"],
                data["url"],
                json.dumps(data.get("headers", [])),
                json.dumps(data.get("query_params", [])),
                data.get("body"),
                data.get("body_type"),
                data.get("auth_type"),
                json.dumps(data.get("auth_config", {})),
                data.get("collection_id"),
                project_id,
                now,
                now,
            ),
        )
        await self._db.commit()
        return {**data, "id": rid, "created_at": now, "project_id": project_id}

    async def list_all(self, collection_id: str | None = None, project_id: str | None = None) -> list[dict]:
        if collection_id:
            return await self._db.fetch_all(
                "SELECT * FROM requests WHERE collection_id = ? ORDER BY name",
                (collection_id,),
            )
        if project_id:
            return await self._db.fetch_all(
                "SELECT * FROM requests WHERE project_id = ? ORDER BY name",
                (project_id,),
            )
        return await self._db.fetch_all("SELECT * FROM requests ORDER BY name")

    async def get(self, request_id: str) -> dict | None:
        return await self._db.fetch_one(
            "SELECT * FROM requests WHERE id = ?", (request_id,)
        )

    async def update(self, request_id: str, data: dict) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        fields = []
        values = []
        for key in ("name", "method", "url", "body", "body_type", "auth_type", "collection_id"):
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        for key in ("headers", "query_params", "auth_config"):
            if key in data:
                fields.append(f"{key} = ?")
                values.append(json.dumps(data[key]))
        fields.append("updated_at = ?")
        values.append(now)
        values.append(request_id)
        sql = f"UPDATE requests SET {', '.join(fields)} WHERE id = ?"
        cursor = await self._db.execute(sql, tuple(values))
        await self._db.commit()
        return cursor.rowcount > 0

    async def delete(self, request_id: str) -> bool:
        cursor = await self._db.execute(
            "DELETE FROM requests WHERE id = ?", (request_id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0
