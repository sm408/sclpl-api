"""What happened, kept so it can be asked about later.

Every run writes a row, its steps, its ports, and a **self-contained NDJSON event log**
beside the database. The log matters as much as the table: history you can only reach
through a query language is history most people will not reach at all, and `grep` is
the tool everyone already has.

Retention defaults to **5** (locked decision 5). Pinned runs are exempt *and not
counted*, so pinning three does not silently evict everything else -- a pin means "keep
this", not "spend the budget on this".

`sqlite3` rather than `aiosqlite`: a run writes here once, at the end, when there is
nothing left to block. An async driver would buy nothing and cost a dependency.
"""

from __future__ import annotations

import os
import sqlite3
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sclpl.errors import ValidationError, did_you_mean
from sclpl.state import migrations

KEEP_DEFAULT = 5

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  workflow TEXT NOT NULL,
  workflow_version INTEGER NOT NULL DEFAULT 1,
  mode TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  duration_ms INTEGER,
  status TEXT NOT NULL,
  exit_code INTEGER,
  steps_run INTEGER DEFAULT 0,
  steps_skipped INTEGER DEFAULT 0,
  steps_failed INTEGER DEFAULT 0,
  retries INTEGER DEFAULT 0,
  cache_hits INTEGER DEFAULT 0,
  cache_misses INTEGER DEFAULT 0,
  peak_rss_bytes INTEGER DEFAULT 0,
  bytes_in INTEGER DEFAULT 0,
  bytes_out INTEGER DEFAULT 0,
  env TEXT,
  pinned INTEGER NOT NULL DEFAULT 0,
  log_path TEXT,
  argv TEXT
);
CREATE TABLE IF NOT EXISTS run_tags (run_id TEXT, tag TEXT);
CREATE TABLE IF NOT EXISTS run_ports (
  run_id TEXT, direction TEXT, name TEXT, path TEXT, digest TEXT
);
CREATE TABLE IF NOT EXISTS run_steps (
  run_id TEXT, step_id TEXT, status TEXT, lane TEXT,
  duration_ms INTEGER, attempts INTEGER DEFAULT 1, error TEXT, cached INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS runs_started ON runs(started_at DESC);
CREATE INDEX IF NOT EXISTS run_steps_run ON run_steps(run_id);
CREATE INDEX IF NOT EXISTS run_tags_run ON run_tags(run_id);
"""


@dataclass(slots=True)
class StepRecord:
    """One step of one run."""

    step_id: str
    status: str
    lane: str = "async"
    duration_ms: int = 0
    attempts: int = 1
    error: str = ""
    cached: bool = False


@dataclass(slots=True)
class RunRecord:
    """One run, as it will be stored."""

    id: str
    name: str
    workflow: str
    status: str = "running"
    workflow_version: int = 1
    mode: str | None = None
    started_at: str = ""
    finished_at: str | None = None
    duration_ms: int = 0
    exit_code: int = 0
    steps_run: int = 0
    steps_skipped: int = 0
    steps_failed: int = 0
    retries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    peak_rss_bytes: int = 0
    bytes_in: int = 0
    bytes_out: int = 0
    env: str | None = None
    pinned: bool = False
    log_path: str | None = None
    argv: str = ""
    tags: list[str] = field(default_factory=list)
    ports: list[tuple[str, str, str, str]] = field(default_factory=list)
    steps: list[StepRecord] = field(default_factory=list)


def default_root() -> Path:
    override = os.environ.get("SCLPL_HOME")
    return Path(override) if override else Path.home() / ".sclpl"


def run_id(workflow: str, started: float) -> str:
    """A short hash. Short enough to type, long enough not to collide in a lifetime."""
    import hashlib

    seed = f"{workflow}:{started}:{os.getpid()}".encode()
    return hashlib.blake2b(seed, digest_size=4).hexdigest()


def default_name(workflow: str, mode: str | None, when: datetime | None = None) -> str:
    """`orders-partial-0821-1432`. Readable, sortable, and unique enough per minute."""
    moment = when or datetime.now(UTC)
    parts = [workflow]
    if mode:
        parts.append(mode)
    parts.append(moment.strftime("%m%d-%H%M"))
    return "-".join(parts)


class History:
    """The run database, and the NDJSON logs beside it."""

    __slots__ = ("_root", "_db", "_logs")

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or default_root()
        self._logs = self._root / "logs"
        self._logs.mkdir(parents=True, exist_ok=True)
        path = self._root / "history.db"
        migrations.migrate(path, _SCHEMA)
        self._db = sqlite3.connect(path, isolation_level=None)
        self._db.row_factory = sqlite3.Row

    # -- writing -----------------------------------------------------------------

    def record(self, run: RunRecord) -> None:
        """Store a finished run, its steps, its ports, and its tags."""
        columns = [
            "id", "name", "workflow", "workflow_version", "mode", "started_at",
            "finished_at", "duration_ms", "status", "exit_code", "steps_run",
            "steps_skipped", "steps_failed", "retries", "cache_hits", "cache_misses",
            "peak_rss_bytes", "bytes_in", "bytes_out", "env", "pinned", "log_path",
            "argv",
        ]  # fmt: skip
        values = [getattr(run, name) for name in columns]
        values[columns.index("pinned")] = int(run.pinned)
        self._db.execute(
            f"INSERT OR REPLACE INTO runs ({', '.join(columns)})"
            f" VALUES ({', '.join('?' for _ in columns)})",
            values,
        )
        self._db.execute("DELETE FROM run_tags WHERE run_id = ?", (run.id,))
        self._db.executemany(
            "INSERT INTO run_tags (run_id, tag) VALUES (?, ?)",
            [(run.id, tag) for tag in run.tags],
        )
        self._db.execute("DELETE FROM run_ports WHERE run_id = ?", (run.id,))
        self._db.executemany(
            "INSERT INTO run_ports (run_id, direction, name, path, digest) VALUES (?, ?, ?, ?, ?)",
            [(run.id, *port) for port in run.ports],
        )
        self._db.execute("DELETE FROM run_steps WHERE run_id = ?", (run.id,))
        self._db.executemany(
            "INSERT INTO run_steps"
            " (run_id, step_id, status, lane, duration_ms, attempts, error, cached)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    run.id,
                    step.step_id,
                    step.status,
                    step.lane,
                    step.duration_ms,
                    step.attempts,
                    step.error,
                    int(step.cached),
                )
                for step in run.steps
            ],
        )

    def log_path(self, identifier: str) -> Path:
        """Where a run's NDJSON log lives. Greppable without the database."""
        return self._logs / f"{identifier}.ndjson"

    @contextmanager
    def log(self, identifier: str) -> Iterator[Any]:
        """Open a run's event log for writing."""
        path = self.log_path(identifier)
        handle = path.open("w", encoding="utf-8")
        try:
            yield handle
        finally:
            handle.close()

    # -- reading -----------------------------------------------------------------

    def recent(self, limit: int = 20, *, workflow: str | None = None) -> list[sqlite3.Row]:
        if workflow:
            return self._db.execute(
                "SELECT * FROM runs WHERE workflow = ? ORDER BY started_at DESC LIMIT ?",
                (workflow, limit),
            ).fetchall()
        return self._db.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()

    def find(self, identifier: str) -> sqlite3.Row:
        """One run, by id, by name, or by a unique prefix of either.

        A prefix, because the id is a hash and nobody wants to type eight characters
        correctly. An ambiguous prefix lists the candidates rather than picking one.
        """
        exact: sqlite3.Row | None = self._db.execute(
            "SELECT * FROM runs WHERE id = ? OR name = ?", (identifier, identifier)
        ).fetchone()
        if exact is not None:
            return exact

        matches: list[sqlite3.Row] = self._db.execute(
            "SELECT * FROM runs WHERE id LIKE ? OR name LIKE ? ORDER BY started_at DESC",
            (f"{identifier}%", f"{identifier}%"),
        ).fetchall()
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValidationError(
                f"{identifier!r} matches {len(matches)} runs",
                remedies=[
                    "be more specific: " + ", ".join(row["id"] for row in matches[:5]),
                ],
            )

        known = [row["id"] for row in self.recent(50)] + [row["name"] for row in self.recent(50)]
        remedies = []
        suggestion = did_you_mean(identifier, known)
        if suggestion:
            remedies.append(suggestion)
        remedies.append("run 'sclpl runs list' to see what is there")
        raise ValidationError(f"no run matching {identifier!r}", remedies=remedies)

    def steps_of(self, run_identifier: str) -> list[sqlite3.Row]:
        return self._db.execute(
            "SELECT * FROM run_steps WHERE run_id = ? ORDER BY rowid", (run_identifier,)
        ).fetchall()

    def ports_of(self, run_identifier: str) -> list[sqlite3.Row]:
        return self._db.execute(
            "SELECT * FROM run_ports WHERE run_id = ? ORDER BY direction, name",
            (run_identifier,),
        ).fetchall()

    def tags_of(self, run_identifier: str) -> list[str]:
        return [
            row["tag"]
            for row in self._db.execute(
                "SELECT tag FROM run_tags WHERE run_id = ? ORDER BY tag", (run_identifier,)
            )
        ]

    def search(self, text: str, *, limit: int = 20) -> list[sqlite3.Row]:
        """Runs mentioning ``text`` in their name, workflow, mode, tags, or a step error.

        `LIKE` rather than FTS5: the corpus is a few hundred short rows, the query is
        one word, and requiring an FTS5 build would make history unavailable on the
        machines least likely to have one.
        """
        pattern = f"%{text}%"
        return self._db.execute(
            "SELECT DISTINCT r.* FROM runs r"
            " LEFT JOIN run_tags t ON t.run_id = r.id"
            " LEFT JOIN run_steps s ON s.run_id = r.id"
            " WHERE r.name LIKE ? OR r.workflow LIKE ? OR r.mode LIKE ?"
            "    OR t.tag LIKE ? OR s.error LIKE ?"
            " ORDER BY r.started_at DESC LIMIT ?",
            (pattern, pattern, pattern, pattern, pattern, limit),
        ).fetchall()

    # -- housekeeping ------------------------------------------------------------

    def pin(self, identifier: str, *, pinned: bool = True) -> str:
        row = self.find(identifier)
        self._db.execute("UPDATE runs SET pinned = ? WHERE id = ?", (int(pinned), row["id"]))
        return str(row["id"])

    def prune(self, keep: int = KEEP_DEFAULT) -> list[str]:
        """Drop all but the most recent ``keep`` runs. Pinned ones are exempt.

        And **not counted**: pinning three runs with `keep = 5` still leaves five
        unpinned. A pin means "keep this", not "spend the budget on this".
        """
        survivors = {
            row["id"]
            for row in self._db.execute(
                "SELECT id FROM runs WHERE pinned = 0 ORDER BY started_at DESC LIMIT ?",
                (max(0, keep),),
            )
        }
        doomed = [
            row["id"]
            for row in self._db.execute("SELECT id FROM runs WHERE pinned = 0")
            if row["id"] not in survivors
        ]
        for identifier in doomed:
            self._forget(identifier)
        return doomed

    def _forget(self, identifier: str) -> None:
        for table in ("run_tags", "run_ports", "run_steps"):
            self._db.execute(f"DELETE FROM {table} WHERE run_id = ?", (identifier,))
        self._db.execute("DELETE FROM runs WHERE id = ?", (identifier,))
        self.log_path(identifier).unlink(missing_ok=True)

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> History:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def compatible(left: sqlite3.Row, right: sqlite3.Row) -> bool:
    """F2: whether two runs are the same workflow in the same environment.

    A diff between an `orders` run and a `refunds` run, or `prod` against `staging`,
    is not "what changed" -- it is two unrelated things that happen to share columns.
    """
    return bool(left["workflow"] == right["workflow"] and left["env"] == right["env"])


def diff(left: sqlite3.Row, right: sqlite3.Row, *, steps: Iterable[Any] = ()) -> list[str]:
    """What changed between two runs, in the order it matters.

    Status first, then timing, then the counts. A run that failed where the other
    succeeded is the answer to "what changed"; a hundred milliseconds is not.
    """
    lines: list[str] = []
    for label, key in (
        ("status", "status"),
        ("exit code", "exit_code"),
        ("steps run", "steps_run"),
        ("steps failed", "steps_failed"),
        ("steps skipped", "steps_skipped"),
        ("cache hits", "cache_hits"),
        ("retries", "retries"),
        ("duration ms", "duration_ms"),
    ):
        before, after = left[key], right[key]
        if before != after:
            lines.append(f"  {label:<14} {before} -> {after}")
    del steps
    return lines


def as_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(zip(row.keys(), tuple(row), strict=True))


def export(history: History, identifier: str) -> dict[str, Any]:
    """One run, whole, as JSON. For sharing, or for a bug report."""
    row = history.find(identifier)
    return {
        "run": as_dict(row),
        "tags": history.tags_of(row["id"]),
        "ports": [as_dict(port) for port in history.ports_of(row["id"])],
        "steps": [as_dict(step) for step in history.steps_of(row["id"])],
    }


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def elapsed_ms(since: float) -> int:
    return int((time.perf_counter() - since) * 1000)
