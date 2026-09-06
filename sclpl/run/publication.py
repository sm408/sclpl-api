"""E8: stage declared outputs, then publish them together, or discard them together.

Opt-in via a project's `[outputs] publish = "validated"` (`project/outputs.py`); a
standalone workflow, or a project that declares nothing, keeps the pre-existing
immediate-write behavior unchanged -- a writer step's path is its real destination,
this module is never involved, and nothing here can be a compatibility break.

Reference dependencies alone are not a safe publication gate: a writer step and an
`assert`-bearing step can be entirely independent branches of the same workflow, with
no data relationship a graph-based check could ever see, yet the author still means
one to gate the other (SPEC 3.5). The only default that is actually safe is the plan's
own: nothing publishes unless the *whole run* finished without a single failure. A
writer step still runs and produces its value on the same schedule as before -- what
changes is that its value lands in a same-directory scratch file next to its real
destination, not the destination itself, until every other step in the run is known
to have succeeded. If the run fails, the scratch files are discarded and the
destination -- whatever a previous successful run left there -- is never touched.

Per-file replacement is atomic (`os.replace` within one directory, so it is a rename,
never a cross-filesystem copy); publishing several outputs together is not a single
transaction across files, since an OS offers no such primitive across arbitrary
paths. What this keeps a promise about instead is the generation manifest: written
only after every file in this generation actually moved, so a reader following it
never sees a generation the run did not really finish producing. If a later file's
replace fails partway through (disk full, a permissions change), the files already
moved stay moved, and the manifest is written over that smaller, still-real set,
recording which ports made it and which did not.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sclpl.state.db import default_root


@dataclass(slots=True)
class Ledger:
    """Where each declared output's writer actually wrote, for one run."""

    #: Port name -> its real destination.
    real: dict[str, Path] = field(default_factory=dict)
    #: Port name -> the scratch file its writer actually wrote to.
    staged: dict[str, Path] = field(default_factory=dict)

    def stage(self, port: str, destination: Path) -> Path:
        """The scratch path a writer for ``port`` should use instead of ``destination``.

        Idempotent per port within one run: a retried step must reuse the same
        scratch file rather than leaking a new one on every attempt.
        """
        existing = self.staged.get(port)
        if existing is not None:
            return existing
        scratch = _scratch_path(destination)
        self.real[port] = destination
        self.staged[port] = scratch
        return scratch


def _scratch_path(destination: Path) -> Path:
    """A same-directory sibling of ``destination``.

    Same directory, not a shared temp root: `os.replace` is only guaranteed atomic
    within one filesystem, and a path's own directory is the one place guaranteed to
    share it.
    """
    unique = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
    return destination.with_name(f".{destination.name}.staged-{unique}")


@dataclass(frozen=True, slots=True)
class PublicationResult:
    """What actually happened to a generation's staged files."""

    #: Ports whose scratch file was successfully moved to its real destination.
    published: tuple[str, ...] = ()
    #: Ports whose replace itself failed (disk full, permissions) -- their scratch
    #: file is left in place rather than guessed at further; the prior destination
    #: (if any) is untouched.
    interrupted: tuple[str, ...] = ()
    generation: str | None = None
    manifest_path: Path | None = None

    @property
    def ok(self) -> bool:
        return not self.interrupted


def publish(ledger: Ledger, *, workflow: str, run_id: str) -> PublicationResult:
    """Replace every real destination with its staged file, one rename at a time.

    Stable (sorted) port order, so which files land first is deterministic and
    reproducible in a test rather than a race between dict iteration and disk timing.
    """
    generation = f"{run_id}-{uuid.uuid4().hex[:8]}"
    published: list[str] = []
    interrupted: list[str] = []
    for port in sorted(ledger.staged):
        try:
            os.replace(ledger.staged[port], ledger.real[port])
        except OSError:
            interrupted.append(port)
            continue
        published.append(port)

    manifest_path = (
        _write_manifest(ledger, published, workflow, run_id, generation) if published else None
    )
    return PublicationResult(
        published=tuple(published),
        interrupted=tuple(interrupted),
        generation=generation if published else None,
        manifest_path=manifest_path,
    )


def discard(ledger: Ledger) -> tuple[str, ...]:
    """Remove every staged file. No real destination is ever touched by this."""
    discarded = tuple(sorted(ledger.staged))
    for scratch in ledger.staged.values():
        scratch.unlink(missing_ok=True)
    return discarded


def _manifest_root() -> Path:
    return default_root() / "publications"


def _write_manifest(
    ledger: Ledger, published: list[str], workflow: str, run_id: str, generation: str
) -> Path:
    """Write the generation manifest atomically -- a reader never sees a half-written one."""
    root = _manifest_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{workflow}.json"
    payload = {
        "workflow": workflow,
        "run_id": run_id,
        "generation": generation,
        "files": {port: str(ledger.real[port]) for port in published},
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    scratch = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    scratch.write_text(text, encoding="utf-8")
    os.replace(scratch, path)
    return path
