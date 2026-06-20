"""Workflows screen with step list and execution."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, ProgressBar, Static


class WorkflowList(Vertical):
    """List of available workflows."""

    CSS = """
    WorkflowList {
        height: 100%;
        padding: 1;
    }

    #workflow-header {
        height: auto;
        margin-bottom: 1;
    }

    #workflow-table {
        height: 1fr;
    }

    #workflow-actions {
        height: auto;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="workflow-header"):
            yield Static("[bold]Workflows[/bold]", classes="header-title")

        yield DataTable(id="workflow-table")

        with Horizontal(id="workflow-actions"):
            yield Button("Run", variant="success", id="run-workflow-btn")
            yield Button("View Steps", id="view-steps-btn")

    def on_mount(self) -> None:
        table = self.query_one("#workflow-table", DataTable)
        table.add_columns("Name", "Steps", "ID")
        table.cursor_type = "row"

    def set_workflows(self, workflows: list[dict]) -> None:
        """Update the workflow table."""
        table = self.query_one("#workflow-table", DataTable)
        table.clear()
        for wf in workflows:
            table.add_row(
                wf.get("name", wf.get("id", "Unknown")),
                str(wf.get("step_count", 0)),
                wf.get("id", "")[:8],
            )


class WorkflowExecution(Vertical):
    """Workflow execution view with progress and step results."""

    CSS = """
    WorkflowExecution {
        height: 100%;
        padding: 1;
    }

    #execution-header {
        height: auto;
        margin-bottom: 1;
    }

    #execution-progress {
        height: auto;
        margin-bottom: 1;
    }

    #execution-steps {
        height: 1fr;
    }

    #execution-summary {
        height: auto;
        margin-top: 1;
        padding: 1;
        background: $surface-darken-1;
    }

    #execution-actions {
        height: auto;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("[bold]Workflow Execution[/bold]", id="execution-header")
        yield ProgressBar(id="execution-progress")
        yield DataTable(id="execution-steps")

        yield Static("", id="execution-summary")

        with Horizontal(id="execution-actions"):
            yield Button("View Output", id="view-output-btn")
            yield Button("Export JSON", id="export-json-btn")
            yield Button("Export CSV", id="export-csv-btn")
            yield Button("Re-run", id="rerun-workflow-btn")

    def on_mount(self) -> None:
        table = self.query_one("#execution-steps", DataTable)
        table.add_columns("Status", "Step", "Type", "Duration", "Output")
        table.cursor_type = "row"

    def set_steps(self, steps: list[dict]) -> None:
        """Update the steps table."""
        table = self.query_one("#execution-steps", DataTable)
        table.clear()
        for step in steps:
            status = "OK" if step.get("success") else "FAIL"
            status_color = "green" if step.get("success") else "red"
            table.add_row(
                f"[{status_color}]{status}[/{status_color}]",
                step.get("step_name", step.get("step_id", "?")),
                step.get("step_type", "request"),
                f"{step.get('duration_ms', 0)}ms",
                self._format_preview(step.get("output")),
            )

    def _format_preview(self, output) -> str:
        """Format output for preview."""
        if output is None:
            return ""
        if isinstance(output, dict):
            sc = output.get("status_code", "")
            return f"HTTP {sc}" if sc else str(output)[:40]
        if isinstance(output, list):
            return f"{len(output)} items"
        return str(output)[:40]

    def set_summary(self, success: bool, duration_ms: int, total: int, passed: int, failed: int) -> None:
        """Update the execution summary."""
        summary = self.query_one("#execution-summary", Static)
        status = "[green]PASSED[/green]" if success else "[red]FAILED[/red]"
        summary.update(
            f"{status}  {duration_ms}ms  {total} steps  "
            f"[green]{passed} ok[/green] / [red]{failed} failed[/red]"
        )
