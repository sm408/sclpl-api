"""The catalogue: importing, listing, and removing registered workflows.

Files on disk, not a database. A registered workflow is a file in
`.sclpl/workflows/` or `~/.sclpl/workflows/`, which means it can be read, edited,
diffed, and committed with everything else. Versioning is by content hash: importing
the same bytes twice is a no-op, and importing different bytes under the same name
keeps the previous version alongside.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sclpl.catalog.resolve import PROJECT_DIR, SUFFIXES, USER_DIR, WORKFLOWS, load
from sclpl.run.errors import UnknownTarget, ValidationError, did_you_mean
from sclpl.run.ir import WorkflowDoc
from sclpl.values.digest import digest

#: Where previous versions go when a name is re-imported with different content.
VERSIONS = "versions"


@dataclass(frozen=True, slots=True)
class Entry:
    """One registered workflow."""

    name: str
    path: Path
    scope: str  # "project" | "user"
    digest: str
    modified: datetime
    description: str = ""
    steps: int = 0

    def describe(self) -> str:
        return f"{self.name:<24} {self.steps:>3} steps  {self.scope:<8} {self.description[:40]}"


def root(scope: str) -> Path:
    if scope == "user":
        return USER_DIR
    if scope == "project":
        return PROJECT_DIR
    raise ValueError(f"unknown scope {scope!r}")


def workflows_dir(scope: str) -> Path:
    return root(scope) / WORKFLOWS


def import_workflow(
    source: Path,
    *,
    scope: str = "project",
    name: str | None = None,
    overwrite: bool = False,
) -> Entry:
    """Register a workflow file, validating it first.

    Importing something unparseable would put a broken file in the catalogue where it
    fails later and further from its cause, so it is parsed before it is copied.
    """
    if not source.is_file():
        raise UnknownTarget(
            f"{source} does not exist",
            remedies=["give a path to a .sclpll or .json file"],
        )
    if source.suffix.lower() not in SUFFIXES:
        raise ValidationError(
            f"{source.name} is not a workflow file",
            remedies=[f"expected one of: {', '.join(SUFFIXES)}"],
        )

    doc = load(source)
    target_name = name or doc.name or source.stem
    directory = workflows_dir(scope)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{target_name}{source.suffix.lower()}"

    content = source.read_bytes()
    incoming = digest(content)

    if destination.exists():
        if digest(destination.read_bytes()) == incoming:
            return _entry(destination, scope, doc)
        if not overwrite:
            _archive(destination, scope)
    shutil.copyfile(source, destination)
    return _entry(destination, scope, doc)


def _archive(existing: Path, scope: str) -> Path:
    """Move the previous content aside, stamped, so an import is never destructive."""
    archive = root(scope) / VERSIONS
    archive.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    kept = archive / f"{existing.stem}-{stamp}{existing.suffix}"
    shutil.copyfile(existing, kept)
    return kept


def _entry(path: Path, scope: str, doc: WorkflowDoc) -> Entry:
    stat = path.stat()
    return Entry(
        name=path.stem,
        path=path,
        scope=scope,
        digest=digest(path.read_bytes()),
        modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        description=doc.description,
        steps=len(doc.all_steps()),
    )


def entries(scope: str | None = None) -> list[Entry]:
    """Every registered workflow. Project scope shadows user scope on a name clash."""
    found: dict[str, Entry] = {}
    scopes = [scope] if scope else ["user", "project"]
    for current in scopes:
        directory = workflows_dir(current)
        if not directory.is_dir():
            continue
        for suffix in SUFFIXES:
            for path in sorted(directory.glob(f"*{suffix}")):
                try:
                    doc = load(path)
                except Exception:  # noqa: BLE001 - a broken file should still be listed
                    doc = WorkflowDoc(name=path.stem, description="(does not parse)")
                found[path.stem] = _entry(path, current, doc)
    return sorted(found.values(), key=lambda entry: entry.name)


def find(name: str, scope: str | None = None) -> Entry:
    for entry in entries(scope):
        if entry.name == name:
            return entry
    known = [entry.name for entry in entries(scope)]
    remedies = []
    suggestion = did_you_mean(name, known)
    if suggestion:
        remedies.append(suggestion)
    remedies.append(f"registered: {', '.join(known)}" if known else "nothing registered yet")
    raise UnknownTarget(f"no registered workflow named {name!r}", remedies=remedies)


def remove(name: str, scope: str = "project", *, keep_versions: bool = True) -> Path:
    """Unregister a workflow. Its archived versions survive unless asked otherwise."""
    entry = find(name, scope)
    if keep_versions:
        _archive(entry.path, scope)
    entry.path.unlink()
    return entry.path


def versions(name: str, scope: str = "project") -> list[Path]:
    archive = root(scope) / VERSIONS
    if not archive.is_dir():
        return []
    return sorted(archive.glob(f"{name}-*"))
