"""Event dataclasses — the reporter protocol.

The engine emits these; it never writes to a terminal (invariants 1 and 4). Every sink
in this package consumes the same stream, so adding a presentation never means adding a
call site in the engine.

Field names are normative — they are the wire format of the ``--json`` sink and of the
per-run NDJSON log, so renaming one is a breaking change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

Status: TypeAlias = Literal["ok", "failed", "skipped", "cancelled"]
Level: TypeAlias = Literal["debug", "info", "warning", "error"]
Lane: TypeAlias = Literal["async", "thread", "process", "serial"]


@dataclass(frozen=True, slots=True)
class RunStarted:
    workflow: str
    version: int = 1
    mode: str | None = None
    steps_total: int = 0
    steps_pruned: int = 0
    hosts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StepStarted:
    id: str
    kind: str
    lane: Lane = "async"


@dataclass(frozen=True, slots=True)
class StepProgress:
    """Incremental progress within a step: pages, rows, or bytes.

    ``total`` is ``None`` when the extent is not known ahead of time, which is the
    normal case for cursor pagination.
    """

    id: str
    detail: str
    current: int
    total: int | None = None


@dataclass(frozen=True, slots=True)
class StepFinished:
    id: str
    status: Status
    duration_ms: int
    summary: str = ""
    cached: bool = False


@dataclass(frozen=True, slots=True)
class StepRetrying:
    id: str
    attempt: int
    max: int
    reason: str
    delay_s: float


@dataclass(frozen=True, slots=True)
class ValueFreed:
    name: str
    bytes: int


@dataclass(frozen=True, slots=True)
class ResourceWarning:
    kind: str
    current: int
    budget: int


@dataclass(frozen=True, slots=True)
class LogRecord:
    level: Level
    message: str
    step: str | None = None


@dataclass(frozen=True, slots=True)
class RunFinished:
    status: Status
    duration_ms: int
    counts: dict[str, int] = field(default_factory=dict)
    exit_code: int = 0


Event: TypeAlias = (
    RunStarted
    | StepStarted
    | StepProgress
    | StepFinished
    | StepRetrying
    | ValueFreed
    | ResourceWarning
    | LogRecord
    | RunFinished
)

#: Verbosity at which each event becomes visible. ``-1`` is ``-q`` (errors and the final
#: summary only); ``0`` is the default; ``1`` is ``-v`` and above. Sinks consult this
#: rather than each re-deriving the policy.
VERBOSITY: dict[type, int] = {
    RunStarted: 0,
    # A start line is redundant at the default level: the live region already shows
    # what is in flight, and the plain rung would print two lines per step.
    StepStarted: 1,
    StepProgress: 0,
    StepFinished: 0,
    StepRetrying: 1,
    ValueFreed: 1,
    ResourceWarning: -1,
    LogRecord: 0,
    RunFinished: -1,
}


def visible_at(event: Event, verbosity: int) -> bool:
    """Whether ``event`` should be shown at ``verbosity``.

    Errors are never suppressed above ``-qq``: a failure the user cannot see is a
    silent wrong answer.
    """
    if isinstance(event, LogRecord) and event.level == "error":
        return True
    if isinstance(event, StepFinished) and event.status == "failed":
        return True
    if isinstance(event, LogRecord):
        return verbosity >= _LOG_LEVEL_FLOOR[event.level]
    return verbosity >= VERBOSITY[type(event)]


_LOG_LEVEL_FLOOR: dict[Level, int] = {
    "error": -1,
    "warning": -1,
    "info": 0,
    "debug": 2,
}


def event_name(event: Event) -> str:
    """The discriminator written to NDJSON, e.g. ``step_finished``."""
    name = type(event).__name__
    out: list[str] = []
    for index, char in enumerate(name):
        if char.isupper() and index:
            out.append("_")
        out.append(char.lower())
    return "".join(out)


def as_dict(event: Event) -> dict[str, Any]:
    """A shallow JSON-ready mapping. Shallow is deliberate — no event nests."""
    fields = type(event).__dataclass_fields__
    payload: dict[str, Any] = {name: getattr(event, name) for name in fields}
    for key, value in payload.items():
        if isinstance(value, tuple):
            payload[key] = list(value)
    return payload
