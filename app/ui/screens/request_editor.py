"""Request editor screen."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Select, Static, TextArea


class RequestEditor(Vertical):
    """Request editor pane with URL, method, headers, body."""

    CSS = """
    RequestEditor {
        height: 100%;
        padding: 1;
    }

    #url-bar {
        height: 3;
        margin-bottom: 1;
    }

    #method-select {
        width: 12;
    }

    #url-input {
        width: 1fr;
    }

    #send-btn {
        width: 10;
        min-width: 10;
    }

    #tabs {
        height: auto;
        margin-bottom: 1;
    }

    .tab-content {
        height: 1fr;
    }

    #body-editor {
        height: 100%;
    }

    #headers-table {
        height: 100%;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._method = "GET"
        self._url = ""
        self._headers: dict[str, str] = {}
        self._body = ""
        self._active_tab = "body"

    def compose(self) -> ComposeResult:
        # URL bar
        with Horizontal(id="url-bar"):
            yield Select(
                [("GET", "GET"), ("POST", "POST"), ("PUT", "PUT"),
                 ("PATCH", "PATCH"), ("DELETE", "DELETE")],
                value="GET",
                id="method-select",
            )
            yield Input(
                placeholder="Enter request URL...",
                id="url-input",
            )
            yield Button("Send", variant="primary", id="send-btn")

        # Tabs
        yield Static("[bold]Body[/bold]  [dim]Headers[/dim]  [dim]Auth[/dim]", id="tabs")

        # Body editor
        yield TextArea(
            id="body-editor",
            language="json",
            theme="monokai",
        )

    @on(Select.Changed, "#method-select")
    def method_changed(self, event: Select.Changed) -> None:
        self._method = str(event.value)

    @on(Input.Changed, "#url-input")
    def url_changed(self, event: Input.Changed) -> None:
        self._url = event.value

    @on(Button.Pressed, "#send-btn")
    def send_pressed(self) -> None:
        self.app.action_run_request()

    def get_request_data(self) -> dict:
        """Get the current request data."""
        body_editor = self.query_one("#body-editor", TextArea)
        return {
            "method": self._method,
            "url": self._url,
            "headers": self._headers,
            "body": body_editor.text,
        }

    def set_request_data(self, method: str, url: str, headers: dict = None, body: str = "") -> None:
        """Load request data into the editor."""
        self._method = method
        self._url = url
        self._headers = headers or {}
        self._body = body

        self.query_one("#method-select", Select).value = method
        self.query_one("#url-input", Input).value = url
        self.query_one("#body-editor", TextArea).text = body
