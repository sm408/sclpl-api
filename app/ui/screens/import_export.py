"""Import/Export screen."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static


class ImportExportView(Vertical):
    """Import/Export view for workspace backup and restore."""

    CSS = """
    ImportExportView {
        height: 100%;
        padding: 1;
    }

    .export-group {
        margin-bottom: 2;
        padding: 1;
        background: $surface-darken-1;
    }

    .group-title {
        text-style: bold;
        margin-bottom: 1;
    }

    .group-actions {
        height: auto;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("[bold]Import / Export[/bold]", id="ie-header")

        # Full workspace
        with Vertical(classes="export-group"):
            yield Static("Full Workspace", classes="group-title")
            yield Static("[dim]Backup or restore everything: collections, environments, history, workflows, functions, plugins[/dim]")
            with Horizontal(classes="group-actions"):
                yield Button("Export All", variant="primary", id="export-all-btn")
                yield Button("Import All", id="import-all-btn")

        # Collections
        with Vertical(classes="export-group"):
            yield Static("Collections", classes="group-title")
            yield Static("[dim]Export or import collections with their saved requests[/dim]")
            with Horizontal(classes="group-actions"):
                yield Button("Export", id="export-collections-btn")
                yield Button("Import", id="import-collections-btn")

        # Environments
        with Vertical(classes="export-group"):
            yield Static("Environments", classes="group-title")
            yield Static("[dim]Export or import environments and their variables[/dim]")
            with Horizontal(classes="group-actions"):
                yield Button("Export", id="export-envs-btn")
                yield Button("Import", id="import-envs-btn")

        # OpenAPI
        with Vertical(classes="export-group"):
            yield Static("OpenAPI / Swagger", classes="group-title")
            yield Static("[dim]Import an OpenAPI spec as a collection[/dim]")
            with Horizontal(classes="group-actions"):
                yield Button("Import OpenAPI", id="import-openapi-btn")
