"""Command palette widget (Ctrl+P)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, ListItem, ListView, Static


@dataclass
class Command:
    """A command that can be executed from the palette."""
    name: str
    handler: Callable[[], Any]
    shortcut: str = ""
    description: str = ""
    category: str = "General"


class CommandPalette(ModalScreen[str | None]):
    """A modal command palette inspired by VS Code."""

    CSS = """
    CommandPalette {
        align: center top;
        padding-top: 5;
    }

    #palette-container {
        width: 60;
        max-height: 30;
        background: $surface;
        border: thick $primary;
    }

    #palette-input {
        width: 100%;
        margin: 0;
    }

    #palette-list {
        width: 100%;
        height: auto;
        max-height: 25;
    }

    .command-item {
        padding: 0 1;
    }

    .command-name {
        width: 1fr;
    }

    .command-shortcut {
        width: 10;
        text-align: right;
        color: $text-muted;
    }

    .command-description {
        width: 2fr;
        color: $text-muted;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "select", "Select"),
        ("up", "cursor_up", "Up"),
        ("down", "cursor_down", "Down"),
    ]

    def __init__(self, commands: list[Command], **kwargs) -> None:
        super().__init__(**kwargs)
        self.commands = commands
        self.filtered_commands = commands
        self.selected_index = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-container"):
            yield Input(placeholder="Type a command...", id="palette-input")
            yield ListView(id="palette-list")

    def on_mount(self) -> None:
        self._update_list()
        self.query_one("#palette-input", Input).focus()

    @on(Input.Changed, "#palette-input")
    def filter_commands(self, event: Input.Changed) -> None:
        query = event.value.lower().strip()
        if not query:
            self.filtered_commands = self.commands
        else:
            self.filtered_commands = [
                c for c in self.commands
                if query in c.name.lower()
                or query in c.description.lower()
                or query in c.category.lower()
            ]
        self.selected_index = 0
        self._update_list()

    def _update_list(self) -> None:
        list_view = self.query_one("#palette-list", ListView)
        list_view.clear()
        for cmd in self.filtered_commands:
            shortcut_text = f"[dim]{cmd.shortcut}[/dim]" if cmd.shortcut else ""
            item = ListItem(
                Static(f"{cmd.name}  {shortcut_text}", classes="command-name"),
                classes="command-item",
            )
            list_view.append(item)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_select(self) -> None:
        if self.filtered_commands:
            cmd = self.filtered_commands[self.selected_index]
            self.dismiss(cmd.name)
            cmd.handler()

    def action_cursor_up(self) -> None:
        if self.selected_index > 0:
            self.selected_index -= 1
            list_view = self.query_one("#palette-list", ListView)
            list_view.index = self.selected_index

    def action_cursor_down(self) -> None:
        if self.selected_index < len(self.filtered_commands) - 1:
            self.selected_index += 1
            list_view = self.query_one("#palette-list", ListView)
            list_view.index = self.selected_index
