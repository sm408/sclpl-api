"""Response viewer screen."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Static, TabbedContent, TabPane, TextArea


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

    def compose(self) -> ComposeResult:
        yield Static("[dim]Send a request to see the response[/dim]", id="response-status")

        with TabbedContent(id="response-tabs"):
            with TabPane("Body", id="body-tab"):
                yield TextArea(
                    id="response-body",
                    language="json",
                    theme="monokai",
                    read_only=True,
                )
            with TabPane("Headers", id="headers-tab"):
                yield Static(id="response-headers")
            with TabPane("Raw", id="raw-tab"):
                yield TextArea(
                    id="response-raw",
                    language="plaintext",
                    theme="monokai",
                    read_only=True,
                )

    def set_response(self, status_code: int, headers: dict[str, str], body: Any, duration_ms: int) -> None:
        """Update the response display."""
        self.status_code = status_code
        self.duration_ms = duration_ms
        self._headers = headers

        # Format body
        import json
        if isinstance(body, str):
            self._raw = body
            try:
                parsed = json.loads(body)
                self._body = json.dumps(parsed, indent=2, default=str)
            except (json.JSONDecodeError, TypeError):
                self._body = body
        elif isinstance(body, (dict, list)):
            self._body = json.dumps(body, indent=2, default=str)
            self._raw = self._body
        else:
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

        # Update body
        self.query_one("#response-body", TextArea).text = self._body

        # Update headers
        headers_text = "\n".join(f"[bold]{k}[/bold]: {v}" for k, v in headers.items())
        self.query_one("#response-headers", Static).update(headers_text)

        # Update raw
        self.query_one("#response-raw", TextArea).text = self._raw

    def clear(self) -> None:
        """Clear the response display."""
        self.status_code = 0
        self.duration_ms = 0
        self.size_bytes = 0
        self._headers = {}
        self._body = ""
        self._raw = ""
        self.query_one("#response-status", Static).update("[dim]Send a request to see the response[/dim]")
        self.query_one("#response-body", TextArea).text = ""
        self.query_one("#response-headers", Static).update("")
        self.query_one("#response-raw", TextArea).text = ""
