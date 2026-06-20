"""User settings and preferences for SCLPLAPI."""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, asdict


DEFAULT_SETTINGS_PATH = Path.home() / ".sclplapi" / "settings.json"


@dataclass
class SCLPLAPISettings:
    """User preferences for SCLPLAPI."""

    default_ui: str = "tui"
    first_run_complete: bool = False
    db_path: str = "data/sclplapi.db"
    theme: str = "dark"

    @classmethod
    def load(cls, path: Path | None = None) -> SCLPLAPISettings:
        """Load settings from file, or return defaults."""
        path = path or DEFAULT_SETTINGS_PATH
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()

    def save(self, path: Path | None = None) -> None:
        """Save settings to file."""
        path = path or DEFAULT_SETTINGS_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def set_default_ui(self, ui: str) -> None:
        """Set the default UI and save."""
        self.default_ui = ui
        self.save()

    def mark_first_run_complete(self) -> None:
        """Mark first run as complete and save."""
        self.first_run_complete = True
        self.save()
