from __future__ import annotations

from datetime import datetime, timezone

from app.core.models.history import HistoryEntry, RunStatus
from app.storage.db import Database


class HistoryRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def save(self, entry: HistoryEntry) -> None:
        await self._db.execute(
            """INSERT INTO history
            (id, request_id, request_name, method, url, status, status_code,
             response_body, response_headers, duration_ms, error_message,
             environment_id, variables_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                entry.created_at or datetime.now(timezone.utc).isoformat(),
            ),
        )
        await self._db.commit()

    async def list_recent(self, limit: int = 50) -> list[dict]:
        return await self._db.fetch_all(
            "SELECT * FROM history ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )

    async def get(self, history_id: str) -> dict | None:
        return await self._db.fetch_one(
            "SELECT * FROM history WHERE id = ?", (history_id,)
        )

    async def list_by_request(self, request_id: str, limit: int = 20) -> list[dict]:
        return await self._db.fetch_all(
            "SELECT * FROM history WHERE request_id = ? ORDER BY created_at DESC LIMIT ?",
            (request_id, limit),
        )

    async def clear(self) -> int:
        cursor = await self._db.execute("DELETE FROM history")
        await self._db.commit()
        return cursor.rowcount
