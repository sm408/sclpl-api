"""SCLPLAPI Terminal User Interface.

Production-quality TUI built with Rich for the SCLPLAPI workflow studio.
Provides interactive menus, live workflow execution, function browsing,
history viewing, environment management, and script validation.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from app.ui.logo import LOGO, VERSION

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

    # ── Entry point ──────────────────────────────────────────────────────

    def run(self) -> None:
        """Launch the TUI main loop."""
        try:
            self._show_splash()
            self._main_menu()
        except KeyboardInterrupt:
            self._goodbye()

    # ── Splash screen ────────────────────────────────────────────────────

    def _show_splash(self) -> None:
        self.console.clear()
        self.console.print(LOGO)
        self.console.print()
        self.console.print(
            Align.center(f"[dim]{VERSION}[/dim]"),
        )
        self.console.print()

    # ── Main menu ────────────────────────────────────────────────────────

    def _main_menu(self) -> None:
        while self._running:
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
                choices=["r", "l", "f", "h", "e", "v", "q"],
                default="q",
                show_choices=False,
            ).lower()

            self.console.print()

            if choice == "r":
                self._workflow_runner()
            elif choice == "l":
                self._load_script()
            elif choice == "f":
                self._function_browser()
            elif choice == "h":
                self._history_viewer()
            elif choice == "e":
                self._environment_manager()
            elif choice == "v":
                self._script_validator()
            elif choice == "q":
                self._running = False

        self._goodbye()

    def _build_menu_content(self) -> Columns:
        items = [
            "[bold cyan][[R]][/bold cyan]  Run Workflow",
            "[bold cyan][[L]][/bold cyan]  Load Script (.sclpll)",
            "[bold cyan][[F]][/bold cyan]  Browse Functions",
            "[bold cyan][[H]][/bold cyan]  View History",
            "[bold cyan][[E]][/bold cyan]  Manage Environments",
            "[bold cyan][[V]][/bold cyan]  Validate Script",
            "[bold red][[Q]][/bold red]  Quit",
        ]
        return Columns(items, equal=True, expand=True)

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
            return
        if idx == 0 or idx > len(sclpll_files):
            return

        selected = sclpll_files[idx - 1]
        self.console.print(f"\n[bold]Loading:[/bold] {selected}")
        self._execute_workflow_file(selected)

    def _discover_sclpll_files(self) -> list[Path]:
        files: list[Path] = []
        for d in [Path("."), Path("examples"), Path("workflows")]:
            if d.exists():
                files.extend(sorted(d.rglob("*.sclpll")))
        return files[:20]

    def _execute_workflow_file(self, path: Path) -> None:
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as e:
            self.console.print(f"[red]Cannot read file: {e}[/red]")
            return

        # Parse the workflow
        if path.suffix == ".sclpll":
            from app.core.engine.sclpll_compiler import SCLPLLCompiler, SCLPLLParseError

            compiler = SCLPLLCompiler()
            try:
                workflow_dict = compiler.parse(source)
            except SCLPLLParseError as e:
                self.console.print(f"[red]Parse error: {e}[/red]")
                return
        elif path.suffix == ".json":
            try:
                workflow_dict = json.loads(source)
            except json.JSONDecodeError as e:
                self.console.print(f"[red]Invalid JSON: {e}[/red]")
                return
        else:
            self.console.print(f"[red]Unsupported file type: {path.suffix}[/red]")
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

        # Run with live display
        asyncio.run(self._run_workflow_live(workflow_dict, step_states))

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
    ) -> None:
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
                    is_parallel = current_group == 0 or any(
                        ss.group_index == current_group
                        for ss in step_states
                        if ss.group_index == current_group
                    )
                    if is_parallel:
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
                    detail = f"[red]{s.error[:50]}[/red]"
                elif s.status == "success" and s.output_summary:
                    detail = s.output_summary[:50]

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
                        await update_event.wait()
                        update_event.clear()
                        live.update(build_display())
                        if workflow_result:
                            break

                await asyncio.gather(run_engine(), refresh_loop())

        # Final summary
        self.console.print()
        if workflow_result:
            self._print_workflow_summary(workflow_result)
        self.console.print()

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

    # ── Load script ──────────────────────────────────────────────────────

    def _load_script(self) -> None:
        self.console.print(Rule("[bold cyan]Load Script[/bold cyan]", style="cyan"))
        self.console.print()

        path_str = Prompt.ask("[cyan]Path to .sclpll file[/cyan]")
        path = Path(path_str)

        if not path.exists():
            self.console.print(f"[red]File not found: {path}[/red]")
            return

        try:
            source = path.read_text(encoding="utf-8")
        except OSError as e:
            self.console.print(f"[red]Cannot read file: {e}[/red]")
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
            "[cyan]Action[/cyan]",
            choices=["run", "validate", "back"],
            default="validate",
        )

        if action == "run":
            self._execute_workflow_file(path)
        elif action == "validate":
            self._validate_sclpll_source(source, str(path))

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
            return

        table = Table(
            title="Discovered Functions",
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

        for i, f in enumerate(funcs, 1):
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

        # Detail view
        if funcs:
            idx_str = Prompt.ask(
                "[cyan]View details (number, or Enter to go back)[/cyan]",
                default="",
            )
            if idx_str:
                try:
                    idx = int(idx_str) - 1
                    if 0 <= idx < len(funcs):
                        self._show_function_detail(funcs[idx])
                except ValueError:
                    pass

    def _show_function_detail(self, func_meta: dict[str, str]) -> None:
        path = Path(func_meta.get("path", ""))
        if not path.exists():
            self.console.print("[red]Function file not found[/red]")
            return

        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            self.console.print("[red]Cannot read function file[/red]")
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
        except ValueError:
            limit = 20

        asyncio.run(self._show_history_async(limit))

    async def _show_history_async(self, limit: int) -> None:
        from app.ui.app import App

        async with App(self.db_path) as application:
            entries = await application.history.list_recent(limit)

            if not entries:
                self.console.print("[dim]No history entries[/dim]")
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

                table.add_row(
                    str(i),
                    entry["id"][:8],
                    entry["created_at"][:19] if entry.get("created_at") else "",
                    f"[{method_color}]{entry.get('method', '?')}[/{method_color}]",
                    entry.get("url", "")[:60],
                    f"[{status_color}]{entry.get('status_code', 'ERR')}[/{status_color}]",
                    f"{entry.get('duration_ms', 0)}ms",
                )

            self.console.print(table)
            self.console.print()

            # Detail view
            idx_str = Prompt.ask(
                "[cyan]Inspect entry (number, or Enter to go back)[/cyan]",
                default="",
            )
            if idx_str:
                try:
                    idx = int(idx_str) - 1
                    if 0 <= idx < len(entries):
                        self._show_history_detail(entries[idx])
                except ValueError:
                    pass

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

        asyncio.run(self._environment_menu())

    async def _environment_menu(self) -> None:
        from app.ui.app import App

        while True:
            self.console.print()
            self.console.print("  [bold cyan][[1]][/bold cyan] List environments")
            self.console.print("  [bold cyan][[2]][/bold cyan] Create environment")
            self.console.print("  [bold cyan][[3]][/bold cyan] View variables")
            self.console.print("  [bold cyan][[4]][/bold cyan] Activate environment")
            self.console.print("  [bold cyan][[0]][/bold cyan] Back")
            self.console.print()

            choice = Prompt.ask(
                "[cyan]Select[/cyan]",
                choices=["0", "1", "2", "3", "4"],
                default="0",
            )

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
            return

        if idx < 0 or idx >= len(envs):
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
            return

        if idx < 0 or idx >= len(envs):
            return

        env = envs[idx]
        await application.environments.set_active(env["id"])
        self.console.print(f"[green]Activated environment '{env['name']}'[/green]")

    # ── Script validator ─────────────────────────────────────────────────

    def _script_validator(self) -> None:
        self.console.print(Rule("[bold cyan]Script Validator[/bold cyan]", style="cyan"))
        self.console.print()

        path_str = Prompt.ask("[cyan]Path to .sclpll file[/cyan]")
        if not path_str:
            return

        path = Path(path_str)
        if not path.exists():
            self.console.print(f"[red]File not found: {path}[/red]")
            return

        try:
            source = path.read_text(encoding="utf-8")
        except OSError as e:
            self.console.print(f"[red]Cannot read file: {e}[/red]")
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
                f"[red]{e}[/red]",
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
        self.console.print(Align.center("[dim]Happy automating![/dim]"))
        self.console.print()


# ─── Public API ──────────────────────────────────────────────────────────────


def launch_tui(db_path: str = "data/sclplapi.db") -> None:
    """Launch the SCLPLAPI Terminal User Interface."""
    tui = TUI(db_path)
    tui.run()
