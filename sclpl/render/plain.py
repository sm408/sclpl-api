"""The ``plain`` rung, and the ``quiet`` sink.

One line per event, no escape sequences, no cursor movement. This is what a pipe, a CI
log, a `dumb` terminal, and `--plain` all get. It is also the floor of the ladder: every
descent ends here, so it must never need anything from the terminal.
"""

from __future__ import annotations

import sys
from typing import TextIO

from sclpl.render.events import (
    Event,
    LogRecord,
    ResourceWarning,
    RunFinished,
    RunStarted,
    StepFinished,
    StepProgress,
    StepRetrying,
    StepStarted,
    ValueFreed,
    visible_at,
)


def format_duration(ms: int) -> str:
    if ms < 1000:
        return f"{ms}ms"
    seconds = ms / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, seconds = divmod(seconds, 60)
    return f"{int(minutes)}m{seconds:04.1f}s"


def format_bytes(count: int) -> str:
    size = float(count)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def format_counts(counts: dict[str, int]) -> str:
    return " ".join(f"{key}={value}" for key, value in sorted(counts.items()))


class PlainSink:
    """One line per event on stderr."""

    __slots__ = ("_stream", "_verbosity")

    def __init__(self, stream: TextIO | None = None, verbosity: int = 0) -> None:
        self._stream = stream if stream is not None else sys.stderr
        self._verbosity = verbosity

    def handle(self, event: Event) -> None:
        if not visible_at(event, self._verbosity):
            return
        line = self.render(event)
        if line is None:
            return
        self._stream.write(line + "\n")
        self._stream.flush()

    def close(self) -> None:
        self._stream.flush()

    def render(self, event: Event) -> str | None:
        match event:
            case RunStarted():
                target = event.workflow
                if event.mode:
                    target = f"{target} [{event.mode}]"
                if event.steps_total:
                    return f"run {target} ({plural(event.steps_total, 'step')})"
                return f"run {target}"
            case StepStarted():
                return f"  -> {event.id} {event.lane}"
            case StepProgress():
                total = f"/{event.total}" if event.total is not None else ""
                return f"  .. {event.id} {event.detail} {event.current}{total}"
            case StepFinished():
                mark = {"ok": "ok", "failed": "FAIL", "skipped": "skip", "cancelled": "cancel"}[
                    event.status
                ]
                parts = [f"{mark:<4} {event.id}", format_duration(event.duration_ms)]
                if event.cached:
                    parts.append("cached")
                if event.summary:
                    parts.append(event.summary)
                return "  ".join(parts)
            case StepRetrying():
                return (
                    f"  retry {event.id} {event.attempt}/{event.max} "
                    f"in {event.delay_s:.1f}s: {event.reason}"
                )
            case ValueFreed():
                return f"  freed {event.name} {format_bytes(event.bytes)}"
            case ResourceWarning():
                return f"  warn {event.kind} at {event.current} of {event.budget}"
            case LogRecord():
                where = f" [{event.step}]" if event.step else ""
                return f"{event.level}{where}: {event.message}"
            case RunFinished():
                counts = format_counts(event.counts)
                tail = f" {counts}" if counts else ""
                return f"{event.status} in {format_duration(event.duration_ms)}{tail}"


class QuietSink:
    """``-q``: errors and the final summary. ``-qq``: nothing at all.

    Kept separate from `PlainSink` rather than expressed as a verbosity, because quiet
    is a promise about *what* is printed, not merely how much: a long run must produce
    no output until something goes wrong.
    """

    __slots__ = ("_stream", "_silent")

    def __init__(self, stream: TextIO | None = None, *, silent: bool = False) -> None:
        self._stream = stream if stream is not None else sys.stderr
        self._silent = silent

    def handle(self, event: Event) -> None:
        if self._silent:
            return
        match event:
            case LogRecord() if event.level in ("error", "warning"):
                where = f" [{event.step}]" if event.step else ""
                self._write(f"{event.level}{where}: {event.message}")
            case StepFinished() if event.status == "failed":
                summary = f": {event.summary}" if event.summary else ""
                self._write(f"FAIL {event.id}{summary}")
            case RunFinished() if event.status != "ok":
                self._write(f"{event.status} in {format_duration(event.duration_ms)}")
            case _:
                return

    def close(self) -> None:
        self._stream.flush()

    def _write(self, line: str) -> None:
        self._stream.write(line + "\n")
        self._stream.flush()
