"""The ``full`` and ``simple`` rungs — the interactive view.

M0 ships the line half of this sink: colour, glyphs, and truncation, all measured
against the probed width. The live region (DECSTBM scroll region, aggregate bar,
bounded repaint) lands in M3 and attaches here; the event stream and the capability
handling it needs are already in place, so nothing below has to move for it.
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
from sclpl.render.plain import PlainSink, format_bytes, format_counts, format_duration, plural
from sclpl.render.term import Caps, truncate

_STATUS_STYLE: dict[str, tuple[str, str]] = {
    "ok": ("ok", "green"),
    "failed": ("fail", "red"),
    "skipped": ("skip", "grey"),
    "cancelled": ("skip", "yellow"),
}

_LEVEL_STYLE: dict[str, str] = {
    "debug": "grey",
    "info": "blue",
    "warning": "yellow",
    "error": "red",
}


class HumanSink:
    """Styled step lines for an interactive terminal."""

    __slots__ = ("_stream", "_caps", "_verbosity")

    def __init__(
        self,
        caps: Caps,
        stream: TextIO | None = None,
        verbosity: int = 0,
    ) -> None:
        self._caps = caps
        self._stream = stream if stream is not None else sys.stderr
        self._verbosity = verbosity

    def handle(self, event: Event) -> None:
        if not visible_at(event, self._verbosity):
            return
        line = self.render(event)
        if line is None:
            return
        self._stream.write(truncate(line, self._caps.width) + "\n")
        self._stream.flush()

    def close(self) -> None:
        self._stream.flush()

    def descend(self) -> HumanSink | PlainSink:
        """One rung down, never up (invariant 5).

        The reporter calls this when a write raises — a resized-away terminal, a closed
        pipe, a console that lied about its capabilities. `simple` still styles;
        `plain` gives up the terminal entirely and cannot fail the same way.
        """
        lowered = self._caps.descend()
        if lowered.rung == "plain":
            return PlainSink(self._stream, self._verbosity)
        return HumanSink(lowered, self._stream, self._verbosity)

    def render(self, event: Event) -> str | None:
        caps = self._caps
        match event:
            case RunStarted():
                target = caps.paint(event.workflow, "bold")
                if event.mode:
                    target = f"{target} {caps.paint('[' + event.mode + ']', 'cyan')}"
                if event.steps_total:
                    pruned = ""
                    if event.steps_pruned:
                        pruned = caps.paint(f" ({event.steps_pruned} pruned)", "grey")
                    counted = caps.paint(plural(event.steps_total, "step"), "grey")
                    return f"{target} {counted}{pruned}"
                return target
            case StepStarted():
                arrow = caps.paint(caps.glyph("arrow"), "grey")
                lane = caps.paint(event.lane, "grey")
                return f" {arrow} {event.id} {lane}"
            case StepProgress():
                total = f"/{event.total}" if event.total is not None else ""
                bullet = caps.paint(caps.glyph("bullet"), "grey")
                detail = caps.paint(f"{event.detail} {event.current}{total}", "grey")
                return f" {bullet} {event.id} {detail}"
            case StepFinished():
                glyph_name, color = _STATUS_STYLE[event.status]
                mark = caps.paint(caps.glyph(glyph_name), color)
                parts = [f" {mark} {event.id}"]
                parts.append(caps.paint(format_duration(event.duration_ms), "grey"))
                if event.cached:
                    parts.append(caps.paint("cached", "cyan"))
                if event.summary:
                    parts.append(event.summary)
                return "  ".join(parts)
            case StepRetrying():
                mark = caps.paint(caps.glyph("skip"), "yellow")
                detail = caps.paint(
                    f"retry {event.attempt}/{event.max} in {event.delay_s:.1f}s: {event.reason}",
                    "yellow",
                )
                return f" {mark} {event.id} {detail}"
            case ValueFreed():
                return caps.paint(f"   freed {event.name} {format_bytes(event.bytes)}", "grey")
            case ResourceWarning():
                return caps.paint(f" ! {event.kind} at {event.current} of {event.budget}", "yellow")
            case LogRecord():
                label = caps.paint(event.level, _LEVEL_STYLE[event.level])
                where = caps.paint(f" [{event.step}]", "grey") if event.step else ""
                return f"{label}{where} {event.message}"
            case RunFinished():
                _, color = _STATUS_STYLE[event.status]
                status = caps.paint(event.status, color, "bold")
                counts = format_counts(event.counts)
                tail = caps.paint(f"  {counts}", "grey") if counts else ""
                duration = caps.paint(format_duration(event.duration_ms), "grey")
                return f"{status} in {duration}{tail}"
