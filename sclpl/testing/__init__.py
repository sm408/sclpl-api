"""Versioned project-test manifest discovery and validation."""

from sclpl.testing.execute import Outcome, run
from sclpl.testing.manifest import Manifest, discover, load

__all__ = ["Manifest", "Outcome", "discover", "load", "run"]
