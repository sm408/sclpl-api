"""Textual-based TUI application.

Primary interaction layer for SCLPLAPI.
"""

from __future__ import annotations

import asyncio
import csv
import json
import time
from datetime import UTC
from pathlib import Path
from typing import Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from app.ui.app import App as SCLPLApp
from app.ui.commands import COMMANDS
from app.ui.screens.batch import BatchView
from app.ui.screens.collections import CollectionList
from app.ui.screens.diff_viewer import DiffViewer
from app.ui.screens.environments import EnvironmentView
from app.ui.screens.functions import FunctionBrowser
from app.ui.screens.history import HistoryView
from app.ui.screens.import_export import ImportExportView
from app.ui.screens.log_viewer import LogViewer
from app.ui.screens.monitors import MonitorList
from app.ui.screens.plugins import PluginBrowser
from app.ui.screens.request_editor import RequestEditor
from app.ui.screens.settings import SettingsView
from app.ui.screens.workflows import WorkflowExecution, WorkflowList
from app.ui.widgets.command_palette import Command, CommandPalette
from app.ui.widgets.sidebar import Sidebar


class SCLPLTextualApp(App):
    """SCLPLAPI Textual TUI."""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 2;
        grid-columns: 25% 1fr 1fr;
        grid-rows: 1fr 3;
    }

    #sidebar {
        row-span: 2;
        background: $surface;
        border-right: solid $primary;
    }

    #workspace {
        column-span: 2;
        background: $surface;
    }

    #log-pane {
        column-span: 3;
        background: $surface-darken-1;
        border-top: solid $primary;
        height: 3;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+p", "command_palette", "Command Palette"),
        Binding("ctrl+t", "new_request", "New Request"),
        Binding("ctrl+r", "run_request", "Run Request"),
        Binding("ctrl+w", "close_tab", "Close Tab"),
        Binding("ctrl+b", "batch_mode", "Batch Mode"),
        Binding("ctrl+m", "show_monitors", "Monitors"),
        Binding("f1", "help", "Help"),
        Binding("f2", "toggle_theme", "Toggle Theme"),
        Binding("f5", "refresh", "Refresh"),
        Binding("escape", "cancel", "Cancel"),
    ]

    THEME = "dark"

    TITLE = "SCLPLAPI"
    SUB_TITLE = "API Workflow Studio"

    def __init__(self, db_path: str = "data/sclplapi.db", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.db_path = db_path
        self._app: SCLPLApp | None = None
        self._commands: list[Command] = []
        self._workflows: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Sidebar(id="sidebar")
        with TabbedContent(id="workspace"):
            with TabPane("Request", id="tab-request"):
                yield RequestEditor()
            with TabPane("Collections", id="tab-collections"):
                yield CollectionList()
            with TabPane("History", id="tab-history"):
                yield HistoryView()
            with TabPane("Workflows", id="tab-workflows"):
                yield WorkflowList()
                yield WorkflowExecution(id="workflow-exec")
            with TabPane("Environments", id="tab-environments"):
                yield EnvironmentView()
            with TabPane("Functions", id="tab-functions"):
                yield FunctionBrowser()
            with TabPane("Plugins", id="tab-plugins"):
                yield PluginBrowser()
            with TabPane("Import/Export", id="tab-import-export"):
                yield ImportExportView()
            with TabPane("Monitors", id="tab-monitors"):
                yield MonitorList()
            with TabPane("Batch", id="tab-batch"):
                yield BatchView()
            with TabPane("Diff", id="tab-diff"):
                yield DiffViewer()
            with TabPane("Logs", id="tab-logs"):
                yield LogViewer()
            with TabPane("Settings", id="tab-settings"):
                yield SettingsView()
        yield Static("[dim]Ready[/dim]", id="log-pane")
        yield Footer()

    async def on_mount(self) -> None:
        self._app = SCLPLApp(self.db_path)
        await self._app.start()
        self._build_commands()
        self._subscribe_events()
        self._load_data()

    def _subscribe_events(self) -> None:
        """Subscribe to event bus for UI updates."""
        if not self._app:
            return

        def on_event(event):
            """Handle events from the event bus."""
            name = event.name
            data = event.data

            # Update log pane
            try:
                log_pane = self.query_one("#log-pane", Static)
                if "workflow" in name:
                    log_pane.update(f"[cyan]{name}[/cyan]")
                elif "request" in name:
                    log_pane.update(f"[yellow]{name}[/yellow]")
                elif "export" in name:
                    log_pane.update(f"[green]{name}[/green]")
                elif "plugin" in name:
                    log_pane.update(f"[magenta]{name}[/magenta]")
                else:
                    log_pane.update(f"[dim]{name}[/dim]")
            except Exception:
                pass

            # Log to log viewer
            try:
                log_viewer = self.query_one("LogViewer")
                if log_viewer:
                    level = "info"
                    if "error" in name or "failed" in name:
                        level = "error"
                    elif "completed" in name or "success" in name:
                        level = "success"
                    log_viewer.add_log(f"{name}: {data}", level=level, source="event-bus")
            except Exception:
                pass

        self._app.event_bus.subscribe("*", on_event)

    async def on_unmount(self) -> None:
        if self._app:
            await self._app.stop()

    def _build_commands(self) -> None:
        self._commands = []
        for cmd_def in COMMANDS:
            handler = getattr(self, cmd_def.handler, None)
            if handler:
                self._commands.append(Command(
                    name=cmd_def.name,
                    handler=handler,
                    shortcut=cmd_def.shortcut,
                    description=cmd_def.description,
                    category=cmd_def.category,
                ))

    @work(exclusive=True)
    async def _load_data(self) -> None:
        if not self._app:
            return
        try:
            # Collections
            cols = await self._app.collections.list_all()
            collections_data = []
            for col in cols:
                reqs = await self._app.requests.list_all(collection_id=col["id"])
                collections_data.append({**col, "requests": reqs})
            sidebar = self.query_one("#sidebar", Sidebar)
            sidebar.update_collections(collections_data)
            try:
                self.query_one("CollectionList").set_collections(collections_data)
            except Exception:
                pass

            # Workflows
            self._workflows = []
            for d in [Path("examples"), Path("workflows")]:
                if d.exists():
                    for wf_file in sorted(d.rglob("*.json")):
                        try:
                            data = json.loads(wf_file.read_text(encoding="utf-8"))
                            if "steps" in data:
                                self._workflows.append({
                                    "id": data.get("id", wf_file.parent.name),
                                    "name": data.get("name", wf_file.stem),
                                    "step_count": len(data.get("steps", [])),
                                    "path": str(wf_file),
                                    "data": data,
                                })
                        except (json.JSONDecodeError, OSError):
                            pass
            sidebar.update_workflows(self._workflows)
            try:
                self.query_one("WorkflowList").set_workflows(self._workflows)
            except Exception:
                pass

            # Environments
            envs = await self._app.environments.list_all()
            active_env = next((e for e in envs if e.get("is_active")), None)
            if active_env:
                sidebar.update_environment(active_env["name"], len(active_env.get("variables", [])))
            try:
                self.query_one("EnvironmentView").set_environments(envs)
            except Exception:
                pass

            # History
            history = await self._app.history.list_recent(50)
            try:
                self.query_one("HistoryView").set_entries(history)
            except Exception:
                pass

            # Functions
            from app.core.engine.function_runner import FilesystemFunctionRunner
            runner = FilesystemFunctionRunner("functions")
            funcs = runner.discover()
            try:
                self.query_one("FunctionBrowser").set_functions(funcs)
            except Exception:
                pass

            # Plugins
            if self._app.plugin_registry:
                plugins = self._app.plugin_registry.list_plugins()
                try:
                    self.query_one("PluginBrowser").set_plugins(plugins)
                except Exception:
                    pass

            # Monitors
            monitors = await self._get_monitor_dicts()
            try:
                self.query_one("MonitorList").set_monitors(monitors)
            except Exception:
                pass

        except Exception as e:
            self.log(f"Error loading data: {e}")

    # ── Workflow Messages ────────────────────────────────────────────────

    @on(WorkflowList.RunWorkflow)
    def on_run_workflow(self, event: WorkflowList.RunWorkflow) -> None:
        self._run_workflow(event.workflow)

    @on(WorkflowList.ViewSteps)
    def on_view_steps(self, event: WorkflowList.ViewSteps) -> None:
        self._view_workflow_steps(event.workflow)

    @on(WorkflowExecution.ReRunWorkflow)
    def on_rerun_workflow(self, event: WorkflowExecution.ReRunWorkflow) -> None:
        self._run_workflow(event.workflow)

    @on(WorkflowExecution.ExportResults)
    def on_export_results(self, event: WorkflowExecution.ExportResults) -> None:
        self._export_workflow_results(event.fmt, event.result)

    # ── Collection Messages ──────────────────────────────────────────────

    @on(Button.Pressed, "#new-collection-btn")
    def on_new_collection(self) -> None:
        self._create_collection()

    @on(Button.Pressed, "#delete-collection-btn")
    def on_delete_collection(self) -> None:
        self._delete_collection()

    # ── History Messages ─────────────────────────────────────────────────

    @on(Button.Pressed, "#clear-history-btn")
    def on_clear_history(self) -> None:
        self._clear_history()

    @on(Button.Pressed, "#inspect-btn")
    def on_inspect_history(self) -> None:
        self._inspect_history()

    # ── Environment Messages ─────────────────────────────────────────────

    @on(Button.Pressed, "#new-env-btn")
    def on_new_env(self) -> None:
        self._create_environment()

    @on(Button.Pressed, "#activate-env-btn")
    def on_activate_env(self) -> None:
        self._activate_environment()

    @on(Button.Pressed, "#delete-env-btn")
    def on_delete_env(self) -> None:
        self._delete_environment()

    @on(Button.Pressed, "#set-var-btn")
    def on_set_var(self) -> None:
        self._set_variable()

    @on(Button.Pressed, "#delete-var-btn")
    def on_delete_var(self) -> None:
        self._delete_variable()

    # ── Plugin Messages ──────────────────────────────────────────────────

    @on(Button.Pressed, "#reload-plugins-btn")
    def on_reload_plugins(self) -> None:
        self._reload_plugins()

    # ── Import/Export Messages ───────────────────────────────────────────

    @on(Button.Pressed, "#export-all-btn")
    def on_export_all(self) -> None:
        self._export_all()

    @on(Button.Pressed, "#import-all-btn")
    def on_import_all(self) -> None:
        self._import_all()

    @on(Button.Pressed, "#export-collections-btn")
    def on_export_collections(self) -> None:
        self._export_collections()

    @on(Button.Pressed, "#import-collections-btn")
    def on_import_collections(self) -> None:
        self._import_collections()

    @on(Button.Pressed, "#export-envs-btn")
    def on_export_envs(self) -> None:
        self._export_environments()

    @on(Button.Pressed, "#import-envs-btn")
    def on_import_envs(self) -> None:
        self._import_environments()

    @on(Button.Pressed, "#import-openapi-btn")
    def on_import_openapi(self) -> None:
        self._import_openapi()

    # ── Batch Messages ───────────────────────────────────────────────────

    @on(BatchView.CsvLoaded)
    def on_csv_loaded(self, event: BatchView.CsvLoaded) -> None:
        self.notify(f"Loaded {len(event.rows)} CSV rows")

    @on(BatchView.BatchStart)
    def on_batch_start(self, event: BatchView.BatchStart) -> None:
        self._run_batch(event.rows)

    @on(Button.Pressed, "#load-csv-btn")
    def on_load_csv(self) -> None:
        # CSV loading is handled by BatchView itself
        pass

    @on(Button.Pressed, "#start-batch-btn")
    def on_start_batch(self) -> None:
        batch_view = self.query_one("BatchView")
        rows = batch_view.get_csv_rows()
        if rows:
            self._run_batch(rows)
        else:
            self.notify("Load a CSV file first", severity="warning")

    @on(Button.Pressed, "#stop-batch-btn")
    def on_stop_batch(self) -> None:
        self.notify("Batch stop requested", severity="warning")

    # ── Monitor Messages ─────────────────────────────────────────────────

    @on(MonitorList.NewMonitor)
    def on_new_monitor(self, event: MonitorList.NewMonitor) -> None:
        self._create_monitor()

    @on(MonitorList.StartMonitor)
    def on_start_monitor(self, event: MonitorList.StartMonitor) -> None:
        self._start_monitor(event.monitor_id)

    @on(MonitorList.StopMonitor)
    def on_stop_monitor(self, event: MonitorList.StopMonitor) -> None:
        self._stop_monitor(event.monitor_id)

    @on(MonitorList.DeleteMonitor)
    def on_delete_monitor(self, event: MonitorList.DeleteMonitor) -> None:
        self._delete_monitor(event.monitor_id)

    @on(MonitorList.ViewDetail)
    def on_view_monitor_detail(self, event: MonitorList.ViewDetail) -> None:
        self._view_monitor_detail(event.monitor_id)

    # ── History Cleanup ──────────────────────────────────────────────────

    @on(Button.Pressed, "#cleanup-btn")
    def on_cleanup_history(self) -> None:
        self._cleanup_history()

    # ── Actions ──────────────────────────────────────────────────────────

    def action_command_palette(self) -> None:
        self.push_screen(CommandPalette(self._commands))

    def action_new_request(self) -> None:
        workspace = self.query_one("#workspace", TabbedContent)
        workspace.active = "tab-request"

    def action_run_request(self) -> None:
        self._execute_request()

    def action_close_tab(self) -> None:
        workspace = self.query_one("#workspace", TabbedContent)
        workspace.active = "tab-request"

    def action_help(self) -> None:
        lines = []
        for cmd in COMMANDS:
            if cmd.shortcut:
                lines.append(f"  {cmd.shortcut:15} {cmd.name}")
        self.notify("Keyboard Shortcuts:\n" + "\n".join(lines), severity="information")

    def action_batch_mode(self) -> None:
        self.query_one("#workspace", TabbedContent).active = "tab-batch"

    def action_show_monitors(self) -> None:
        self.query_one("#workspace", TabbedContent).active = "tab-monitors"

    def action_new_monitor(self) -> None:
        self._create_monitor()

    def action_start_monitor(self) -> None:
        monitor_list = self.query_one("MonitorList")
        m = monitor_list.get_selected_monitor()
        if m:
            self._start_monitor(m["id"])
        else:
            self.notify("Select a monitor first", severity="warning")

    def action_stop_monitor(self) -> None:
        monitor_list = self.query_one("MonitorList")
        m = monitor_list.get_selected_monitor()
        if m:
            self._stop_monitor(m["id"])
        else:
            self.notify("Select a monitor first", severity="warning")

    def action_toggle_theme(self) -> None:
        """Toggle between dark and light themes."""
        if self.THEME == "dark":
            self.THEME = "light"
            self.notify("Switched to light theme")
        else:
            self.THEME = "dark"
            self.notify("Switched to dark theme")

    def action_refresh(self) -> None:
        self._load_data()
        self.notify("Refreshed", severity="information")

    def action_cancel(self) -> None:
        pass

    def action_show_collections(self) -> None:
        self.query_one("#workspace", TabbedContent).active = "tab-collections"

    def action_show_history(self) -> None:
        self.query_one("#workspace", TabbedContent).active = "tab-history"

    def action_show_workflows(self) -> None:
        self.query_one("#workspace", TabbedContent).active = "tab-workflows"

    def action_show_environments(self) -> None:
        self.query_one("#workspace", TabbedContent).active = "tab-environments"

    def action_show_functions(self) -> None:
        self.query_one("#workspace", TabbedContent).active = "tab-functions"

    def action_show_plugins(self) -> None:
        self.query_one("#workspace", TabbedContent).active = "tab-plugins"

    def action_show_import_export(self) -> None:
        self.query_one("#workspace", TabbedContent).active = "tab-import-export"

    def action_show_settings(self) -> None:
        self.query_one("#workspace", TabbedContent).active = "tab-settings"

    def action_run_workflow(self) -> None:
        self.query_one("#workspace", TabbedContent).active = "tab-workflows"

    def action_recent_workflows(self) -> None:
        self.query_one("#workspace", TabbedContent).active = "tab-workflows"

    def action_validate_script(self) -> None:
        self.notify("Open a .sclpll file to validate", severity="information")

    def action_switch_environment(self) -> None:
        self.query_one("#workspace", TabbedContent).active = "tab-environments"

    # ── Workflow Execution ───────────────────────────────────────────────

    @work(exclusive=True)
    async def _run_workflow(self, workflow: dict) -> None:
        if not self._app:
            return

        path = Path(workflow.get("path", ""))
        if not path.exists():
            self.notify(f"Workflow file not found: {path}", severity="error")
            return

        try:
            source = path.read_text(encoding="utf-8")
            if path.suffix == ".sclpll":
                from app.core.engine.sclpll_compiler import SCLPLLCompiler
                compiler = SCLPLLCompiler()
                workflow_dict = compiler.parse(source)
            else:
                workflow_dict = json.loads(source)
        except Exception as e:
            self.notify(f"Failed to parse workflow: {e}", severity="error")
            return

        # Build workflow objects
        from app.core.engine.parallel_workflow import ParallelWorkflowEngine
        from app.core.models.context import ExecutionContext
        from app.core.models.workflow import StepType, WorkflowDef, WorkflowStep

        steps = []
        for s in workflow_dict.get("steps", []):
            steps.append(WorkflowStep(
                id=s["id"],
                name=s.get("name", s["id"]),
                step_type=StepType(s["type"]),
                config=s.get("config", {}),
                depends_on=s.get("depends_on", []),
                output_variable=s.get("output_variable"),
            ))

        workflow_def = WorkflowDef(
            id=workflow_dict.get("id", "tui-workflow"),
            name=workflow_dict.get("name", "TUI Workflow"),
            description=workflow_dict.get("description", ""),
            steps=steps,
            variables=workflow_dict.get("variables", {}),
        )

        # Switch to workflows tab
        self.query_one("#workspace", TabbedContent).active = "tab-workflows"

        # Execute
        self.notify(f"Running {workflow_def.name}...")
        log = self.query_one("#log-pane", Static)
        log.update(f"[yellow]Running {workflow_def.name}...[/yellow]")

        try:
            engine = ParallelWorkflowEngine(
                request_executor=self._app.request_executor,
                event_bus=self._app.event_bus,
            )
            ctx = ExecutionContext()
            result = await engine.execute(workflow_def, ctx, {})

            # Update execution view
            exec_view = self.query_one("#workflow-exec", WorkflowExecution)
            exec_view.set_workflow(workflow)
            exec_view.set_result(result)

            # Update log
            status = "[green]PASSED[/green]" if result.success else "[red]FAILED[/red]"
            log.update(f"{status}  {workflow_def.name}  {result.total_duration_ms}ms")

            # Reload history
            history = await self._app.history.list_recent(50)
            try:
                self.query_one("HistoryView").set_entries(history)
            except Exception:
                pass

        except Exception as e:
            self.notify(f"Workflow failed: {e}", severity="error")
            log.update(f"[red]Workflow failed: {e}[/red]")

    def _view_workflow_steps(self, workflow: dict) -> None:
        data = workflow.get("data", {})
        steps = data.get("steps", [])
        if not steps:
            self.notify("No steps in this workflow", severity="warning")
            return

        lines = []
        for i, step in enumerate(steps, 1):
            deps = step.get("depends_on", [])
            dep_str = f" <- {', '.join(deps)}" if deps else ""
            lines.append(f"  {i}. {step.get('name', step['id'])} ({step.get('type', 'request')}){dep_str}")

        self.notify("Workflow Steps:\n" + "\n".join(lines), severity="information")

    # ── Request Execution ────────────────────────────────────────────────

    @work(exclusive=True)
    async def _execute_request(self) -> None:
        if not self._app:
            return

        try:
            request_editor = self.query_one("RequestEditor")
        except Exception:
            return

        data = request_editor.get_request_data()
        url = data.get("url", "")
        if not url:
            self.notify("No URL provided", severity="warning")
            return

        from app.core.models.request import HttpMethod, RequestDef
        method = data.get("method", "GET")
        try:
            http_method = HttpMethod(method)
        except ValueError:
            http_method = HttpMethod.GET

        request = RequestDef(
            id="tui-request",
            name=f"{method} {url}",
            method=http_method,
            url=url,
            headers=data.get("headers", {}),
            body=data.get("body") or None,
        )

        from app.core.models.context import ExecutionContext
        ctx = ExecutionContext()

        self.notify(f"Sending {method} {url}...")
        log = self.query_one("#log-pane", Static)
        log.update(f"[yellow]Sending {method} {url}...[/yellow]")

        try:
            result, history = await self._app.request_executor.execute_with_history(request, ctx)
            await self._app.history.save(history)

            try:
                response_viewer = self.query_one("ResponseViewer")
                response_viewer.set_response(
                    status_code=result.status_code,
                    headers=dict(result.headers) if result.headers else {},
                    body=result.body,
                    duration_ms=history.duration_ms,
                )
            except Exception:
                pass

            status_color = "green" if 200 <= result.status_code < 300 else "red"
            log.update(f"[{status_color}]{result.status_code}[/{status_color}]  {method} {url}  {history.duration_ms}ms")

            # Reload history
            try:
                history_entries = await self._app.history.list_recent(50)
                self.query_one("HistoryView").set_entries(history_entries)
            except Exception:
                pass

        except Exception as e:
            self.notify(f"Request failed: {e}", severity="error")
            log.update(f"[red]Error: {e}[/red]")

    # ── Workflow Export ──────────────────────────────────────────────────

    @work(exclusive=True)
    async def _export_workflow_results(self, fmt: str, result: Any) -> None:
        rows = []
        for sr in result.step_results:
            row = {
                "step_id": sr.step_id,
                "step_name": sr.step_name,
                "success": sr.success,
                "duration_ms": sr.duration_ms,
                "error": sr.error or "",
            }
            if sr.output is not None:
                if isinstance(sr.output, dict):
                    row["output_status_code"] = sr.output.get("status_code", "")
                    body = sr.output.get("body", "")
                    row["output_body"] = body[:5000] if isinstance(body, str) else json.dumps(body, default=str)[:5000]
                elif isinstance(sr.output, list):
                    row["output_body"] = json.dumps(sr.output, default=str)[:5000]
                else:
                    row["output_body"] = str(sr.output)[:5000]
            else:
                row["output_body"] = ""
            rows.append(row)

        if not rows:
            self.notify("No results to export", severity="warning")
            return

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"data/exports/{result.workflow_id}_{timestamp}.{fmt}")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if fmt == "json":
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(rows, f, indent=2, default=str)
            elif fmt == "csv":
                fieldnames = list(rows[0].keys())
                with open(output_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)

            self.notify(f"Exported to {output_path}", severity="information")
        except OSError as e:
            self.notify(f"Export failed: {e}", severity="error")

    # ── Monitor Operations ───────────────────────────────────────────────

    @work(exclusive=True)
    async def _create_monitor(self) -> None:
        """Create a new monitor."""
        if not self._app:
            return

        name = await self.prompt("Monitor name:")
        if not name:
            return

        url = await self.prompt("URL to monitor:")
        if not url:
            return

        interval_str = await self.prompt("Poll interval (seconds):", default="60")
        try:
            interval = int(interval_str)
        except (ValueError, TypeError):
            interval = 60

        condition = await self.prompt("Condition (e.g., status == 200):", default="")

        try:
            monitor = await self._app.monitors.create(
                name=name,
                url=url,
                interval_seconds=interval,
                condition=condition,
            )
            self.notify(f"Created monitor '{name}'")
            self._load_monitors()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @work(exclusive=True)
    async def _start_monitor(self, monitor_id: str) -> None:
        """Start a monitor."""
        if not self._app or not self._app.monitor_runner:
            return
        try:
            await self._app.monitor_runner.start_monitor(monitor_id)
            self.notify("Monitor started")
            self._load_monitors()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @work(exclusive=True)
    async def _stop_monitor(self, monitor_id: str) -> None:
        """Stop a monitor."""
        if not self._app or not self._app.monitor_runner:
            return
        try:
            await self._app.monitor_runner.stop_monitor(monitor_id)
            self.notify("Monitor stopped")
            self._load_monitors()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @work(exclusive=True)
    async def _delete_monitor(self, monitor_id: str) -> None:
        """Delete a monitor."""
        if not self._app:
            return
        try:
            monitor = await self._app.monitors.get(monitor_id)
            if monitor and await self.confirm(f"Delete monitor '{monitor.name}'?"):
                # Stop first if running
                if self._app.monitor_runner:
                    await self._app.monitor_runner.stop_monitor(monitor_id)
                await self._app.monitors.delete(monitor_id)
                self.notify(f"Deleted monitor '{monitor.name}'")
                self._load_monitors()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @work(exclusive=True)
    async def _view_monitor_detail(self, monitor_id: str) -> None:
        """View monitor detail."""
        if not self._app:
            return
        try:
            monitor = await self._app.monitors.get(monitor_id)
            if not monitor:
                self.notify("Monitor not found", severity="error")
                return

            events = await self._app.monitors.get_events(monitor_id, limit=100)

            # Switch to monitors tab and show detail
            workspace = self.query_one("#workspace", TabbedContent)
            workspace.active = "tab-monitors"

            monitor_list = self.query_one("MonitorList")
            monitor_list.set_monitors(await self._get_monitor_dicts())

            # TODO: Show detail view in a modal or sub-screen
            self.notify(f"Monitor: {monitor.name} - {len(events)} events")

        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    def _load_monitors(self) -> None:
        """Load monitors into the list."""
        if not self._app:
            return
        try:
            asyncio.create_task(self._load_monitors_async())
        except Exception:
            pass

    async def _load_monitors_async(self) -> None:
        """Load monitors asynchronously."""
        if not self._app:
            return
        try:
            monitors = await self._get_monitor_dicts()
            monitor_list = self.query_one("MonitorList")
            monitor_list.set_monitors(monitors)
        except Exception:
            pass

    async def _get_monitor_dicts(self) -> list[dict]:
        """Get monitors as dicts."""
        if not self._app:
            return []
        monitors = await self._app.monitors.list_all()
        return [
            {
                "id": m.id,
                "name": m.name,
                "url": m.url,
                "method": m.method,
                "interval_seconds": m.interval_seconds,
                "condition": m.condition,
                "status": m.status.value,
                "enabled": m.enabled,
                "run_count": m.run_count,
                "trigger_count": m.trigger_count,
                "last_run": m.last_run,
                "last_status_code": m.last_status_code,
            }
            for m in monitors
        ]

    # ── Batch Execution ──────────────────────────────────────────────────

    @work(exclusive=True)
    async def _run_batch(self, rows: list[dict]) -> None:
        """Execute a batch of requests from CSV rows."""
        if not self._app:
            return

        batch_view = self.query_one("BatchView")
        self.notify(f"Starting batch with {len(rows)} rows...")

        completed = 0
        failed = 0

        for i, row in enumerate(rows, 1):
            try:
                url = row.get("url", "")
                if not url:
                    failed += 1
                    batch_view.add_row_result(i, False, 0, "No URL")
                    continue

                # Build request from CSV row
                from app.core.models.context import ExecutionContext
                from app.core.models.request import HttpMethod, RequestDef

                method = row.get("method", "GET").upper()
                try:
                    http_method = HttpMethod(method)
                except ValueError:
                    http_method = HttpMethod.GET

                request = RequestDef(
                    id=f"batch-{i}",
                    name=f"Batch {i}",
                    method=http_method,
                    url=url,
                    headers={k: v for k, v in row.items() if k not in ("url", "method")},
                    body=row.get("body"),
                )

                ctx = ExecutionContext()
                result, history = await self._app.request_executor.execute_with_history(request, ctx)
                await self._app.history.save(history)

                completed += 1
                batch_view.add_row_result(i, True, history.duration_ms)

            except Exception as e:
                failed += 1
                batch_view.add_row_result(i, False, 0, str(e)[:50])

            batch_view.set_progress(completed, failed, len(rows))

        self.notify(f"Batch complete: {completed} ok, {failed} failed")

    # ── History Cleanup ──────────────────────────────────────────────────

    @work(exclusive=True)
    async def _cleanup_history(self) -> None:
        """Clean up old history entries."""
        if not self._app:
            return

        try:
            history_tab = self.query_one("HistoryView")
            policy_select = history_tab.query_one("#cleanup-policy", Select)
            policy = str(policy_select.value)

            if policy == "all":
                self.notify("Keeping all history")
                return

            # Parse policy
            days = int(policy.replace("d", ""))
            self.notify(f"Cleaning up history older than {days} days...")

            # Get all entries and delete old ones
            entries = await self._app.history.list_recent(10000)
            from datetime import datetime, timedelta
            cutoff = datetime.now(UTC) - timedelta(days=days)

            deleted = 0
            for entry in entries:
                created_at = entry.get("created_at", "")
                if created_at:
                    try:
                        entry_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        if entry_time < cutoff:
                            # Delete old entry
                            deleted += 1
                    except (ValueError, TypeError):
                        pass

            self.notify(f"Cleanup: would delete {deleted} entries older than {days} days")

            # Reload history
            history = await self._app.history.list_recent(50)
            history_tab.set_entries(history)

        except Exception as e:
            self.notify(f"Cleanup failed: {e}", severity="error")

    # ── Collection CRUD ──────────────────────────────────────────────────

    @on(CollectionList.CollectionCreated)
    def on_collection_created(self, event: CollectionList.CollectionCreated) -> None:
        self._create_collection()

    @on(CollectionList.CollectionDeleted)
    def on_collection_deleted(self, event: CollectionList.CollectionDeleted) -> None:
        self._delete_collection_by_id(event.collection_id)

    @on(CollectionList.CollectionRenamed)
    def on_collection_renamed(self, event: CollectionList.CollectionRenamed) -> None:
        self._rename_collection(event.collection_id)

    @on(CollectionList.CollectionDuplicated)
    def on_collection_duplicated(self, event: CollectionList.CollectionDuplicated) -> None:
        self._duplicate_collection(event.collection_id)

    @work(exclusive=True)
    async def _create_collection(self) -> None:
        if not self._app:
            return
        name = await self.prompt("Collection name:")
        if not name:
            return
        try:
            await self._app.collections.create(name)
            self.notify(f"Created collection '{name}'")
            self._load_data()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @work(exclusive=True)
    async def _delete_collection_by_id(self, collection_id: str) -> None:
        if not self._app:
            return
        try:
            col = await self._app.collections.get(collection_id)
            if col and await self.confirm(f"Delete '{col['name']}'?"):
                await self._app.collections.delete(collection_id)
                self.notify(f"Deleted '{col['name']}'")
                self._load_data()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @work(exclusive=True)
    async def _rename_collection(self, collection_id: str) -> None:
        if not self._app:
            return
        try:
            col = await self._app.collections.get(collection_id)
            if not col:
                return
            new_name = await self.prompt(f"Rename '{col['name']}' to:", default=col["name"])
            if not new_name or new_name == col["name"]:
                return
            # Update collection name
            await self._app.collections.delete(collection_id)
            new_col = await self._app.collections.create(new_name, col.get("description", ""))
            # Move requests to new collection
            reqs = await self._app.requests.list_all(collection_id=collection_id)
            for req in reqs:
                await self._app.requests.create({
                    "collection_id": new_col["id"],
                    "name": req.get("name", ""),
                    "method": req.get("method", "GET"),
                    "url": req.get("url", ""),
                    "headers": req.get("headers", []),
                    "body": req.get("body"),
                })
            self.notify(f"Renamed to '{new_name}'")
            self._load_data()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @work(exclusive=True)
    async def _duplicate_collection(self, collection_id: str) -> None:
        if not self._app:
            return
        try:
            col = await self._app.collections.get(collection_id)
            if not col:
                return
            new_name = f"{col['name']} (copy)"
            new_col = await self._app.collections.create(new_name, col.get("description", ""))
            # Copy requests
            reqs = await self._app.requests.list_all(collection_id=collection_id)
            for req in reqs:
                await self._app.requests.create({
                    "collection_id": new_col["id"],
                    "name": req.get("name", ""),
                    "method": req.get("method", "GET"),
                    "url": req.get("url", ""),
                    "headers": req.get("headers", []),
                    "body": req.get("body"),
                })
            self.notify(f"Duplicated as '{new_name}'")
            self._load_data()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    # ── History ──────────────────────────────────────────────────────────

    @work(exclusive=True)
    async def _clear_history(self) -> None:
        if not self._app:
            return
        if await self.confirm("Clear all history?"):
            await self._app.history.clear()
            self.notify("History cleared")
            self._load_data()

    @work(exclusive=True)
    async def _inspect_history(self) -> None:
        if not self._app:
            return
        try:
            history_tab = self.query_one("HistoryView")
            table = history_tab.query_one("#history-table", DataTable)
            entries = await self._app.history.list_recent(50)
            if table.cursor_row is not None and table.cursor_row < len(entries):
                history_tab.show_detail(entries[table.cursor_row])
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    # ── Environment CRUD ─────────────────────────────────────────────────

    @work(exclusive=True)
    async def _create_environment(self) -> None:
        if not self._app:
            return
        name = await self.prompt("Environment name:")
        if not name:
            return
        try:
            await self._app.environments.create(name)
            self.notify(f"Created environment '{name}'")
            self._load_data()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @work(exclusive=True)
    async def _activate_environment(self) -> None:
        if not self._app:
            return
        try:
            env_tab = self.query_one("EnvironmentView")
            table = env_tab.query_one("#env-table", DataTable)
            envs = await self._app.environments.list_all()
            if table.cursor_row is not None and table.cursor_row < len(envs):
                env = envs[table.cursor_row]
                await self._app.environments.set_active(env["id"])
                self.notify(f"Activated '{env['name']}'")
                self._load_data()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @work(exclusive=True)
    async def _delete_environment(self) -> None:
        if not self._app:
            return
        try:
            env_tab = self.query_one("EnvironmentView")
            table = env_tab.query_one("#env-table", DataTable)
            envs = await self._app.environments.list_all()
            if table.cursor_row is not None and table.cursor_row < len(envs):
                env = envs[table.cursor_row]
                if await self.confirm(f"Delete '{env['name']}'?"):
                    await self._app.environments.delete(env["id"])
                    self.notify(f"Deleted '{env['name']}'")
                    self._load_data()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @work(exclusive=True)
    async def _set_variable(self) -> None:
        if not self._app:
            return
        try:
            env_tab = self.query_one("EnvironmentView")
            table = env_tab.query_one("#env-table", DataTable)
            envs = await self._app.environments.list_all()
            if table.cursor_row is not None and table.cursor_row < len(envs):
                env = envs[table.cursor_row]
                key = await self.prompt("Variable name:")
                if not key:
                    return
                value = await self.prompt(f"{key} =")
                await self._app.environments.set_variable(env["id"], key, value)
                self.notify(f"Set {key} in '{env['name']}'")
                self._load_data()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @work(exclusive=True)
    async def _delete_variable(self) -> None:
        if not self._app:
            return
        try:
            env_tab = self.query_one("EnvironmentView")
            env_table = env_tab.query_one("#env-table", DataTable)
            var_table = env_tab.query_one("#env-variables", DataTable)
            envs = await self._app.environments.list_all()
            if env_table.cursor_row is not None and env_table.cursor_row < len(envs):
                env = envs[env_table.cursor_row]
                variables = env.get("variables", [])
                if var_table.cursor_row is not None and var_table.cursor_row < len(variables):
                    var = variables[var_table.cursor_row]
                    if await self.confirm(f"Delete '{var['key']}'?"):
                        await self._app.environments.delete_variable(env["id"], var["key"])
                        self.notify(f"Deleted {var['key']}")
                        self._load_data()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    # ── Plugins ──────────────────────────────────────────────────────────

    @work(exclusive=True)
    async def _reload_plugins(self) -> None:
        if not self._app or not self._app.plugin_registry:
            return
        try:
            self._app.plugin_registry.reload()
            plugins = self._app.plugin_registry.list_plugins()
            self.query_one("PluginBrowser").set_plugins(plugins)
            self.notify(f"Reloaded {len(plugins)} plugins")
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    # ── Import/Export ────────────────────────────────────────────────────

    @work(exclusive=True)
    async def _export_all(self) -> None:
        if not self._app:
            return
        try:
            from app.services.full_export_service import FullExportService
            svc = FullExportService(self._app)
            path = await svc.export_all("data/export_backup")
            self.notify(f"Exported to {path}")
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @work(exclusive=True)
    async def _import_all(self) -> None:
        if not self._app:
            return
        try:
            from app.services.full_import_service import FullImportService
            svc = FullImportService(self._app)
            result = await svc.import_all("data/export_backup")
            self.notify(f"Imported: {result}")
            self._load_data()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @work(exclusive=True)
    async def _export_collections(self) -> None:
        if not self._app:
            return
        try:
            cols = await self._app.collections.list_all()
            data = []
            for col in cols:
                reqs = await self._app.requests.list_all(collection_id=col["id"])
                data.append({"collection": col, "requests": reqs})
            output = Path("data/collections_export.json")
            output.parent.mkdir(parents=True, exist_ok=True)
            with open(output, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            self.notify(f"Exported {len(data)} collections")
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @work(exclusive=True)
    async def _import_collections(self) -> None:
        if not self._app:
            return
        try:
            with open("data/collections_export.json", encoding="utf-8") as f:
                data = json.load(f)
            count = 0
            for item in data:
                col = item.get("collection", {})
                reqs = item.get("requests", [])
                new_col = await self._app.collections.create(col.get("name", "Imported"), col.get("description", ""))
                for req in reqs:
                    await self._app.requests.create({
                        "collection_id": new_col["id"],
                        "name": req.get("name", "Untitled"),
                        "method": req.get("method", "GET"),
                        "url": req.get("url", ""),
                        "headers": req.get("headers", []),
                        "body": req.get("body"),
                    })
                count += 1
            self.notify(f"Imported {count} collections")
            self._load_data()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @work(exclusive=True)
    async def _export_environments(self) -> None:
        if not self._app:
            return
        try:
            envs = await self._app.environments.list_all()
            output = Path("data/environments_export.json")
            output.parent.mkdir(parents=True, exist_ok=True)
            with open(output, "w", encoding="utf-8") as f:
                json.dump(envs, f, indent=2, default=str)
            self.notify(f"Exported {len(envs)} environments")
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @work(exclusive=True)
    async def _import_environments(self) -> None:
        if not self._app:
            return
        try:
            with open("data/environments_export.json", encoding="utf-8") as f:
                envs = json.load(f)
            count = 0
            for env in envs:
                new_env = await self._app.environments.create(env.get("name", "Imported"))
                for var in env.get("variables", []):
                    await self._app.environments.set_variable(new_env["id"], var["key"], var["value"])
                count += 1
            self.notify(f"Imported {count} environments")
            self._load_data()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @work(exclusive=True)
    async def _import_openapi(self) -> None:
        if not self._app:
            return
        file_path = await self.prompt("OpenAPI/Swagger file path:")
        if not file_path:
            return
        try:
            with open(file_path, encoding="utf-8") as f:
                spec = json.load(f)

            paths = spec.get("paths", {})
            if not paths:
                self.notify("No paths found in spec", severity="warning")
                return

            base_url = ""
            if "servers" in spec and spec["servers"]:
                base_url = spec["servers"][0].get("url", "")
            elif "host" in spec:
                scheme = spec.get("schemes", ["https"])[0]
                base_url = f"{scheme}://{spec['host']}{spec.get('basePath', '')}"

            collection_name = spec.get("info", {}).get("title", "OpenAPI Import")
            requests = []
            for path_str, methods in paths.items():
                for method, details in methods.items():
                    if method.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                        url = f"{base_url}{path_str}" if base_url else path_str
                        requests.append({
                            "name": f"{method.upper()} {path_str}",
                            "method": method.upper(),
                            "url": url,
                        })

            if not requests:
                self.notify("No operations found", severity="warning")
                return

            col = await self._app.collections.create(collection_name, "Imported from OpenAPI")
            for req in requests:
                await self._app.requests.create({
                    "collection_id": col["id"],
                    "name": req["name"],
                    "method": req["method"],
                    "url": req["url"],
                    "headers": [],
                })

            self.notify(f"Imported {len(requests)} operations as '{collection_name}'")
            self._load_data()

        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    # ── Prompt helper ────────────────────────────────────────────────────

    async def prompt(self, message: str, default: str = "") -> str | None:
        """Show a text input prompt using Textual's built-in."""
        from textual.screen import ModalScreen
        from textual.widgets import Button, Static

        class PromptScreen(ModalScreen[str | None]):
            CSS = """
            PromptScreen {
                align: center middle;
            }
            #dialog {
                width: 50;
                background: $surface;
                border: thick $primary;
                padding: 1;
            }
            """

            def __init__(self, message: str, default: str) -> None:
                super().__init__()
                self._message = message
                self._default = default

            def compose(self) -> ComposeResult:
                with Vertical(id="dialog"):
                    yield Static(self._message)
                    yield Input(self._default, id="prompt-input")
                    with Horizontal():
                        yield Button("Cancel", id="cancel-btn")
                        yield Button("OK", variant="primary", id="ok-btn")

            def on_mount(self) -> None:
                self.query_one("#prompt-input", Input).focus()

            @on(Button.Pressed, "#cancel-btn")
            def cancel(self) -> None:
                self.dismiss(None)

            @on(Button.Pressed, "#ok-btn")
            def ok(self) -> None:
                self.dismiss(self.query_one("#prompt-input", Input).value)

            @on(Input.Submitted, "#prompt-input")
            def submitted(self) -> None:
                self.dismiss(self.query_one("#prompt-input", Input).value)

        return await self.push_screen_wait(PromptScreen(message, default))

    async def confirm(self, message: str) -> bool:
        """Show a confirmation dialog."""
        from textual.screen import ModalScreen

        class ConfirmScreen(ModalScreen[bool]):
            CSS = """
            ConfirmScreen {
                align: center middle;
            }
            #dialog {
                width: 50;
                background: $surface;
                border: thick $primary;
                padding: 1;
            }
            """

            def __init__(self, message: str) -> None:
                super().__init__()
                self._message = message

            def compose(self) -> ComposeResult:
                with Vertical(id="dialog"):
                    yield Static(self._message)
                    with Horizontal():
                        yield Button("No", id="no-btn")
                        yield Button("Yes", variant="primary", id="yes-btn")

            @on(Button.Pressed, "#no-btn")
            def no(self) -> None:
                self.dismiss(False)

            @on(Button.Pressed, "#yes-btn")
            def yes(self) -> None:
                self.dismiss(True)

        return await self.push_screen_wait(ConfirmScreen(message))


def launch_textual_tui(db_path: str = "data/sclplapi.db") -> None:
    """Launch the Textual TUI."""
    app = SCLPLTextualApp(db_path)
    app.run()
