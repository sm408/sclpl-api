"""Registered, integrity-pinned Python scripts for a project.

Scripts are executable code, not ordinary workflow data. A workflow names a manifest
registration; it never supplies an executable filesystem path or remote URI. Remote
scripts are materialized through the existing resource provider/cache boundary and every
registration carries a SHA-256 digest, so changing a blob in place cannot silently change
what a workflow executes.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import urlsplit

from sclpl.errors import ValidationError
from sclpl.ext.resources import resource_provider, resource_scheme
from sclpl.state.resource_cache import ResourceCache

if TYPE_CHECKING:
    from sclpl.project.context import ProjectContext


_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class WorkflowDoc(Protocol):
    """The small workflow shape needed for executable-script preflight."""

    def all_steps(self) -> list[Any]: ...


@dataclass(frozen=True, slots=True)
class Registration:
    name: str
    path: str | None
    uri: str | None
    sha256: str


def registrations(project: ProjectContext) -> dict[str, Registration]:
    """Parse the project's allowlist without touching the registered source bytes."""
    raw = project.manifest.get("python", {})
    assert isinstance(raw, dict)  # validated by project.context
    scripts = raw.get("scripts", {})
    assert isinstance(scripts, dict)  # validated by project.context
    parsed: dict[str, Registration] = {}
    for name, value in scripts.items():
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ValidationError(
                f"python script name {name!r} is invalid",
                where=str(project.manifest_path),
                remedies=["use letters, digits, _ or -; start with a letter"],
            )
        if not isinstance(value, dict):
            raise ValidationError(
                f"python.scripts.{name} must be a table", where=str(project.manifest_path)
            )
        unknown = set(value) - {"path", "uri", "sha256"}
        if unknown:
            raise ValidationError(
                f"unknown python script key {sorted(unknown)[0]!r}",
                where=str(project.manifest_path),
            )
        path, uri, digest = value.get("path"), value.get("uri"), value.get("sha256")
        if (path is None) == (uri is None):
            raise ValidationError(
                f"python script {name!r} needs exactly one of path or uri",
                where=str(project.manifest_path),
            )
        if path is not None and not isinstance(path, str):
            raise ValidationError(f"python script {name!r} path must be a string")
        if uri is not None and not isinstance(uri, str):
            raise ValidationError(f"python script {name!r} uri must be a string")
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise ValidationError(
                f"python script {name!r} sha256 must be a lowercase 64-character digest",
                where=str(project.manifest_path),
                remedies=['pin the exact source bytes with sha256 = "..."'],
            )
        if path is not None and Path(path).suffix.lower() != ".py":
            raise ValidationError(f"python script {name!r} path must end in .py")
        if uri is not None:
            _validate_uri(name, uri, project)
        parsed[name] = Registration(name, path, uri, digest)
    return parsed


def check_workflow(doc: WorkflowDoc, project: ProjectContext | None) -> None:
    """Reject unregistered or dynamic script names before the scheduler starts."""
    python_steps = [
        step for step in doc.all_steps() if getattr(step.config, "name", None) == "python"
    ]
    if not python_steps:
        return
    if project is None:
        raise ValidationError(
            "python steps require a project with registered scripts",
            remedies=["run sclpl init", "declare [python.scripts.<name>] in sclpl.toml"],
        )
    known = registrations(project)
    for step in python_steps:
        config: Any = step.config
        if (
            not config.args
            or not isinstance(config.args[0], str)
            or not _NAME.fullmatch(config.args[0])
        ):
            raise ValidationError(
                f"python step {step.id!r} must name a registered script",
                remedies=['use: python "registered-name" input=@value'],
            )
        if config.args[0] not in known:
            available = ", ".join(sorted(known)) or "none"
            raise ValidationError(
                f"python step {step.id!r} names unregistered script {config.args[0]!r}",
                remedies=[f"registered scripts: {available}"],
            )


def materialize(
    project: ProjectContext,
    name: str,
    *,
    cache_read: bool = True,
    cache_write: bool = True,
    cache_require_hit: bool = False,
) -> Path:
    """Return verified local bytes for one registered local or remote script."""
    entry = registrations(project).get(name)
    if entry is None:
        raise ValidationError(f"unregistered python script {name!r}")
    if entry.path is not None:
        path = project.resolve_path(entry.path)
        if not path.is_file():
            raise ValidationError(f"registered python script {name!r} does not exist: {entry.path}")
        _verify(path, entry.sha256, name)
        return path

    assert entry.uri is not None
    provider = resource_provider(entry.uri)
    uri = provider.normalize(entry.uri)
    cache = ResourceCache()
    staged = cache.root / "scripts" / f"{hashlib.sha256(uri.encode()).hexdigest()[:24]}.py"
    cache.materialize(
        provider,
        uri,
        staged,
        read=cache_read,
        write=cache_write,
        require_hit=cache_require_hit,
    )
    _verify(staged, entry.sha256, name)
    return staged


def _validate_uri(name: str, uri: str, project: ProjectContext) -> None:
    if resource_scheme(uri) is None or Path(urlsplit(uri).path).suffix.lower() != ".py":
        raise ValidationError(f"python script {name!r} uri must be a resource URI ending in .py")
    parts = urlsplit(uri)
    if parts.query or parts.fragment or parts.username or parts.password:
        raise ValidationError(
            f"python script {name!r} uri may not contain credentials or query parameters",
            where=str(project.manifest_path),
            remedies=["configure provider authentication outside sclpl.toml"],
        )


def _verify(path: Path, expected: str, name: str) -> None:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise ValidationError(
            f"registered python script {name!r} does not match its pinned sha256",
            remedies=["review the source, then update the manifest digest deliberately"],
        )
