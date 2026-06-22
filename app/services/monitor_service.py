"""Monitor service for CRUD operations."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.models.monitor import Monitor, MonitorEvent, MonitorStatus, NotificationMode
from app.storage.db import Database


class MonitorService:
    """Service for managing monitors."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(
        self,
        name: str,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str | None = None,
        interval_seconds: int = 60,
        condition: str = "",
        notification_on: str = "change",
        project_id: str | None = None,
    ) -> Monitor:
        """Create a new monitor."""
        now = datetime.now(timezone.utc).isoformat()
        monitor_id = str(uuid.uuid4())

        if project_id:
            await self._db.execute(
                """INSERT INTO monitors
                (id, name, url, method, headers, body, interval_seconds, condition,
                 notification_on, enabled, status, run_count, trigger_count, project_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    monitor_id, name, url, method,
                    json.dumps(headers or {}),
                    body, interval_seconds, condition,
                    notification_on, True, MonitorStatus.STOPPED.value,
                    0, 0, project_id, now, now,
                ),
            )
        else:
            await self._db.execute(
                """INSERT INTO monitors
                (id, name, url, method, headers, body, interval_seconds, condition,
                 notification_on, enabled, status, run_count, trigger_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    monitor_id, name, url, method,
                    json.dumps(headers or {}),
                    body, interval_seconds, condition,
                    notification_on, True, MonitorStatus.STOPPED.value,
                    0, 0, now, now,
                ),
            )
        await self._db.commit()

        return Monitor(
            id=monitor_id,
            name=name,
            url=url,
            method=method,
            headers=headers or {},
            body=body,
            interval_seconds=interval_seconds,
            condition=condition,
            notification_on=NotificationMode(notification_on),
            enabled=True,
            status=MonitorStatus.STOPPED,
            created_at=now,
            updated_at=now,
        )

    async def list_all(self, project_id: str | None = None) -> list[Monitor]:
        """List all monitors."""
        if project_id:
            rows = await self._db.fetch_all(
                "SELECT * FROM monitors WHERE project_id = ? ORDER BY name",
                (project_id,),
            )
        else:
            rows = await self._db.fetch_all("SELECT * FROM monitors ORDER BY name")
        return [self._row_to_monitor(row) for row in rows]

    async def get(self, monitor_id: str) -> Monitor | None:
        """Get a monitor by ID."""
        row = await self._db.fetch_one(
            "SELECT * FROM monitors WHERE id = ?", (monitor_id,)
        )
        return self._row_to_monitor(row) if row else None

    async def update(self, monitor_id: str, data: dict[str, Any]) -> bool:
        """Update a monitor."""
        now = datetime.now(timezone.utc).isoformat()
        fields = []
        values = []

        for key in ("name", "url", "method", "body", "interval_seconds", "condition",
                     "notification_on", "enabled"):
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])

        if "headers" in data:
            fields.append("headers = ?")
            values.append(json.dumps(data["headers"]))

        if "status" in data:
            fields.append("status = ?")
            values.append(data["status"].value if isinstance(data["status"], MonitorStatus) else data["status"])

        fields.append("updated_at = ?")
        values.append(now)
        values.append(monitor_id)

        sql = f"UPDATE monitors SET {', '.join(fields)} WHERE id = ?"
        cursor = await self._db.execute(sql, tuple(values))
        await self._db.commit()
        return cursor.rowcount > 0

    async def delete(self, monitor_id: str) -> bool:
        """Delete a monitor."""
        cursor = await self._db.execute(
            "DELETE FROM monitors WHERE id = ?", (monitor_id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def set_status(self, monitor_id: str, status: MonitorStatus) -> None:
        """Update monitor status."""
        await self.update(monitor_id, {"status": status})

    async def record_run(
        self,
        monitor_id: str,
        status_code: int | None,
        body: str | None,
        error: str | None = None,
    ) -> None:
        """Record a monitor run."""
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            """UPDATE monitors SET
            last_run = ?, last_status_code = ?, last_body = ?, last_error = ?,
            run_count = run_count + 1, updated_at = ?
            WHERE id = ?""",
            (now, status_code, body[:5000] if body else None, error, now, monitor_id),
        )
        await self._db.commit()

    async def record_trigger(self, monitor_id: str) -> None:
        """Record a monitor trigger."""
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            """UPDATE monitors SET
            last_changed = ?, trigger_count = trigger_count + 1, updated_at = ?
            WHERE id = ?""",
            (now, now, monitor_id),
        )
        await self._db.commit()

    # ── Monitor Events ───────────────────────────────────────────────────

    async def save_event(self, event: MonitorEvent) -> None:
        """Save a monitor event."""
        await self._db.execute(
            """INSERT INTO monitor_events
            (id, monitor_id, monitor_name, event_type, status_code, body,
             condition_met, changed, error, duration_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.id, event.monitor_id, event.monitor_name, event.event_type,
                event.status_code, event.body[:5000] if event.body else None,
                event.condition_met, event.changed, event.error,
                event.duration_ms, event.created_at,
            ),
        )
        await self._db.commit()

    async def get_events(self, monitor_id: str, limit: int = 50) -> list[MonitorEvent]:
        """Get events for a monitor."""
        rows = await self._db.fetch_all(
            "SELECT * FROM monitor_events WHERE monitor_id = ? ORDER BY created_at DESC LIMIT ?",
            (monitor_id, limit),
        )
        return [self._row_to_event(row) for row in rows]

    async def clear_events(self, monitor_id: str) -> None:
        """Clear events for a monitor."""
        await self._db.execute(
            "DELETE FROM monitor_events WHERE monitor_id = ?", (monitor_id,)
        )
        await self._db.commit()

    # ── Helpers ──────────────────────────────────────────────────────────

    def _row_to_monitor(self, row: dict) -> Monitor:
        """Convert a database row to a Monitor."""
        headers = row.get("headers", "{}")
        if isinstance(headers, str):
            try:
                headers = json.loads(headers)
            except (json.JSONDecodeError, TypeError):
                headers = {}

        return Monitor(
            id=row["id"],
            name=row["name"],
            url=row["url"],
            method=row.get("method", "GET"),
            headers=headers,
            body=row.get("body"),
            interval_seconds=row.get("interval_seconds", 60),
            condition=row.get("condition", ""),
            notification_on=NotificationMode(row.get("notification_on", "change")),
            enabled=bool(row.get("enabled", True)),
            status=MonitorStatus(row.get("status", "stopped")),
            last_run=row.get("last_run"),
            last_status_code=row.get("last_status_code"),
            last_body=row.get("last_body"),
            last_error=row.get("last_error"),
            last_changed=row.get("last_changed"),
            run_count=row.get("run_count", 0),
            trigger_count=row.get("trigger_count", 0),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
        )

    def _row_to_event(self, row: dict) -> MonitorEvent:
        """Convert a database row to a MonitorEvent."""
        return MonitorEvent(
            id=row["id"],
            monitor_id=row["monitor_id"],
            monitor_name=row["monitor_name"],
            event_type=row["event_type"],
            status_code=row.get("status_code"),
            body=row.get("body"),
            condition_met=bool(row.get("condition_met", False)),
            changed=bool(row.get("changed", False)),
            error=row.get("error"),
            duration_ms=row.get("duration_ms", 0),
            created_at=row.get("created_at", ""),
        )
