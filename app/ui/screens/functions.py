"""Functions screen with browser and source viewer."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Static, TextArea


class FunctionBrowser(Vertical):
    """Function browser with search and detail view."""

    CSS = """
    FunctionBrowser {
        height: 100%;
        padding: 1;
    }

    #func-filter {
        height: auto;
        margin-bottom: 1;
    }

    #func-table {
        height: 1fr;
    }

    #func-detail {
        height: 1fr;
        margin-top: 1;
    }

    #func-source {
        height: 100%;
    }

    #func-actions {
        height: auto;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="func-filter"):
            yield Input(placeholder="Filter by name...", id="func-search")

        yield DataTable(id="func-table")

        yield Static("[dim]Select a function to view source[/dim]", id="func-info")

        yield Static("[bold]Source[/bold]", id="func-source-header")
        yield TextArea(
            id="func-source",
            language="python",
            theme="monokai",
            read_only=True,
        )

    def on_mount(self) -> None:
        table = self.query_one("#func-table", DataTable)
        table.add_columns("Name", "Type", "Version", "Path")
        table.cursor_type = "row"

    def set_functions(self, funcs: list[dict]) -> None:
        """Update the function table."""
        table = self.query_one("#func-table", DataTable)
        table.clear()
        for f in funcs:
            table.add_row(
                f.get("name", "?"),
                f.get("type", "?"),
                f.get("version", "?"),
                f.get("path", "?"),
            )

    def show_function(self, func: dict, source: str) -> None:
        """Show function details and source."""
        info = self.query_one("#func-info", Static)
        info_text = "\n".join(f"[bold]{k}[/bold]: {v}" for k, v in func.items() if k != "path")
        info.update(info_text)

        self.query_one("#func-source", TextArea).text = source
