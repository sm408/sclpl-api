"""Project model for workspace isolation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


# Well-known UUID for the Default project.  Every existing row in the
# database is assigned to this project during migration.  The Default
# project cannot be deleted and its root files are not relocated.
DEFAULT_PROJECT_ID = "00000000-0000-0000-0000-000000000001"

# Subdirectories created inside each managed project root.
PROJECT_SUBDIRS = ("functions", "plugins", "workflows", "exports")


@dataclass
class Project:
    """A scoped workspace that groups collections, requests, environments, etc."""

    id: str
    name: str
    description: str = ""
    root_path: str = ""  # Relative path, e.g. "data/projects/<uuid>"
    is_default: bool = False
    created_at: str | None = None
    updated_at: str | None = None


def ensure_project_dirs(root: Path) -> None:
    """Create the standard subdirectories for a managed project root."""
    for subdir in PROJECT_SUBDIRS:
        (root / subdir).mkdir(parents=True, exist_ok=True)
