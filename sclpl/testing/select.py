"""E4: which test manifests a `--changed --base REF` run actually needs.

Conservative throughout, on purpose: anything this cannot determine selects the
manifest -- or, for a change to a shared dependency, every manifest -- rather than
silently skipping a test that might have broken.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from sclpl.catalog import resolve as catalog
from sclpl.project.context import ProjectContext
from sclpl.testing.manifest import Manifest

#: Directories whose changes are treated as touching every test: a shared function
#: or plugin's actual dependents are not tracked per test manifest, so a change here
#: could affect any of them.
_SHARED_DIR_NAMES = ("functions", "plugins")

_GIT_TIMEOUT = 15.0


def changed_paths(base: str, *, cwd: Path) -> set[Path] | None:
    """Absolute paths changed since ``base``, including untracked files.

    ``None`` is the conservative "cannot answer" signal -- no git repository, no
    such base ref, git itself unavailable, or the command timed out -- and callers
    treat it as "run everything" rather than as "nothing changed".
    """
    try:
        diff = subprocess.run(
            ["git", "diff", "--name-only", "--find-renames", f"{base}...HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if diff.returncode != 0 or untracked.returncode != 0:
        return None
    lines = diff.stdout.splitlines() + untracked.stdout.splitlines()
    return {(cwd / line.strip()).resolve() for line in lines if line.strip()}


def select(manifests: list[Manifest], project: ProjectContext, *, base: str) -> list[Manifest]:
    """The subset of ``manifests`` worth running for this change, or all of them."""
    changed = changed_paths(base, cwd=project.root)
    if changed is None or _touches_shared_dependency(changed, project):
        return list(manifests)
    return [manifest for manifest in manifests if _is_affected(manifest, changed, project)]


def _touches_shared_dependency(changed: set[Path], project: ProjectContext) -> bool:
    if project.manifest_path.resolve() in changed:
        return True
    for path in changed:
        try:
            relative = path.relative_to(project.root)
        except ValueError:
            continue  # outside the project entirely: cannot be one of its shared dirs
        if relative.parts and relative.parts[0] in _SHARED_DIR_NAMES:
            return True
    return False


def _is_affected(manifest: Manifest, changed: set[Path], project: ProjectContext) -> bool:
    if manifest.path in changed:
        return True
    if any(_is_under(path, manifest.fixture) for path in changed):
        return True
    try:
        located = catalog.resolve(manifest.workflow, extra_dirs=project.workflow_dirs)
    except Exception:  # noqa: BLE001 - cannot rule it out, so keep it: conservative
        return True
    return located.path.resolve() in changed


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
