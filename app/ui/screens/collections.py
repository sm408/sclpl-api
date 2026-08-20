"""Collections screen with full CRUD operations."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
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

    class CollectionCreated(Message):
        def __init__(self, name: str) -> None:
            self.name = name
            super().__init__()

    class CollectionDeleted(Message):
        def __init__(self, collection_id: str) -> None:
            self.collection_id = collection_id
            super().__init__()

    class CollectionRenamed(Message):
        def __init__(self, collection_id: str, new_name: str) -> None:
            self.collection_id = collection_id
            self.new_name = new_name
            super().__init__()

    class CollectionDuplicated(Message):
        def __init__(self, collection_id: str) -> None:
            self.collection_id = collection_id
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._all_collections: list[dict] = []
        self._collections: list[dict] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="collections-header"):
            yield Static("[bold]Collections[/bold]", classes="header-title")
            yield Input(placeholder="Search collections...", id="collection-search")
            yield Button("New", variant="primary", id="new-collection-btn", classes="header-action")

        yield DataTable(id="collections-table")

        with Horizontal(id="collections-actions"):
            yield Button("Rename", id="rename-collection-btn")
            yield Button("Duplicate", id="duplicate-collection-btn")
            yield Button("Delete", variant="error", id="delete-collection-btn")

    def on_mount(self) -> None:
        table = self.query_one("#collections-table", DataTable)
        table.add_columns("Name", "Requests", "ID")
        table.cursor_type = "row"

    @on(Input.Changed, "#collection-search")
    def search_changed(self, event: Input.Changed) -> None:
        query = event.value.lower().strip()
        if not query:
            self._collections = self._all_collections
        else:
            self._collections = [c for c in self._all_collections if query in c.get("name", "").lower()]
        self._update_table()

    def set_collections(self, collections: list[dict]) -> None:
        self._all_collections = collections
        self._collections = collections
        self._update_table()

    def _update_table(self) -> None:
        table = self.query_one("#collections-table", DataTable)
        table.clear()
        for col in self._collections:
            req_count = len(col.get("requests", []))
            table.add_row(col["name"], str(req_count), col["id"][:8])

    def get_selected_collection(self) -> dict | None:
        table = self.query_one("#collections-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self._collections):
            return self._collections[table.cursor_row]
        return None

    @on(Button.Pressed, "#new-collection-btn")
    def new_pressed(self) -> None:
        self.post_message(self.CollectionCreated(""))

    @on(Button.Pressed, "#rename-collection-btn")
    def rename_pressed(self) -> None:
        col = self.get_selected_collection()
        if col:
            self.post_message(self.CollectionRenamed(col["id"], ""))

    @on(Button.Pressed, "#duplicate-collection-btn")
    def duplicate_pressed(self) -> None:
        col = self.get_selected_collection()
        if col:
            self.post_message(self.CollectionDuplicated(col["id"]))

    @on(Button.Pressed, "#delete-collection-btn")
    def delete_pressed(self) -> None:
        col = self.get_selected_collection()
        if col:
            self.post_message(self.CollectionDeleted(col["id"]))


class RequestList(Vertical):
    """List of requests in a collection."""

    CSS = """
    RequestList {
        height: 100%;
        padding: 1;
    }

    #requests-table {
        height: 1fr;
    }

    #requests-actions {
        height: auto;
        margin-top: 1;
    }
    """

    class RequestCreated(Message):
        def __init__(self, collection_id: str) -> None:
            self.collection_id = collection_id
            super().__init__()

    class RequestDeleted(Message):
        def __init__(self, request_id: str) -> None:
            self.request_id = request_id
            super().__init__()

    class RequestLoaded(Message):
        def __init__(self, request: dict) -> None:
            self.request = request
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._requests: list[dict] = []

    def compose(self) -> ComposeResult:
        yield DataTable(id="requests-table")

        with Horizontal(id="requests-actions"):
            yield Button("Add", variant="primary", id="add-request-btn")
            yield Button("Load", id="load-request-btn")
            yield Button("Delete", variant="error", id="delete-request-btn")

    def on_mount(self) -> None:
        table = self.query_one("#requests-table", DataTable)
        table.add_columns("Method", "Name", "URL")
        table.cursor_type = "row"

    def set_requests(self, requests: list[dict]) -> None:
        self._requests = requests
        table = self.query_one("#requests-table", DataTable)
        table.clear()
        for req in requests:
            table.add_row(
                req.get("method", "GET"),
                req.get("name", "Untitled"),
                req.get("url", "")[:60],
            )

    def get_selected_request(self) -> dict | None:
        table = self.query_one("#requests-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self._requests):
            return self._requests[table.cursor_row]
        return None

    @on(Button.Pressed, "#add-request-btn")
    def add_pressed(self) -> None:
        self.post_message(self.RequestCreated(""))

    @on(Button.Pressed, "#load-request-btn")
    def load_pressed(self) -> None:
        req = self.get_selected_request()
        if req:
            self.post_message(self.RequestLoaded(req))

    @on(Button.Pressed, "#delete-request-btn")
    def delete_pressed(self) -> None:
        req = self.get_selected_request()
        if req:
            self.post_message(self.RequestDeleted(req.get("id", "")))


class NewCollectionDialog(ModalScreen[str | None]):
    """Dialog for creating/renaming a collection."""

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

    def __init__(self, title: str = "New Collection", default_name: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._default = default_name

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(f"[bold]{self._title}[/bold]")
            yield Input(self._default, placeholder="Collection name...", id="name-input")
            with Horizontal(id="dialog-buttons"):
                yield Button("Cancel", id="cancel-btn")
                yield Button("OK", variant="primary", id="ok-btn")

    def on_mount(self) -> None:
        self.query_one("#name-input", Input).focus()

    @on(Button.Pressed, "#cancel-btn")
    def cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#ok-btn")
    def ok(self) -> None:
        name = self.query_one("#name-input", Input).value
        self.dismiss(name if name else None)

    @on(Input.Submitted, "#name-input")
    def submitted(self) -> None:
        name = self.query_one("#name-input", Input).value
        self.dismiss(name if name else None)
