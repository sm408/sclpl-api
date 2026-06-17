from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RunStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class HistoryEntry:
    id: str
    request_id: str
    request_name: str
    method: str
    url: str
    status: RunStatus
    status_code: int | None = None
    response_body: str | None = None
    response_headers: dict[str, str] = field(default_factory=dict)
    duration_ms: int = 0
    error_message: str | None = None
    environment_id: str | None = None
    variables_used: dict[str, str] = field(default_factory=dict)
    created_at: str | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "request_name": self.request_name,
            "method": self.method,
            "url": self.url,
            "status": self.status.value,
            "status_code": self.status_code,
            "duration_ms": self.duration_ms,
        }
