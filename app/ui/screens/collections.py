"""Collections screen with tree view and CRUD."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Static


class CollectionList(Vertical):
    """List of collections with CRUD operations."""

    CSS = """
    CollectionList {
        height: 100%;
        padding: 1;
    }

    #collections-header {
        height: auto;
        margin-bottom: 1;
    }

    #collections-table {
        height: 1fr;
    }

    #collections-actions {
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._all_collections: list[dict] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="collections-header"):
            yield Static("[bold]Collections[/bold]", classes="header-title")
            yield Input(placeholder="Search collections...", id="collection-search")
            yield Button("New", variant="primary", id="new-collection-btn", classes="header-action")

        yield DataTable(id="collections-table")

        with Horizontal(id="collections-actions"):
            yield Button("View", id="view-collection-btn")
            yield Button("Delete", variant="error", id="delete-collection-btn")

    def on_mount(self) -> None:
        table = self.query_one("#collections-table", DataTable)
        table.add_columns("Name", "Requests", "ID")
        table.cursor_type = "row"

    @on(Input.Changed, "#collection-search")
    def search_changed(self, event: Input.Changed) -> None:
        """Filter collections by search query."""
        query = event.value.lower().strip()
        if not query:
            self.set_collections(self._all_collections)
        else:
            filtered = [c for c in self._all_collections if query in c.get("name", "").lower()]
            self.set_collections(filtered)

    def set_collections(self, collections: list[dict]) -> None:
        """Update the collection table."""
        self._all_collections = collections
        table = self.query_one("#collections-table", DataTable)
        table.clear()
        for col in collections:
            req_count = len(col.get("requests", []))
            table.add_row(col["name"], str(req_count), col["id"][:8])


class RequestList(Vertical):
    """List of requests in a collection."""

    CSS = """
    RequestList {
        height: 100%;
        padding: 1;
    }

    #requests-header {
        height: auto;
        margin-bottom: 1;
    }

    #requests-table {
        height: 1fr;
    }

    #requests-actions {
        height: auto;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="requests-header"):
            yield Static("[bold]Requests[/bold]", classes="header-title")
            yield Button("Add", variant="primary", id="add-request-btn", classes="header-action")

        yield DataTable(id="requests-table")

        with Horizontal(id="requests-actions"):
            yield Button("Load", id="load-request-btn")
            yield Button("Run", variant="success", id="run-request-btn")
            yield Button("Delete", variant="error", id="delete-request-btn")

    def on_mount(self) -> None:
        table = self.query_one("#requests-table", DataTable)
        table.add_columns("Method", "Name", "URL")
        table.cursor_type = "row"

    def set_requests(self, requests: list[dict]) -> None:
        """Update the request table."""
        table = self.query_one("#requests-table", DataTable)
        table.clear()
        for req in requests:
            table.add_row(
                req.get("method", "GET"),
                req.get("name", "Untitled"),
                req.get("url", "")[:60],
            )


class NewCollectionDialog(ModalScreen[str | None]):
    """Dialog for creating a new collection."""

    CSS = """
    NewCollectionDialog {
        align: center middle;
    }

    #dialog {
        width: 50;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1;
    }

    #name-input {
        width: 100%;
        margin: 1 0;
    }

    #dialog-buttons {
        width: 100%;
        height: auto;
        align: right middle;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("[bold]New Collection[/bold]")
            yield Input(placeholder="Collection name...", id="name-input")
            with Horizontal(id="dialog-buttons"):
                yield Button("Cancel", id="cancel-btn")
                yield Button("Create", variant="primary", id="create-btn")

    @on(Button.Pressed, "#cancel-btn")
    def cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#create-btn")
    def create(self) -> None:
        name = self.query_one("#name-input", Input).value
        self.dismiss(name if name else None)
