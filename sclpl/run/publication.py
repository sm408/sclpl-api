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

import contextlib
import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sclpl.state.db import default_root, file_digest


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

    G4: a durable record of this generation's intent -- every port's scratch path,
    destination, and content digest -- is written *before* the first file moves.
    A crash between committing one file and the next leaves that record behind
    (it is only ever removed once this loop actually finishes, success or partial
    failure alike); `recover()` is what a later, separate invocation reads to tell
    "already committed" from "never touched" per port, without this process ever
    getting to say what happened.
    """
    generation = f"{run_id}-{uuid.uuid4().hex[:8]}"
    if ledger.staged:
        # Best-effort: a generation `recover()` cannot later reconstruct is a
        # strictly worse debugging position than today's, but it must never be a
        # *new* reason this run's actual outputs fail to publish.
        with contextlib.suppress(OSError):
            _write_pending(ledger, workflow, run_id, generation)
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
    if ledger.staged:
        with contextlib.suppress(OSError):
            _pending_path(workflow, generation).unlink(missing_ok=True)
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


def _read_manifest(workflow: str) -> dict[str, Any] | None:
    path = _manifest_root() / f"{workflow}.json"
    if not path.is_file():
        return None
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload


def _pending_path(workflow: str, generation: str) -> Path:
    """Keyed by generation, not just workflow: two generations can be interrupted
    without either overwriting the other's evidence before `recover()` sees it --
    which a single shared `{workflow}.pending.json` would silently do the moment
    an unrelated, later publish for the same workflow started.
    """
    return _manifest_root() / f"{workflow}.{generation}.pending.json"


def _pending_paths(workflow: str) -> list[Path]:
    """Every unresolved generation's intent record for ``workflow``, oldest first."""
    root = _manifest_root()
    if not root.is_dir():
        return []
    return sorted(root.glob(f"{workflow}.*.pending.json"), key=lambda path: path.name)


def _write_pending(ledger: Ledger, workflow: str, run_id: str, generation: str) -> None:
    """The intent `publish()` is about to act on, durable before the first move.

    Every port's digest is of its *scratch* file, taken now, before anything
    moves -- the one moment both the pre-commit content and a stable path to it
    are guaranteed to exist together.
    """
    root = _manifest_root()
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "workflow": workflow,
        "run_id": run_id,
        "generation": generation,
        "ports": {
            port: {
                "staged": str(ledger.staged[port]),
                "destination": str(ledger.real[port]),
                "digest": file_digest(ledger.staged[port]),
            }
            for port in sorted(ledger.staged)
        },
    }
    path = _pending_path(workflow, generation)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    scratch = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    scratch.write_text(text, encoding="utf-8")
    os.replace(scratch, path)


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    """What a crash-recovery pass against a workflow's last publish attempt found."""

    #: Whether an interrupted generation's intent record was even there to read.
    found: bool
    #: Ports whose replace had not yet happened, and were completed just now.
    completed: tuple[str, ...] = ()
    #: Ports whose replace had already happened before the crash -- verified by
    #: digest, not merely assumed because the scratch file was gone.
    already_committed: tuple[str, ...] = ()
    #: A committed port whose destination no longer matches the digest recorded
    #: at intent time -- something else touched it since. Never silently trusted.
    tampered: tuple[str, ...] = ()
    #: A newer generation has published since the crash; completing the old,
    #: interrupted one now could overwrite it. Nothing is touched.
    ambiguous: bool = False
    generation: str | None = None
    manifest_path: Path | None = None

    @property
    def ok(self) -> bool:
        return self.found and not self.tampered and not self.ambiguous


def pending_destinations(workflow: str) -> list[Path]:
    """Destinations the oldest unresolved generation for ``workflow`` would touch.

    For a caller to lock before calling `recover()` -- reading this is not itself
    safe to act on, since another process could resolve or replace the same
    record between the two calls; the lock is what makes the sequence safe, not
    this function.
    """
    candidates = _pending_paths(workflow)
    if not candidates:
        return []
    payload = json.loads(candidates[0].read_text(encoding="utf-8"))
    ports: dict[str, dict[str, str]] = payload["ports"]
    return [Path(info["destination"]) for info in ports.values()]


def recover(workflow: str) -> RecoveryReport:
    """Complete or report on whatever ``workflow``'s last publish left behind.

    Never touches anything for a workflow whose last `publish()` call returned
    normally -- the intent record `publish()` itself writes is removed the
    moment its own loop finishes, success or partial failure alike. Its mere
    presence means the process that started this generation never got to say
    what happened to it; this is what says it instead, from the one place a
    crash cannot also have erased: the filesystem itself.

    Caller's responsibility: hold the same C5 output locks this generation's
    own destinations would need, for the same reason a run does -- so recovery
    never races a concurrent run or another recovery attempt over the same files.

    Handles the oldest unresolved generation per call, not all of them at once
    -- ordinarily there is at most one, but nothing prevents more than one crash
    accumulating before anyone looks; call again to work through the rest.
    """
    candidates = _pending_paths(workflow)
    if not candidates:
        return RecoveryReport(found=False)
    path = candidates[0]
    payload = json.loads(path.read_text(encoding="utf-8"))
    generation: str = payload["generation"]
    run_id: str = payload["run_id"]
    ports: dict[str, dict[str, str]] = payload["ports"]

    current = _read_manifest(workflow)
    if current is not None and current.get("generation") != generation:
        # Something has published *since* the crash. Finishing this older,
        # interrupted generation now could stomp a newer, complete one with a
        # partial one -- an ambiguous fixed-path commit, reported rather than
        # guessed at. The stale record itself is left alone too: it is the
        # only evidence of what actually happened, until someone looks at it.
        return RecoveryReport(found=True, ambiguous=True, generation=generation)

    completed: list[str] = []
    already_committed: list[str] = []
    tampered: list[str] = []
    destinations: dict[str, Path] = {}
    for port, info in sorted(ports.items()):
        staged = Path(info["staged"])
        destination = Path(info["destination"])
        destinations[port] = destination
        if staged.is_file():
            try:
                os.replace(staged, destination)
            except OSError:
                continue
            completed.append(port)
        elif file_digest(destination) == info["digest"]:
            already_committed.append(port)
        else:
            tampered.append(port)

    settled = completed + already_committed
    manifest_path = None
    if settled:
        ledger = Ledger(real={port: destinations[port] for port in settled})
        manifest_path = _write_manifest(ledger, settled, workflow, run_id, generation)
    path.unlink(missing_ok=True)
    return RecoveryReport(
        found=True,
        completed=tuple(completed),
        already_committed=tuple(already_committed),
        tampered=tuple(tampered),
        generation=generation,
        manifest_path=manifest_path,
    )
