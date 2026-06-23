"""Commands API route.

Provides the list of registered commands for the command palette
help view. Commands are registered on the frontend; this endpoint
returns the canonical command list with shortcuts and categories.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.web.dto import CamelModel

router = APIRouter(prefix="/api/v1/commands", tags=["commands"])


class CommandEntry(CamelModel):
    id: str
    label: str
    shortcut: str = ""
    category: str = "General"


class CommandListResponse(CamelModel):
    items: list[CommandEntry]
    total: int


# Canonical command list — kept in sync with frontend command registrations
_CANONICAL_COMMANDS = [
    CommandEntry(id="palette.open", label="Open Command Palette", shortcut="Ctrl+K", category="General"),
    CommandEntry(id="theme.cycle", label="Cycle Theme", shortcut="Ctrl+Shift+T", category="Appearance"),
    CommandEntry(id="view.settings", label="Open Settings", shortcut="Ctrl+,", category="Navigation"),
    CommandEntry(id="view.history", label="Open History", shortcut="Ctrl+H", category="Navigation"),
    CommandEntry(id="view.collections", label="Open Collections", shortcut="Ctrl+1", category="Navigation"),
    CommandEntry(id="view.workflows", label="Open Workflows", shortcut="Ctrl+2", category="Navigation"),
    CommandEntry(id="view.monitors", label="Open Monitors", shortcut="Ctrl+3", category="Navigation"),
    CommandEntry(id="view.functions", label="Open Functions", shortcut="Ctrl+4", category="Navigation"),
    CommandEntry(id="view.plugins", label="Open Plugins", shortcut="Ctrl+5", category="Navigation"),
    CommandEntry(id="view.logs", label="Open Logs", shortcut="Ctrl+L", category="Navigation"),
    CommandEntry(id="request.new", label="New Request", shortcut="Ctrl+N", category="Requests"),
    CommandEntry(id="request.send", label="Send Request", shortcut="Ctrl+Enter", category="Requests"),
    CommandEntry(id="request.save", label="Save Request", shortcut="Ctrl+S", category="Requests"),
    CommandEntry(id="tab.close", label="Close Tab", shortcut="Ctrl+W", category="Tabs"),
    CommandEntry(id="tab.next", label="Next Tab", shortcut="Ctrl+Tab", category="Tabs"),
    CommandEntry(id="tab.prev", label="Previous Tab", shortcut="Ctrl+Shift+Tab", category="Tabs"),
    CommandEntry(id="explorer.toggle", label="Toggle Explorer", shortcut="Ctrl+B", category="View"),
    CommandEntry(id="export.full", label="Export Workspace", shortcut="", category="Export"),
    CommandEntry(id="import.full", label="Import Workspace", shortcut="", category="Export"),
]


@router.get("", response_model=CommandListResponse)
async def list_commands() -> CommandListResponse:
    """List all registered commands with shortcuts and categories."""
    return CommandListResponse(items=_CANONICAL_COMMANDS, total=len(_CANONICAL_COMMANDS))
