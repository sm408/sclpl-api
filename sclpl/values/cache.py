"""Not doing the same work twice.

A cache entry is keyed by everything that could change the answer and nothing else. The
"nothing else" is the part that takes care: a key that includes the mode would mean a
`partial` run and a `full` run never share the fetch they have in common, which is
exactly the case a cache is for.

**What goes into the key** (SPEC section 12):

    blake2b(step_kind, method, resolved_url, sorted_query, body_digest,
            headers_minus_volatile, function_name, function_version,
            input_value_digests, plugin_version, engine_version,
            credential_identity_salt)

The last one is a hash *of* the credential, never the credential. Two people running the
same workflow against the same API with different tokens must not read each other's
entries -- they may be different tenants -- but the token itself has no business being
part of a filename.

**Volatile headers are excluded** -- `Date`, `Authorization`, `User-Agent`, a request id.
Including them would make every key unique, which is a cache that never hits.

**Five flags**, and what each means:

| Flag | Read | Write | A miss |
|---|:-:|:-:|---|
| *(default)* | yes | yes | do the work |
| `--refresh` | no | yes | do the work, replace what was there |
| `--no-cache` | no | no | do the work |
| `--offline` | yes | no | **exit 5** -- the point is to not touch the network |
| `--http-cache` | yes | yes | revalidate with ETag; a 304 counts as a hit |

**Storage** is content-addressed blobs plus a SQLite index. The blob name is the digest
of its own contents, so two steps that produce the same value share one file, and a
half-written blob can never be mistaken for a good one -- its name would not match.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sclpl.errors import EXIT_CACHE_MISS, SclplError
from sclpl.values.digest import digest as digest_of

#: Headers that differ between two identical requests. Keying on them is keying on
#: nothing.
VOLATILE_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "date",
        "user-agent",
        "x-request-id",
        "x-correlation-id",
        "traceparent",
        "if-none-match",
        "if-modified-since",
    }
)

#: Bumped when the engine changes how a step's value is computed. Every existing entry
#: becomes unreachable, which is the point: a stale answer is worse than a slow one.
ENGINE_VERSION = 1

DEFAULT_TTL = 24 * 60 * 60
DEFAULT_MAX_BYTES = 2 * 1024**3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    key        TEXT PRIMARY KEY,
    blob       TEXT NOT NULL,
    bytes      INTEGER NOT NULL,
    created    REAL NOT NULL,
    accessed   REAL NOT NULL,
    hits       INTEGER NOT NULL DEFAULT 0,
    expires    REAL,
    etag       TEXT,
    modified   TEXT,
    step       TEXT
);
CREATE INDEX IF NOT EXISTS entries_accessed ON entries(accessed);
CREATE INDEX IF NOT EXISTS entries_expires ON entries(expires);
"""


@dataclass(frozen=True, slots=True)
class Policy:
    """What this run is allowed to do with the cache."""

    read: bool = True
    write: bool = True
    #: A miss is exit 5 rather than doing the work.
    require_hit: bool = False
    #: Revalidate with ETag / Last-Modified rather than trusting the TTL.
    revalidate: bool = False

    @classmethod
    def from_flags(
        cls,
        *,
        no_cache: bool = False,
        refresh: bool = False,
        offline: bool = False,
        http_cache: bool = False,
    ) -> Policy:
        if no_cache:
            return cls(read=False, write=False)
        if offline:
            return cls(read=True, write=False, require_hit=True)
        if refresh:
            return cls(read=False, write=True)
        return cls(read=True, write=True, revalidate=http_cache)

    @property
    def enabled(self) -> bool:
        return self.read or self.write


@dataclass(slots=True)
class Entry:
    """One cached value, and what the HTTP layer needs to revalidate it."""

    key: str
    value: Any
    etag: str | None = None
    modified: str | None = None
    age: float = 0.0
    #: False for a past-TTL entry returned only because the policy allows
    #: revalidating it with the server instead of an outright miss. The caller must
    #: check with the origin (a conditional request) before trusting the value.
    fresh: bool = True


