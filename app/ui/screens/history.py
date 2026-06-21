"""History screen with timeline view and filtering."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Select, Static


class HistoryView(Vertical):
    """History view with filter and detail inspection."""

    CSS = """
    HistoryView {
        height: 100%;
        padding: 1;
    }

    #history-filter {
        height: auto;
        margin-bottom: 1;
    }

    #history-table {
        height: 1fr;
    }

    #history-detail {
        height: auto;
        margin-top: 1;
        padding: 1;
        background: $surface-darken-1;
    }

    #history-actions {
        height: auto;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="history-filter"):
            yield Input(placeholder="Filter by method/url/status...", id="filter-input")
            yield Select(
                [("All", "all"), ("GET", "GET"), ("POST", "POST"),
                 ("PUT", "PUT"), ("DELETE", "DELETE")],
                value="all",
                id="method-filter",
            )
            yield Button("Clear All", variant="error", id="clear-history-btn")

        yield DataTable(id="history-table")

        with Horizontal():
            yield Select(
                [("Keep All", "all"), ("1 Day", "1d"), ("7 Days", "7d"), ("30 Days", "30d")],
                value="all",
                id="cleanup-policy",
            )
            yield Button("Apply Cleanup", id="cleanup-btn")

        yield Static("[dim]Select an entry to view details[/dim]", id="history-detail")

        with Horizontal(id="history-actions"):
            yield Button("Inspect", id="inspect-btn")
            yield Button("Re-run", id="rerun-btn")

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Time", "Method", "URL", "Status", "Duration")
        table.cursor_type = "row"

    def set_entries(self, entries: list[dict]) -> None:
        """Update the history table."""
        table = self.query_one("#history-table", DataTable)
        table.clear()
        for entry in entries:
            status_color = "green" if entry.get("status") == "success" else "red"
            table.add_row(
                entry.get("created_at", "")[:19],
                entry.get("method", "?"),
                (entry.get("url", "") or "")[:50],
                f"[{status_color}]{entry.get('status_code', '?')}[/{status_color}]",
                f"{entry.get('duration_ms', 0)}ms",
            )

    def show_detail(self, entry: dict) -> None:
        """Show details for a history entry."""
        detail = self.query_one("#history-detail", Static)
        status = entry.get("status", "unknown")
        status_color = "green" if status == "success" else "red"

        text = (
            f"[bold]{entry.get('method', '?')}[/bold] {entry.get('url', '')}\n"
            f"Status: [{status_color}]{entry.get('status_code', '?')} ({status})[/{status_color}]\n"
            f"Duration: {entry.get('duration_ms', 0)}ms\n"
            f"Time: {entry.get('created_at', '')}"
        )

        if entry.get("error_message"):
            text += f"\n[red]Error: {entry['error_message']}[/red]"

        detail.update(text)
