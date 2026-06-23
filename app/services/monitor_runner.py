"""Monitor runner for background API polling."""

from __future__ import annotations

import asyncio
import operator
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.contracts.event_bus import Event, EventBus
from app.core.models.monitor import Monitor, MonitorEvent, MonitorStatus, NotificationMode
from app.services.monitor_service import MonitorService

# ── Condition evaluator ──────────────────────────────────────────────────────

OPS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
}


def evaluate_condition(condition: str, status_code: int, body: Any, headers: dict) -> bool:
    """Evaluate a condition against a response.

    Supported syntax:
        status == 200
        body.price > 100
        body.items.length > 0
        body.status == "active"
    """
    if not condition:
        return True

    try:
        parts = condition.split()
        if len(parts) != 3:
            return False

        left, op, right = parts

        # Get left value
        if left == "status":
            left_val = status_code
        elif left.startswith("body."):
            path = left[5:]  # Remove "body."
            left_val = _get_nested(body, path)
        elif left.startswith("headers."):
            key = left[8:]
            left_val = headers.get(key)
        else:
            return False

        # Parse right value
        if right.startswith('"') and right.endswith('"') or right.startswith("'") and right.endswith("'"):
            right_val = right[1:-1]
        elif right == "null":
            right_val = None
        elif right == "true":
            right_val = True
        elif right == "false":
            right_val = False
        else:
            try:
                right_val = int(right)
            except ValueError:
                try:
                    right_val = float(right)
                except ValueError:
                    right_val = right

        # Evaluate
        if op in OPS:
            return OPS[op](left_val, right_val)

        return False

    except Exception:
        return False


def _get_nested(data: Any, path: str) -> Any:
    """Get a nested value from a dict/list using dot notation."""
    if data is None:
        return None

    parts = path.split(".")
    current = data

    for part in parts:
        if current is None:
            return None

        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            if part == "length":
                return len(current)
            try:
                idx = int(part)
                current = current[idx] if 0 <= idx < len(current) else None
            except (ValueError, IndexError):
                return None
        else:
            return None

    return current


# ── Monitor Runner ───────────────────────────────────────────────────────────


class MonitorRunner:
    """Runs monitors in background, publishes events."""

    def __init__(
        self,
        monitor_service: MonitorService,
        event_bus: EventBus,
    ) -> None:
        self._service = monitor_service
        self._event_bus = event_bus
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False
        self._previous_bodies: dict[str, str] = {}

    async def start(self) -> None:
        """Start all enabled monitors."""
        self._running = True
        monitors = await self._service.list_all()
        for monitor in monitors:
            if monitor.enabled and monitor.status != MonitorStatus.RUNNING:
                await self.start_monitor(monitor.id)

    async def stop(self) -> None:
        """Stop all monitors."""
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()

    async def start_monitor(self, monitor_id: str) -> None:
        """Start a single monitor."""
        monitor = await self._service.get(monitor_id)
        if not monitor:
            return

        await self._service.set_status(monitor_id, MonitorStatus.RUNNING)

        task = asyncio.create_task(self._run_monitor(monitor))
        self._tasks[monitor_id] = task

        self._event_bus.publish(Event(
            name="monitor.started",
            data={"monitor_id": monitor_id, "monitor_name": monitor.name},
        ))

    async def stop_monitor(self, monitor_id: str) -> None:
        """Stop a single monitor."""
        task = self._tasks.pop(monitor_id, None)
        if task:
            task.cancel()

        await self._service.set_status(monitor_id, MonitorStatus.STOPPED)

        monitor = await self._service.get(monitor_id)
        if monitor:
            self._event_bus.publish(Event(
                name="monitor.stopped",
                data={"monitor_id": monitor_id, "monitor_name": monitor.name},
            ))

    async def _run_monitor(self, monitor: Monitor) -> None:
        """Poll loop for a single monitor."""
        try:
            while self._running and monitor.enabled:
                await self._poll(monitor)

                # Re-fetch to check if still enabled
                monitor = await self._service.get(monitor.id)
                if not monitor or not monitor.enabled:
                    break

                await asyncio.sleep(monitor.interval_seconds)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self._service.set_status(monitor.id, MonitorStatus.ERROR)
            await self._save_event(monitor, "error", error=str(e))

    async def _poll(self, monitor: Monitor) -> None:
        """Execute a single poll."""
        start_time = time.monotonic()

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.request(
                    method=monitor.method,
                    url=monitor.url,
                    headers=monitor.headers if monitor.headers else None,
                    content=monitor.body if monitor.body else None,
                )

                duration_ms = int((time.monotonic() - start_time) * 1000)
                status_code = response.status_code

                # Parse body
                try:
                    body_json = response.json()
                    body_str = response.text
                except Exception:
                    body_json = None
                    body_str = response.text

                # Record run
                await self._service.record_run(monitor.id, status_code, body_str)

                # Check for changes
                previous_body = self._previous_bodies.get(monitor.id)
                changed = previous_body is not None and body_str != previous_body
                self._previous_bodies[monitor.id] = body_str

                # Evaluate condition
                condition_met = evaluate_condition(
                    monitor.condition, status_code, body_json, dict(response.headers)
                )

                # Determine if should notify
                should_notify = False
                if monitor.notification_on == NotificationMode.ALWAYS or monitor.notification_on == NotificationMode.CHANGE and changed or monitor.notification_on == NotificationMode.CONDITION and condition_met:
                    should_notify = True

                # Save event and notify
                if should_notify:
                    await self._service.record_trigger(monitor.id)
                    await self._save_event(
                        monitor, "triggered",
                        status_code=status_code,
                        body=body_str[:2000],
                        condition_met=condition_met,
                        changed=changed,
                        duration_ms=duration_ms,
                    )

                    # Publish to event bus
                    self._event_bus.publish(Event(
                        name="monitor.triggered",
                        data={
                            "monitor_id": monitor.id,
                            "monitor_name": monitor.name,
                            "status_code": status_code,
                            "condition_met": condition_met,
                            "changed": changed,
                            "duration_ms": duration_ms,
                        },
                    ))

        except httpx.TimeoutException:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            await self._service.record_run(monitor.id, None, None, error="Timeout")
            await self._save_event(monitor, "error", error="Request timed out", duration_ms=duration_ms)

        except httpx.ConnectError:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            await self._service.record_run(monitor.id, None, None, error="Connection failed")
            await self._save_event(monitor, "error", error="Connection failed", duration_ms=duration_ms)

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            await self._service.record_run(monitor.id, None, None, error=str(e)[:200])
            await self._save_event(monitor, "error", error=str(e)[:200], duration_ms=duration_ms)

    async def _save_event(
        self,
        monitor: Monitor,
        event_type: str,
        status_code: int | None = None,
        body: str | None = None,
        condition_met: bool = False,
        changed: bool = False,
        error: str | None = None,
        duration_ms: int = 0,
    ) -> None:
        """Save a monitor event."""
        event = MonitorEvent(
            id=str(uuid.uuid4()),
            monitor_id=monitor.id,
            monitor_name=monitor.name,
            event_type=event_type,
            status_code=status_code,
            body=body,
            condition_met=condition_met,
            changed=changed,
            error=error,
            duration_ms=duration_ms,
            created_at=datetime.now(UTC).isoformat(),
        )
        await self._service.save_event(event)
