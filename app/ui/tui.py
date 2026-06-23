"""SCLPLAPI Terminal User Interface.

Production-quality TUI built with Rich for the SCLPLAPI workflow studio.
Provides interactive menus, live workflow execution, function browsing,
history viewing, environment management, import/export, and script validation.
"""

from __future__ import annotations

import asyncio
import csv
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from app.ui.logo import LOGO, VERSION

# ─── Keyboard shortcuts ──────────────────────────────────────────────────────

SHORTCUTS_HELP = (
    "[dim]Shortcuts: "
    "[bold]R[/bold]=Run  "
    "[bold]S[/bold]=Send  "
    "[bold]C[/bold]=Collections  "
    "[bold]H[/bold]=History  "
    "[bold]M[/bold]=Manage  "
    "[bold]I[/bold]=Tools  "
    "[bold]Q[/bold]=Quit  "
    "[bold]?[/bold]=Help"
    "[/dim]"
)

# ─── Status icons ────────────────────────────────────────────────────────────

PENDING = "[dim]○[/dim]"
RUNNING = "[bold yellow]◉[/bold yellow]"
SUCCESS = "[bold green]●[/bold green]"
FAILED = "[bold red]●[/bold red]"
SKIPPED = "[dim]◌[/dim]"

STATUS_MAP = {
    "pending": PENDING,
    "running": RUNNING,
    "success": SUCCESS,
    "failed": FAILED,
    "skipped": SKIPPED,
}


# ─── Data classes for step tracking ──────────────────────────────────────────


@dataclass
class StepState:
    id: str
    name: str
    step_type: str
    status: str = "pending"
    started_at: float = 0.0
    completed_at: float = 0.0
    duration_ms: int = 0
    error: str | None = None
    output_summary: str = ""
    depends_on: list[str] = field(default_factory=list)
    group_index: int = 0


# ─── TUI Application ────────────────────────────────────────────────────────


