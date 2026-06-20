"""Main entry point for SCLPLAPI.

Launches the Text User Interface (TUI) - zero web dependencies, pure terminal.
"""

import argparse
import importlib
import json
import sys
from pathlib import Path


def _find_python() -> str:
    """Return the absolute path of the current Python interpreter."""
    return sys.executable


def _run_cli_command(args: list[str]) -> None:
    """Run a CLI subcommand by dynamically importing the appropriate module."""
    commands = {
        "plugins": "app.ui.cli_plugins",
        "collections": "app.ui.cli_collections",
        "environments": "app.ui.cli_environments",
        "history": "app.ui.cli_history",
        "export": "app.ui.cli_export",
    }

    if not args:
        print("Available commands: " + ", ".join(commands.keys()))
        print("Usage: python -m app <command> [args]")
        return

    cmd = args[0]
    if cmd in commands:
        try:
            module = importlib.import_module(commands[cmd])
            if hasattr(module, "main"):
                module.main(args[1:])
            else:
                print(f"Error: {cmd} command not properly implemented")
        except ImportError as e:
            print(f"Error: Could not load {cmd} module: {e}")
    else:
        print(f"Unknown command: {cmd}")
        print("Available commands: " + ", ".join(commands.keys()))


def run_tui() -> None:
    """Launch the Text User Interface."""
    from app.ui.tui import TUI
    app = TUI()
    app.run()


def run_launcher() -> None:
    """Parse CLI arguments and launch the appropriate mode."""
    # Check for CLI subcommands first (e.g., python -m app plugins list)
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        _run_cli_command(sys.argv[1:])
        return

    parser = argparse.ArgumentParser(
        prog="sclplapi",
        description="SCLPLAPI - Local-first, Python-first API workflow studio",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Launch TUI directly",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run setup wizard again",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset settings to defaults",
    )
    parser.add_argument(
        "--enable-plugins",
        action="store_true",
        help="Enable plugin system (adds dependency overhead)",
    )

    args = parser.parse_args()

    # Handle --reset
    if args.reset:
        settings_path = Path("settings.json")
        if settings_path.exists():
            settings_path.unlink()
            print("Settings reset to defaults")
        else:
            print("No settings file found")
        return

    # Check if plugins should be enabled
    if args.enable_plugins:
        import os
        os.environ["SCLPLAPI_PLUGINS_ENABLED"] = "1"
        print("Plugin system enabled")

    # Check for first run
    settings = _load_settings()
    if settings.get("first_run", True) or args.setup:
        _run_setup_wizard(settings)
        settings["first_run"] = False
        _save_settings(settings)
        print()

    # Check for updates
    if settings.get("auto_check_updates", True):
        _check_for_updates(silent=True)

    # Always launch TUI
    run_tui()


def _load_settings() -> dict:
    """Load settings from settings.json."""
    settings_path = Path("settings.json")
    if settings_path.exists():
        try:
            return json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "first_run": True,
        "default_mode": "tui",
        "auto_check_updates": True,
        "plugins_enabled": False,
        "theme": "dark",
    }


def _save_settings(settings: dict) -> None:
    """Save settings to settings.json."""
    settings_path = Path("settings.json")
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def _run_setup_wizard(settings: dict) -> None:
    """Run the first-time setup wizard."""
    print("=" * 60)
    print("  SCLPLAPI Setup Wizard")
    print("=" * 60)
    print()

    # Show ASCII art
    try:
        from app.ui.logo import get_logo
        print(get_logo())
        print()
    except ImportError:
        pass

    # Show welcome message
    print("Welcome to SCLPLAPI - Local-first, Python-first API workflow studio!")
    print()
    print("SCLPLAPI lets you:")
    print("  * Send HTTP requests and test APIs")
    print("  * Create workflows with the SCLPLL scripting language")
    print("  * Build data pipelines with Python functions")
    print("  * Export results to JSON, CSV, and HTML reports")
    print()

    # Check Python version
    python_version = sys.version_info
    print(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 9):
        print("WARNING: SCLPLAPI requires Python 3.9 or higher")
    else:
        print("OK: Python version is compatible")
    print()

    # Check dependencies
    print("Checking dependencies...")
    deps_ok = _check_dependencies()
    print()

    # Show features
    print("SCLPLAPI Features:")
    print("  * TUI Mode - Terminal-based interface (no web dependencies)")
    print("  * SCLPLL Language - Custom scripting for API workflows")
    print("  * Plugin System - Extend with custom functions")
    print("  * Export Engine - JSON, CSV, HTML, and summary exports")
    print("  * Visual Workflows - See your data flow in real-time")
    print()

    # Ask for default mode (always TUI now)
    settings["default_mode"] = "tui"

    # Ask about updates
    print("Automatic update checking:")
    print("  SCLPLAPI can check for updates on startup.")
    response = input("  Enable automatic update checking? (Y/n): ").strip().lower()
    settings["auto_check_updates"] = response not in ("n", "no")
    print()

    print("Setup complete! SCLPLAPI is ready to use.")
    print()


def _check_dependencies() -> bool:
    """Check if all required dependencies are installed."""
    import importlib

    required = [
        ("httpx", "HTTP client"),
        ("pydantic", "Data validation"),
        ("rich", "TUI rendering"),
        ("prompt_toolkit", "TUI input"),
    ]

    optional = [
        ("uvicorn", "Web server"),
        ("fastapi", "Web framework"),
    ]

    all_ok = True

    for module_name, description in required:
        try:
            importlib.import_module(module_name)
            print(f"  OK: {description} ({module_name})")
        except ImportError:
            print(f"  MISSING: {description} ({module_name})")
            all_ok = False

    for module_name, description in optional:
        try:
            importlib.import_module(module_name)
            print(f"  OK: {description} ({module_name})")
        except ImportError:
            print(f"  SKIP: {description} ({module_name}) - optional")

    return all_ok


def _check_for_updates(silent: bool = False) -> None:
    """Check for updates from PyPI."""
    try:
        from app.core.updater import check_for_updates
        update_info = check_for_updates()
        if update_info and not silent:
            print(f"Update available: {update_info['latest_version']}")
            print(f"Current version: {update_info['current_version']}")
            print("Run 'pip install --upgrade sclplapi' to update")
    except Exception:
        if not silent:
            print("Could not check for updates")


if __name__ == "__main__":
    run_launcher()
