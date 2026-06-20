"""Textual-based TUI application.

Primary interaction layer for SCLPLAPI.
Replaces the Rich-based menu-driven TUI with a modern, keyboard-first interface.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from app.ui.app import App as SCLPLApp
from app.ui.adapter import UIAdapter, LogLevel
from app.ui.commands import COMMANDS, CommandDef
from app.ui.widgets.sidebar import Sidebar
from app.ui.widgets.command_palette import CommandPalette, Command
from app.ui.screens.request_editor import RequestEditor
from app.ui.screens.response_viewer import ResponseViewer
from app.ui.screens.collections import CollectionList, RequestList, NewCollectionDialog
from app.ui.screens.history import HistoryView
from app.ui.screens.workflows import WorkflowList, WorkflowExecution
from app.ui.screens.environments import EnvironmentView
from app.ui.screens.functions import FunctionBrowser
from app.ui.screens.plugins import PluginBrowser
from app.ui.screens.settings import SettingsView
from app.ui.screens.import_export import ImportExportView


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
        self._commands: list[Command] = []

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
            with TabPane("Environments", id="tab-environments"):
                yield EnvironmentView()
            with TabPane("Functions", id="tab-functions"):
                yield FunctionBrowser()
            with TabPane("Plugins", id="tab-plugins"):
                yield PluginBrowser()
            with TabPane("Import/Export", id="tab-import-export"):
                yield ImportExportView()
            with TabPane("Settings", id="tab-settings"):
                yield SettingsView()
        yield Static("[dim]Ready[/dim]", id="log-pane")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the application backend."""
        self._app = SCLPLApp(self.db_path)
        await self._app.start()
        self._build_commands()
        self._load_data()

    async def on_unmount(self) -> None:
        """Cleanup on exit."""
        if self._app:
            await self._app.stop()

    def _build_commands(self) -> None:
        """Build command palette entries."""
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
        """Load all data into sidebar and screens."""
        if not self._app:
            return

        try:
            # Load collections
            cols = await self._app.collections.list_all()
            collections_data = []
            for col in cols:
                reqs = await self._app.requests.list_all(collection_id=col["id"])
                collections_data.append({**col, "requests": reqs})

            sidebar = self.query_one("#sidebar", Sidebar)
            sidebar.update_collections(collections_data)

            # Update collections screen
            collections_tab = self.query_one("CollectionList")
            if collections_tab:
                collections_tab.set_collections(collections_data)

            # Load workflows
            from pathlib import Path
            import json
            workflows = []
            for d in [Path("examples"), Path("workflows")]:
                if d.exists():
                    for wf_file in sorted(d.rglob("*.json")):
                        try:
                            data = json.loads(wf_file.read_text(encoding="utf-8"))
                            if "steps" in data:
                                workflows.append({
                                    "id": data.get("id", wf_file.parent.name),
                                    "name": data.get("name", wf_file.stem),
                                    "step_count": len(data.get("steps", [])),
                                    "path": str(wf_file),
                                })
                        except (json.JSONDecodeError, OSError):
                            pass
            sidebar.update_workflows(workflows)

            workflow_tab = self.query_one("WorkflowList")
            if workflow_tab:
                workflow_tab.set_workflows(workflows)

            # Load environments
            envs = await self._app.environments.list_all()
            active_env = next((e for e in envs if e.get("is_active")), None)
            if active_env:
                sidebar.update_environment(active_env["name"], len(active_env.get("variables", [])))
            env_tab = self.query_one("EnvironmentView")
            if env_tab:
                env_tab.set_environments(envs)

            # Load history
            history = await self._app.history.list_recent(50)
            history_tab = self.query_one("HistoryView")
            if history_tab:
                history_tab.set_entries(history)

            # Load functions
            from app.core.engine.function_runner import FilesystemFunctionRunner
            runner = FilesystemFunctionRunner("functions")
            funcs = runner.discover()
            func_tab = self.query_one("FunctionBrowser")
            if func_tab:
                func_tab.set_functions(funcs)

            # Load plugins
            if self._app.plugin_registry:
                plugins = self._app.plugin_registry.list_plugins()
                plugin_tab = self.query_one("PluginBrowser")
                if plugin_tab:
                    plugin_tab.set_plugins(plugins)

        except Exception as e:
            self.log(f"Error loading data: {e}")

    # ── Actions ──────────────────────────────────────────────────────────

    def action_command_palette(self) -> None:
        """Open the command palette (Ctrl+P)."""
        self.push_screen(CommandPalette(self._commands))

    def action_new_request(self) -> None:
        """Create a new request tab (Ctrl+T)."""
        workspace = self.query_one("#workspace", TabbedContent)
        workspace.active = "tab-request"

    def action_run_request(self) -> None:
        """Run the current request (Ctrl+R)."""
        self._execute_request()

    def action_close_tab(self) -> None:
        """Close the current tab (Ctrl+W)."""
        # For now, just switch to request tab
        workspace = self.query_one("#workspace", TabbedContent)
        workspace.active = "tab-request"

    def action_batch_mode(self) -> None:
        """Enter batch mode (Ctrl+B)."""
        self.notify("Batch mode coming soon", severity="information")

    def action_help(self) -> None:
        """Show help (F1)."""
        help_text = "\n".join(
            f"  {cmd.shortcut:15} {cmd.name}" for cmd in COMMANDS if cmd.shortcut
        )
        self.notify(f"Keyboard Shortcuts:\n{help_text}", severity="information")

    def action_refresh(self) -> None:
        """Refresh data (F5)."""
        self._load_data()
        self.notify("Refreshed", severity="information")

    def action_cancel(self) -> None:
        """Cancel current operation (Escape)."""
        pass

    def action_show_collections(self) -> None:
        workspace = self.query_one("#workspace", TabbedContent)
        workspace.active = "tab-collections"

    def action_show_history(self) -> None:
        workspace = self.query_one("#workspace", TabbedContent)
        workspace.active = "tab-history"

    def action_show_workflows(self) -> None:
        workspace = self.query_one("#workspace", TabbedContent)
        workspace.active = "tab-workflows"

    def action_show_environments(self) -> None:
        workspace = self.query_one("#workspace", TabbedContent)
        workspace.active = "tab-environments"

    def action_show_functions(self) -> None:
        workspace = self.query_one("#workspace", TabbedContent)
        workspace.active = "tab-functions"

    def action_show_plugins(self) -> None:
        workspace = self.query_one("#workspace", TabbedContent)
        workspace.active = "tab-plugins"

    def action_show_import_export(self) -> None:
        workspace = self.query_one("#workspace", TabbedContent)
        workspace.active = "tab-import-export"

    def action_show_settings(self) -> None:
        workspace = self.query_one("#workspace", TabbedContent)
        workspace.active = "tab-settings"

    def action_run_workflow(self) -> None:
        workspace = self.query_one("#workspace", TabbedContent)
        workspace.active = "tab-workflows"

    def action_recent_workflows(self) -> None:
        workspace = self.query_one("#workspace", TabbedContent)
        workspace.active = "tab-workflows"

    def action_validate_script(self) -> None:
        self.notify("Validate script coming soon", severity="information")

    def action_switch_environment(self) -> None:
        workspace = self.query_one("#workspace", TabbedContent)
        workspace.active = "tab-environments"

    # ── Request Execution ────────────────────────────────────────────────

    @work(exclusive=True)
    async def _execute_request(self) -> None:
        """Execute the current request through the service layer."""
        if not self._app:
            return

        request_editor = self.query_one("RequestEditor")
        if not request_editor:
            return

        data = request_editor.get_request_data()
        url = data.get("url", "")
        if not url:
            self.notify("No URL provided", severity="warning")
            return

        # Build RequestDef
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

        # Execute through service layer
        from app.core.models.context import ExecutionContext
        ctx = ExecutionContext()

        try:
            self.notify(f"Sending {method} {url}...")
            result, history = await self._app.request_executor.execute_with_history(request, ctx)

            # Save to history
            await self._app.history.save(history)

            # Update response viewer
            response_viewer = self.query_one("ResponseViewer")
            if response_viewer:
                response_viewer.set_response(
                    status_code=result.status_code,
                    headers=dict(result.headers) if result.headers else {},
                    body=result.body,
                    duration_ms=history.duration_ms,
                )

            # Log
            status_color = "green" if 200 <= result.status_code < 300 else "red"
            log = self.query_one("#log-pane", Static)
            log.update(f"[{status_color}]{result.status_code}[/{status_color}]  {method} {url}  {history.duration_ms}ms")

        except Exception as e:
            self.notify(f"Request failed: {e}", severity="error")
            log = self.query_one("#log-pane", Static)
            log.update(f"[red]Error: {e}[/red]")


# ── Entry point ──────────────────────────────────────────────────────────────


def launch_textual_tui(db_path: str = "data/sclplapi.db") -> None:
    """Launch the Textual TUI."""
    app = SCLPLTextualApp(db_path)
    app.run()
