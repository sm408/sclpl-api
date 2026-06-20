"""Plugins screen with browser and details."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Static


class PluginBrowser(Vertical):
    """Plugin browser with status and details."""

    CSS = """
    PluginBrowser {
        height: 100%;
        padding: 1;
    }

    #plugin-header {
        height: auto;
        margin-bottom: 1;
    }

    #plugin-table {
        height: 1fr;
    }

    #plugin-detail {
        height: auto;
        margin-top: 1;
        padding: 1;
        background: $surface-darken-1;
    }

    #plugin-actions {
        height: auto;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="plugin-header"):
            yield Static("[bold]Plugins[/bold]", classes="header-title")
            yield Button("Reload", id="reload-plugins-btn", classes="header-action")

        yield DataTable(id="plugin-table")

        yield Static("[dim]Select a plugin to view details[/dim]", id="plugin-detail")

        with Horizontal(id="plugin-actions"):
            yield Button("View Functions", id="view-plugin-funcs-btn")

    def on_mount(self) -> None:
        table = self.query_one("#plugin-table", DataTable)
        table.add_columns("Name", "Version", "Functions", "Status")
        table.cursor_type = "row"

    def set_plugins(self, plugins: list) -> None:
        """Update the plugin table."""
        table = self.query_one("#plugin-table", DataTable)
        table.clear()
        for p in plugins:
            name = p.manifest.name
            version = p.manifest.version
            func_count = len(p.functions)
            status = p.status.value if hasattr(p.status, 'value') else str(p.status)
            status_color = {
                "active": "green",
                "loaded": "yellow",
                "discovered": "dim",
                "error": "red",
            }.get(status, "white")
            table.add_row(name, version, str(func_count), f"[{status_color}]{status}[/{status_color}]")

    def show_detail(self, plugin) -> None:
        """Show plugin details."""
        m = plugin.manifest
        detail = self.query_one("#plugin-detail", Static)
        text = (
            f"[bold]{m.name}[/bold] v{m.version}\n"
            f"{m.description or 'No description'}\n"
            f"Author: {m.author or 'Unknown'}\n"
            f"Functions: {len(plugin.functions)}  Workflows: {len(plugin.workflows)}"
        )
        if plugin.error:
            text += f"\n[red]Error: {plugin.error}[/red]"
        detail.update(text)
