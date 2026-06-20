"""Log viewer with filtering and search."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Select, Static


class LogViewer(Vertical):
    """Log viewer with filtering and search."""

    CSS = """
    LogViewer {
        height: 100%;
        padding: 1;
    }

    #log-filter {
        height: auto;
        margin-bottom: 1;
    }

    #log-content {
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._logs: list[dict] = []
        self._filter_level = "all"
        self._filter_text = ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="log-filter"):
            yield Input(placeholder="Search logs...", id="log-search")
            yield Select(
                [("All", "all"), ("Info", "info"), ("Warning", "warning"),
                 ("Error", "error"), ("Debug", "debug")],
                value="all",
                id="level-filter",
            )

        yield Static("[dim]No logs yet[/dim]", id="log-content")

    def add_log(self, message: str, level: str = "info", source: str = "") -> None:
        """Add a log entry."""
        self._logs.append({
            "message": message,
            "level": level,
            "source": source,
        })
        self._update_display()

    @on(Input.Changed, "#log-search")
    def search_changed(self, event: Input.Changed) -> None:
        self._filter_text = event.value.lower()
        self._update_display()

    @on(Select.Changed, "#level-filter")
    def level_changed(self, event: Select.Changed) -> None:
        self._filter_level = str(event.value)
        self._update_display()

    def _update_display(self) -> None:
        """Update the log display with current filters."""
        content = self.query_one("#log-content", Static)

        filtered = self._logs
        if self._filter_level != "all":
            filtered = [l for l in filtered if l["level"] == self._filter_level]
        if self._filter_text:
            filtered = [l for l in filtered if self._filter_text in l["message"].lower()]

        if not filtered:
            content.update("[dim]No matching logs[/dim]")
            return

        lines = []
        for log in filtered[-100:]:  # Show last 100
            level = log["level"]
            color = {
                "info": "blue",
                "warning": "yellow",
                "error": "red",
                "debug": "dim",
                "success": "green",
            }.get(level, "white")
            source = f"[dim][{log['source']}][/dim] " if log["source"] else ""
            lines.append(f"[{color}]{level.upper():7}[/{color}] {source}{log['message']}")

        content.update("\n".join(lines))

    def clear(self) -> None:
        """Clear all logs."""
        self._logs = []
        self._update_display()
