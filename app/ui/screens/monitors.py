"""Monitors screen for live API monitoring."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, DataTable, Input, Static


class MonitorList(Vertical):
    """List of monitors with controls."""

    CSS = """
    MonitorList {
        height: 100%;
        padding: 1;
    }

    #monitor-header {
        height: auto;
        margin-bottom: 1;
    }

    #monitor-table {
        height: 1fr;
    }

    #monitor-actions {
        height: auto;
        margin-top: 1;
    }

    #monitor-stats {
        height: auto;
        margin-top: 1;
        padding: 1;
        background: $surface-darken-1;
    }
    """

    class NewMonitor(Message):
        """Create a new monitor."""
        pass

    class StartMonitor(Message):
        """Start a monitor."""
        def __init__(self, monitor_id: str) -> None:
            self.monitor_id = monitor_id
            super().__init__()

    class StopMonitor(Message):
        """Stop a monitor."""
        def __init__(self, monitor_id: str) -> None:
            self.monitor_id = monitor_id
            super().__init__()

    class DeleteMonitor(Message):
        """Delete a monitor."""
        def __init__(self, monitor_id: str) -> None:
            self.monitor_id = monitor_id
            super().__init__()

    class ViewDetail(Message):
        """View monitor detail."""
        def __init__(self, monitor_id: str) -> None:
            self.monitor_id = monitor_id
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._monitors: list[dict] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="monitor-header"):
            yield Static("[bold]Live Monitors[/bold]", classes="header-title")
            yield Input(placeholder="Search monitors...", id="monitor-search")
            yield Button("New", variant="primary", id="new-monitor-btn", classes="header-action")

        yield DataTable(id="monitor-table")

        yield Static("[dim]No monitors running[/dim]", id="monitor-stats")

        with Horizontal(id="monitor-actions"):
            yield Button("Start", variant="success", id="start-monitor-btn")
            yield Button("Stop", variant="error", id="stop-monitor-btn")
            yield Button("View", id="view-monitor-btn")
            yield Button("Delete", variant="error", id="delete-monitor-btn")

    def on_mount(self) -> None:
        table = self.query_one("#monitor-table", DataTable)
        table.add_columns("Name", "URL", "Interval", "Status", "Runs", "Triggers")
        table.cursor_type = "row"

    def set_monitors(self, monitors: list[dict]) -> None:
        """Update the monitor table."""
        self._monitors = monitors
        table = self.query_one("#monitor-table", DataTable)
        table.clear()

        running = 0
        for m in monitors:
            status = m.get("status", "stopped")
            if status == "running":
                running += 1

            status_color = {
                "running": "green",
                "stopped": "dim",
                "paused": "yellow",
                "error": "red",
            }.get(status, "white")

            interval = m.get("interval_seconds", 60)
            if interval < 60:
                interval_str = f"{interval}s"
            elif interval < 3600:
                interval_str = f"{interval // 60}m"
            else:
                interval_str = f"{interval // 3600}h"

            table.add_row(
                m.get("name", "Untitled"),
                (m.get("url", "") or "")[:40],
                interval_str,
                f"[{status_color}]{status}[/{status_color}]",
                str(m.get("run_count", 0)),
                str(m.get("trigger_count", 0)),
            )

        stats = self.query_one("#monitor-stats", Static)
        if monitors:
            stats.update(f"[green]{running} running[/green] / {len(monitors)} total")
        else:
            stats.update("[dim]No monitors configured[/dim]")

    def get_selected_monitor(self) -> dict | None:
        table = self.query_one("#monitor-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self._monitors):
            return self._monitors[table.cursor_row]
        return None

    @on(Input.Changed, "#monitor-search")
    def search_changed(self, event: Input.Changed) -> None:
        query = event.value.lower().strip()
        if not query:
            self.set_monitors(self._monitors)
        else:
            filtered = [m for m in self._monitors if query in m.get("name", "").lower()]
            self.set_monitors(filtered)

    @on(Button.Pressed, "#new-monitor-btn")
    def new_pressed(self) -> None:
        self.post_message(self.NewMonitor())

    @on(Button.Pressed, "#start-monitor-btn")
    def start_pressed(self) -> None:
        m = self.get_selected_monitor()
        if m:
            self.post_message(self.StartMonitor(m["id"]))

    @on(Button.Pressed, "#stop-monitor-btn")
    def stop_pressed(self) -> None:
        m = self.get_selected_monitor()
        if m:
            self.post_message(self.StopMonitor(m["id"]))

    @on(Button.Pressed, "#view-monitor-btn")
    def view_pressed(self) -> None:
        m = self.get_selected_monitor()
        if m:
            self.post_message(self.ViewDetail(m["id"]))

    @on(Button.Pressed, "#delete-monitor-btn")
    def delete_pressed(self) -> None:
        m = self.get_selected_monitor()
        if m:
            self.post_message(self.DeleteMonitor(m["id"]))


class MonitorDetail(Vertical):
    """Monitor detail view."""

    CSS = """
    MonitorDetail {
        height: 100%;
        padding: 1;
    }

    #detail-header {
        height: auto;
        margin-bottom: 1;
    }

    #detail-info {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        background: $surface-darken-1;
    }

    #detail-events {
        height: 1fr;
    }

    #detail-actions {
        height: auto;
        margin-top: 1;
    }
    """

    class Back(Message):
        """Go back to monitor list."""
        pass

    def compose(self) -> ComposeResult:
        yield Static("[bold]Monitor Detail[/bold]", id="detail-header")
        yield Static("", id="detail-info")
        yield DataTable(id="detail-events")

        with Horizontal(id="detail-actions"):
            yield Button("Back", id="back-btn")
            yield Button("Clear Events", id="clear-events-btn")

    def on_mount(self) -> None:
        table = self.query_one("#detail-events", DataTable)
        table.add_columns("Time", "Type", "Status", "Changed", "Condition", "Duration", "Error")
        table.cursor_type = "row"

    def set_monitor(self, monitor: dict) -> None:
        """Update monitor info."""
        info = self.query_one("#detail-info", Static)
        info.update(
            f"[bold]{monitor.get('name', 'Untitled')}[/bold]\n"
            f"URL: {monitor.get('url', '')}\n"
            f"Method: {monitor.get('method', 'GET')}  Interval: {monitor.get('interval_seconds', 60)}s\n"
            f"Condition: {monitor.get('condition', 'none')}\n"
            f"Status: {monitor.get('status', 'stopped')}  "
            f"Runs: {monitor.get('run_count', 0)}  Triggers: {monitor.get('trigger_count', 0)}\n"
            f"Last Run: {monitor.get('last_run', 'never')}\n"
            f"Last Status: {monitor.get('last_status_code', 'N/A')}"
        )

    def set_events(self, events: list[dict]) -> None:
        """Update events table."""
        table = self.query_one("#detail-events", DataTable)
        table.clear()
        for e in events:
            event_type = e.get("event_type", "unknown")
            type_color = {
                "triggered": "green",
                "error": "red",
                "started": "blue",
                "stopped": "yellow",
            }.get(event_type, "white")

            changed = "[green]Yes[/green]" if e.get("changed") else "No"
            condition = "[green]Yes[/green]" if e.get("condition_met") else "No"

            table.add_row(
                (e.get("created_at", "") or "")[:19],
                f"[{type_color}]{event_type}[/{type_color}]",
                str(e.get("status_code", "")),
                changed,
                condition,
                f"{e.get('duration_ms', 0)}ms",
                (e.get("error", "") or "")[:30],
            )

    @on(Button.Pressed, "#back-btn")
    def back_pressed(self) -> None:
        self.post_message(self.Back())

    @on(Button.Pressed, "#clear-events-btn")
    def clear_pressed(self) -> None:
        # Will be handled by parent
        pass
