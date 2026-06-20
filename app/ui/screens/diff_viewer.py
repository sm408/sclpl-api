"""Diff viewer for comparing responses."""

from __future__ import annotations

import difflib
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, TextArea


class DiffViewer(Vertical):
    """Side-by-side diff viewer for comparing two responses."""

    CSS = """
    DiffViewer {
        height: 100%;
        padding: 1;
    }

    #diff-header {
        height: auto;
        margin-bottom: 1;
    }

    #diff-content {
        height: 1fr;
    }

    #diff-left {
        width: 1fr;
        border-right: solid $primary;
    }

    #diff-right {
        width: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("[bold]Diff Viewer[/bold]", id="diff-header")
        with Horizontal(id="diff-content"):
            yield TextArea(
                "[dim]Load left side...[/dim]",
                id="diff-left",
                read_only=True,
            )
            yield TextArea(
                "[dim]Load right side...[/dim]",
                id="diff-right",
                read_only=True,
            )

    def set_diff(self, left: str, right: str, left_label: str = "Left", right_label: str = "Right") -> None:
        """Set the two sides to compare."""
        header = self.query_one("#diff-header", Static)
        header.update(f"[bold]Diff: {left_label} vs {right_label}[/bold]")

        self.query_one("#diff-left", TextArea).text = left
        self.query_one("#diff-right", TextArea).text = right

    def set_unified_diff(self, text_a: str, text_b: str, fromfile: str = "a", tofile: str = "b") -> None:
        """Generate and display a unified diff."""
        a_lines = text_a.splitlines(keepends=True)
        b_lines = text_b.splitlines(keepends=True)

        diff = list(difflib.unified_diff(a_lines, b_lines, fromfile=fromfile, tofile=tofile))

        if not diff:
            header = self.query_one("#diff-header", Static)
            header.update("[green]No differences[/green]")
            return

        diff_text = "".join(diff)

        # Color the diff
        colored_lines = []
        for line in diff_text.splitlines():
            if line.startswith("+"):
                colored_lines.append(f"[green]{line}[/green]")
            elif line.startswith("-"):
                colored_lines.append(f"[red]{line}[/red]")
            elif line.startswith("@@"):
                colored_lines.append(f"[cyan]{line}[/cyan]")
            else:
                colored_lines.append(line)

        header = self.query_one("#diff-header", Static)
        header.update(f"[bold]Unified Diff: {fromfile} -> {tofile}[/bold]")

        self.query_one("#diff-left", TextArea).text = "\n".join(colored_lines)
        self.query_one("#diff-right", TextArea).text = ""
