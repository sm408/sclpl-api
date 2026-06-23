"""Logs API routes.

Provides a ring-buffer log handler that captures Python logging output
and exposes it via REST endpoints with filtering, clearing, and
redacted export.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import time
from collections import deque
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.web.dto import CamelModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/logs", tags=["logs"])


# ── Log ring buffer handler ───────────────────────────────────────────────

_LOG_BUFFER: deque[dict[str, Any]] = deque(maxlen=2000)
_PAUSED = False

# Patterns to redact in exported logs
_REDACT_PATTERNS = [
    (re.compile(r"(?i)(authorization|api[_-]?key|token|secret|password)[=:\s]+\S+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)Bearer\s+\S+"), "Bearer [REDACTED]"),
    (re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"), "[REDACTED_CARD]"),
]


def _redact(text: str) -> str:
    """Apply redaction patterns to a log message."""
    for pattern, replacement in _REDACT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RingBufferHandler(logging.Handler):
    """Logging handler that stores records in a bounded ring buffer.

    All entries are written to the module-level ``_LOG_BUFFER`` deque so
    that every instance (and the module-level ``_ring_handler`` singleton)
    shares the same bounded store.  The handler intentionally has no
    instance-level buffer.
    """

    def emit(self, record: logging.LogRecord) -> None:
        if _PAUSED:
            return
        try:
            entry = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
                "level": record.levelname.lower(),
                "source": record.name,
                "message": self.format(record),
            }
            _LOG_BUFFER.append(entry)
        except Exception:
            self.handleError(record)


# Install the handler on the root logger
_ring_handler = RingBufferHandler()
_ring_handler.setFormatter(logging.Formatter("%(message)s"))
logging.getLogger().addHandler(_ring_handler)


# ── DTOs ──────────────────────────────────────────────────────────────────


class LogEntry(CamelModel):
    timestamp: str
    level: str
    source: str
    message: str


class LogListResponse(CamelModel):
    items: list[LogEntry]
    total: int
    paused: bool


# ── Routes ────────────────────────────────────────────────────────────────


@router.get("", response_model=LogListResponse)
async def list_logs(
    level: str | None = Query(None, description="Filter by log level"),
    source: str | None = Query(None, description="Filter by source (contains)"),
    search: str | None = Query(None, description="Search message text"),
    limit: int = Query(200, ge=1, le=2000, description="Max entries"),
) -> LogListResponse:
    """List log entries with optional filtering."""
    entries = list(_LOG_BUFFER)

    if level and level != "all":
        level_lower = level.lower()
        entries = [e for e in entries if e["level"] == level_lower]

    if source:
        source_lower = source.lower()
        entries = [e for e in entries if source_lower in e["source"].lower()]

    if search:
        search_lower = search.lower()
        entries = [e for e in entries if search_lower in e["message"].lower()]

    total = len(entries)
    entries = entries[-limit:]

    return LogListResponse(items=entries, total=total, paused=_PAUSED)


@router.post("/pause")
async def pause_logs() -> dict[str, Any]:
    """Pause log collection (new entries are dropped until resumed)."""
    global _PAUSED
    _PAUSED = True
    return {"paused": True}


@router.post("/resume")
async def resume_logs() -> dict[str, Any]:
    """Resume log collection."""
    global _PAUSED
    _PAUSED = False
    return {"paused": False}


@router.delete("")
async def clear_logs() -> dict[str, int]:
    """Clear the in-memory log buffer (view-only, not persistent deletion)."""
    count = len(_LOG_BUFFER)
    _LOG_BUFFER.clear()
    return {"cleared": count}


@router.get("/export")
async def export_logs(
    level: str | None = Query(None),
    source: str | None = Query(None),
    search: str | None = Query(None),
    redact: bool = Query(True, description="Apply redaction to sensitive data"),
) -> StreamingResponse:
    """Export logs as CSV with optional redaction."""
    entries = list(_LOG_BUFFER)

    if level and level != "all":
        entries = [e for e in entries if e["level"] == level.lower()]
    if source:
        entries = [e for e in entries if source.lower() in e["source"].lower()]
    if search:
        entries = [e for e in entries if search.lower() in e["message"].lower()]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "level", "source", "message"])

    for entry in entries:
        msg = _redact(entry["message"]) if redact else entry["message"]
        writer.writerow([entry["timestamp"], entry["level"], entry["source"], msg])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sclplapi-logs.csv"},
    )
