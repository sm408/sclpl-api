"""Small OS-backed locks for short project metadata mutations and output ownership."""

from __future__ import annotations

import contextlib
import os
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from sclpl.errors import ValidationError


@dataclass(slots=True)
class Lock:
    """An advisory lock with a bounded wait and readable owner information."""

    path: Path
    timeout: float = 2.0
    _handle: BinaryIO | None = None

    def __enter__(self) -> Lock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        deadline = time.monotonic() + self.timeout
        while True:
            if _try_lock(handle):
                owner = f"pid={os.getpid()}"
                handle.seek(0)
                handle.truncate()
                handle.write(f"{owner}\n".encode())
                handle.flush()
                self._owner_path.write_text(owner + "\n", encoding="utf-8")
                self._handle = handle
                return self
            if time.monotonic() >= deadline:
                owner = _owner(self._owner_path)
                handle.close()
                raise ValidationError(
                    f"timed out waiting for project mutation lock {self.path.name}",
                    remedies=[f"current owner: {owner}", "wait for the other operation to finish"],
                )
            time.sleep(0.05)

    def __exit__(self, *args: object) -> None:
        if self._handle is not None:
            _unlock(self._handle)
            self._handle.close()
            self._handle = None
            self._owner_path.unlink(missing_ok=True)

    @property
    def _owner_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".owner")


def _try_lock(handle: BinaryIO) -> bool:
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl: Any = __import__("fcntl")

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(handle: BinaryIO) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl: Any = __import__("fcntl")

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _owner(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        return "unknown"


#: C5 -- output ownership. Two runs targeting different destinations must never wait
#: on each other; two racing the same one must. The lock lives beside the destination
#: itself, not in a project-wide registry, because a managed output need not be inside
#: any project at all (a standalone `run --out /tmp/report.csv`).
_OUTPUT_SUFFIX = ".sclpl-lock"


def canonical_path(path: Path) -> Path:
    """A destination path, resolved and case-folded, so two names for the same file
    on disk collide in the lock even when the strings that produced them did not.

    `Path.resolve()` follows symlinks and collapses `..`; Windows filesystems are
    ordinarily case-insensitive regardless of what case a workflow happened to type,
    so the comparison folds case there and nowhere else.
    """
    resolved = path.expanduser().resolve()
    return Path(str(resolved).lower()) if os.name == "nt" else resolved


def output_lock_path(path: Path) -> Path:
    """Where the advisory lock for ``path`` lives: beside it, not inside a registry."""
    canonical = canonical_path(path)
    return canonical.with_name(canonical.name + _OUTPUT_SUFFIX)


@contextlib.contextmanager
def output_locks(paths: Iterable[Path], *, timeout: float = 30.0) -> Iterator[None]:
    """Hold exclusive ownership of every path in ``paths`` for the block's duration.

    Locks are canonicalized, deduplicated, and then acquired in one fixed order --
    sorted by their canonical form -- regardless of the order the caller listed them
    in. Two runs racing the same two outputs always try to acquire them in the same
    order, so neither can hold one while waiting on the other (the classic deadlock
    a per-resource lock invites the moment more than one resource is involved).
    """
    ordered = sorted({canonical_path(path) for path in paths}, key=str)
    with contextlib.ExitStack() as stack:
        for canonical in ordered:
            stack.enter_context(Lock(canonical.with_name(canonical.name + _OUTPUT_SUFFIX), timeout))
        yield
