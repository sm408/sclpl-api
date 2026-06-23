from __future__ import annotations

from datetime import datetime, timezone

from app.core.models.history import HistoryEntry, RunStatus
from app.core.models.project import DEFAULT_PROJECT_ID
from app.storage.db import Database


class HistoryRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def save(self, entry: HistoryEntry, project_id: str | None = None) -> None:
        pid = project_id or DEFAULT_PROJECT_ID
        await self._db.execute(
            """INSERT INTO history
            (id, request_id, request_name, method, url, status, status_code,
             response_body, response_headers, duration_ms, error_message,
             environment_id, variables_used, project_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.id,
                entry.request_id,
                entry.request_name,
                entry.method,
                entry.url,
                entry.status.value,
                entry.status_code,
                entry.response_body,
                str(entry.response_headers),
                entry.duration_ms,
                entry.error_message,
                entry.environment_id,
                str(entry.variables_used),
                pid,
                entry.created_at or datetime.now(timezone.utc).isoformat(),
            ),
        )
        await self._db.commit()

    async def list_recent(self, limit: int = 50, project_id: str | None = None) -> list[dict]:
        if project_id:
            return await self._db.fetch_all(
                "SELECT * FROM history WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                (project_id, limit),
            )
        return await self._db.fetch_all(
            "SELECT * FROM history ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )

    async def list_paginated(
        self,
        project_id: str,
        *,
        cursor: str | None = None,
        limit: int = 50,
        request_id: str | None = None,
    ) -> tuple[list[dict], str | None]:
        """Cursor-based pagination.

        Returns (items, next_cursor).  Cursor is the created_at of the last
        item in the previous page.
        """
        if request_id:
            if cursor:
                rows = await self._db.fetch_all(
                    """SELECT * FROM history
                    WHERE project_id = ? AND request_id = ? AND created_at < ?
                    ORDER BY created_at DESC LIMIT ?""",
                    (project_id, request_id, cursor, limit + 1),
                )
            else:
                rows = await self._db.fetch_all(
                    """SELECT * FROM history
                    WHERE project_id = ? AND request_id = ?
                    ORDER BY created_at DESC LIMIT ?""",
                    (project_id, request_id, limit + 1),
                )
        else:
            if cursor:
                rows = await self._db.fetch_all(
                    """SELECT * FROM history
                    WHERE project_id = ? AND created_at < ?
                    ORDER BY created_at DESC LIMIT ?""",
                    (project_id, cursor, limit + 1),
                )
            else:
                rows = await self._db.fetch_all(
                    """SELECT * FROM history
                    WHERE project_id = ?
                    ORDER BY created_at DESC LIMIT ?""",
                    (project_id, limit + 1),
                )
        next_cursor = None
        if len(rows) > limit:
            next_cursor = rows[limit - 1]["created_at"]
            rows = rows[:limit]
        return rows, next_cursor

    async def get(self, history_id: str) -> dict | None:
        return await self._db.fetch_one(
            "SELECT * FROM history WHERE id = ?", (history_id,)
        )

    async def list_by_request(self, request_id: str, limit: int = 20) -> list[dict]:
        return await self._db.fetch_all(
            "SELECT * FROM history WHERE request_id = ? ORDER BY created_at DESC LIMIT ?",
            (request_id, limit),
        )

    async def count(self, project_id: str | None = None) -> int:
        if project_id:
            row = await self._db.fetch_one(
                "SELECT COUNT(*) as cnt FROM history WHERE project_id = ?", (project_id,)
            )
        else:
            row = await self._db.fetch_one("SELECT COUNT(*) as cnt FROM history")
        return row["cnt"] if row else 0

    async def clear(self, project_id: str | None = None) -> int:
        if project_id:
            cursor = await self._db.execute(
                "DELETE FROM history WHERE project_id = ?", (project_id,)
            )
        else:
            cursor = await self._db.execute("DELETE FROM history")
        await self._db.commit()
        return cursor.rowcount
