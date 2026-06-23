"""Request editor screen with authentication support."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Select, Static, TabbedContent, TabPane, TextArea


class RequestEditor(Vertical):
    """Request editor pane with URL, method, headers, body, auth."""

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

    #editor-tabs {
        height: 1fr;
    }

    #body-editor {
        height: 100%;
    }

    #auth-type {
        width: 20;
        margin-bottom: 1;
    }

    .auth-field {
        width: 100%;
        margin-bottom: 1;
    }

    #headers-table {
        height: 100%;
    }

    #params-table {
        height: 100%;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._method = "GET"
        self._url = ""
        self._headers: dict[str, str] = {}
        self._params: dict[str, str] = {}
        self._body = ""
        self._auth_type = "none"
        self._auth_token = ""
        self._auth_username = ""
        self._auth_password = ""
        self._auth_api_key = ""

    def compose(self) -> ComposeResult:
        # URL bar
        with Horizontal(id="url-bar"):
            yield Select(
                [("GET", "GET"), ("POST", "POST"), ("PUT", "PUT"),
                 ("PATCH", "PATCH"), ("DELETE", "DELETE"),
                 ("HEAD", "HEAD"), ("OPTIONS", "OPTIONS")],
                value="GET",
                id="method-select",
            )
            yield Input(
                placeholder="Enter request URL (e.g. https://api.example.com/users)",
                id="url-input",
            )
            yield Button("Send", variant="primary", id="send-btn")

        # Tabs for Body, Headers, Params, Auth
        with TabbedContent(id="editor-tabs"):
            with TabPane("Body", id="tab-body"):
                yield TextArea(
                    id="body-editor",
                    language="json",
                    theme="monokai",
                )
            with TabPane("Headers", id="tab-headers"):
                yield Static("[dim]Headers (Key: Value, one per line)[/dim]")
                yield TextArea(
                    id="headers-editor",
                    language="plaintext",
                    theme="monokai",
                )
            with TabPane("Params", id="tab-params"):
                yield Static("[dim]Query Parameters (Key=Value, one per line)[/dim]")
                yield TextArea(
                    id="params-editor",
                    language="plaintext",
                    theme="monokai",
                )
            with TabPane("Auth", id="tab-auth"):
                yield Select(
                    [("None", "none"), ("Bearer Token", "bearer"),
                     ("Basic Auth", "basic"), ("API Key", "apikey")],
                    value="none",
                    id="auth-type",
                )
                yield Input(placeholder="Token", id="auth-token", classes="auth-field")
                yield Input(placeholder="Username", id="auth-username", classes="auth-field")
                yield Input(placeholder="Password", id="auth-password", classes="auth-field", password=True)
                yield Input(placeholder="API Key", id="auth-api-key", classes="auth-field")

    @on(Select.Changed, "#method-select")
    def method_changed(self, event: Select.Changed) -> None:
        self._method = str(event.value)

    @on(Input.Changed, "#url-input")
    def url_changed(self, event: Input.Changed) -> None:
        self._url = event.value

    @on(Select.Changed, "#auth-type")
    def auth_type_changed(self, event: Select.Changed) -> None:
        self._auth_type = str(event.value)

    @on(Input.Changed, "#auth-token")
    def auth_token_changed(self, event: Input.Changed) -> None:
        self._auth_token = event.value

    @on(Input.Changed, "#auth-username")
    def auth_username_changed(self, event: Input.Changed) -> None:
        self._auth_username = event.value

    @on(Input.Changed, "#auth-password")
    def auth_password_changed(self, event: Input.Changed) -> None:
        self._auth_password = event.value

    @on(Input.Changed, "#auth-api-key")
    def auth_api_key_changed(self, event: Input.Changed) -> None:
        self._auth_api_key = event.value

    @on(Button.Pressed, "#send-btn")
    def send_pressed(self) -> None:
        self.app.action_run_request()

    def get_request_data(self) -> dict:
        """Get the current request data."""
        body_editor = self.query_one("#body-editor", TextArea)
        headers_editor = self.query_one("#headers-editor", TextArea)
        params_editor = self.query_one("#params-editor", TextArea)

        # Parse headers
        headers = {}
        for line in headers_editor.text.split("\n"):
            line = line.strip()
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()

        # Parse params
        params = {}
        for line in params_editor.text.split("\n"):
            line = line.strip()
            if "=" in line:
                key, value = line.split("=", 1)
                params[key.strip()] = value.strip()

        # Build auth config
        auth_config = None
        if self._auth_type == "bearer":
            auth_config = {"token": self._auth_token}
        elif self._auth_type == "basic":
            auth_config = {"username": self._auth_username, "password": self._auth_password}
        elif self._auth_type == "apikey":
            auth_config = {"key": self._auth_api_key}

        return {
            "method": self._method,
            "url": self._url,
            "headers": headers,
            "params": params,
            "body": body_editor.text,
            "auth_type": self._auth_type if self._auth_type != "none" else None,
            "auth_config": auth_config,
        }

    def set_request_data(self, method: str, url: str, headers: dict = None, body: str = "",
                         params: dict = None, auth_type: str = None, auth_config: dict = None) -> None:
        """Load request data into the editor."""
        self._method = method
        self._url = url
        self._headers = headers or {}
        self._params = params or {}
        self._body = body

        self.query_one("#method-select", Select).value = method
        self.query_one("#url-input", Input).value = url
        self.query_one("#body-editor", TextArea).text = body

        # Set headers
        headers_text = "\n".join(f"{k}: {v}" for k, v in self._headers.items())
        self.query_one("#headers-editor", TextArea).text = headers_text

        # Set params
        params_text = "\n".join(f"{k}={v}" for k, v in self._params.items())
        self.query_one("#params-editor", TextArea).text = params_text

        # Set auth
        if auth_type:
            self._auth_type = auth_type
            self.query_one("#auth-type", Select).value = auth_type
            if auth_config:
                if auth_type == "bearer":
                    self._auth_token = auth_config.get("token", "")
                    self.query_one("#auth-token", Input).value = self._auth_token
                elif auth_type == "basic":
                    self._auth_username = auth_config.get("username", "")
                    self._auth_password = auth_config.get("password", "")
                    self.query_one("#auth-username", Input).value = self._auth_username
                    self.query_one("#auth-password", Input).value = self._auth_password
                elif auth_type == "apikey":
                    self._auth_api_key = auth_config.get("key", "")
                    self.query_one("#auth-api-key", Input).value = self._auth_api_key
