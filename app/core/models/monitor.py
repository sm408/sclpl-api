"""Monitor data model for live API monitoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class MonitorStatus(StrEnum):
    """Monitor status."""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class NotificationMode(StrEnum):
    """When to send notifications."""
    ALWAYS = "always"  # Every poll
    CHANGE = "change"  # When response changes
    CONDITION = "condition_met"  # When condition is met


@dataclass
class Monitor:
    """A live API monitor."""
    id: str
    name: str
    url: str
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    body: str | None = None
    interval_seconds: int = 60
    condition: str = ""  # e.g., "status == 200", "body.price > 100"
    notification_on: NotificationMode = NotificationMode.CHANGE
    enabled: bool = True
    status: MonitorStatus = MonitorStatus.STOPPED
    last_run: str | None = None
    last_status_code: int | None = None
    last_body: str | None = None
    last_error: str | None = None
    last_changed: str | None = None
    run_count: int = 0
    trigger_count: int = 0
    created_at: str = ""
    updated_at: str = ""


@dataclass
class MonitorEvent:
    """An event from a monitor."""
    id: str
    monitor_id: str
    monitor_name: str
    event_type: str  # "triggered", "error", "started", "stopped"
    status_code: int | None = None
    body: str | None = None
    condition_met: bool = False
    changed: bool = False
    error: str | None = None
    duration_ms: int = 0
    created_at: str = ""
