"""SCLPLAPI entry point.

Usage:
    python -m app              # Launch UI selector (first run: setup wizard)
    python -m app --tui        # Launch TUI directly
    python -m app --gui        # Launch Web GUI directly
    python -m app --setup      # Run setup wizard again
    python -m app --reset      # Reset settings to defaults
    python -m app <command>    # Run CLI command (e.g., plugins list)
"""

from app.ui.launcher import run_launcher

run_launcher()
