"""Settings API routes.

Provides GET/PATCH for application settings. Settings that affect
server behaviour (defaultTimeout, followRedirects, maxHistoryEntries)
are flagged as requiring a restart to take full effect.

Settings are persisted to the ``settings`` table in SQLite so they
survive server restarts.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from pydantic import Field

from app.storage.db import Database
from app.web.deps import _get_db
from app.web.dto import CamelModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

SETTINGS_KEY = "app_settings"

# ── Settings model ────────────────────────────────────────────────────────


class EditorSettings(CamelModel):
    """Editor-specific settings."""
    tab_size: int = 4
    word_wrap: str = "off"  # "off" | "on" | "wordWrapColumn"
    minimap: bool = True
    font_size: int = 14


class HistorySettings(CamelModel):
    """History retention settings."""
    max_entries: int = 500
    auto_clear_days: int = 0  # 0 = never auto-clear


class StartupSettings(CamelModel):
    """Startup behaviour settings."""
    default_project_id: str | None = None
    reopen_last_tabs: bool = True


class AppSettingsResponse(CamelModel):
    """Full application settings."""
    # Server-side settings (require restart)
    default_timeout: int = 30
    follow_redirects: bool = True
    max_history_entries: int = 500
    # Client-side settings
    editor: EditorSettings = Field(default_factory=EditorSettings)
    history: HistorySettings = Field(default_factory=HistorySettings)
    startup: StartupSettings = Field(default_factory=StartupSettings)
    # Restart flag
    restart_required: bool = False


class SettingsUpdate(CamelModel):
    """Partial settings update."""
    default_timeout: int | None = None
    follow_redirects: bool | None = None
    max_history_entries: int | None = None
    editor: EditorSettings | None = None
    history: HistorySettings | None = None
    startup: StartupSettings | None = None


# ── Persistence helpers ───────────────────────────────────────────────────

_restart_required = False


async def _load_settings(db: Database) -> AppSettingsResponse:
    """Load settings from the database, returning defaults if absent."""
    row = await db.fetch_one(
        "SELECT value FROM settings WHERE key = ?", (SETTINGS_KEY,)
    )
    if row:
        try:
            data = json.loads(row["value"])
            data["restart_required"] = _restart_required
            return AppSettingsResponse(**data)
        except (json.JSONDecodeError, TypeError, KeyError):
            logger.warning("Corrupt settings row; returning defaults")
    return AppSettingsResponse(restart_required=_restart_required)


async def _save_settings(db: Database, settings: AppSettingsResponse) -> None:
    """Persist settings to the database."""
    payload = settings.model_dump(mode="json")
    # Don't persist the transient restart_required flag
    payload.pop("restart_required", None)
    blob = json.dumps(payload, separators=(",", ":"))
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (SETTINGS_KEY, blob),
    )
    await db.commit()


def _apply_updates(current: AppSettingsResponse, updates: SettingsUpdate) -> AppSettingsResponse:
    """Apply partial updates to settings and track restart requirement."""
    global _restart_required
    data = current.model_dump()

    server_fields = {"default_timeout", "follow_redirects", "max_history_entries"}
    update_data = updates.model_dump(exclude_none=True)

    for key, value in update_data.items():
        if key in server_fields and data.get(key) != value:
            _restart_required = True
        if key == "editor" and isinstance(value, dict):
            data["editor"] = {**data["editor"], **value}
        elif key == "history" and isinstance(value, dict):
            data["history"] = {**data["history"], **value}
        elif key == "startup" and isinstance(value, dict):
            data["startup"] = {**data["startup"], **value}
        else:
            data[key] = value

    data["restart_required"] = _restart_required
    return AppSettingsResponse(**data)


# ── Routes ────────────────────────────────────────────────────────────────


@router.get("", response_model=AppSettingsResponse)
async def get_settings(
    db: Database = Depends(_get_db),  # noqa: B008
) -> AppSettingsResponse:
    """Get current application settings."""
    return await _load_settings(db)


@router.patch("", response_model=AppSettingsResponse)
async def update_settings(
    body: SettingsUpdate,
    db: Database = Depends(_get_db),  # noqa: B008
) -> AppSettingsResponse:
    """Update application settings. Returns updated settings with restart flag."""
    current = await _load_settings(db)
    updated = _apply_updates(current, body)
    await _save_settings(db, updated)
    logger.info("Settings updated (restart_required=%s)", updated.restart_required)
    return updated
