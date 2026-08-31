"""Resolving a workflow: a name, or a path.

Resolution order, first match wins:

1. An existing path, exactly as given
2. `./<name>.sclpll`, then `./<name>.json`, then the same under `./workflows/`
3. The project catalogue, `.sclpl/workflows/`
4. The user catalogue, `~/.sclpl/workflows/`

Local before installed, so a file you are editing wins over a registered copy of it --
the alternative is editing a file and running a different one, which is the kind of
confusion that costs an afternoon.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sclpl.errors import UnknownTarget, did_you_mean
from sclpl.run import compile_json
from sclpl.run.ir import WorkflowDoc
from sclpl.run.sclpll import parse as parse_sclpll

SUFFIXES = (".sclpll", ".json")

PROJECT_DIR = Path(".sclpl")
USER_DIR = Path.home() / ".sclpl"
WORKFLOWS = "workflows"


@dataclass(frozen=True, slots=True)
class Located:
    """A workflow, and where it was found."""

    doc: WorkflowDoc
    path: Path
    source: str  # "path" | "cwd" | "project" | "user"

    def describe(self) -> str:
        return f"{self.doc.name} ({self.source}: {self.path})"


def load(path: Path) -> WorkflowDoc:
    """Parse a workflow file, choosing the surface by extension."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return compile_json.loads(text, origin=str(path))
    return parse_sclpll(text, origin=str(path))


def resolve(target: str, *, extra_dirs: list[Path] | None = None) -> Located:
    """Find a workflow by name or path, or raise listing what is available."""
    candidate = Path(target)
    if candidate.exists() and candidate.is_file():
        return Located(doc=load(candidate), path=candidate, source="path")

    if candidate.suffix and not candidate.exists() and _looks_like_a_path(target):
        raise UnknownTarget(
            f"{target} does not exist",
            remedies=["check the path, or use a registered name: sclpl list"],
        )

    for directory, source in _search_path(extra_dirs):
        for suffix in SUFFIXES:
            found = directory / f"{target}{suffix}"
            if found.is_file():
                return Located(doc=load(found), path=found, source=source)

    raise _not_found(target, extra_dirs)


def _looks_like_a_path(target: str) -> bool:
    return "/" in target or "\\" in target or target.startswith(".")


def _search_path(extra_dirs: list[Path] | None) -> list[tuple[Path, str]]:
    directories: list[tuple[Path, str]] = [(Path(), "cwd"), (Path(WORKFLOWS), "cwd")]
    directories.extend((directory, "given") for directory in (extra_dirs or []))
    directories.append((PROJECT_DIR / WORKFLOWS, "project"))
    directories.append((USER_DIR / WORKFLOWS, "user"))
    return directories


def available(extra_dirs: list[Path] | None = None) -> dict[str, Path]:
    """Every resolvable workflow name, first-found winning."""
    found: dict[str, Path] = {}
    for directory, _ in _search_path(extra_dirs):
        if not directory.is_dir():
            continue
        for suffix in SUFFIXES:
            for path in sorted(directory.glob(f"*{suffix}")):
                found.setdefault(path.stem, path)
    return found


def _not_found(target: str, extra_dirs: list[Path] | None) -> UnknownTarget:
    known = available(extra_dirs)
    remedies = []
    suggestion = did_you_mean(target, list(known))
    if suggestion:
        remedies.append(suggestion)
    if known:
        listing = ", ".join(sorted(known)[:8])
        more = f" (+{len(known) - 8} more)" if len(known) > 8 else ""
        remedies.append(f"available: {listing}{more}")
    else:
        remedies.append("no workflows found -- import one with 'sclpl import workflow <file>'")
    remedies.append("or give a path to a .sclpll or .json file")
    return UnknownTarget(f"no workflow named {target!r}", remedies=remedies)
