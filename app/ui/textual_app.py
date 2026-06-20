"""Textual-based TUI application.

Primary interaction layer for SCLPLAPI.
Replaces the Rich-based menu-driven TUI with a modern, keyboard-first interface.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from app.ui.app import App as SCLPLApp
from app.ui.adapter import UIAdapter, LogLevel


# ── Layout widgets ────────────────────────────────────────────────────────────


class Sidebar(Static):
    """Left sidebar with collection tree, workflow list, environments."""

    def compose(self) -> ComposeResult:
        yield Static("[bold cyan]Collections[/bold cyan]", classes="sidebar-section")
        yield Static("[dim]Loading...[/dim]", id="collection-tree")
        yield Static("")
        yield Static("[bold cyan]Workflows[/bold cyan]", classes="sidebar-section")
        yield Static("[dim]Loading...[/dim]", id="workflow-tree")
        yield Static("")
        yield Static("[bold cyan]Environments[/bold cyan]", classes="sidebar-section")
        yield Static("[dim]None active[/dim]", id="env-display")


class RequestEditor(Static):
    """Request editor pane: URL, method, headers, body."""

    def compose(self) -> ComposeResult:
        yield Static("[bold cyan]Request Editor[/bold cyan]", classes="pane-header")
        yield Static("[dim]Select a request or press Ctrl+T for new[/dim]", id="request-placeholder")


class ResponseViewer(Static):
    """Response viewer pane: status, headers, body, timings."""

    def compose(self) -> ComposeResult:
        yield Static("[bold cyan]Response[/bold cyan]", classes="pane-header")
        yield Static("[dim]Send a request to see the response[/dim]", id="response-placeholder")


class LogPane(Static):
    """Bottom log pane for events and notifications."""

    def compose(self) -> ComposeResult:
        yield Static("[bold cyan]Logs[/bold cyan]", classes="pane-header")
        yield Static("[dim]No events yet[/dim]", id="log-content")


# ── Main Application ─────────────────────────────────────────────────────────


class SCLPLTextualApp(App):
    """SCLPLAPI Textual TUI.

    Primary interaction layer for the application.
    Keyboard-first, panel-based layout inspired by Lazygit/k9s.
    """

    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 2;
        grid-columns: 25% 1fr 1fr;
        grid-rows: 1fr 3;
    }

    Sidebar {
        row-span: 2;
        background: $surface;
        border-right: solid $primary;
        padding: 1;
    }

    .sidebar-section {
        padding: 0 0 0 0;
        margin: 1 0 0 0;
    }

    RequestEditor {
        background: $surface;
        border-bottom: solid $primary;
        padding: 1;
    }

    ResponseViewer {
        background: $surface;
        border-bottom: solid $primary;
        border-left: solid $primary;
        padding: 1;
    }

    LogPane {
        column-span: 3;
        background: $surface-darken-1;
        border-top: solid $primary;
        padding: 0 1;
        height: 3;
    }

    .pane-header {
        text-style: bold;
        margin: 0 0 1 0;
    }
    """

    BINDINGS = [
        Binding("ctrl+p", "command_palette", "Command Palette"),
        Binding("ctrl+t", "new_request", "New Request"),
        Binding("ctrl+r", "run_request", "Run Request"),
        Binding("ctrl+w", "close_tab", "Close Tab"),
        Binding("ctrl+b", "batch_mode", "Batch Mode"),
        Binding("f1", "help", "Help"),
        Binding("f5", "refresh", "Refresh"),
        Binding("escape", "cancel", "Cancel"),
        Binding("q", "quit", "Quit"),
    ]

    TITLE = "SCLPLAPI"
    SUB_TITLE = "API Workflow Studio"

    def __init__(self, db_path: str = "data/sclplapi.db", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.db_path = db_path
        self._app: SCLPLApp | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Sidebar()
            with Vertical():
                yield RequestEditor()
                yield ResponseViewer()
        yield LogPane()
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the application backend."""
        self._app = SCLPLApp(self.db_path)
        await self._app.start()
        self._load_sidebar_data()

    async def on_unmount(self) -> None:
        """Cleanup on exit."""
        if self._app:
            await self._app.stop()

    def _load_sidebar_data(self) -> None:
        """Load collections, workflows, environments into sidebar."""
        # Will be implemented when sidebar widgets are built out
        pass

    # ── Actions ──────────────────────────────────────────────────────────

    def action_command_palette(self) -> None:
        """Open the command palette (Ctrl+P)."""
        self.notify("Command palette coming soon", severity="information")

    def action_new_request(self) -> None:
        """Create a new request tab (Ctrl+T)."""
        self.notify("New request coming soon", severity="information")

    def action_run_request(self) -> None:
        """Run the current request (Ctrl+R)."""
        self.notify("Run request coming soon", severity="information")

    def action_close_tab(self) -> None:
        """Close the current tab (Ctrl+W)."""
        self.notify("Close tab coming soon", severity="information")

    def action_batch_mode(self) -> None:
        """Enter batch mode (Ctrl+B)."""
        self.notify("Batch mode coming soon", severity="information")

    def action_help(self) -> None:
        """Show help (F1)."""
        self.notify("Help coming soon", severity="information")

    def action_refresh(self) -> None:
        """Refresh data (F5)."""
        self._load_sidebar_data()
        self.notify("Refreshed", severity="information")

    def action_cancel(self) -> None:
        """Cancel current operation (Escape)."""
        pass


# ── Entry point ──────────────────────────────────────────────────────────────


def launch_textual_tui(db_path: str = "data/sclplapi.db") -> None:
    """Launch the Textual TUI."""
    app = SCLPLTextualApp(db_path)
    app.run()