@dataclass(slots=True)
class Stats:
    hits: int = 0
    misses: int = 0
    writes: int = 0
    evicted: int = 0
    bytes_written: int = 0

    def summary(self) -> str:
        total = self.hits + self.misses
        rate = f"{self.hits / total:.0%}" if total else "-"
        return f"cache {self.hits} hit / {self.misses} miss ({rate})"


def key_for(
    *,
    step_kind: str,
    method: str | None = None,
    url: str | None = None,
    query: dict[str, Any] | None = None,
    body: Any = None,
    headers: dict[str, str] | None = None,
    function: str | None = None,
    function_version: int = 1,
    inputs: Iterable[str] = (),
    plugin_version: str = "",
    credential: str | None = None,
) -> str:
    """The cache key for one step.

    **Mode is deliberately absent.** A `partial` run and a `full` run share every step
    they have in common, which is most of the value a cache has in a workflow tool.
    """
    hasher = hashlib.blake2b(digest_size=32)

    def feed(label: str, value: Any) -> None:
        hasher.update(label.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(json.dumps(value, sort_keys=True, default=str).encode("utf-8"))
        hasher.update(b"\x1e")

    feed("kind", step_kind)
    feed("method", (method or "").upper())
    feed("url", url or "")
    feed("query", sorted((query or {}).items()))
    feed("body", digest_of(body) if body is not None else "")
    feed(
        "headers",
        sorted(
            (name.lower(), value)
            for name, value in (headers or {}).items()
            if name.lower() not in VOLATILE_HEADERS
        ),
    )
    feed("function", function or "")
    feed("function_version", function_version)
    feed("inputs", sorted(inputs))
    feed("plugin_version", plugin_version)
    feed("engine", ENGINE_VERSION)
    # A hash of the credential, never the credential. Different tokens may be different
    # tenants, and must not share entries.
    feed("credential", _salt(credential) if credential else "")
    return hasher.hexdigest()


def _salt(credential: str) -> str:
    return hashlib.blake2b(credential.encode("utf-8"), digest_size=16).hexdigest()


class Cache:
    """Content-addressed blobs, with a SQLite index over them.

    The index is the source of truth about what exists; a blob without an index row is
    garbage from an interrupted write and is collected on the next prune. A row without
    a blob is a miss, which is safe -- the work is simply done again.
    """

    __slots__ = ("_root", "_blobs", "_db", "_policy", "_ttl", "_max_bytes", "stats")

    def __init__(
        self,
        root: Path,
        *,
        policy: Policy | None = None,
        ttl: int | None = DEFAULT_TTL,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        self._root = root
        self._blobs = root / "blobs"
        self._policy = policy or Policy()
        self._ttl = ttl
        self._max_bytes = max_bytes
        self.stats = Stats()

        self._blobs.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(root / "index.db", isolation_level=None)
        self._db.executescript(_SCHEMA)

    @property
    def policy(self) -> Policy:
        return self._policy

    def get(self, key: str) -> Entry | None:
        """The cached value for ``key``, or None. Expired entries are a miss."""
        if not self._policy.read:
            return None
        row = self._db.execute(
            "SELECT blob, created, expires, etag, modified FROM entries WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            self.stats.misses += 1
            return None

        blob, created, expires, etag, modified = row
        fresh = expires is None or expires > time.time()
        path = self._blobs / blob
        if not path.exists():
            # Index says yes, disk says no. Believe the disk.
            self._forget(key)
            self.stats.misses += 1
            return None

        if not fresh and not (self._policy.revalidate and (etag or modified)):
            # No validator to revalidate with is the same as no permission to: there
            # is nothing to send the server, so this is a plain miss either way.
            self.stats.misses += 1
            return None

        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._forget(key)
            self.stats.misses += 1
            return None

        self._db.execute(
            "UPDATE entries SET accessed = ?, hits = hits + 1 WHERE key = ?",
            (time.time(), key),
        )
        if fresh:
            self.stats.hits += 1
        return Entry(
            key=key,
            value=value,
            etag=etag,
            modified=modified,
            age=time.time() - created,
            fresh=fresh,
        )

    def put(
        self,
        key: str,
        value: Any,
        *,
        ttl: int | None = None,
        etag: str | None = None,
        modified: str | None = None,
        step: str = "",
    ) -> bool:
        """Store ``value``. False when the policy forbids it or it will not serialise."""
        if not self._policy.write:
            return False
        try:
            payload = json.dumps(value, default=str).encode("utf-8")
        except (TypeError, ValueError):
            # Not everything a step produces is JSON. A value that will not serialise is
            # not an error -- it simply is not cached, and the step runs next time.
            return False

        name = hashlib.blake2b(payload, digest_size=32).hexdigest()
        path = self._blobs / name
        if not path.exists():
            # Written beside and renamed, so a crash mid-write cannot leave a blob whose
            # name promises contents it does not have.
            scratch = path.with_suffix(".partial")
            scratch.write_bytes(payload)
            os.replace(scratch, path)

        lifetime = self._ttl if ttl is None else ttl
        now = time.time()
        self._db.execute(
            "INSERT OR REPLACE INTO entries"
            " (key, blob, bytes, created, accessed, hits, expires, etag, modified, step)"
            " VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)",
            (
                key,
                name,
                len(payload),
                now,
                now,
                None if lifetime is None else now + lifetime,
                etag,
                modified,
                step,
            ),
        )
        self.stats.writes += 1
        self.stats.bytes_written += len(payload)
        return True

    def prune(self) -> int:
        """Drop expired entries, then evict least-recently-used down to the size cap.

        Returns how many entries went. Called at the end of a run rather than on every
        write: eviction is bookkeeping, and doing it in the middle of a pipeline spends
        time the pipeline wanted.
        """
        now = time.time()
        removed = self._db.execute(
            "DELETE FROM entries WHERE expires IS NOT NULL AND expires <= ?", (now,)
        ).rowcount

        total = self._db.execute("SELECT COALESCE(SUM(bytes), 0) FROM entries").fetchone()[0]
        if total > self._max_bytes:
            rows = self._db.execute(
                "SELECT key, bytes FROM entries ORDER BY accessed ASC"
            ).fetchall()
            for key, size in rows:
                if total <= self._max_bytes:
                    break
                self._db.execute("DELETE FROM entries WHERE key = ?", (key,))
                total -= size
                removed += 1

        self._collect()
        self.stats.evicted += removed
        return removed

    def _collect(self) -> None:
        """Delete blobs no index row points at."""
        referenced = {
            row[0] for row in self._db.execute("SELECT DISTINCT blob FROM entries").fetchall()
        }
        for path in self._blobs.iterdir():
            if path.name not in referenced:
                path.unlink(missing_ok=True)

    def _forget(self, key: str) -> None:
        self._db.execute("DELETE FROM entries WHERE key = ?", (key,))

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> Cache:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


class Missing(SclplError):
    """`--offline` and nothing cached.

    Exit 5, not 1: the work was *refused*, not attempted and failed. A script running
    with `--offline` on purpose wants to tell those apart.
    """

    exit_code = EXIT_CACHE_MISS

    def __init__(self, step: str) -> None:
        super().__init__(
            f"step {step!r} is not in the cache, and --offline forbids fetching it",
            remedies=[
                "run once without --offline to populate the cache",
                "or drop --offline to let it fetch",
            ],
        )


def default_root() -> Path:
    """Where the cache lives when nobody said.

    Follows the platform's cache convention rather than inventing one, so it is where a
    user's cleanup tools already look.
    """
    override = os.environ.get("SCLPL_CACHE_DIR")
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
        return Path(base) / "sclpl" / "cache"
    xdg = os.environ.get("XDG_CACHE_HOME")
    return Path(xdg) / "sclpl" if xdg else Path.home() / ".cache" / "sclpl"
