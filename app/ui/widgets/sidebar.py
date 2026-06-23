"""Sidebar widget with collection tree, workflow list, and environments."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Static, Tree


class SidebarTree(Tree):
    """Base tree widget for sidebar sections."""

    def __init__(self, title: str, **kwargs) -> None:
        super().__init__(title, **kwargs)
        self.show_root = False
        self.guide_depth = 2


class CollectionTree(SidebarTree):
    """Tree displaying collections and their requests."""

    def __init__(self, **kwargs) -> None:
        super().__init__("Collections", **kwargs)
        self._collections: list[dict] = []

    def set_collections(self, collections: list[dict]) -> None:
        """Update the collection tree."""
        self._collections = collections
        self.root.remove_children()
        for col in collections:
            col_node = self.root.add(f"[bold]{col['name']}[/bold]")
            for req in col.get("requests", []):
                method = req.get("method", "GET")
                name = req.get("name", "Untitled")
                col_node.add_leaf(f"[dim]{method}[/dim] {name}")
        self.root.expand()


class WorkflowTree(SidebarTree):
    """Tree displaying available workflows."""

    def __init__(self, **kwargs) -> None:
        super().__init__("Workflows", **kwargs)
        self._workflows: list[dict] = []

    def set_workflows(self, workflows: list[dict]) -> None:
        """Update the workflow tree."""
        self._workflows = workflows
        self.root.remove_children()
        for wf in workflows:
            name = wf.get("name", wf.get("id", "Unknown"))
            steps = wf.get("step_count", 0)
            self.root.add_leaf(f"[bold]{name}[/bold] [dim]({steps} steps)[/dim]")
        self.root.expand()


class EnvironmentDisplay(Static):
    """Display for active environment and variables."""

    env_name: reactive[str] = reactive("none")
    var_count: reactive[int] = reactive(0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def render(self) -> str:
        if self.env_name == "none":
            return "[dim]No environment active[/dim]"
        return f"[bold]{self.env_name}[/bold] [dim]({self.var_count} vars)[/dim]"

    def set_environment(self, name: str, var_count: int) -> None:
        self.env_name = name
        self.var_count = var_count


class Sidebar(VerticalScroll):
    """Left sidebar with collections, workflows, and environments."""

    CSS = """
    Sidebar {
        width: 100%;
        height: 100%;
        background: $surface;
    }

    .sidebar-header {
        padding: 1;
        text-style: bold;
        background: $primary;
        color: $text;
    }

    .sidebar-section {
        margin: 0;
        padding: 0;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.collection_tree = CollectionTree(classes="sidebar-section")
        self.workflow_tree = WorkflowTree(classes="sidebar-section")
        self.env_display = EnvironmentDisplay(classes="sidebar-section")

    def compose(self) -> ComposeResult:
        yield Static("SCLPLAPI", classes="sidebar-header")
        yield self.collection_tree
        yield Static("")
        yield self.workflow_tree
        yield Static("")
        yield Static("[bold]Environment[/bold]", classes="sidebar-header")
        yield self.env_display

    def update_collections(self, collections: list[dict]) -> None:
        self.collection_tree.set_collections(collections)

    def update_workflows(self, workflows: list[dict]) -> None:
        self.workflow_tree.set_workflows(workflows)

    def update_environment(self, name: str, var_count: int) -> None:
        self.env_display.set_environment(name, var_count)
