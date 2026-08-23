"""Spilled values.

A `ValueRef` stands in for a value that lives on disk instead of in memory. It knows
how to bring it back and it caches the result for the lifetime of the binding, so a
value read twice is read from disk once.

Rehydration is lazy and transparent: `ValueStore.get` resolves refs, so no step and no
operator ever has to know a value was spilled.
"""

from __future__ import annotations

import pickle
import shutil
import tempfile
import weakref
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Below this a spill costs more than it saves — the file, the syscalls, and the code
#: path are all more expensive than just holding the object.
MIN_SPILL_BYTES = 64 * 1024


class Scratch:
    """A temporary directory that cleans itself up.

    One per run. Registered with `weakref.finalize` rather than `__del__` so an
    interpreter shutdown mid-run still removes it.
    """

    __slots__ = ("_path", "_finalizer", "__weakref__")

    def __init__(self, parent: Path | None = None) -> None:
        self._path = Path(tempfile.mkdtemp(prefix="sclpl-", dir=parent))
        self._finalizer = weakref.finalize(self, shutil.rmtree, self._path, True)

    @property
    def path(self) -> Path:
        return self._path

    def file(self, name: str, suffix: str) -> Path:
        safe = "".join(char if char.isalnum() or char in "-_." else "_" for char in name)
        return self._path / f"{safe}{suffix}"

    def close(self) -> None:
        self._finalizer()


@dataclass(slots=True)
class ValueRef:
    """A value that currently lives at ``path``.

    ``rehydrate`` is the inverse of whatever wrote the file. Keeping it as a callable
    rather than a format enum means a table backend can supply its own without this
    module learning about it.
    """

    path: Path
    rehydrate: Callable[[Path], Any]
    size_bytes: int
    kind: str = "pickle"
    _cached: Any = field(default=None, repr=False)
    _loaded: bool = field(default=False, repr=False)

    def load(self) -> Any:
        if not self._loaded:
            self._cached = self.rehydrate(self.path)
            self._loaded = True
        return self._cached

    def drop(self) -> None:
        """Release the memoised copy and delete the file."""
        self._cached = None
        self._loaded = False
        self.path.unlink(missing_ok=True)

    def forget(self) -> None:
        """Release the memoised copy but keep the file, so it can be read again."""
        self._cached = None
        self._loaded = False


def spill(name: str, value: Any, scratch: Scratch) -> ValueRef:
    """Write ``value`` to scratch and return a reference to it.

    Tables go out as Parquet, which is columnar, compressed, and readable by anything.
    Everything else goes out as pickle protocol 5 with out-of-band buffers, which keeps
    large binary payloads from being copied on the way to the file.
    """
    to_parquet = getattr(value, "to_parquet", None)
    if callable(to_parquet):
        path = scratch.file(name, ".parquet")
        to_parquet(path)
        return ValueRef(
            path=path,
            rehydrate=_read_parquet,
            size_bytes=path.stat().st_size,
            kind="parquet",
        )

    path = scratch.file(name, ".pickle")
    buffers: list[pickle.PickleBuffer] = []
    payload = pickle.dumps(value, protocol=5, buffer_callback=buffers.append)
    with path.open("wb") as handle:
        handle.write(payload)
    if buffers:
        # Out-of-band buffers go into a sidecar so the main payload stays small.
        sidecar = path.with_suffix(".buffers")
        with sidecar.open("wb") as handle:
            for buffer in buffers:
                data = buffer.raw()
                handle.write(len(data).to_bytes(8, "little"))
                handle.write(data)
    return ValueRef(
        path=path,
        rehydrate=_read_pickle,
        size_bytes=path.stat().st_size,
        kind="pickle",
    )


def _read_pickle(path: Path) -> Any:
    sidecar = path.with_suffix(".buffers")
    buffers: list[bytes] = []
    if sidecar.exists():
        with sidecar.open("rb") as handle:
            while header := handle.read(8):
                length = int.from_bytes(header, "little")
                buffers.append(handle.read(length))
    with path.open("rb") as handle:
        return pickle.loads(handle.read(), buffers=buffers or None)


#: Format name -> how to read it back. `tables/` registers "parquet" when it loads, so
#: this module never imports it: spilling knows how to write a Table only because the
#: object offered `to_parquet`, and it should learn how to read one the same way.
READERS: dict[str, Callable[[Path], Any]] = {}


def register_reader(kind: str, reader: Callable[[Path], Any]) -> None:
    READERS[kind] = reader


def _read_parquet(path: Path) -> Any:
    reader = READERS.get("parquet")
    if reader is None:
        raise RuntimeError(
            f"{path.name} was spilled as Parquet but no table backend is loaded to read "
            "it back. Install the data extra: pip install 'sclpl[data]'"
        )
    return reader(path)


def size_of(value: Any) -> int:
    """A cheap, deliberately approximate size in bytes.

    Exactness is not worth a deep walk of every object on every put. This is used to
    decide whether spilling is worth it and to report freed memory, and both tolerate
    being wrong by a factor of two.
    """
    nbytes = getattr(value, "nbytes", None)
    if isinstance(nbytes, int):
        return nbytes
    match value:
        case None | bool() | int() | float():
            return 8
        case str():
            return len(value) * 2 + 48
        case bytes() | bytearray():
            return len(value) + 32
        case list() | tuple() | set() | frozenset():
            items = list(value)
            sample = items[:64]
            if not sample:
                return 56
            average = sum(size_of(item) for item in sample) / len(sample)
            return int(average * len(items)) + 56
        case dict():
            keys = list(value)
            sample = keys[:64]
            if not sample:
                return 64
            average = sum(size_of(key) + size_of(value[key]) for key in sample) / len(sample)
            return int(average * len(keys)) + 64
        case _:
            return 512
