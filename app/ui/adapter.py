"""UI Adapter abstraction.

Defines the interface that all frontends (CLI, TUI, GUI) implement.
This ensures the service layer is never coupled to a specific UI framework.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class UIAdapter(ABC):
    """Abstract interface for UI operations.

    All frontends (CLI, Textual TUI, future GUI) implement this.
    The TUI/CLI/GUI code talks to services through this adapter.
    Business logic never lives here.
    """

    # ── Notifications ───────────────────────────────────────────────────

    @abstractmethod
    def notify(self, message: str, level: LogLevel = LogLevel.INFO) -> None:
        """Show a toast/status message."""

    @abstractmethod
    async def confirm(self, message: str, default: bool = False) -> bool:
        """Show a confirmation dialog. Returns True if confirmed."""

    @abstractmethod
    async def prompt(self, message: str, default: str = "") -> str:
        """Show a text input prompt. Returns the entered value."""

    @abstractmethod
    async def choose(self, message: str, options: list[str]) -> str:
        """Show a selection dialog. Returns the chosen option."""

    # ── Progress ────────────────────────────────────────────────────────

    @abstractmethod
    def progress_start(self, task: str, total: int) -> str:
        """Start a progress bar. Returns a task ID."""

    @abstractmethod
    def progress_advance(self, task_id: str, amount: int = 1) -> None:
        """Advance a progress bar."""

    @abstractmethod
    def progress_stop(self, task_id: str) -> None:
        """Stop/remove a progress bar."""

    # ── File Operations ─────────────────────────────────────────────────

    @abstractmethod
    async def file_picker(
        self,
        mode: str = "open",
        filters: list[str] | None = None,
        default_path: str | None = None,
    ) -> Path | None:
        """Show a file picker dialog.
        mode: 'open', 'save', 'directory'
        filters: list of extensions like ['*.json', '*.sclpll']
        Returns selected path or None if cancelled.
        """

    # ── Clipboard ───────────────────────────────────────────────────────

    @abstractmethod
    def clipboard_copy(self, text: str) -> None:
        """Copy text to clipboard."""

    # ── Logging ─────────────────────────────────────────────────────────

    @abstractmethod
    def log(self, message: str, level: LogLevel = LogLevel.INFO) -> None:
        """Write to the log pane."""

    # ── Command Registration ────────────────────────────────────────────

    @abstractmethod
    def register_command(
        self,
        name: str,
        handler: Callable[[], Any],
        shortcut: str | None = None,
        description: str = "",
    ) -> None:
        """Register a command for the command palette."""

    # ── Navigation ──────────────────────────────────────────────────────

    @abstractmethod
    def open_url(self, url: str) -> None:
        """Open a URL in the browser."""

    @abstractmethod
    def set_title(self, title: str) -> None:
        """Set the window/tab title."""
