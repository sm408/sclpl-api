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
        return {"id": cid, "name": name, "description": description, "created_at": now, "project_id": pid, "revision": 1}

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

    async def update(self, collection_id: str, data: dict, revision: int | None = None) -> dict | None:
        """Update a collection. Returns updated dict or None if not found or revision mismatch."""
        existing = await self.get(collection_id)
        if not existing:
            return None
        if revision is not None and existing.get("revision", 1) != revision:
            return None  # Revision mismatch — caller should raise ConflictError
        now = datetime.now(timezone.utc).isoformat()
        fields = []
        values = []
        if "name" in data and data["name"] is not None:
            fields.append("name = ?")
            values.append(data["name"])
        if "description" in data and data["description"] is not None:
            fields.append("description = ?")
            values.append(data["description"])
        new_rev = (existing.get("revision", 1) or 1) + 1
        fields.append("revision = ?")
        values.append(new_rev)
        fields.append("updated_at = ?")
        values.append(now)
        values.append(collection_id)
        sql = f"UPDATE collections SET {', '.join(fields)} WHERE id = ?"
        await self._db.execute(sql, tuple(values))
        await self._db.commit()
        return await self.get(collection_id)

    async def duplicate(self, collection_id: str, new_name: str | None = None) -> dict | None:
        """Duplicate a collection and all its requests. Returns the new collection dict."""
        source = await self.get(collection_id)
        if not source:
            return None
        name = new_name or f"{source['name']} (copy)"
        new_col = await self.create(
            name=name,
            description=source.get("description", ""),
            project_id=source.get("project_id"),
        )
        # Duplicate all requests in the collection
        requests = await self._db.fetch_all(
            "SELECT * FROM requests WHERE collection_id = ?", (collection_id,)
        )
        now = datetime.now(timezone.utc).isoformat()
        for req in requests:
            new_rid = str(uuid.uuid4())
            await self._db.execute(
                """INSERT INTO requests
                (id, name, method, url, headers, query_params, body, body_type, auth_type, auth_config, collection_id, project_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_rid, req["name"], req["method"], req["url"],
                    req["headers"], req["query_params"], req.get("body"),
                    req.get("body_type"), req.get("auth_type"), req.get("auth_config", "{}"),
                    new_col["id"], new_col["project_id"], now, now,
                ),
            )
        await self._db.commit()
        return new_col

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
                data.get("method", "GET"),
                data.get("url", ""),
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
        return {**data, "id": rid, "created_at": now, "updated_at": now, "project_id": project_id, "revision": 1}

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

    async def update(self, request_id: str, data: dict, revision: int | None = None) -> dict | None:
        """Update a request. Returns updated dict or None if not found or revision mismatch."""
        existing = await self.get(request_id)
        if not existing:
            return None
        if revision is not None and existing.get("revision", 1) != revision:
            return None  # Revision mismatch
        now = datetime.now(timezone.utc).isoformat()
        fields = []
        values = []
        for key in ("name", "method", "url", "body", "body_type", "auth_type", "collection_id"):
            if key in data and data[key] is not None:
                fields.append(f"{key} = ?")
                values.append(data[key])
        for key in ("headers", "query_params", "auth_config"):
            if key in data and data[key] is not None:
                fields.append(f"{key} = ?")
                values.append(json.dumps(data[key]))
        new_rev = (existing.get("revision", 1) or 1) + 1
        fields.append("revision = ?")
        values.append(new_rev)
        fields.append("updated_at = ?")
        values.append(now)
        values.append(request_id)
        sql = f"UPDATE requests SET {', '.join(fields)} WHERE id = ?"
        cursor = await self._db.execute(sql, tuple(values))
        await self._db.commit()
        if cursor.rowcount > 0:
            return await self.get(request_id)
        return None

    async def move(self, request_id: str, target_collection_id: str | None) -> dict | None:
        """Move a request to a different collection."""
        return await self.update(request_id, {"collection_id": target_collection_id})

    async def delete(self, request_id: str) -> bool:
        cursor = await self._db.execute(
            "DELETE FROM requests WHERE id = ?", (request_id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0
