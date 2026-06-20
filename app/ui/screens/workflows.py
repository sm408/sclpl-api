"""Workflows screen with step list and execution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, DataTable, Input, ProgressBar, Static


class WorkflowList(Vertical):
    """List of available workflows."""

    CSS = """
    WorkflowList {
        height: 100%;
        padding: 1;
    }

    #workflow-table {
        height: 1fr;
    }

    #workflow-actions {
        height: auto;
        margin-top: 1;
    }
    """

    class RunWorkflow(Message):
        """Message sent when user wants to run a workflow."""
        def __init__(self, workflow: dict) -> None:
            self.workflow = workflow
            super().__init__()

    class ViewSteps(Message):
        """Message sent when user wants to view workflow steps."""
        def __init__(self, workflow: dict) -> None:
            self.workflow = workflow
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._workflows: list[dict] = []
        self._all_workflows: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search workflows...", id="workflow-search")
        yield DataTable(id="workflow-table")

        with Horizontal(id="workflow-actions"):
            yield Button("Run", variant="success", id="run-workflow-btn")
            yield Button("View Steps", id="view-steps-btn")

    @on(Input.Changed, "#workflow-search")
    def search_changed(self, event: Input.Changed) -> None:
        """Filter workflows by search query."""
        query = event.value.lower().strip()
        if not query:
            self.set_workflows(self._all_workflows)
        else:
            filtered = [w for w in self._all_workflows if query in w.get("name", "").lower()]
            self.set_workflows(filtered)

    def on_mount(self) -> None:
        table = self.query_one("#workflow-table", DataTable)
        table.add_columns("Name", "Steps", "ID")
        table.cursor_type = "row"

    def set_workflows(self, workflows: list[dict]) -> None:
        """Update the workflow table."""
        self._all_workflows = workflows
        self._workflows = workflows
        table = self.query_one("#workflow-table", DataTable)
        table.clear()
        for wf in workflows:
            table.add_row(
                wf.get("name", wf.get("id", "Unknown")),
                str(wf.get("step_count", 0)),
                wf.get("id", "")[:8],
            )

    def _get_selected_workflow(self) -> dict | None:
        """Get the currently selected workflow."""
        table = self.query_one("#workflow-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self._workflows):
            return self._workflows[table.cursor_row]
        return None

    @on(Button.Pressed, "#run-workflow-btn")
    def run_pressed(self) -> None:
        wf = self._get_selected_workflow()
        if wf:
            self.post_message(self.RunWorkflow(wf))
        else:
            self.notify("Select a workflow first", severity="warning")

    @on(Button.Pressed, "#view-steps-btn")
    def view_steps_pressed(self) -> None:
        wf = self._get_selected_workflow()
        if wf:
            self.post_message(self.ViewSteps(wf))
        else:
            self.notify("Select a workflow first", severity="warning")


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

    class ReRunWorkflow(Message):
        """Message sent when user wants to re-run."""
        def __init__(self, workflow: dict) -> None:
            self.workflow = workflow
            super().__init__()

    class ExportResults(Message):
        """Message sent when user wants to export results."""
        def __init__(self, fmt: str, result: Any) -> None:
            self.fmt = fmt
            self.result = result
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._workflow: dict | None = None
        self._result: Any = None

    def compose(self) -> ComposeResult:
        yield Static("[bold]Workflow Execution[/bold]", id="execution-header")
        yield ProgressBar(id="execution-progress")
        yield DataTable(id="execution-steps")

        yield Static("", id="execution-summary")

        with Horizontal(id="execution-actions"):
            yield Button("Export JSON", id="export-json-btn")
            yield Button("Export CSV", id="export-csv-btn")
            yield Button("Re-run", id="rerun-workflow-btn")

    def on_mount(self) -> None:
        table = self.query_one("#execution-steps", DataTable)
        table.add_columns("Status", "Step", "Type", "Duration", "Output")
        table.cursor_type = "row"

    def set_workflow(self, workflow: dict) -> None:
        self._workflow = workflow

    def set_result(self, result: Any) -> None:
        """Set the workflow result and update display."""
        self._result = result
        if not result:
            return

        # Update header
        header = self.query_one("#execution-header", Static)
        header.update(f"[bold]{result.workflow_name}[/bold]")

        # Update steps table
        table = self.query_one("#execution-steps", DataTable)
        table.clear()
        for sr in result.step_results:
            status = "OK" if sr.success else "FAIL"
            status_color = "green" if sr.success else "red"
            preview = ""
            if sr.error:
                preview = f"[red]{str(sr.error)[:50]}[/red]"
            elif sr.output is not None:
                if isinstance(sr.output, dict):
                    sc = sr.output.get("status_code", "")
                    preview = f"HTTP {sc}" if sc else str(sr.output)[:40]
                elif isinstance(sr.output, list):
                    preview = f"{len(sr.output)} items"
                else:
                    preview = str(sr.output)[:40]
            table.add_row(
                f"[{status_color}]{status}[/{status_color}]",
                sr.step_name,
                "request",
                f"{sr.duration_ms}ms",
                preview,
            )

        # Update summary
        passed = sum(1 for r in result.step_results if r.success)
        failed = sum(1 for r in result.step_results if not r.success)
        summary = self.query_one("#execution-summary", Static)
        status = "[green]PASSED[/green]" if result.success else "[red]FAILED[/red]"
        summary.update(
            f"{status}  {result.total_duration_ms}ms  {len(result.step_results)} steps  "
            f"[green]{passed} ok[/green] / [red]{failed} failed[/red]"
        )

        # Update progress
        progress = self.query_one("#execution-progress", ProgressBar)
        progress.total = len(result.step_results)
        progress.progress = len(result.step_results)

    @on(Button.Pressed, "#export-json-btn")
    def export_json_pressed(self) -> None:
        if self._result:
            self.post_message(self.ExportResults("json", self._result))
        else:
            self.notify("No results to export", severity="warning")

    @on(Button.Pressed, "#export-csv-btn")
    def export_csv_pressed(self) -> None:
        if self._result:
            self.post_message(self.ExportResults("csv", self._result))
        else:
            self.notify("No results to export", severity="warning")

    @on(Button.Pressed, "#rerun-workflow-btn")
    def rerun_pressed(self) -> None:
        if self._workflow:
            self.post_message(self.ReRunWorkflow(self._workflow))
        else:
            self.notify("No workflow to re-run", severity="warning")
