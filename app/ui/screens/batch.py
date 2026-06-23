"""Batch execution screen with CSV import."""

from __future__ import annotations

import csv
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, DataTable, Input, ProgressBar, Static


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

    #batch-csv-input {
        width: 100%;
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

    class CsvLoaded(Message):
        """Message sent when CSV is loaded."""
        def __init__(self, rows: list[dict]) -> None:
            self.rows = rows
            super().__init__()

    class BatchStart(Message):
        """Message sent when batch should start."""
        def __init__(self, rows: list[dict]) -> None:
            self.rows = rows
            super().__init__()

    completed: reactive[int] = reactive(0)
    failed: reactive[int] = reactive(0)
    total: reactive[int] = reactive(0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._csv_rows: list[dict] = []
        self._csv_path: str = ""

    def compose(self) -> ComposeResult:
        yield Static("[bold]Batch Execution[/bold]", id="batch-header")

        with Horizontal():
            yield Input(placeholder="CSV file path...", id="batch-csv-input")
            yield Button("Load", id="load-csv-btn")

        yield DataTable(id="batch-table")

        yield Static("[dim]No batch loaded[/dim]", id="batch-summary")

        yield ProgressBar(id="batch-progress")

        with Horizontal(id="batch-actions"):
            yield Button("Start", variant="success", id="start-batch-btn")
            yield Button("Stop", variant="error", id="stop-batch-btn")

    def on_mount(self) -> None:
        table = self.query_one("#batch-table", DataTable)
        table.add_columns("Row", "Status", "Duration", "Error")
        table.cursor_type = "row"

    @on(Input.Submitted, "#batch-csv-input")
    def csv_path_submitted(self, event: Input.Submitted) -> None:
        self._csv_path = event.value
        self._load_csv(event.value)

    @on(Button.Pressed, "#load-csv-btn")
    def load_csv_pressed(self) -> None:
        csv_input = self.query_one("#batch-csv-input", Input)
        self._csv_path = csv_input.value
        self._load_csv(csv_input.value)

    def _load_csv(self, path: str) -> None:
        """Load a CSV file."""
        if not path:
            self.notify("Enter a CSV file path", severity="warning")
            return

        csv_path = Path(path)
        if not csv_path.exists():
            self.notify(f"File not found: {path}", severity="error")
            return

        try:
            with open(csv_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self._csv_rows = list(reader)

            if not self._csv_rows:
                self.notify("CSV file is empty", severity="warning")
                return

            # Update table with preview
            table = self.query_one("#batch-table", DataTable)
            table.clear()
            for i, row in enumerate(self._csv_rows[:20], 1):  # Show first 20
                table.add_row(str(i), "[dim]Pending[/dim]", "", "")

            self.total = len(self._csv_rows)
            summary = self.query_one("#batch-summary", Static)
            summary.update(f"[green]Loaded {len(self._csv_rows)} rows from {csv_path.name}[/green]")

            self.notify(f"Loaded {len(self._csv_rows)} rows")
            self.post_message(self.CsvLoaded(self._csv_rows))

        except Exception as e:
            self.notify(f"Failed to load CSV: {e}", severity="error")

    @on(Button.Pressed, "#start-batch-btn")
    def start_batch_pressed(self) -> None:
        if not self._csv_rows:
            self.notify("Load a CSV file first", severity="warning")
            return
        self.post_message(self.BatchStart(self._csv_rows))

    @on(Button.Pressed, "#stop-batch-btn")
    def stop_batch_pressed(self) -> None:
        self.notify("Batch stop requested", severity="warning")

    def set_progress(self, completed: int, failed: int, total: int) -> None:
        """Update progress."""
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
        """Add a row result to the table."""
        table = self.query_one("#batch-table", DataTable)
        status = "[green]OK[/green]" if success else "[red]FAIL[/red]"
        table.add_row(str(row), status, f"{duration_ms}ms", error[:50])

    def get_csv_rows(self) -> list[dict]:
        """Get the loaded CSV rows."""
        return self._csv_rows
