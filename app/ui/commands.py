"""Command registry for the TUI command palette."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CommandDef:
    """Definition of a command for the palette."""
    name: str
    handler: str  # method name on the app
    shortcut: str = ""
    description: str = ""
    category: str = "General"


# ── Built-in commands ────────────────────────────────────────────────────────

COMMANDS: list[CommandDef] = [
    # Request
    CommandDef("New Request", "action_new_request", "Ctrl+T", "Create a new request", "Request"),
    CommandDef("Send Request", "action_run_request", "Ctrl+R", "Execute the current request", "Request"),
    CommandDef("Close Tab", "action_close_tab", "Ctrl+W", "Close the current tab", "Request"),

    # Workflow
    CommandDef("Run Workflow", "action_run_workflow", "", "Execute a workflow file", "Workflow"),
    CommandDef("Recent Workflows", "action_recent_workflows", "", "Re-run a recent workflow", "Workflow"),

    # Navigation
    CommandDef("Collections", "action_show_collections", "", "Browse collections", "Navigation"),
    CommandDef("History", "action_show_history", "", "View request history", "Navigation"),
    CommandDef("Environments", "action_show_environments", "", "Manage environments", "Navigation"),
    CommandDef("Functions", "action_show_functions", "", "Browse functions", "Navigation"),
    CommandDef("Plugins", "action_show_plugins", "", "View plugins", "Navigation"),
    CommandDef("Monitors", "action_show_monitors", "Ctrl+M", "Live API monitors", "Navigation"),

    # Monitor
    CommandDef("New Monitor", "action_new_monitor", "", "Create a new API monitor", "Monitor"),
    CommandDef("Start Monitor", "action_start_monitor", "", "Start a monitor", "Monitor"),
    CommandDef("Stop Monitor", "action_stop_monitor", "", "Stop a monitor", "Monitor"),

    # Tools
    CommandDef("Import/Export", "action_show_import_export", "", "Backup or restore workspace", "Tools"),
    CommandDef("Validate Script", "action_validate_script", "", "Check a .sclpll file for errors", "Tools"),
    CommandDef("Settings", "action_show_settings", "", "Configure TUI defaults", "Tools"),

    # Environment
    CommandDef("Switch Environment", "action_switch_environment", "", "Change active environment", "Environment"),

    # System
    CommandDef("Refresh", "action_refresh", "F5", "Reload all data", "System"),
    CommandDef("Help", "action_help", "F1", "Show keyboard shortcuts", "System"),
    CommandDef("Command Palette", "action_command_palette", "Ctrl+P", "Search all commands", "System"),
]
