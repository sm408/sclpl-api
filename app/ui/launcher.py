"""Unified launcher with setup wizard for SCLPLAPI."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

from app.core.settings import SCLPLAPISettings

console = Console()

LOGO = r"""
[bold cyan]  ____  ____  ____  ____  ____  _      ____  ____  ____
 / ___)( __ \( ___)( ___)(  _ \( \    / ___)( ___)(  _ \
( (__  /    / )__)  )__)  )   / ) \   \___ \ )__)  )   /
 \___)\_\_\_)(____)(____)(_)\_)(___)  (____/(___)(_)\_)

  API Workflow Studio  ·  Python-First  ·  Local-First[/bold cyan]
"""


def show_setup_wizard(settings: SCLPLAPISettings) -> None:
    """Run first-time setup wizard."""
    console.clear()
    console.print(LOGO)
    console.print()

    console.print(Panel(
        "[bold]Welcome to SCLPLAPI![/bold]\n\n"
        "This is your first run. Let's get you set up.",
        title="[cyan]Setup Wizard[/cyan]",
        border_style="cyan",
    ))
    console.print()

    # Step 1: Database path
    console.print("[bold]Step 1/3: Database Location[/bold]")
    console.print("SCLPLAPI stores data in a local SQLite database.")
    db_path = Prompt.ask(
        "Database path",
        default=settings.db_path,
    )
    settings.db_path = db_path
    console.print(f"  [green]✓[/green] Database: {db_path}")
    console.print()

    # Step 2: Default UI
    console.print("[bold]Step 2/3: Default Interface[/bold]")
    console.print("Choose your preferred interface:")
    console.print("  [cyan]1.[/cyan] TUI  — Terminal UI (Rich-based, works in any terminal)")
    console.print("  [cyan]2.[/cyan] GUI  — Web Browser UI (FastAPI-based, modern SPA)")
    console.print()

    choice = Prompt.ask(
        "Select default UI",
        choices=["1", "2", "tui", "gui"],
        default="tui",
    )
    if choice in ("1", "tui"):
        settings.default_ui = "tui"
        console.print("  [green]✓[/green] Default UI: TUI (Terminal)")
    else:
        settings.default_ui = "gui"
        console.print("  [green]✓[/green] Default UI: GUI (Browser)")
    console.print()

    # Step 3: Web GUI settings (if selected)
    if settings.default_ui == "gui":
        console.print("[bold]Step 3/3: Web Server Settings[/bold]")
        settings.web_host = Prompt.ask("Host", default=settings.web_host)
        settings.web_port = int(Prompt.ask("Port", default=str(settings.web_port)))
        settings.web_open_browser = Confirm.ask("Open browser on start", default=True)
        console.print(f"  [green]✓[/green] Server: {settings.web_host}:{settings.web_port}")
    else:
        console.print("[bold]Step 3/3: All Set[/bold]")
    console.print()

    # Save
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Saving settings...", total=None)
        settings.mark_first_run_complete()
        settings.save()
        time.sleep(0.5)
        progress.update(task, description="[green]Settings saved![/green]")
        time.sleep(0.3)

    console.print()
    console.print(Panel(
        f"[green]Setup complete![/green]\n\n"
        f"Default UI: [cyan]{settings.default_ui.upper()}[/cyan]\n"
        f"Database: [cyan]{settings.db_path}[/cyan]\n\n"
        f"You can change these settings anytime from:\n"
        f"  • TUI: Settings menu\n"
        f"  • GUI: Settings page\n"
        f"  • CLI: [cyan]sclplapi config[/cyan]",
        title="[green]Ready![/green]",
        border_style="green",
    ))
    console.print()


def show_ui_selector(settings: SCLPLAPISettings) -> str:
    """Show UI selection menu and return choice."""
    console.print()
    console.print(Panel(
        "[bold]SCLPLAPI[/bold] — Choose your interface",
        border_style="cyan",
    ))
    console.print()

    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_column("Key", style="cyan", width=4)
    table.add_column("Option", style="white", width=30)
    table.add_column("Description", style="dim")

    table.add_row("[bold]1[/bold]", "TUI (Terminal)", "Rich-based terminal interface")
    table.add_row("[bold]2[/bold]", "GUI (Browser)", "Web-based SPA interface")
    table.add_row("[bold]S[/bold]", "Settings", "Configure default UI and preferences")
    table.add_row("[bold]Q[/bold]", "Quit", "Exit SCLPLAPI")

    console.print(table)
    console.print()

    default_hint = f"[dim](Enter for {settings.default_ui.upper()})[/dim]"
    choice = Prompt.ask(
        f"Select {default_hint}",
        choices=["1", "2", "tui", "gui", "s", "settings", "q", "quit", ""],
        default="",
    )

    if choice == "":
        return settings.default_ui
    if choice in ("1", "tui"):
        return "tui"
    if choice in ("2", "gui"):
        return "gui"
    if choice in ("s", "settings"):
        return "settings"
    return "quit"


def launch_tui(settings: SCLPLAPISettings) -> None:
    """Launch the Terminal UI."""
    from app.ui.tui import TUI
    tui = TUI(db_path=settings.db_path)
    tui.run()


def launch_gui(settings: SCLPLAPISettings) -> None:
    """Launch the Web GUI."""
    try:
        import uvicorn
        from app.web.server import create_app
    except ImportError:
        console.print("[red]Web UI dependencies not installed.[/red]")
        console.print("Install with: [cyan]pip install sclplapi[web][/cyan]")
        return

    application = create_app(settings.db_path)
    if settings.web_open_browser:
        import webbrowser
        webbrowser.open(f"http://{settings.web_host}:{settings.web_port}")
    console.print(f"[green]Starting web server at http://{settings.web_host}:{settings.web_port}[/green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    uvicorn.run(application, host=settings.web_host, port=settings.web_port)


def run_launcher() -> None:
    """Main entry point for SCLPLAPI launcher."""
    settings = SCLPLAPISettings.load()

    # First run: show setup wizard (only in interactive mode)
    if not settings.first_run_complete and sys.stdin.isatty():
        show_setup_wizard(settings)

    # Parse command line args
    args = sys.argv[1:] if len(sys.argv) > 1 else []

    # Direct launch flags
    if "--tui" in args:
        launch_tui(settings)
        return
    if "--gui" in args or "--web" in args:
        launch_gui(settings)
        return
    if "--setup" in args:
        show_setup_wizard(settings)
        return
    if "--reset" in args:
        settings = SCLPLAPISettings()
        settings.save()
        console.print("[yellow]Settings reset to defaults.[/yellow]")
        return

    # If user passed other args, let Typer handle them
    if args:
        from app.ui.cli import app
        app()
        return

    # Non-interactive mode: show help
    if not sys.stdin.isatty():
        from app.ui.cli import app
        app(["--help"])
        return

    # No args + interactive: show UI selector
    while True:
        choice = show_ui_selector(settings)

        if choice == "tui":
            launch_tui(settings)
            break
        elif choice == "gui":
            launch_gui(settings)
            break
        elif choice == "settings":
            show_settings_menu(settings)
            continue
        else:
            console.print("[dim]Goodbye![/dim]")
            break


def show_settings_menu(settings: SCLPLAPISettings) -> None:
    """Interactive settings menu."""
    console.print()
    console.print(Panel("[bold]Settings[/bold]", border_style="cyan"))
    console.print()

    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_column("Setting", style="white", width=25)
    table.add_column("Value", style="cyan")

    table.add_row("Default UI", settings.default_ui.upper())
    table.add_row("Database path", settings.db_path)
    table.add_row("Web host", settings.web_host)
    table.add_row("Web port", str(settings.web_port))
    table.add_row("Open browser", str(settings.web_open_browser))
    table.add_row("Theme", settings.theme)

    console.print(table)
    console.print()

    console.print("[bold]Change settings:[/bold]")
    console.print("  [cyan]1.[/cyan] Set default UI")
    console.print("  [cyan]2.[/cyan] Change database path")
    console.print("  [cyan]3.[/cyan] Web server settings")
    console.print("  [cyan]4.[/cyan] Reset all settings")
    console.print("  [cyan]B.[/cyan] Back")
    console.print()

    choice = Prompt.ask("Select", choices=["1", "2", "3", "4", "b", "back"], default="b")

    if choice == "1":
        ui = Prompt.ask("Default UI", choices=["tui", "gui"], default=settings.default_ui)
        settings.set_default_ui(ui)
        console.print(f"[green]Default UI set to {ui.upper()}[/green]")
    elif choice == "2":
        db = Prompt.ask("Database path", default=settings.db_path)
        settings.db_path = db
        settings.save()
        console.print(f"[green]Database path set to {db}[/green]")
    elif choice == "3":
        settings.web_host = Prompt.ask("Host", default=settings.web_host)
        settings.web_port = int(Prompt.ask("Port", default=str(settings.web_port)))
        settings.web_open_browser = Confirm.ask("Open browser", default=settings.web_open_browser)
        settings.save()
        console.print("[green]Web settings updated[/green]")
    elif choice == "4":
        if Confirm.ask("Reset all settings to defaults?"):
            settings = SCLPLAPISettings()
            settings.save()
            console.print("[yellow]Settings reset[/yellow]")

    console.print()
