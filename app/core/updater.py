"""SCLPLAPI self-updater from GitHub releases."""

import subprocess
import sys

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()
REPO_URL = "https://github.com/sm408/sclpl-api.git"

def check_for_updates() -> dict:
    """Check if updates are available."""
    try:
        # Get current commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10
        )
        current = result.stdout.strip()[:7]
        
        # Fetch latest
        subprocess.run(
            ["git", "fetch", "origin", "main"],
            capture_output=True, text=True, timeout=30
        )
        
        # Get remote commit
        result = subprocess.run(
            ["git", "rev-parse", "origin/main"],
            capture_output=True, text=True, timeout=10
        )
        latest = result.stdout.strip()[:7]
        
        # Compare
        result = subprocess.run(
            ["git", "rev-list", "HEAD..origin/main", "--count"],
            capture_output=True, text=True, timeout=10
        )
        commits_behind = int(result.stdout.strip() or 0)
        
        return {
            "current": current,
            "latest": latest,
            "commits_behind": commits_behind,
            "update_available": commits_behind > 0,
        }
    except Exception as e:
        return {"error": str(e), "update_available": False}

def apply_update() -> bool:
    """Pull latest changes and update dependencies."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Pulling updates...", total=None)
        
        # Pull changes
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            capture_output=True, text=True, timeout=60
        )
        
        if result.returncode != 0:
            progress.update(task, description=f"[red]Update failed: {result.stderr}[/red]")
            return False
        
        progress.update(task, description="Installing dependencies...")
        
        # Update dependencies
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", ".[all]", "-q"],
            capture_output=True, text=True, timeout=120
        )
        
        progress.update(task, description="[green]Update complete![/green]")
        return True

def show_update_info(info: dict) -> None:
    """Display update information."""
    if info.get("error"):
        console.print(f"[yellow]Could not check for updates: {info['error']}[/yellow]")
        return
    
    if info["update_available"]:
        console.print("[green]Update available![/green]")
        console.print(f"  Current: {info['current']}")
        console.print(f"  Latest:  {info['latest']}")
        console.print(f"  {info['commits_behind']} commits behind")
    else:
        console.print(f"[green]Up to date![/green] ({info['current']})")
