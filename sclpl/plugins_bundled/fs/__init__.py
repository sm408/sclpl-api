"""Files as *paths*, not as contents.

The built-in `read_csv` / `save_json` family is about formats. This is about the other
half: what exists, how big it is, and moving it around. A workflow that writes a report
and then archives yesterday's needs both, and neither belongs inside the other.

Public API only, like every bundled plugin.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sclpl.ext.api import ValidationError, connector


def register() -> None:
    """Called once at load. The decorators have already run on import."""


def _described(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "name": path.name,
        "suffix": path.suffix,
        "bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        "is_dir": path.is_dir(),
    }


@connector("fs.glob")
def glob(pattern: str, *, recursive: bool = False) -> list[dict[str, Any]]:
    """Paths matching a pattern, sorted, with size and mtime.

    Returns records rather than strings, so the result can go straight into `sort_by` or
    a `foreach` without a second step to look each one up.

    An empty match is an empty list, not an error: "no files today" is a normal answer,
    and the workflow can `assert_rowcount` if it disagrees.
    """
    base = Path(pattern)
    root = base.parent if str(base.parent) != "." else Path()
    found = root.rglob(base.name) if recursive else root.glob(base.name)
    return [_described(path) for path in sorted(found)]


@connector("fs.stat")
def stat(path: str) -> dict[str, Any]:
    """What is known about one path."""
    target = Path(path)
    if not target.exists():
        raise ValidationError(
            f"{path} does not exist",
            remedies=["fs.exists tells you without failing"],
        )
    return _described(target)


@connector("fs.exists")
def exists(path: str) -> bool:
    """Whether a path is there. Never raises -- that is the point of it."""
    return Path(path).exists()


@connector("fs.copy", lane="thread")
def copy(source: str, target: str, *, overwrite: bool = True) -> str:
    """Copy a file, creating the destination's directory. Returns the new path."""
    destination = Path(target)
    if destination.exists() and not overwrite:
        raise ValidationError(
            f"{target} already exists",
            remedies=["pass overwrite=true to replace it"],
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(source), destination)
    return str(destination)


@connector("fs.move", lane="thread")
def move(source: str, target: str) -> str:
    """Move or rename a file. Returns the new path."""
    destination = Path(target)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(Path(source)), str(destination))
    return str(destination)


@connector("fs.remove")
def remove(path: str, *, directory: bool = False) -> dict[str, Any]:
    """Delete a path. A directory needs `directory=true`, said out loud.

    Removing a tree by accident is not recoverable, and the difference between a file
    and a directory is one character in a glob. Asking for it explicitly costs a word
    and buys the difference between a mistake and a disaster.
    """
    target = Path(path)
    if not target.exists():
        return {"removed": False, "path": path}
    if target.is_dir():
        if not directory:
            raise ValidationError(
                f"{path} is a directory",
                remedies=["pass directory=true if that is what you meant"],
            )
        shutil.rmtree(target)
    else:
        target.unlink()
    return {"removed": True, "path": path}


@connector("fs.mkdir")
def mkdir(path: str) -> str:
    """Create a directory and its parents. Returns the path."""
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return str(target)