class TUI:
    """Interactive Terminal User Interface for SCLPLAPI."""

    def __init__(self, db_path: str = "data/sclplapi.db") -> None:
        self.console = Console()
        self.db_path = db_path
        self._running = True
        self._recent_workflows: list[Path] = []
        self._current_env: str = "none"
        self._last_workflow_path: Path | None = None
        self._last_workflow_result: Any = None
        self._request_rerun: bool = False

    # ── Entry point ──────────────────────────────────────────────────────

    def run(self) -> None:
        """Launch the TUI main loop."""
        try:
            self._show_splash()
            self._main_menu()
        except KeyboardInterrupt:
            self._goodbye()
        except Exception as e:
            self.console.print()
            self.console.print(Panel(
                f"[red]{type(e).__name__}: {e}[/red]\n\n"
                "[dim]This is an unexpected error. You can:\n"
                "  - Restart the TUI with: python -m app\n"
                "  - Report the issue at: https://github.com/sm408/sclpl-api/issues[/dim]",
                title="[bold red]Unexpected Error[/bold red]",
                border_style="red",
                box=box.ROUNDED,
            ))
            self.console.print()

    # ── Splash screen ────────────────────────────────────────────────────

    def _show_splash(self) -> None:
        self.console.clear()
        self.console.print(LOGO)
        self.console.print()
        self.console.print(
            Align.center(f"[dim]{VERSION}[/dim]"),
        )
        self.console.print()
        self.console.print(Align.center(SHORTCUTS_HELP))
        self.console.print()

    # ── Status bar ───────────────────────────────────────────────────────

    def _print_status_bar(self) -> None:
        env_display = self._current_env if self._current_env != "none" else "[dim]none[/dim]"
        recent_count = len(self._recent_workflows)
        recent_display = f"[dim]{recent_count} recent[/dim]" if recent_count else "[dim]no recent[/dim]"
        self.console.print(
            Panel(
                f"  Env: {env_display}  |  {recent_display}  |  {SHORTCUTS_HELP}",
                style="dim",
                box=box.SIMPLE,
                padding=(0, 1),
            )
        )

    # ── Help screen ──────────────────────────────────────────────────────

    def _show_help(self) -> None:
        self.console.print()
        help_table = Table(
            title="Keyboard Shortcuts & Help",
            box=box.ROUNDED,
            border_style="cyan",
            header_style="bold cyan",
            show_lines=True,
        )
        help_table.add_column("Key", width=6, justify="center")
        help_table.add_column("Action", min_width=20)
        help_table.add_column("Description", min_width=40)

        help_table.add_row("R", "Run", "Run workflow, recent, or load script (submenu)")
        help_table.add_row("S", "Send Request", "Send a single HTTP request")
        help_table.add_row("C", "Collections", "Browse saved collections and requests")
        help_table.add_row("H", "History", "Browse past request and workflow history")
        help_table.add_row("M", "Manage", "Environments, functions, plugins, settings (submenu)")
        help_table.add_row("I", "Tools", "Import, export, validate (submenu)")
        help_table.add_row("?", "Help", "Show this help screen")
        help_table.add_row("Q", "Quit", "Exit SCLPLAPI")

        self.console.print(help_table)
        self.console.print()
        self.console.print("[dim]Tip: Steps without dependencies run in parallel automatically.[/dim]")
        self.console.print("[dim]Tip: Use {{variable}} syntax to reference step outputs in URLs and headers.[/dim]")
        self.console.print()

    # ── Main menu ────────────────────────────────────────────────────────

    def _main_menu(self) -> None:
        while self._running:
            self._print_status_bar()
            self.console.print()
            self.console.print(Panel(
                self._build_menu_content(),
                title="[bold cyan]Main Menu[/bold cyan]",
                border_style="cyan",
                box=box.ROUNDED,
                padding=(1, 2),
            ))
            self.console.print()

            choice = Prompt.ask(
                "[bold cyan]Select[/bold cyan]",
                default="q",
            ).strip().lower()

            self.console.print()

            if choice == "r":
                self._run_submenu()
            elif choice == "s":
                self._send_request()
            elif choice == "c":
                self._collections_browser()
            elif choice == "h":
                self._history_viewer()
            elif choice == "m":
                self._manage_submenu()
            elif choice == "i":
                self._tools_submenu()
            elif choice == "?":
                self._show_help()
            elif choice == "q":
                self._running = False

        self._goodbye()

    def _build_menu_content(self) -> Table:
        menu = Table(box=None, show_header=False, padding=(0, 2))
        menu.add_column("Key", width=4)
        menu.add_column("Label", min_width=14)
        menu.add_column("Description", min_width=40, style="dim")
        menu.add_row("[bold cyan][R][/bold cyan]", "Run", "Execute, validate, or re-run workflows")
        menu.add_row("[bold cyan][S][/bold cyan]", "Send", "Send a single HTTP request")
        menu.add_row("[bold cyan][C][/bold cyan]", "Collections", "Browse saved collections and requests")
        menu.add_row("[bold cyan][H][/bold cyan]", "History", "Browse past request and workflow history")
        menu.add_row("[bold cyan][M][/bold cyan]", "Manage", "Environments, functions, plugins, settings")
        menu.add_row("[bold cyan][I][/bold cyan]", "Tools", "Import, export, and utilities")
        menu.add_row("", "", "")
        menu.add_row("[bold cyan][?][/bold cyan]", "Help", "Keyboard shortcuts and tips")
        menu.add_row("[bold red][Q][/bold red]", "Quit", "Exit SCLPLAPI")
        return menu

    # ── Run submenu ─────────────────────────────────────────────────────

    def _run_submenu(self) -> None:
        self.console.print(Rule("[bold cyan]Run[/bold cyan]", style="cyan"))
        self.console.print()
        self.console.print("  [bold cyan][[1]][/bold cyan] Run workflow file")
        self.console.print("  [bold cyan][[2]][/bold cyan] Recent workflows")
        self.console.print("  [bold cyan][[3]][/bold cyan] Load script (view / validate / run)")
        self.console.print("  [dim][[0]] Back[/dim]")
        self.console.print()

        choice = Prompt.ask("[cyan]Select (0-3)[/cyan]", default="1").strip()
        if choice == "1":
            self._workflow_runner()
        elif choice == "2":
            self._recent_workflows_menu()
        elif choice == "3":
            self._load_script()

    # ── Manage submenu ──────────────────────────────────────────────────

    def _manage_submenu(self) -> None:
        self.console.print(Rule("[bold cyan]Manage[/bold cyan]", style="cyan"))
        self.console.print()
        self.console.print("  [bold cyan][[1]][/bold cyan] Environments")
        self.console.print("  [bold cyan][[2]][/bold cyan] Functions")
        self.console.print("  [bold cyan][[3]][/bold cyan] Plugins")
        self.console.print("  [bold cyan][[4]][/bold cyan] Settings")
        self.console.print("  [dim][[0]] Back[/dim]")
        self.console.print()

        choice = Prompt.ask("[cyan]Select (0-4)[/cyan]", default="0").strip()
        if choice == "1":
            self._environment_manager()
        elif choice == "2":
            self._function_browser()
        elif choice == "3":
            self._plugin_browser()
        elif choice == "4":
            self._settings_menu()

    # ── Tools submenu ───────────────────────────────────────────────────

    def _tools_submenu(self) -> None:
        self.console.print(Rule("[bold cyan]Tools[/bold cyan]", style="cyan"))
        self.console.print()
        self.console.print("  [bold cyan][[1]][/bold cyan] Import / Export")
        self.console.print("  [bold cyan][[2]][/bold cyan] Validate script")
        self.console.print("  [dim][[0]] Back[/dim]")
        self.console.print()

        choice = Prompt.ask("[cyan]Select (0-2)[/cyan]", default="0").strip()
        if choice == "1":
            self._import_export_menu()
        elif choice == "2":
            self._script_validator()

    # ── Settings ────────────────────────────────────────────────────────

    def _settings_menu(self) -> None:
        self.console.print(Rule("[bold cyan]Settings[/bold cyan]", style="cyan"))
        self.console.print()

        while True:
            self.console.print(f"  [bold]Database:[/bold]         {self.db_path}")
            self.console.print(f"  [bold]Environment:[/bold]      {self._current_env}")
            self.console.print("  [bold]Export dir:[/bold]        data/exports")
            self.console.print("  [bold]Request timeout:[/bold]   30s")
            self.console.print()
            self.console.print("  [bold cyan][[1]][/bold cyan] Change database path")
            self.console.print("  [dim][[0]] Back[/dim]")
            self.console.print()

            choice = Prompt.ask("[cyan]Select (0-1)[/cyan]", default="0").strip()
            if choice == "0":
                break
            elif choice == "1":
                new_path = Prompt.ask("[cyan]New database path[/cyan]", default=self.db_path)
                if new_path:
                    self.db_path = new_path
                    self.console.print(f"[green]Database path set to {new_path}[/green]")

    # ── Workflow runner ──────────────────────────────────────────────────

    def _workflow_runner(self) -> None:
        self.console.print(Rule("[bold cyan]Workflow Runner[/bold cyan]", style="cyan"))

        # Discover .sclpll files
        sclpll_files = self._discover_sclpll_files()
        if not sclpll_files:
            self.console.print(
                "[yellow]No .sclpll files found in current dir or examples/[/yellow]"
            )
            self.console.print("[dim]Provide a path to a .sclpll or .json workflow file.[/dim]")
            path_str = Prompt.ask("[cyan]Workflow file path[/cyan]", default="")
            if not path_str:
                return
            sclpll_files = [Path(path_str)]

        self.console.print()
        for i, f in enumerate(sclpll_files, 1):
            self.console.print(f"  [cyan][[{i}]][/cyan] {f}")
        self.console.print("  [dim][[0]] Cancel[/dim]")
        self.console.print()

        idx_str = Prompt.ask(
            "[cyan]Select file[/cyan]",
            default="1",
        )
        try:
            idx = int(idx_str)
        except ValueError:
            self.console.print("[red]Invalid selection. Enter a number.[/red]")
            return
        if idx == 0:
            return
        if idx > len(sclpll_files):
            self.console.print(f"[red]Invalid selection. Choose 1-{len(sclpll_files)}.[/red]")
            return

        selected = sclpll_files[idx - 1]
        self.console.print(f"\n[bold]Loading:[/bold] {selected}")
        self._track_recent(selected)
        self._execute_workflow_file(selected)

    def _discover_sclpll_files(self) -> list[Path]:
        files: list[Path] = []
        for d in [Path("."), Path("examples"), Path("workflows")]:
            if d.exists():
                files.extend(sorted(d.rglob("*.sclpll")))
        return files[:20]

    # ── Recent workflows ─────────────────────────────────────────────────

    def _track_recent(self, path: Path) -> None:
        """Track a workflow file in the recent list (most recent first)."""
        resolved = path.resolve()
        self._recent_workflows = [p for p in self._recent_workflows if p.resolve() != resolved]
        self._recent_workflows.insert(0, path)
        self._recent_workflows = self._recent_workflows[:10]

    def _recent_workflows_menu(self) -> None:
        self.console.print(Rule("[bold cyan]Recent Workflows[/bold cyan]", style="cyan"))
        self.console.print()

        if not self._recent_workflows:
            self.console.print("[dim]No recent workflows. Run a workflow first with [R].[/dim]")
            return

        for i, f in enumerate(self._recent_workflows, 1):
            exists = f.exists()
            status = "" if exists else " [red](missing)[/red]"
            self.console.print(f"  [cyan][[{i}]][/cyan] {f}{status}")
        self.console.print("  [dim][[0]] Cancel[/dim]")
        self.console.print()

        idx_str = Prompt.ask("[cyan]Select workflow to run[/cyan]", default="0")
        try:
            idx = int(idx_str)
        except ValueError:
            self.console.print("[red]Invalid selection. Enter a number.[/red]")
            return
        if idx == 0:
            return
        if idx > len(self._recent_workflows):
            self.console.print(f"[red]Invalid selection. Choose 1-{len(self._recent_workflows)}.[/red]")
            return

        selected = self._recent_workflows[idx - 1]
        if not selected.exists():
            self.console.print(f"[red]File no longer exists: {selected}[/red]")
            return

        self._track_recent(selected)
        self._execute_workflow_file(selected)

    def _execute_workflow_file(self, path: Path) -> None:
        self._last_workflow_path = path
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as e:
            self.console.print(
                f"[red]Cannot read file:[/red] {e}\n"
                f"[dim]Tip: Check that the file exists and you have read permissions.[/dim]"
            )
            return

        # Parse the workflow
        if path.suffix == ".sclpll":
            from app.core.engine.sclpll_compiler import SCLPLLCompiler, SCLPLLParseError

            compiler = SCLPLLCompiler()
            try:
                workflow_dict = compiler.parse(source)
            except SCLPLLParseError as e:
                self.console.print(
                    f"[red]Syntax error in {path.name}:[/red]\n{e}\n"
                    f"[dim]Tip: Check indentation, missing quotes, or typos in directives.[/dim]"
                )
                return
        elif path.suffix == ".json":
            try:
                workflow_dict = json.loads(source)
            except json.JSONDecodeError as e:
                self.console.print(
                    f"[red]Invalid JSON in {path.name}:[/red]\n{e}\n"
                    f"[dim]Tip: Validate your JSON at jsonlint.com or check for trailing commas.[/dim]"
                )
                return
        else:
            self.console.print(
                f"[red]Unsupported file type:[/red] {path.suffix}\n"
                f"[dim]Tip: SCLPLAPI supports .sclpll and .json workflow files.[/dim]"
            )
            return

        # Build step states
        step_states: list[StepState] = []
        for s in workflow_dict.get("steps", []):
            step_states.append(StepState(
                id=s["id"],
                name=s.get("name", s["id"]),
                step_type=s.get("type", "request"),
                depends_on=s.get("depends_on", []),
            ))

        # Assign group indices for parallel visualization
        self._assign_groups(step_states)

        # Run with live display, support re-run loop
        while True:
            self._request_rerun = False
            try:
                self._last_workflow_result = asyncio.run(
                    self._run_workflow_live(workflow_dict, step_states)
                )
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Workflow cancelled by user[/yellow]")
                break
            except Exception as e:
                self.console.print()
                self.console.print(Panel(
                    f"[red]Workflow execution failed:[/red]\n{e}\n\n"
                    "[dim]Possible causes:\n"
                    "  - Network timeout or DNS failure\n"
                    "  - Invalid workflow configuration\n"
                    "  - Dependency not installed[/dim]",
                    title="[bold red]Execution Error[/bold red]",
                    border_style="red",
                    box=box.ROUNDED,
                ))
                break

            # Show summary and post-workflow menu (outside async context)
            self.console.print()
            if self._last_workflow_result:
                self._print_workflow_summary(self._last_workflow_result)
                self._post_workflow_menu(self._last_workflow_result)
            self.console.print()

            if not self._request_rerun:
                break

    def _assign_groups(self, steps: list[StepState]) -> None:
        """Assign execution group indices based on dependency depth."""
        step_map = {s.id: s for s in steps}
        assigned: dict[str, int] = {}

        def depth(step_id: str) -> int:
            if step_id in assigned:
                return assigned[step_id]
            step = step_map.get(step_id)
            if not step or not step.depends_on:
                assigned[step_id] = 0
                return 0
            d = max(depth(dep) for dep in step.depends_on) + 1
            assigned[step_id] = d
            return d

        for s in steps:
            s.group_index = depth(s.id)

    async def _run_workflow_live(
        self,
        workflow_dict: dict[str, Any],
        step_states: list[StepState],
    ) -> Any:
        from app.core.engine.parallel_workflow import ParallelWorkflowEngine
        from app.core.models.context import ExecutionContext
        from app.core.models.workflow import StepType, WorkflowDef, WorkflowStep
        from app.ui.app import App

        # Build workflow objects
        steps = []
        for s in workflow_dict.get("steps", []):
            steps.append(WorkflowStep(
                id=s["id"],
                name=s.get("name", s["id"]),
                step_type=StepType(s["type"]),
                config=s.get("config", {}),
                depends_on=s.get("depends_on", []),
                output_variable=s.get("output_variable"),
            ))

        workflow_def = WorkflowDef(
            id=workflow_dict.get("id", "tui-workflow"),
            name=workflow_dict.get("name", "TUI Workflow"),
            description=workflow_dict.get("description", ""),
            steps=steps,
            variables=workflow_dict.get("variables", {}),
        )

        # Step state lookup
        state_map = {s.id: s for s in step_states}

        # Create progress bar
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
        )
        total_steps = len(step_states)
        task_id = progress.add_task("Executing workflow", total=total_steps)

        # Event-driven live display
        update_event = asyncio.Event()

        def on_step_started(event):
            sid = event.data.get("step_id", "")
            if sid in state_map:
                state_map[sid].status = "running"
                state_map[sid].started_at = time.monotonic()
                update_event.set()

        def on_step_completed(event):
            sid = event.data.get("step_id", "")
            if sid in state_map:
                s = state_map[sid]
                s.status = "success"
                s.completed_at = time.monotonic()
                if s.started_at:
                    s.duration_ms = int((s.completed_at - s.started_at) * 1000)
                progress.advance(task_id)
                update_event.set()

        def on_step_failed(event):
            sid = event.data.get("step_id", "")
            if sid in state_map:
                s = state_map[sid]
                s.status = "failed"
                s.error = event.data.get("error", "")
                s.completed_at = time.monotonic()
                if s.started_at:
                    s.duration_ms = int((s.completed_at - s.started_at) * 1000)
                progress.advance(task_id)
                update_event.set()

        def on_workflow_event(event):
            update_event.set()

        # Build display layout
        def build_display() -> Panel:
            table = Table(
                box=box.SIMPLE_HEAVY,
                show_header=True,
                header_style="bold cyan",
                expand=True,
                padding=(0, 1),
            )
            table.add_column("Status", width=8, justify="center")
            table.add_column("Step", min_width=20)
            table.add_column("Type", width=10, justify="center")
            table.add_column("Group", width=8, justify="center")
            table.add_column("Duration", width=10, justify="right")
            table.add_column("Details", min_width=20)

            current_group = -1
            for s in step_states:
                # Add group separator
                if s.group_index != current_group:
                    current_group = s.group_index
                    group_label = f"Group {current_group}"
                    if current_group > 0:
                        group_label += " (parallel)"
                    table.add_row(
                        "", f"[dim]── {group_label} ──[/dim]", "", "", "", "",
                        style="dim",
                    )

                status_icon = STATUS_MAP.get(s.status, PENDING)
                duration = (
                    f"{s.duration_ms}ms" if s.duration_ms
                    else ("..." if s.status == "running" else "")
                )
                detail = ""
                if s.error:
                    detail = f"[red]{s.error[:120]}[/red]"
                elif s.status == "success" and s.output_summary:
                    detail = s.output_summary[:60]

                type_color = {
                    "request": "yellow",
                    "function": "magenta",
                    "delay": "dim",
                }.get(s.step_type, "white")

                table.add_row(
                    status_icon,
                    s.name,
                    f"[{type_color}]{s.step_type}[/{type_color}]",
                    str(s.group_index),
                    duration,
                    detail,
                )

            return Panel(
                Group(progress, table),
                title=f"[bold cyan]{workflow_def.name}[/bold cyan]",
                subtitle=(
                f"[dim]{len(step_states)} steps"
                f" · {'parallel' if any(s.group_index > 0 for s in step_states) else 'sequential'}"
                "[/dim]"
            ),
                border_style="cyan",
                box=box.ROUNDED,
                padding=(1, 1),
            )

        # Run with live display
        self.console.print()
        workflow_result = None

        live_display = build_display()
        with Live(
            live_display,
            console=self.console,
            refresh_per_second=8,
            transient=False,
        ) as live:
            async with App(self.db_path) as application:
                engine = ParallelWorkflowEngine(
                    request_executor=application.request_executor,
                    event_bus=application.event_bus,
                )

                # Subscribe to workflow events for live tracking
                application.event_bus.subscribe("workflow.step_started", on_workflow_event)
                application.event_bus.subscribe("workflow.step_completed", on_workflow_event)
                application.event_bus.subscribe("workflow.step_failed", on_workflow_event)
                application.event_bus.subscribe("*", on_workflow_event)

                ctx = ExecutionContext()

                # Run in background, update display periodically
                async def run_engine():
                    nonlocal workflow_result
                    workflow_result = await engine.execute(workflow_def, ctx, {})
                    # Sync final states from result
                    if workflow_result:
                        for sr in workflow_result.step_results:
                            if sr.step_id in state_map:
                                s = state_map[sr.step_id]
                                s.status = "success" if sr.success else "failed"
                                s.duration_ms = sr.duration_ms
                                s.error = sr.error
                                if sr.output:
                                    if isinstance(sr.output, dict):
                                        sc = sr.output.get("status_code", "")
                                        s.output_summary = (
                                            f"HTTP {sc}" if sc
                                            else str(sr.output)[:40]
                                        )
                                    else:
                                        s.output_summary = str(sr.output)[:40]
                    update_event.set()

                async def refresh_loop():
                    while True:
                        try:
                            await asyncio.wait_for(update_event.wait(), timeout=30.0)
                            update_event.clear()
                            live.update(build_display())
                            if workflow_result:
                                break
                        except TimeoutError:
                            live.update(build_display())
                            if workflow_result:
                                break

                try:
                    await asyncio.gather(run_engine(), refresh_loop())
                except Exception as e:
                    self.console.print(f"\n[red]Error during execution: {e}[/red]")

        return workflow_result

    def _print_workflow_summary(self, result: Any) -> None:
        color = "green" if result.success else "red"
        status = "PASSED" if result.success else "FAILED"

        summary_table = Table(box=box.ROUNDED, show_header=False, border_style=color)
        summary_table.add_column("Key", style="bold")
        summary_table.add_column("Value")
        summary_table.add_row("Status", f"[{color}]{status}[/{color}]")
        summary_table.add_row("Duration", f"{result.total_duration_ms}ms")
        summary_table.add_row("Steps", str(len(result.step_results)))
        ok = sum(1 for r in result.step_results if r.success)
        fail = sum(1 for r in result.step_results if not r.success)
        summary_table.add_row("Results", f"[green]{ok} ok[/green] / [red]{fail} failed[/red]")

        if result.parallel_groups:
            summary_table.add_row("Parallel Groups", str(len(result.parallel_groups)))

        self.console.print(Panel(
            summary_table,
            title=f"[bold {color}]Workflow Result[/bold {color}]",
            border_style=color,
            box=box.ROUNDED,
        ))

        # Show step results table
        self.console.print()
        steps_table = Table(
            title="Step Results",
            box=box.ROUNDED,
            border_style="cyan",
            header_style="bold cyan",
            show_lines=True,
        )
        steps_table.add_column("#", width=4, justify="right", style="dim")
        steps_table.add_column("Step", min_width=20)
        steps_table.add_column("Status", width=8, justify="center")
        steps_table.add_column("Duration", width=10, justify="right")
        steps_table.add_column("Output Preview", min_width=30)

        for i, sr in enumerate(result.step_results, 1):
            status_icon = "[green]OK[/green]" if sr.success else "[red]FAIL[/red]"
            duration = f"{sr.duration_ms}ms"
            preview = ""
            if sr.error:
                preview = f"[red]{str(sr.error)[:60]}[/red]"
            elif sr.output is not None:
                if isinstance(sr.output, dict):
                    sc = sr.output.get("status_code", "")
                    preview = f"HTTP {sc}" if sc else str(sr.output)[:60]
                elif isinstance(sr.output, list):
                    preview = f"{len(sr.output)} items"
                else:
                    preview = str(sr.output)[:60]
            steps_table.add_row(str(i), sr.step_name, status_icon, duration, preview)

        self.console.print(steps_table)

    def _post_workflow_menu(self, result: Any) -> None:
        """Menu for actions after workflow completion."""
        while True:
            self.console.print()
            self.console.print("  [bold cyan][[1]][/bold cyan] View step output")
            self.console.print("  [bold cyan][[2]][/bold cyan] Export results (JSON)")
            self.console.print("  [bold cyan][[3]][/bold cyan] Export results (CSV)")
            if self._last_workflow_path:
                self.console.print("  [bold cyan][[R]][/bold cyan] Re-run workflow")
            self.console.print("  [bold cyan][[0]][/bold cyan] Back to main menu")
            self.console.print()

            choice = Prompt.ask("[cyan]Select (0/1/2/3/R)[/cyan]", default="0").strip().lower()

            if choice == "0":
                break
            elif choice == "1":
                self._view_step_output(result)
            elif choice == "2":
                self._export_results(result, "json")
            elif choice == "3":
                self._export_results(result, "csv")
            elif choice == "r":
                self._request_rerun = True
                break
            else:
                self.console.print("[red]Invalid choice. Enter 0, 1, 2, 3, or R.[/red]")

    def _view_step_output(self, result: Any) -> None:
        """Display detailed output for a selected step, with loop for multiple views."""
        if not result.step_results:
            self.console.print("[dim]No step results to display[/dim]")
            return

        while True:
            self.console.print()
            for i, sr in enumerate(result.step_results, 1):
                status = "[green]OK[/green]" if sr.success else "[red]FAIL[/red]"
                self.console.print(f"  [cyan][[{i}]][/cyan] {sr.step_name} ({status})")
            self.console.print("  [dim][[0]] Back[/dim]")
            self.console.print()

            idx_str = Prompt.ask("[cyan]Select step (number)[/cyan]", default="0")
            if not idx_str or idx_str == "0":
                return
            try:
                idx = int(idx_str) - 1
            except ValueError:
                self.console.print("[red]Invalid selection. Enter a number.[/red]")
                continue

            if idx < 0 or idx >= len(result.step_results):
                self.console.print(f"[red]Invalid selection. Choose 1-{len(result.step_results)}.[/red]")
                continue

            sr = result.step_results[idx]
            self.console.print()

            # Step info
            info_table = Table(box=box.SIMPLE, show_header=False)
            info_table.add_column("Key", style="bold cyan", min_width=14)
            info_table.add_column("Value")
            info_table.add_row("Step ID", sr.step_id)
            info_table.add_row("Name", sr.step_name)
            info_table.add_row("Status", "[green]Success[/green]" if sr.success else "[red]Failed[/red]")
            info_table.add_row("Duration", f"{sr.duration_ms}ms")
            if sr.error:
                info_table.add_row("Error", f"[red]{sr.error}[/red]")

            self.console.print(Panel(
                info_table,
                title=f"[bold cyan]Step: {sr.step_name}[/bold cyan]",
                border_style="cyan",
                box=box.ROUNDED,
            ))

            # Output body
            if sr.output is not None:
                output_str = self._format_output(sr.output)
                self.console.print(Panel(
                    output_str,
                    title="[bold]Output[/bold]",
                    border_style="cyan",
                    box=box.ROUNDED,
                    padding=(1, 2),
                ))

            self.console.print()
            Prompt.ask("[dim]Press Enter to go back to step list[/dim]", default="")

    def _format_output(self, output: Any) -> str:
        """Format step output for display."""
        if output is None:
            return "[dim]No output[/dim]"

        if isinstance(output, dict):
            if "body" in output and isinstance(output["body"], str):
                try:
                    body_parsed = json.loads(output["body"])
                    output = {**output, "body": body_parsed}
                except (json.JSONDecodeError, TypeError):
                    pass
            return json.dumps(output, indent=2, default=str)[:5000]

        if isinstance(output, list):
            formatted_items = []
            for item in output[:10]:
                if isinstance(item, dict) and "body" in item and isinstance(item["body"], str):
                    try:
                        item = {**item, "body": json.loads(item["body"])}
                    except (json.JSONDecodeError, TypeError):
                        pass
                formatted_items.append(json.dumps(item, indent=2, default=str))
            result = "[\n" + ",\n".join(formatted_items)
            if len(output) > 10:
                result += f",\n  ... ({len(output) - 10} more items)"
            result += "\n]"
            return result[:5000]

        if isinstance(output, str):
            try:
                parsed = json.loads(output)
                return json.dumps(parsed, indent=2, default=str)[:5000]
            except (json.JSONDecodeError, TypeError):
                return output[:5000]

        return str(output)[:5000]

    def _export_results(self, result: Any, fmt: str) -> None:
        """Export workflow results to JSON or CSV."""
        rows = []
        for sr in result.step_results:
            row = {
                "step_id": sr.step_id,
                "step_name": sr.step_name,
                "success": sr.success,
                "duration_ms": sr.duration_ms,
                "error": sr.error or "",
            }
            if sr.output is not None:
                if isinstance(sr.output, dict):
                    row["output_status_code"] = sr.output.get("status_code", "")
                    body = sr.output.get("body", "")
                    if isinstance(body, str):
                        row["output_body"] = body[:5000]
                    else:
                        row["output_body"] = json.dumps(body, default=str)[:5000]
                elif isinstance(sr.output, list):
                    row["output_body"] = json.dumps(sr.output, default=str)[:5000]
                else:
                    row["output_body"] = str(sr.output)[:5000]
            else:
                row["output_body"] = ""
            rows.append(row)

        if not rows:
            self.console.print("[yellow]No results to export[/yellow]")
            return

        # Build default filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        workflow_id = getattr(result, 'workflow_id', 'workflow')
        default_filename = f"{workflow_id}_{timestamp}.{fmt}"
        default_dir = Path("data/exports")

        # Ask user for filename and location
        self.console.print()
        self.console.print(f"[dim]Default: {default_dir / default_filename}[/dim]")
        custom_path = Prompt.ask(
            "[cyan]Save path (Enter for default)[/cyan]",
            default="",
        )

        if custom_path:
            output_path = Path(custom_path)
            if output_path.is_dir():
                output_path = output_path / default_filename
            if output_path.suffix not in (f".{fmt}",):
                output_path = output_path.with_suffix(f".{fmt}")
        else:
            output_path = default_dir / default_filename

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Handle file collision
        output_path = self._handle_file_collision(output_path, fmt)
        if output_path is None:
            self.console.print("[yellow]Export cancelled[/yellow]")
            return

        # Write file
        try:
            if fmt == "json":
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(rows, f, indent=2, default=str)
            elif fmt == "csv":
                if rows:
                    fieldnames = list(rows[0].keys())
                    with open(output_path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)

            self.console.print(f"[green]Exported to {output_path}[/green]")
            self.console.print(f"[dim]{len(rows)} records written[/dim]")
        except OSError as e:
            self.console.print(f"[red]Export failed: {e}[/red]")

    def _handle_file_collision(self, path: Path, fmt: str) -> Path | None:
        """Handle file name collision."""
        if not path.exists():
            return path

        self.console.print()
        self.console.print(f"[yellow]File already exists:[/yellow] {path}")
        self.console.print()
        self.console.print("  [bold cyan][[1]][/bold cyan] Replace (overwrite)")
        self.console.print("  [bold cyan][[2]][/bold cyan] Keep old file, cancel export")
        self.console.print("  [bold cyan][[3]][/bold cyan] Add prefix to new file")
        self.console.print("  [bold cyan][[4]][/bold cyan] Rename new file")
        self.console.print("  [bold cyan][[0]][/bold cyan] Cancel")
        self.console.print()

        choice = Prompt.ask("[cyan]Select (0/1/2/3/4)[/cyan]", default="2").strip()

        if choice == "0":
            return None
        elif choice == "1":
            return path
        elif choice == "2":
            return None
        elif choice == "3":
            prefix = Prompt.ask("[cyan]Prefix[/cyan]", default="new_")
            new_name = f"{prefix}{path.name}"
            return path.parent / new_name
        elif choice == "4":
            new_name = Prompt.ask("[cyan]New filename[/cyan]", default=path.name)
            new_path = path.parent / new_name
            if new_path.suffix not in (f".{fmt}",):
                new_path = new_path.with_suffix(f".{fmt}")
            return self._handle_file_collision(new_path, fmt)
        return None

    # ── Load script ──────────────────────────────────────────────────────

    def _load_script(self) -> None:
        self.console.print(Rule("[bold cyan]Load Script[/bold cyan]", style="cyan"))
        self.console.print()

        path_str = Prompt.ask("[cyan]Path to .sclpll or .json file[/cyan]")
        path = Path(path_str)

        if not path.exists():
            self.console.print(
                f"[red]File not found:[/red] {path}\n"
                "[dim]Tip: Check the path and try again. Use tab-completion if available.[/dim]"
            )
            return

        try:
            source = path.read_text(encoding="utf-8")
        except OSError as e:
            self.console.print(
                f"[red]Cannot read file:[/red] {e}\n"
                "[dim]Tip: Check that you have read permissions for this file.[/dim]"
            )
            return

        self.console.print()
        self.console.print(Panel(
            source,
            title=f"[bold]{path.name}[/bold]",
            border_style="cyan",
            box=box.ROUNDED,
        ))
        self.console.print()

        action = Prompt.ask(
            "[cyan]Action (run/validate/back)[/cyan]",
            default="validate",
        ).strip().lower()

        if action == "run":
            self._execute_workflow_file(path)
        elif action == "validate":
            self._validate_sclpll_source(source, str(path))

    # ── Collections browser ──────────────────────────────────────────────

    def _collections_browser(self) -> None:
        self.console.print(Rule("[bold cyan]Collections[/bold cyan]", style="cyan"))
        self.console.print()

        try:
            asyncio.run(self._collections_menu())
        except Exception as e:
            self.console.print(f"[red]Collections error: {e}[/red]")

    async def _collections_menu(self) -> None:
        from app.ui.app import App

        async with App(self.db_path) as application:
            cols = await application.collections.list_all()

            if not cols:
                self.console.print("[dim]No collections yet[/dim]")
                self.console.print("[dim]Create collections via CLI: python -m app collections create <name>[/dim]")
                return

            table = Table(
                title="Collections",
                box=box.ROUNDED,
                border_style="cyan",
                header_style="bold cyan",
            )
            table.add_column("#", width=4, justify="right", style="dim")
            table.add_column("Name", min_width=20)
            table.add_column("Requests", width=10, justify="right")
            table.add_column("ID", width=10, style="dim")

            for i, col in enumerate(cols, 1):
                reqs = await application.requests.list_all(collection_id=col["id"])
                table.add_row(str(i), col["name"], str(len(reqs)), col["id"][:8])

            self.console.print(table)
            self.console.print()

            idx_str = Prompt.ask(
                "[cyan]View collection (number, or Enter to go back)[/cyan]",
                default="",
            )
            if not idx_str:
                return
            try:
                idx = int(idx_str) - 1
            except ValueError:
                self.console.print("[red]Invalid selection. Enter a number.[/red]")
                return

            if idx < 0 or idx >= len(cols):
                self.console.print(f"[red]Invalid selection. Choose 1-{len(cols)}.[/red]")
                return

            col = cols[idx]
            reqs = await application.requests.list_all(collection_id=col["id"])

            if not reqs:
                self.console.print(f"[dim]No requests in '{col['name']}'[/dim]")
                return

            self.console.print()
            req_table = Table(
                title=f"Requests in {col['name']}",
                box=box.ROUNDED,
                border_style="cyan",
                header_style="bold cyan",
            )
            req_table.add_column("#", width=4, justify="right", style="dim")
            req_table.add_column("Name", min_width=25)
            req_table.add_column("Method", width=8, justify="center")
            req_table.add_column("URL", min_width=40)

            for i, req in enumerate(reqs, 1):
                method = req.get("method", "GET")
                method_color = {"GET": "green", "POST": "yellow", "PUT": "blue", "DELETE": "red"}.get(method, "white")
                req_table.add_row(
                    str(i),
                    req.get("name", "Untitled"),
                    f"[{method_color}]{method}[/{method_color}]",
                    req.get("url", "")[:60],
                )

            self.console.print(req_table)

    # ── Send request ────────────────────────────────────────────────────

    def _send_request(self) -> None:
        self.console.print(Rule("[bold cyan]Send Request[/bold cyan]", style="cyan"))
        self.console.print()

        method = Prompt.ask(
            "[cyan]Method (GET/POST/PUT/PATCH/DELETE)[/cyan]",
            default="GET",
        ).strip().upper()
        url = Prompt.ask("[cyan]URL[/cyan]")
        if not url:
            self.console.print("[yellow]No URL provided[/yellow]")
            return

        # Optional headers
        headers: dict[str, str] = {}
        self.console.print("[dim]Add headers (empty key to stop):[/dim]")
        while True:
            key = Prompt.ask("[cyan]Header name[/cyan]", default="")
            if not key:
                break
            value = Prompt.ask(f"[cyan]{key}[/cyan]", default="")
            headers[key] = value

        # Optional body
        body = ""
        if method in ("POST", "PUT", "PATCH"):
            body = Prompt.ask("[cyan]Body (JSON)[/cyan]", default="")

        self.console.print()
        self.console.print(f"[dim]{method} {url}[/dim]")
        if headers:
            for k, v in headers.items():
                self.console.print(f"[dim]  {k}: {v}[/dim]")
        self.console.print()

        # Execute
        self.console.print("[dim]Sending...[/dim]")
        try:
            asyncio.run(self._execute_single_request(method, url, headers, body))
        except Exception as e:
            self.console.print(f"[red]Request failed: {e}[/red]")

    async def _execute_single_request(self, method: str, url: str, headers: dict, body: str) -> None:
        import httpx

        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            start = time.monotonic()
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers if headers else None,
                    content=body if body else None,
                )
                elapsed = int((time.monotonic() - start) * 1000)

                # Status
                status_color = "green" if 200 <= response.status_code < 300 else "red"
                self.console.print()
                self.console.print(Panel(
                    f"[{status_color}]{response.status_code}[/{status_color}]  {elapsed}ms  {len(response.content)} bytes",
                    title="[bold]Response[/bold]",
                    border_style="cyan",
                    box=box.ROUNDED,
                ))

                # Response headers
                headers_table = Table(box=box.SIMPLE, show_header=False)
                headers_table.add_column("Key", style="dim", min_width=20)
                headers_table.add_column("Value")
                for k, v in response.headers.items():
                    headers_table.add_row(k, v)
                self.console.print(Panel(headers_table, title="Headers", border_style="dim"))

                # Body
                try:
                    body_json = response.json()
                    body_str = json.dumps(body_json, indent=2, default=str)[:3000]
                except Exception:
                    body_str = response.text[:3000]

                self.console.print(Panel(body_str, title="Body", border_style="cyan", box=box.ROUNDED))

            except httpx.TimeoutException:
                self.console.print("[red]Request timed out (30s)[/red]")
            except httpx.ConnectError:
                self.console.print(f"[red]Connection failed: {url}[/red]")
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")

    # ── Plugin browser ──────────────────────────────────────────────────

    def _plugin_browser(self) -> None:
        self.console.print(Rule("[bold cyan]Plugins[/bold cyan]", style="cyan"))
        self.console.print()

        from app.core.engine.plugin_registry import FilesystemPluginRegistry

        registry = FilesystemPluginRegistry("plugins")
        plugins = registry.list_plugins()

        if not plugins:
            self.console.print("[dim]No plugins found in plugins/ directory[/dim]")
            return

        while True:
            table = Table(
                title="Installed Plugins",
                box=box.ROUNDED,
                border_style="cyan",
                header_style="bold cyan",
            )
            table.add_column("#", width=4, justify="right", style="dim")
            table.add_column("Name", min_width=20)
            table.add_column("Version", width=10)
            table.add_column("Description", min_width=30)
            table.add_column("Functions", width=10, justify="right")
            table.add_column("Status", width=10, justify="center")

            for i, p in enumerate(plugins, 1):
                name = p.manifest.name
                version = p.manifest.version
                desc = p.manifest.description[:40] if p.manifest.description else ""
                func_count = len(p.functions)
                status = p.status.value if hasattr(p.status, 'value') else str(p.status)
                status_color = {
                    "active": "green",
                    "loaded": "yellow",
                    "discovered": "dim",
                    "error": "red",
                }.get(status, "white")
                table.add_row(
                    str(i), name, version, desc, str(func_count),
                    f"[{status_color}]{status}[/{status_color}]"
                )

            self.console.print(table)
            self.console.print()
            self.console.print("  [dim][[0]] Back to main menu[/dim]")
            self.console.print()

            idx_str = Prompt.ask("[cyan]Select plugin (number)[/cyan]", default="0").strip()
            if not idx_str or idx_str == "0":
                return
            try:
                idx = int(idx_str) - 1
            except ValueError:
                self.console.print("[red]Invalid selection. Enter a number.[/red]")
                continue
            if idx < 0 or idx >= len(plugins):
                self.console.print(f"[red]Invalid selection. Choose 1-{len(plugins)}.[/red]")
                continue

            self._show_plugin_detail(plugins[idx])
            self.console.print()
            Prompt.ask("[dim]Press Enter to go back to plugin list[/dim]", default="")

    def _show_plugin_detail(self, plugin: Any) -> None:
        m = plugin.manifest
        self.console.print()

        info_table = Table(box=box.SIMPLE, show_header=False)
        info_table.add_column("Key", style="bold cyan", min_width=14)
        info_table.add_column("Value")
        info_table.add_row("Name", m.name)
        info_table.add_row("Version", m.version)
        info_table.add_row("Description", m.description or "[dim]none[/dim]")
        info_table.add_row("Author", m.author or "[dim]none[/dim]")
        info_table.add_row("Category", m.category or "[dim]none[/dim]")
        info_table.add_row("Path", m.path or "[dim]none[/dim]")
        status = plugin.status.value if hasattr(plugin.status, 'value') else str(plugin.status)
        info_table.add_row("Status", status)
        info_table.add_row("Functions", str(len(plugin.functions)))
        info_table.add_row("Workflows", str(len(plugin.workflows)))

        if plugin.error:
            info_table.add_row("Error", f"[red]{plugin.error}[/red]")

        self.console.print(Panel(
            info_table,
            title=f"[bold cyan]Plugin: {m.name}[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
        ))

        if plugin.functions:
            func_table = Table(
                title="Functions",
                box=box.ROUNDED,
                border_style="cyan",
                header_style="bold cyan",
            )
            func_table.add_column("#", width=4, justify="right", style="dim")
            func_table.add_column("Name", min_width=20)
            func_table.add_column("Type", width=10)
            func_table.add_column("Version", width=10)

            for i, f in enumerate(plugin.functions, 1):
                func_table.add_row(
                    str(i),
                    f.get("name", "?"),
                    f.get("type", "?"),
                    f.get("version", "?"),
                )
            self.console.print(func_table)

        if m.hooks:
            self.console.print()
            self.console.print("[bold]Hooks:[/bold]")
            for hook_type, hook_path in m.hooks.items():
                self.console.print(f"  {hook_type}: [dim]{hook_path}[/dim]")

        if m.variables:
            self.console.print()
            self.console.print("[bold]Variables:[/bold]")
            for key, value in m.variables.items():
                self.console.print(f"  {key} = [dim]{value}[/dim]")

    # ── Function browser ─────────────────────────────────────────────────

    def _function_browser(self) -> None:
        self.console.print(Rule("[bold cyan]Function Browser[/bold cyan]", style="cyan"))
        self.console.print()

        from app.core.engine.function_runner import FilesystemFunctionRunner

        func_dir = Prompt.ask("[cyan]Functions directory[/cyan]", default="functions")
        runner = FilesystemFunctionRunner(func_dir)
        funcs = runner.discover()

        if not funcs:
            self.console.print("[yellow]No functions discovered[/yellow]")
            self.console.print(f"[dim]Searched in: {Path(func_dir).resolve()}[/dim]")
            self.console.print(
                "[dim]Tip: Create a Python file in the functions/ directory with a docstring "
                "containing @name, @type, and @version metadata, and a run(ctx) function.[/dim]"
            )
            return

        while True:
            search = Prompt.ask("[cyan]Filter by name (or Enter for all)[/cyan]", default="")
            filtered = funcs
            if search.strip():
                search_lower = search.strip().lower()
                filtered = [f for f in funcs if search_lower in f.get("name", "").lower()]

            if not filtered:
                self.console.print(f"[dim]No functions matching '{search}'[/dim]")
                continue

            table = Table(
                title=f"Functions ({len(filtered)} of {len(funcs)})",
                box=box.ROUNDED,
                border_style="cyan",
                show_lines=True,
                header_style="bold cyan",
            )
            table.add_column("#", width=4, justify="right", style="dim")
            table.add_column("Name", min_width=20)
            table.add_column("Type", width=10, justify="center")
            table.add_column("Version", width=8, justify="center")
            table.add_column("Path", min_width=30, style="dim")

            for i, f in enumerate(filtered, 1):
                type_color = {
                    "engine": "yellow",
                    "transformer": "magenta",
                    "exporter": "green",
                    "validator": "red",
                }.get(f.get("type", ""), "white")

                table.add_row(
                    str(i),
                    f.get("name", "?"),
                    f"[{type_color}]{f.get('type', '?')}[/{type_color}]",
                    f.get("version", "?"),
                    f.get("path", "?"),
                )

            self.console.print(table)
            self.console.print()
            self.console.print("  [dim][[0]] Back to main menu[/dim]")
            self.console.print()

            idx_str = Prompt.ask(
                "[cyan]Select function (number)[/cyan]",
                default="0",
            )
            if not idx_str or idx_str == "0":
                return
            try:
                idx = int(idx_str) - 1
            except ValueError:
                self.console.print("[red]Invalid selection. Enter a number.[/red]")
                continue
            if idx < 0 or idx >= len(filtered):
                self.console.print(f"[red]Invalid selection. Choose 1-{len(filtered)}.[/red]")
                continue

            self._show_function_detail(filtered[idx])
            self.console.print()
            Prompt.ask("[dim]Press Enter to go back to function list[/dim]", default="")

    def _show_function_detail(self, func_meta: dict[str, str]) -> None:
        path = Path(func_meta.get("path", ""))
        if not path.exists():
            self.console.print(
                "[red]Function file not found[/red]\n"
                f"[dim]Expected at: {path}[/dim]\n"
                "[dim]Tip: The function may have been moved or deleted since discovery.[/dim]"
            )
            return

        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            self.console.print(
                "[red]Cannot read function file[/red]\n"
                f"[dim]Path: {path}[/dim]\n"
                "[dim]Tip: Check file permissions.[/dim]"
            )
            return

        self.console.print()
        detail_table = Table(box=box.SIMPLE, show_header=False)
        detail_table.add_column("Key", style="bold cyan", min_width=12)
        detail_table.add_column("Value")

        for key, value in func_meta.items():
            if key != "path":
                detail_table.add_row(key.capitalize(), value)
        detail_table.add_row("File", str(path))

        self.console.print(Panel(
            Group(
                detail_table,
                "",
                Panel(
                    source,
                    title="[bold]Source[/bold]",
                    border_style="dim",
                    box=box.ROUNDED,
                ),
            ),
            title=f"[bold cyan]{func_meta.get('name', 'Function')}[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2),
        ))

    # ── History viewer ───────────────────────────────────────────────────

    def _history_viewer(self) -> None:
        self.console.print(Rule("[bold cyan]History Viewer[/bold cyan]", style="cyan"))
        self.console.print()

        limit_str = Prompt.ask("[cyan]Number of entries[/cyan]", default="20")
        try:
            limit = int(limit_str)
            if limit <= 0:
                self.console.print("[yellow]Using default: 20[/yellow]")
                limit = 20
        except ValueError:
            self.console.print("[red]Invalid number. Using default: 20[/red]")
            limit = 20

        search = Prompt.ask("[cyan]Filter (method/url/status, or Enter for all)[/cyan]", default="")

        try:
            asyncio.run(self._show_history_async(limit, search.strip()))
        except Exception as e:
            self.console.print(f"[red]Failed to load history: {e}[/red]")

    async def _show_history_async(self, limit: int, search: str = "") -> None:
        from app.ui.app import App

        async with App(self.db_path) as application:
            entries = await application.history.list_recent(limit)

            if not entries:
                self.console.print("[dim]No history entries[/dim]")
                return

            # Apply filter
            if search:
                search_lower = search.lower()
                filtered = []
                for e in entries:
                    if (search_lower in (e.get("method", "") or "").lower()
                        or search_lower in (e.get("url", "") or "").lower()
                        or search_lower in str(e.get("status_code", "")).lower()
                        or search_lower in (e.get("status", "") or "").lower()):
                        filtered.append(e)
                entries = filtered
                if not entries:
                    self.console.print(f"[dim]No entries matching '{search}'[/dim]")
                    return

            table = Table(
                title="Request History",
                box=box.ROUNDED,
                border_style="cyan",
                header_style="bold cyan",
                show_lines=True,
            )
            table.add_column("#", width=4, justify="right", style="dim")
            table.add_column("ID", width=10, style="dim")
            table.add_column("Time", width=20)
            table.add_column("Method", width=8, justify="center")
            table.add_column("URL", min_width=30)
            table.add_column("Status", width=8, justify="center")
            table.add_column("Duration", width=10, justify="right")

            for i, entry in enumerate(entries, 1):
                status_color = "green" if entry["status"] == "success" else "red"
                method_color = {
                    "GET": "green",
                    "POST": "yellow",
                    "PUT": "blue",
                    "PATCH": "magenta",
                    "DELETE": "red",
                }.get(entry.get("method", ""), "white")

                url = entry.get("url", "") or ""
                url_display = url[:60] + ("..." if len(url) > 60 else "")

                table.add_row(
                    str(i),
                    entry["id"][:8],
                    entry["created_at"][:19] if entry.get("created_at") else "",
                    f"[{method_color}]{entry.get('method', '?')}[/{method_color}]",
                    url_display,
                    f"[{status_color}]{entry.get('status_code', 'ERR')}[/{status_color}]",
                    f"{entry.get('duration_ms', 0)}ms",
                )

            self.console.print(table)
            self.console.print()

            # Detail view and actions
            self.console.print("  [dim][[C]] Clear all history[/dim]")
            self.console.print()
            idx_str = Prompt.ask(
                "[cyan]Inspect entry (number), C=clear, or Enter to go back[/cyan]",
                default="",
            )
            if idx_str.lower() == "c":
                if Confirm.ask("[yellow]Clear all history? This cannot be undone.[/yellow]", default=False):
                    await application.history.clear()
                    self.console.print("[green]History cleared[/green]")
            elif idx_str:
                try:
                    idx = int(idx_str) - 1
                    if 0 <= idx < len(entries):
                        self._show_history_detail(entries[idx])
                    else:
                        self.console.print(f"[red]Invalid selection. Choose 1-{len(entries)}.[/red]")
                except ValueError:
                    self.console.print("[red]Invalid selection. Enter a number or C.[/red]")

    def _show_history_detail(self, entry: dict[str, Any]) -> None:
        self.console.print()
        detail = Table(box=box.SIMPLE, show_header=False)
        detail.add_column("Key", style="bold cyan", min_width=16)
        detail.add_column("Value")

        detail.add_row("ID", entry.get("id", ""))
        detail.add_row("Time", entry.get("created_at", ""))
        detail.add_row("Method", entry.get("method", ""))
        detail.add_row("URL", entry.get("url", ""))

        status_color = "green" if entry["status"] == "success" else "red"
        sc = entry.get("status_code", "N/A")
        st = entry["status"]
        detail.add_row(
            "Status",
            f"[{status_color}]{sc} ({st})[/{status_color}]",
        )
        detail.add_row("Duration", f"{entry.get('duration_ms', 0)}ms")

        if entry.get("error_message"):
            detail.add_row("Error", f"[red]{entry['error_message']}[/red]")

        body_content = ""
        if entry.get("response_body"):
            try:
                parsed = json.loads(entry["response_body"])
                body_content = json.dumps(parsed, indent=2)[:2000]
            except (json.JSONDecodeError, TypeError):
                body_content = entry["response_body"][:2000]

        self.console.print(Panel(
            Group(
                detail,
                "",
                Panel(
                    body_content or "[dim]No response body[/dim]",
                    title="[bold]Response Body[/bold]",
                    border_style="dim",
                ) if body_content else Text(""),
            ),
            title="[bold cyan]History Entry Detail[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2),
        ))

    # ── Environment manager ──────────────────────────────────────────────

    def _environment_manager(self) -> None:
        self.console.print(Rule("[bold cyan]Environment Manager[/bold cyan]", style="cyan"))
        self.console.print()

        try:
            asyncio.run(self._environment_menu())
        except Exception as e:
            self.console.print(f"[red]Environment manager error: {e}[/red]")

    async def _environment_menu(self) -> None:
        from app.ui.app import App

        while True:
            self.console.print()
            self.console.print("  [bold cyan][[1]][/bold cyan] List environments")
            self.console.print("  [bold cyan][[2]][/bold cyan] Create environment")
            self.console.print("  [bold cyan][[3]][/bold cyan] View variables")
            self.console.print("  [bold cyan][[4]][/bold cyan] Activate environment")
            self.console.print("  [bold cyan][[5]][/bold cyan] Set variable")
            self.console.print("  [bold cyan][[6]][/bold cyan] Delete variable")
            self.console.print("  [bold cyan][[7]][/bold cyan] Delete environment")
            self.console.print("  [bold cyan][[0]][/bold cyan] Back")
            self.console.print()

            choice = Prompt.ask(
                "[cyan]Select (0-7)[/cyan]",
                default="0",
            ).strip()

            if choice == "0":
                break

            async with App(self.db_path) as application:
                if choice == "1":
                    await self._list_environments(application)
                elif choice == "2":
                    await self._create_environment(application)
                elif choice == "3":
                    await self._view_env_variables(application)
                elif choice == "4":
                    await self._activate_environment(application)
                elif choice == "5":
                    await self._set_env_variable(application)
                elif choice == "6":
                    await self._delete_env_variable(application)
                elif choice == "7":
                    await self._delete_environment(application)

    async def _list_environments(self, application: Any) -> None:
        envs = await application.environments.list_all()

        if not envs:
            self.console.print("[dim]No environments configured[/dim]")
            return

        table = Table(
            title="Environments",
            box=box.ROUNDED,
            border_style="cyan",
            header_style="bold cyan",
        )
        table.add_column("#", width=4, justify="right", style="dim")
        table.add_column("Name", min_width=20)
        table.add_column("Active", width=8, justify="center")
        table.add_column("Variables", width=10, justify="right")
        table.add_column("ID", width=10, style="dim")

        for i, e in enumerate(envs, 1):
            active = "[green]yes[/green]" if e["is_active"] else "no"
            var_count = len(e.get("variables", []))
            table.add_row(str(i), e["name"], active, str(var_count), e["id"][:8])

        self.console.print(table)

    async def _create_environment(self, application: Any) -> None:
        name = Prompt.ask("[cyan]Environment name[/cyan]")
        if not name:
            return
        env = await application.environments.create(name)
        self.console.print(f"[green]Created environment '{name}' ({env['id'][:8]})[/green]")

    async def _view_env_variables(self, application: Any) -> None:
        envs = await application.environments.list_all()
        if not envs:
            self.console.print("[dim]No environments[/dim]")
            return

        for i, e in enumerate(envs, 1):
            self.console.print(f"  [cyan][[{i}]][/cyan] {e['name']}")
        self.console.print()

        idx_str = Prompt.ask("[cyan]Select environment[/cyan]", default="1")
        try:
            idx = int(idx_str) - 1
        except ValueError:
            self.console.print("[red]Invalid selection[/red]")
            return

        if idx < 0 or idx >= len(envs):
            self.console.print("[red]Invalid selection[/red]")
            return

        env = envs[idx]
        variables = env.get("variables", [])

        if not variables:
            self.console.print(f"[dim]No variables in '{env['name']}'[/dim]")
            return

        table = Table(
            title=f"Variables in {env['name']}",
            box=box.ROUNDED,
            border_style="cyan",
            header_style="bold cyan",
        )
        table.add_column("Key", min_width=20)
        table.add_column("Value", min_width=20)
        table.add_column("Secret", width=8, justify="center")

        for v in variables:
            val = "****" if v.get("is_secret") else v["value"]
            secret = "[yellow]yes[/yellow]" if v.get("is_secret") else "no"
            table.add_row(v["key"], val, secret)

        self.console.print(table)

    async def _activate_environment(self, application: Any) -> None:
        envs = await application.environments.list_all()
        if not envs:
            self.console.print("[dim]No environments[/dim]")
            return

        for i, e in enumerate(envs, 1):
            active_marker = " [green](active)[/green]" if e["is_active"] else ""
            self.console.print(f"  [cyan][[{i}]][/cyan] {e['name']}{active_marker}")
        self.console.print()

        idx_str = Prompt.ask("[cyan]Select environment to activate[/cyan]", default="1")
        try:
            idx = int(idx_str) - 1
        except ValueError:
            self.console.print("[red]Invalid selection[/red]")
            return

        if idx < 0 or idx >= len(envs):
            self.console.print("[red]Invalid selection[/red]")
            return

        env = envs[idx]
        if env["is_active"]:
            self.console.print(f"[dim]'{env['name']}' is already active.[/dim]")
            return

        if not Confirm.ask(f"[cyan]Activate '{env['name']}'?[/cyan]", default=True):
            return

        await application.environments.set_active(env["id"])
        self._current_env = env["name"]
        self.console.print(f"[green]Activated environment '{env['name']}'[/green]")

    async def _set_env_variable(self, application: Any) -> None:
        envs = await application.environments.list_all()
        if not envs:
            self.console.print("[dim]No environments[/dim]")
            return

        for i, e in enumerate(envs, 1):
            self.console.print(f"  [cyan][[{i}]][/cyan] {e['name']}")
        self.console.print()

        idx_str = Prompt.ask("[cyan]Select environment[/cyan]", default="1")
        try:
            idx = int(idx_str) - 1
        except ValueError:
            self.console.print("[red]Invalid selection[/red]")
            return

        if idx < 0 or idx >= len(envs):
            self.console.print("[red]Invalid selection[/red]")
            return

        env = envs[idx]
        key = Prompt.ask("[cyan]Variable name[/cyan]")
        if not key:
            return
        value = Prompt.ask(f"[cyan]{key} =[/cyan]")

        await application.environments.set_variable(env["id"], key, value)
        self.console.print(f"[green]Set {key} in '{env['name']}'[/green]")

    async def _delete_env_variable(self, application: Any) -> None:
        envs = await application.environments.list_all()
        if not envs:
            self.console.print("[dim]No environments[/dim]")
            return

        for i, e in enumerate(envs, 1):
            self.console.print(f"  [cyan][[{i}]][/cyan] {e['name']}")
        self.console.print()

        idx_str = Prompt.ask("[cyan]Select environment[/cyan]", default="1")
        try:
            idx = int(idx_str) - 1
        except ValueError:
            self.console.print("[red]Invalid selection[/red]")
            return

        if idx < 0 or idx >= len(envs):
            self.console.print("[red]Invalid selection[/red]")
            return

        env = envs[idx]
        variables = env.get("variables", [])
        if not variables:
            self.console.print(f"[dim]No variables in '{env['name']}'[/dim]")
            return

        for i, v in enumerate(variables, 1):
            self.console.print(f"  [cyan][[{i}]][/cyan] {v['key']} = {v['value'][:30]}")
        self.console.print()

        var_idx_str = Prompt.ask("[cyan]Select variable to delete[/cyan]", default="")
        if not var_idx_str:
            return
        try:
            var_idx = int(var_idx_str) - 1
        except ValueError:
            self.console.print("[red]Invalid selection[/red]")
            return

        if var_idx < 0 or var_idx >= len(variables):
            self.console.print("[red]Invalid selection[/red]")
            return

        var = variables[var_idx]
        if Confirm.ask(f"[yellow]Delete '{var['key']}' from '{env['name']}'?[/yellow]", default=False):
            await application.environments.delete_variable(env["id"], var["key"])
            self.console.print(f"[green]Deleted {var['key']}[/green]")

    async def _delete_environment(self, application: Any) -> None:
        envs = await application.environments.list_all()
        if not envs:
            self.console.print("[dim]No environments[/dim]")
            return

        for i, e in enumerate(envs, 1):
            active_marker = " [green](active)[/green]" if e["is_active"] else ""
            self.console.print(f"  [cyan][[{i}]][/cyan] {e['name']}{active_marker}")
        self.console.print()

        idx_str = Prompt.ask("[cyan]Select environment to delete[/cyan]", default="")
        if not idx_str:
            return
        try:
            idx = int(idx_str) - 1
        except ValueError:
            self.console.print("[red]Invalid selection[/red]")
            return

        if idx < 0 or idx >= len(envs):
            self.console.print("[red]Invalid selection[/red]")
            return

        env = envs[idx]
        if Confirm.ask(f"[yellow]Delete environment '{env['name']}'? This cannot be undone.[/yellow]", default=False):
            await application.environments.delete(env["id"])
            if self._current_env == env["name"]:
                self._current_env = "none"
            self.console.print(f"[green]Deleted environment '{env['name']}'[/green]")

    # ── Import / Export ─────────────────────────────────────────────────

    def _import_export_menu(self) -> None:
        self.console.print(Rule("[bold cyan]Import / Export[/bold cyan]", style="cyan"))
        self.console.print()

        while True:
            self.console.print("  [bold cyan][[1]][/bold cyan] Export all (full workspace backup)")
            self.console.print("  [bold cyan][[2]][/bold cyan] Import all (from backup)")
            self.console.print("  [bold cyan][[3]][/bold cyan] Export collections")
            self.console.print("  [bold cyan][[4]][/bold cyan] Import collections")
            self.console.print("  [bold cyan][[5]][/bold cyan] Export environments")
            self.console.print("  [bold cyan][[6]][/bold cyan] Import environments")
            self.console.print("  [bold cyan][[7]][/bold cyan] Import OpenAPI/Swagger spec")
            self.console.print("  [bold cyan][[0]][/bold cyan] Back")
            self.console.print()

            choice = Prompt.ask("[cyan]Select (0-7)[/cyan]", default="0").strip()

            if choice == "0":
                break
            elif choice == "1":
                self._export_all()
            elif choice == "2":
                self._import_all()
            elif choice == "3":
                self._export_collections()
            elif choice == "4":
                self._import_collections()
            elif choice == "5":
                self._export_environments()
            elif choice == "6":
                self._import_environments()
            elif choice == "7":
                self._import_openapi()
            else:
                self.console.print("[red]Invalid choice[/red]")

    def _export_all(self) -> None:
        output_dir = Prompt.ask("[cyan]Export directory[/cyan]", default="data/export_backup")
        if not output_dir:
            return
        self.console.print("[dim]Exporting workspace...[/dim]")
        try:
            asyncio.run(self._do_export_all(output_dir))
        except Exception as e:
            self.console.print(f"[red]Export failed: {e}[/red]")

    async def _do_export_all(self, output_dir: str) -> None:
        from app.services.full_export_service import FullExportService
        from app.ui.app import App

        async with App(self.db_path) as application:
            svc = FullExportService(application)
            path = await svc.export_all(output_dir)
            self.console.print(f"[green]Workspace exported to {path}[/green]")

    def _import_all(self) -> None:
        import_dir = Prompt.ask("[cyan]Import directory[/cyan]", default="data/export_backup")
        if not import_dir:
            return
        path = Path(import_dir)
        if not path.exists():
            self.console.print(f"[red]Directory not found: {import_dir}[/red]")
            return
        self.console.print("[dim]Importing workspace...[/dim]")
        try:
            asyncio.run(self._do_import_all(import_dir))
        except Exception as e:
            self.console.print(f"[red]Import failed: {e}[/red]")

    async def _do_import_all(self, import_dir: str) -> None:
        from app.services.full_import_service import FullImportService
        from app.ui.app import App

        async with App(self.db_path) as application:
            svc = FullImportService(application)
            result = await svc.import_all(import_dir)
            self.console.print("[green]Import complete:[/green]")
            for key, count in result.items():
                self.console.print(f"  {key}: {count}")

    def _export_collections(self) -> None:
        output_file = Prompt.ask("[cyan]Output file[/cyan]", default="data/collections_export.json")
        if not output_file:
            return
        self.console.print("[dim]Exporting collections...[/dim]")
        try:
            asyncio.run(self._do_export_collections(output_file))
        except Exception as e:
            self.console.print(f"[red]Export failed: {e}[/red]")

    async def _do_export_collections(self, output_file: str) -> None:
        from app.ui.app import App

        async with App(self.db_path) as application:
            cols = await application.collections.list_all()
            data = []
            for col in cols:
                reqs = await application.requests.list_all(collection_id=col["id"])
                data.append({"collection": col, "requests": reqs})

            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            self.console.print(f"[green]Exported {len(data)} collections to {output_file}[/green]")

    def _import_collections(self) -> None:
        input_file = Prompt.ask("[cyan]Import file[/cyan]", default="data/collections_export.json")
        if not input_file:
            return
        path = Path(input_file)
        if not path.exists():
            self.console.print(f"[red]File not found: {input_file}[/red]")
            return
        self.console.print("[dim]Importing collections...[/dim]")
        try:
            asyncio.run(self._do_import_collections(input_file))
        except Exception as e:
            self.console.print(f"[red]Import failed: {e}[/red]")

    async def _do_import_collections(self, input_file: str) -> None:
        from app.ui.app import App

        with open(input_file, encoding="utf-8") as f:
            data = json.load(f)

        async with App(self.db_path) as application:
            count = 0
            for item in data:
                col = item.get("collection", {})
                reqs = item.get("requests", [])
                name = col.get("name", "Imported Collection")
                desc = col.get("description", "")

                new_col = await application.collections.create(name, desc)
                for req in reqs:
                    await application.requests.create({
                        "collection_id": new_col["id"],
                        "name": req.get("name", "Untitled"),
                        "method": req.get("method", "GET"),
                        "url": req.get("url", ""),
                        "headers": req.get("headers", []),
                        "body": req.get("body"),
                        "body_type": req.get("body_type"),
                        "auth_type": req.get("auth_type"),
                        "auth_config": req.get("auth_config", {}),
                    })
                count += 1

            self.console.print(f"[green]Imported {count} collections[/green]")

    def _export_environments(self) -> None:
        output_file = Prompt.ask("[cyan]Output file[/cyan]", default="data/environments_export.json")
        if not output_file:
            return
        self.console.print("[dim]Exporting environments...[/dim]")
        try:
            asyncio.run(self._do_export_environments(output_file))
        except Exception as e:
            self.console.print(f"[red]Export failed: {e}[/red]")

    async def _do_export_environments(self, output_file: str) -> None:
        from app.ui.app import App

        async with App(self.db_path) as application:
            envs = await application.environments.list_all()
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(envs, f, indent=2, default=str)
            self.console.print(f"[green]Exported {len(envs)} environments to {output_file}[/green]")

    def _import_environments(self) -> None:
        input_file = Prompt.ask("[cyan]Import file[/cyan]", default="data/environments_export.json")
        if not input_file:
            return
        path = Path(input_file)
        if not path.exists():
            self.console.print(f"[red]File not found: {input_file}[/red]")
            return
        self.console.print("[dim]Importing environments...[/dim]")
        try:
            asyncio.run(self._do_import_environments(input_file))
        except Exception as e:
            self.console.print(f"[red]Import failed: {e}[/red]")

    async def _do_import_environments(self, input_file: str) -> None:
        from app.ui.app import App

        with open(input_file, encoding="utf-8") as f:
            envs = json.load(f)

        async with App(self.db_path) as application:
            count = 0
            for env in envs:
                name = env.get("name", "Imported Environment")
                new_env = await application.environments.create(name)
                for var in env.get("variables", []):
                    await application.environments.set_variable(
                        new_env["id"],
                        var.get("key", ""),
                        var.get("value", ""),
                    )
                count += 1

            self.console.print(f"[green]Imported {count} environments[/green]")

    def _import_openapi(self) -> None:
        input_file = Prompt.ask("[cyan]OpenAPI/Swagger file (JSON)[/cyan]").strip()
        if not input_file:
            return
        path = Path(input_file)
        if not path.exists():
            self.console.print(f"[red]File not found: {input_file}[/red]")
            return

        try:
            with open(path, encoding="utf-8") as f:
                spec = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            self.console.print(f"[red]Invalid JSON: {e}[/red]")
            return

        paths = spec.get("paths", {})
        if not paths:
            self.console.print("[yellow]No paths found in spec[/yellow]")
            return

        base_url = ""
        if "servers" in spec and spec["servers"]:
            base_url = spec["servers"][0].get("url", "")
        elif "host" in spec:
            scheme = spec.get("schemes", ["https"])[0]
            base_url = f"{scheme}://{spec['host']}{spec.get('basePath', '')}"

        collection_name = spec.get("info", {}).get("title", "OpenAPI Import")
        requests = []
        for path_str, methods in paths.items():
            for method, details in methods.items():
                if method.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                    summary = details.get("summary", details.get("operationId", ""))
                    url = f"{base_url}{path_str}" if base_url else path_str
                    requests.append({
                        "name": f"{method.upper()} {path_str}" + (f" - {summary}" if summary else ""),
                        "method": method.upper(),
                        "url": url,
                    })

        if not requests:
            self.console.print("[yellow]No API operations found in spec[/yellow]")
            return

        self.console.print(f"\n[bold]Found {len(requests)} operations in '{collection_name}'[/bold]")
        self.console.print()
        for i, req in enumerate(requests[:20], 1):
            method_color = {"GET": "green", "POST": "yellow", "PUT": "blue", "DELETE": "red"}.get(req["method"], "white")
            self.console.print(f"  [{method_color}]{req['method']}[/{method_color}] {req['name']}")
        if len(requests) > 20:
            self.console.print(f"  [dim]... and {len(requests) - 20} more[/dim]")
        self.console.print()

        if not Confirm.ask(f"[cyan]Import as collection '{collection_name}'?[/cyan]", default=True):
            return

        try:
            asyncio.run(self._do_import_openapi(collection_name, requests))
        except Exception as e:
            self.console.print(f"[red]Import failed: {e}[/red]")

    async def _do_import_openapi(self, name: str, requests: list[dict]) -> None:
        from app.ui.app import App

        async with App(self.db_path) as application:
            col = await application.collections.create(name, "Imported from OpenAPI spec")
            for req in requests:
                await application.requests.create({
                    "collection_id": col["id"],
                    "name": req["name"],
                    "method": req["method"],
                    "url": req["url"],
                    "headers": [],
                })
            self.console.print(f"[green]Created collection '{name}' with {len(requests)} requests[/green]")

    # ── Script validator ─────────────────────────────────────────────────

    def _script_validator(self) -> None:
        self.console.print(Rule("[bold cyan]Script Validator[/bold cyan]", style="cyan"))
        self.console.print()

        path_str = Prompt.ask("[cyan]Path to .sclpll file[/cyan]")
        if not path_str:
            return

        path = Path(path_str)
        if not path.exists():
            self.console.print(
                f"[red]File not found:[/red] {path}\n"
                "[dim]Tip: Provide the full path or navigate to the directory first.[/dim]"
            )
            return

        try:
            source = path.read_text(encoding="utf-8")
        except OSError as e:
            self.console.print(
                f"[red]Cannot read file:[/red] {e}\n"
                "[dim]Tip: Check file permissions.[/dim]"
            )
            return

        self._validate_sclpll_source(source, str(path))

    def _validate_sclpll_source(self, source: str, filename: str) -> None:
        from app.core.engine.sclpll_compiler import SCLPLLCompiler, SCLPLLParseError

        compiler = SCLPLLCompiler()

        try:
            workflow = compiler.parse(source)
        except SCLPLLParseError as e:
            self.console.print()
            self.console.print(Panel(
                f"[red]{e}[/red]\n\n"
                "[dim]Common fixes:\n"
                "  - Check indentation (step body must be indented)\n"
                "  - Ensure @workflow directive is present\n"
                "  - Verify quoted strings have closing quotes\n"
                "  - Check step syntax: @step id <- deps -> output[/dim]",
                title="[bold red]Validation Failed[/bold red]",
                border_style="red",
                box=box.ROUNDED,
            ))
            return

        # Build validation report
        self.console.print()

        info_table = Table(box=box.SIMPLE, show_header=False)
        info_table.add_column("Key", style="bold cyan", min_width=16)
        info_table.add_column("Value")
        info_table.add_row("Workflow ID", workflow["id"])
        info_table.add_row("Name", workflow["name"])
        info_table.add_row("Description", workflow.get("description", "") or "[dim]none[/dim]")
        info_table.add_row("Steps", str(len(workflow["steps"])))
        info_table.add_row("Variables", str(len(workflow.get("variables", {}))))

        steps_table = Table(
            title="Steps",
            box=box.ROUNDED,
            border_style="cyan",
            header_style="bold cyan",
        )
        steps_table.add_column("#", width=4, justify="right", style="dim")
        steps_table.add_column("ID", min_width=15)
        steps_table.add_column("Type", width=10, justify="center")
        steps_table.add_column("Dependencies", min_width=15)
        steps_table.add_column("Output Var", width=15)

        for i, step in enumerate(workflow["steps"], 1):
            deps = step.get("depends_on", [])
            dep_str = ", ".join(deps) if deps else "[dim]-[/dim]"
            out = step.get("output_variable", "")
            out_str = out or "[dim]-[/dim]"

            type_color = {
                "request": "yellow",
                "function": "magenta",
                "delay": "dim",
            }.get(step.get("type", ""), "white")

            steps_table.add_row(
                str(i),
                step["id"],
                f"[{type_color}]{step.get('type', '?')}[/{type_color}]",
                dep_str,
                out_str,
            )

        # Check for parallel groups
        has_parallel = len(workflow["steps"]) > 1
        step_ids = {s["id"] for s in workflow["steps"]}
        for s in workflow["steps"]:
            deps = set(s.get("depends_on", []))
            if deps and deps != step_ids:
                has_parallel = True
                break

        parallel_info = "[green]yes[/green]" if has_parallel else "[dim]no[/dim]"

        self.console.print(Panel(
            Group(
                info_table,
                "",
                steps_table,
                "",
                Text.from_markup(f"  Parallel execution: {parallel_info}"),
            ),
            title=f"[bold green]Valid: {filename}[/bold green]",
            subtitle=f"[dim]{len(workflow['steps'])} steps[/dim]",
            border_style="green",
            box=box.ROUNDED,
            padding=(1, 2),
        ))

    # ── Goodbye ──────────────────────────────────────────────────────────

    def _goodbye(self) -> None:
        self.console.print()
        self.console.print(Align.center("[bold cyan]Goodbye from SCLPLAPI[/bold cyan]"))
        self.console.print(Align.center("[dim]Happy automating!  docs: https://github.com/sm408/sclpl-api[/dim]"))
        self.console.print()


# ─── Public API ──────────────────────────────────────────────────────────────


def launch_tui(db_path: str = "data/sclplapi.db") -> None:
    """Launch the SCLPLAPI Terminal User Interface."""
    tui = TUI(db_path)
    tui.run()
