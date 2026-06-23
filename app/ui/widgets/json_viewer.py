"""Collapsible JSON tree viewer widget."""

from __future__ import annotations

import json
from typing import Any

from textual.widgets import Tree


class JsonViewer(Tree):
    """A tree widget that displays JSON data with collapsible nodes."""

    def __init__(self, data: Any = None, **kwargs) -> None:
        super().__init__("root", **kwargs)
        self._data = data
        if data is not None:
            self._build_tree(data, self.root)

    def set_data(self, data: Any) -> None:
        """Update the displayed JSON data."""
        self._data = data
        self.root.remove_children()
        if data is not None:
            self._build_tree(data, self.root)
            self.root.expand()

    def _build_tree(self, data: Any, node, depth: int = 0) -> None:
        """Recursively build tree from JSON data."""
        if depth > 10:
            node.add_leaf("[dim]... (truncated)[/dim]")
            return

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    child = node.add(f"[bold]{key}[/bold]")
                    self._build_tree(value, child, depth + 1)
                else:
                    node.add_leaf(f"[bold]{key}[/bold]: {self._format_value(value)}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    child = node.add(f"[dim][{i}][/dim]")
                    self._build_tree(item, child, depth + 1)
                else:
                    node.add_leaf(f"[dim][{i}][/dim]: {self._format_value(item)}")
        else:
            node.add_leaf(self._format_value(data))

    def _format_value(self, value: Any) -> str:
        """Format a primitive value for display."""
        if value is None:
            return "[dim]null[/dim]"
        if isinstance(value, bool):
            return f"[yellow]{str(value).lower()}[/yellow]"
        if isinstance(value, (int, float)):
            return f"[cyan]{value}[/cyan]"
        if isinstance(value, str):
            if len(value) > 100:
                return f'[green]"{value[:100]}..."[/green]'
            return f'[green]"{value}"[/green]'
        return str(value)


def format_json(data: Any, indent: int = 2) -> str:
    """Format JSON data as a pretty-printed string."""
    try:
        return json.dumps(data, indent=indent, default=str)
    except (TypeError, ValueError):
        return str(data)
