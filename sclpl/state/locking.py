"""Small OS-backed locks for short project metadata mutations."""

from __future__ import annotations

import os
import time
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
