"""Environments screen with variable editor."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Static


class EnvironmentView(Vertical):
    """Environment management view."""

    CSS = """
    EnvironmentView {
        height: 100%;
        padding: 1;
    }

    #env-header {
        height: auto;
        margin-bottom: 1;
    }

    #env-table {
        height: 1fr;
    }

    #env-variables {
        height: 1fr;
        margin-top: 1;
    }

    #env-actions {
        height: auto;
        margin-top: 1;
    }

    #var-actions {
        height: auto;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="env-header"):
            yield Static("[bold]Environments[/bold]", classes="header-title")
            yield Button("New", variant="primary", id="new-env-btn", classes="header-action")

        yield DataTable(id="env-table")

        with Horizontal(id="env-actions"):
            yield Button("Activate", variant="success", id="activate-env-btn")
            yield Button("Delete", variant="error", id="delete-env-btn")

        yield Static("[bold]Variables[/bold]", id="var-header")
        yield DataTable(id="env-variables")

        with Horizontal(id="var-actions"):
            yield Button("Set Variable", id="set-var-btn")
            yield Button("Delete Variable", variant="error", id="delete-var-btn")

    def on_mount(self) -> None:
        env_table = self.query_one("#env-table", DataTable)
        env_table.add_columns("Name", "Active", "Variables", "ID")
        env_table.cursor_type = "row"

        var_table = self.query_one("#env-variables", DataTable)
        var_table.add_columns("Key", "Value", "Secret")
        var_table.cursor_type = "row"

    def set_environments(self, envs: list[dict]) -> None:
        """Update the environment table."""
        table = self.query_one("#env-table", DataTable)
        table.clear()
        for env in envs:
            active = "[green]yes[/green]" if env.get("is_active") else "no"
            var_count = len(env.get("variables", []))
            table.add_row(env["name"], active, str(var_count), env["id"][:8])

    def set_variables(self, variables: list[dict]) -> None:
        """Update the variables table."""
        table = self.query_one("#env-variables", DataTable)
        table.clear()
        for var in variables:
            val = "****" if var.get("is_secret") else var.get("value", "")
            secret = "[yellow]yes[/yellow]" if var.get("is_secret") else "no"
            table.add_row(var["key"], val, secret)
