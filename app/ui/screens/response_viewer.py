"""Response viewer with JSON collapse/expand support."""

from __future__ import annotations

import json
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Static, TabbedContent, TabPane, TextArea, Tree


class ResponseViewer(Vertical):
    """Response viewer pane with status, headers, body, timings."""

    CSS = """
    ResponseViewer {
        height: 100%;
        padding: 1;
    }

    #response-status {
        height: auto;
        margin-bottom: 1;
    }

    #response-tabs {
        height: 1fr;
    }

    #response-body {
        height: 100%;
    }

    #response-json-tree {
        height: 100%;
    }

    #response-headers {
        height: 100%;
    }

    #response-raw {
        height: 100%;
    }
    """

    status_code: reactive[int] = reactive(0)
    duration_ms: reactive[int] = reactive(0)
    size_bytes: reactive[int] = reactive(0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._headers: dict[str, str] = {}
        self._body: str = ""
        self._raw: str = ""
        self._parsed_json: Any = None

    def compose(self) -> ComposeResult:
        yield Static("[dim]Send a request to see the response[/dim]", id="response-status")

        with TabbedContent(id="response-tabs"):
            with TabPane("Pretty", id="pretty-tab"):
                yield Tree("root", id="response-json-tree")
            with TabPane("Raw", id="raw-tab"):
                yield TextArea(
                    id="response-raw",
                    language="plaintext",
                    theme="monokai",
                    read_only=True,
                )
            with TabPane("Headers", id="headers-tab"):
                yield Static(id="response-headers")
            with TabPane("Size", id="size-tab"):
                yield Static(id="response-size-info")

    def set_response(self, status_code: int, headers: dict[str, str], body: Any, duration_ms: int) -> None:
        """Update the response display."""
        self.status_code = status_code
        self.duration_ms = duration_ms
        self._headers = headers

        # Format body
        if isinstance(body, str):
            self._raw = body
            try:
                self._parsed_json = json.loads(body)
                self._body = json.dumps(self._parsed_json, indent=2, default=str)
            except (json.JSONDecodeError, TypeError):
                self._parsed_json = None
                self._body = body
        elif isinstance(body, (dict, list)):
            self._parsed_json = body
            self._body = json.dumps(body, indent=2, default=str)
            self._raw = self._body
        else:
            self._parsed_json = None
            self._body = str(body)
            self._raw = self._body

        self.size_bytes = len(self._body)

        # Update status display
        status_color = "green" if 200 <= status_code < 300 else "red"
        status_text = (
            f"[{status_color}]{status_code}[/{status_color}]  "
            f"[dim]{duration_ms}ms[/dim]  "
            f"[dim]{self.size_bytes} bytes[/dim]"
        )
        self.query_one("#response-status", Static).update(status_text)

        # Update JSON tree
        tree = self.query_one("#response-json-tree", Tree)
        tree.clear()
        if self._parsed_json is not None:
            self._build_json_tree(self._parsed_json, tree.root)
            tree.root.expand()
        else:
            tree.root.add_leaf(self._body[:500])

        # Update raw
        self.query_one("#response-raw", TextArea).text = self._raw

        # Update headers
        headers_text = "\n".join(f"[bold]{k}[/bold]: {v}" for k, v in headers.items())
        self.query_one("#response-headers", Static).update(headers_text)

        # Update size info
        size_info = self.query_one("#response-size-info", Static)
        size_info.update(
            f"[bold]Status:[/bold] {status_code}\n"
            f"[bold]Duration:[/bold] {duration_ms}ms\n"
            f"[bold]Size:[/bold] {self.size_bytes} bytes\n"
            f"[bold]Headers:[/bold] {len(headers)}"
        )

    def _build_json_tree(self, data: Any, node, depth: int = 0) -> None:
        """Build collapsible JSON tree."""
        if depth > 10:
            node.add_leaf("[dim]... (truncated)[/dim]")
            return

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    child = node.add(f"[bold]{key}[/bold]")
                    self._build_json_tree(value, child, depth + 1)
                else:
                    node.add_leaf(f"[bold]{key}[/bold]: {self._format_value(value)}")
        elif isinstance(data, list):
            for i, item in enumerate(data[:50]):  # Limit to 50 items
                if isinstance(item, (dict, list)):
                    child = node.add(f"[dim][{i}][/dim]")
                    self._build_json_tree(item, child, depth + 1)
                else:
                    node.add_leaf(f"[dim][{i}][/dim]: {self._format_value(item)}")
            if len(data) > 50:
                node.add_leaf(f"[dim]... ({len(data) - 50} more items)[/dim]")
        else:
            node.add_leaf(self._format_value(data))

    def _format_value(self, value: Any) -> str:
        """Format a primitive value."""
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

    def clear(self) -> None:
        """Clear the response display."""
        self.status_code = 0
        self.duration_ms = 0
        self.size_bytes = 0
        self._headers = {}
        self._body = ""
        self._raw = ""
        self._parsed_json = None
        self.query_one("#response-status", Static).update("[dim]Send a request to see the response[/dim]")
        tree = self.query_one("#response-json-tree", Tree)
        tree.clear()
        tree.root.add_leaf("[dim]No response[/dim]")
        self.query_one("#response-raw", TextArea).text = ""
        self.query_one("#response-headers", Static).update("")
        self.query_one("#response-size-info", Static).update("")
