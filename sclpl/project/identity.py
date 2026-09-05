"""Portable, non-secret identities for project workflows."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sclpl.project.context import ProjectContext


@dataclass(frozen=True, slots=True)
class WorkflowIdentity:
    """The deterministic facts needed to verify a workflow before it runs."""

    name: str
    source: str
    source_digest: str
    configuration_digest: str
    digest: str
    runtime: str

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "source": self.source,
            "source_digest": self.source_digest,
            "configuration_digest": self.configuration_digest,
            "digest": self.digest,
            "runtime": self.runtime,
        }


def identify(name: str, path: Path, context: ProjectContext | None) -> WorkflowIdentity:
    """Hash source and effective non-secret configuration without machine paths."""
    source = _relative(path, context)
    source_digest = _digest(path.read_bytes())
    configuration = context.settings if context else {}
    configuration_digest = _canonical_digest(configuration)
    runtime = (
        f"python:{sys.version_info.major}.{sys.version_info.minor};platform:{platform.system()}"
    )
    digest = _canonical_digest(
        {
            "schema": 1,
            "name": name,
            "source": source,
            "source_digest": source_digest,
            "configuration_digest": configuration_digest,
        }
    )
    return WorkflowIdentity(name, source, source_digest, configuration_digest, digest, runtime)


def _relative(path: Path, context: ProjectContext | None) -> str:
    resolved = path.resolve()
    if context is not None:
        try:
            return resolved.relative_to(context.root).as_posix()
        except ValueError:
            pass
    return path.name


def _canonical_digest(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return _digest(rendered.encode("utf-8"))


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
