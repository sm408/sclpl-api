"""Batch execution screen."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, DataTable, ProgressBar, Static


class BatchView(Vertical):
    """Batch execution view with CSV import and progress tracking."""

    CSS = """
    BatchView {
        height: 100%;
        padding: 1;
    }

    #batch-header {
        height: auto;
        margin-bottom: 1;
    }

    #batch-progress {
        height: auto;
        margin-bottom: 1;
    }

    #batch-table {
        height: 1fr;
    }

    #batch-summary {
        height: auto;
        margin-top: 1;
        padding: 1;
        background: $surface-darken-1;
    }

    #batch-actions {
        height: auto;
        margin-top: 1;
    }
    """

    completed: reactive[int] = reactive(0)
    failed: reactive[int] = reactive(0)
    total: reactive[int] = reactive(0)

    def compose(self) -> ComposeResult:
        yield Static("[bold]Batch Execution[/bold]", id="batch-header")
        yield ProgressBar(id="batch-progress")
        yield DataTable(id="batch-table")

        yield Static("[dim]No batch running[/dim]", id="batch-summary")

        with Horizontal(id="batch-actions"):
            yield Button("Load CSV", id="load-csv-btn")
            yield Button("Start", variant="success", id="start-batch-btn")
            yield Button("Stop", variant="error", id="stop-batch-btn")

    def on_mount(self) -> None:
        table = self.query_one("#batch-table", DataTable)
        table.add_columns("Row", "Status", "Duration", "Error")
        table.cursor_type = "row"

    def set_progress(self, completed: int, failed: int, total: int) -> None:
        self.completed = completed
        self.failed = failed
        self.total = total

        progress = self.query_one("#batch-progress", ProgressBar)
        progress.total = total
        progress.progress = completed + failed

        summary = self.query_one("#batch-summary", Static)
        summary.update(
            f"[green]{completed} completed[/green] / "
            f"[red]{failed} failed[/red] / "
            f"{total} total"
        )

    def add_row_result(self, row: int, success: bool, duration_ms: int, error: str = "") -> None:
        table = self.query_one("#batch-table", DataTable)
        status = "[green]OK[/green]" if success else "[red]FAIL[/red]"
        table.add_row(str(row), status, f"{duration_ms}ms", error[:50])
