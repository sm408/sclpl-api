"""G1: durable checkpoints for completed step values.

A checkpoint is only ever "reusable" once both halves of writing it are durably on
disk: the blob (written beside its final name and atomically renamed into place,
never left half-written where a crash could leave it) and a metadata row in SQLite
recording it. The two are ordered on purpose -- write the blob, *then* commit the
row -- so a process death between them leaves an orphaned blob and no row naming it,
which `read()` (and G2's later eligibility planning) simply never sees: it only ever
asks the metadata table what exists, never the filesystem directly.

Only two shapes are eligible: a `Table` (Parquet, which already keeps a value's
notion of columns and dtypes -- the same backend `values/ref.py`'s spill path
already trusts) and anything strict JSON can hold without inventing a fallback
encoding for what it cannot (a plain `json.dumps` with no `default=`, so a shape
JSON has no honest representation for is refused, not silently stringified).
Everything else is simply not checkpointed -- `write()` returns `None` rather than
raising, and the step that produced it re-runs on resume, which is always correct.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sclpl.state import migrations
from sclpl.state.db import default_root, file_digest, now
from sclpl.tables.base import Table

_SCHEMA = """
CREATE TABLE IF NOT EXISTS checkpoints (
  run_id TEXT NOT NULL,
  step_id TEXT NOT NULL,
  format TEXT NOT NULL,
  path TEXT NOT NULL,
  digest TEXT NOT NULL,
  committed_at TEXT NOT NULL,
  PRIMARY KEY (run_id, step_id)
);
"""


@dataclass(frozen=True, slots=True)
class Checkpoint:
    """One step's durably committed value, as of the moment it was written."""

    run_id: str
    step_id: str
    format: str
    path: Path
    digest: str
    committed_at: str


def _format_of(value: Any) -> str | None:
    """`"parquet"`, `"json"`, or `None` for a value neither format can honestly hold."""
    if isinstance(value, Table):
        return "parquet"
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return None
    return "json"


class Store:
    """Where a run's eligible step values are durably kept, for a later resume."""

    __slots__ = ("_root", "_db")

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or (default_root() / "checkpoints")
        self._root.mkdir(parents=True, exist_ok=True)
        db_path = self._root / "checkpoints.db"
        migrations.migrate(db_path, _SCHEMA)
        self._db = sqlite3.connect(db_path, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")

    def eligible(self, value: Any) -> bool:
        return _format_of(value) is not None

    def write(self, run_id: str, step_id: str, value: Any) -> Checkpoint | None:
        """Durably checkpoint ``value``, or ``None`` for an unsupported type.

        A `Checkpoint` is only ever returned once the blob has already been
        renamed into place *and* the metadata row naming it has committed --
        never partway through either step, including on cancellation, which is
        a `BaseException` a plain `except Exception` would not see.
        """
        fmt = _format_of(value)
        if fmt is None:
            return None
        destination = self._blob_path(run_id, step_id, fmt)
        destination.parent.mkdir(parents=True, exist_ok=True)
        scratch = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
        done = False
        try:
            if fmt == "parquet":
                assert isinstance(value, Table)
                value.to_parquet(scratch)
            else:
                scratch.write_text(json.dumps(value), encoding="utf-8")
            os.replace(scratch, destination)
            done = True
        finally:
            if not done:
                scratch.unlink(missing_ok=True)

        digest = file_digest(destination)
        committed_at = now()
        self._db.execute(
            "INSERT OR REPLACE INTO checkpoints"
            " (run_id, step_id, format, path, digest, committed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, step_id, fmt, str(destination), digest, committed_at),
        )
        return Checkpoint(run_id, step_id, fmt, destination, digest, committed_at)

    def exists(self, run_id: str, step_id: str) -> bool:
        """Whether a durably committed, still-valid checkpoint is there -- without
        paying to deserialize it.

        The only way to tell "nothing was ever checkpointed" apart from "the
        checkpointed value was itself JSON `null`", which `read()` alone cannot
        distinguish -- both come back as `None`. G2's resume planning needs the
        former without loading a potentially large table just to answer it.
        """
        row = self._db.execute(
            "SELECT path, digest FROM checkpoints WHERE run_id = ? AND step_id = ?",
            (run_id, step_id),
        ).fetchone()
        if row is None:
            return False
        path = Path(row["path"])
        return path.is_file() and file_digest(path) == row["digest"]

    def read(self, run_id: str, step_id: str) -> Any:
        """The checkpointed value, or a sentinel-free ``None`` if there is none.

        Re-hashes the blob before trusting it: a committed row whose file has
        since changed on disk -- or vanished -- is not the value that was
        actually checkpointed, and reusing it anyway would silently resume from
        data that was never durably confirmed as what this run produced.
        """
        row = self._db.execute(
            "SELECT * FROM checkpoints WHERE run_id = ? AND step_id = ?", (run_id, step_id)
        ).fetchone()
        if row is None:
            return None
        path = Path(row["path"])
        if not path.is_file() or file_digest(path) != row["digest"]:
            return None
        if row["format"] == "parquet":
            return Table.read(path, "parquet")
        return json.loads(path.read_text(encoding="utf-8"))

    def discard(self, run_id: str) -> None:
        """Forget every checkpoint a run wrote, and remove their blobs."""
        rows = self._db.execute(
            "SELECT path FROM checkpoints WHERE run_id = ?", (run_id,)
        ).fetchall()
        self._db.execute("DELETE FROM checkpoints WHERE run_id = ?", (run_id,))
        for row in rows:
            Path(row["path"]).unlink(missing_ok=True)

    def _blob_path(self, run_id: str, step_id: str, fmt: str) -> Path:
        extension = "parquet" if fmt == "parquet" else "json"
        return self._root / run_id / f"{step_id}.{extension}"

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
