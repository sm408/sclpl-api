"""Colored HTTP method badge widget."""

from __future__ import annotations

from textual.widgets import Static

METHOD_COLORS = {
    "GET": "green",
    "POST": "yellow",
    "PUT": "blue",
    "PATCH": "magenta",
    "DELETE": "red",
    "HEAD": "cyan",
    "OPTIONS": "dim",
}


class MethodBadge(Static):
    """A colored badge displaying an HTTP method."""

    def __init__(self, method: str = "GET", **kwargs) -> None:
        self.method = method.upper()
        super().__init__(**kwargs)

    def render(self) -> str:
        color = METHOD_COLORS.get(self.method, "white")
        return f"[{color}]{self.method}[/{color}]"
