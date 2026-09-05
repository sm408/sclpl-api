"""Versioned workflow locks: explicit writes and side-effect-free verification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sclpl.errors import ValidationError
from sclpl.project.context import ProjectContext
from sclpl.project.identity import WorkflowIdentity
from sclpl.state.locking import Lock

LOCK_NAME = "sclpl.lock"
SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class Lockfile:
    workflows: dict[str, dict[str, str]]


def path_for(context: ProjectContext) -> Path:
    return context.root / LOCK_NAME


def read(context: ProjectContext) -> Lockfile:
    path = path_for(context)
    if not path.is_file():
        raise ValidationError(f"no {LOCK_NAME} found", remedies=["run sclpl workflow lock"])
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValidationError(f"invalid {LOCK_NAME}: {error}", where=str(path)) from error
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA_VERSION:
        raise ValidationError(f"unsupported {LOCK_NAME} schema", where=str(path))
    workflows = payload.get("workflows")
    if not isinstance(workflows, dict) or not all(
        isinstance(name, str) and isinstance(value, dict) for name, value in workflows.items()
    ):
        raise ValidationError(f"invalid workflows in {LOCK_NAME}", where=str(path))
    return Lockfile({name: dict(value) for name, value in workflows.items()})


def write(context: ProjectContext, identities: list[WorkflowIdentity]) -> Path:
    """Atomically replace the lock only when the caller deliberately requested it."""
    path = path_for(context)
    payload = {
        "schema": SCHEMA_VERSION,
        "workflows": {
            identity.name: identity.as_dict()
            for identity in sorted(identities, key=lambda item: item.name)
        },
    }
    with Lock(context.root / ".sclpl" / "locks" / "workflow.lock"):
        temporary = path.with_suffix(".lock.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    return path


def verify(context: ProjectContext, identity: WorkflowIdentity) -> None:
    locked = read(context).workflows.get(identity.name)
    if locked is None:
        raise ValidationError(
            f"workflow {identity.name!r} is not locked",
            remedies=[f"run sclpl workflow lock {identity.name}"],
        )
    expected = locked.get("digest")
    if expected != identity.digest:
        raise ValidationError(
            f"lock drift for workflow {identity.name!r}",
            remedies=[
                f"run sclpl workflow lock {identity.name}",
                "review source and configuration changes before updating",
            ],
        )
