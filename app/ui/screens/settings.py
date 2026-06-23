"""Settings screen."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Static


class SettingsView(Vertical):
    """Settings view for configuring TUI defaults."""

    CSS = """
    SettingsView {
        height: 100%;
        padding: 1;
    }

    .settings-group {
        margin-bottom: 2;
    }

    .settings-label {
        text-style: bold;
        margin-bottom: 0;
    }

    .settings-input {
        width: 100%;
        margin-bottom: 1;
    }

    #settings-actions {
        height: auto;
        margin-top: 2;
    }
    """

    def __init__(self, db_path: str = "data/sclplapi.db", **kwargs) -> None:
        super().__init__(**kwargs)
        self._db_path = db_path

    def compose(self) -> ComposeResult:
        yield Static("[bold]Settings[/bold]", id="settings-header")

        with Vertical(classes="settings-group"):
            yield Static("Database Path", classes="settings-label")
            yield Input(self._db_path, id="db-path-input", classes="settings-input")

        with Vertical(classes="settings-group"):
            yield Static("Export Directory", classes="settings-label")
            yield Input("data/exports", id="export-dir-input", classes="settings-input")

        with Vertical(classes="settings-group"):
            yield Static("Request Timeout (seconds)", classes="settings-label")
            yield Input("30", id="timeout-input", classes="settings-input")

        with Horizontal(id="settings-actions"):
            yield Button("Save", variant="primary", id="save-settings-btn")
            yield Button("Reset", id="reset-settings-btn")

    @on(Button.Pressed, "#save-settings-btn")
    def save_settings(self) -> None:
        self._db_path = self.query_one("#db-path-input", Input).value
        self.notify("Settings saved")

    @on(Button.Pressed, "#reset-settings-btn")
    def reset_settings(self) -> None:
        self.query_one("#db-path-input", Input).value = "data/sclplapi.db"
        self.query_one("#export-dir-input", Input).value = "data/exports"
        self.query_one("#timeout-input", Input).value = "30"
        self.notify("Settings reset to defaults")
