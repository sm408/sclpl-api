"""The ``full`` and ``simple`` rungs — the interactive view.

Two halves, deliberately separate. **Step lines** scroll: one per event, styled and
truncated to the probed width. The **live region** does not: a fixed pane at the bottom
holding the aggregate bar and the instrument line (see `live.py`).

Both are fed the same event. The pane summarises what the lines detail, so a user who
has scrolled back through a long run still has the totals in front of them.
"""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Callable
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
from sclpl.render.live import LiveRegion
from sclpl.render.plain import PlainSink, format_bytes, format_counts, format_duration, plural
from sclpl.render.term import Caps, on_resize, truncate

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
    """Styled step lines above a live region."""

    __slots__ = ("_stream", "_caps", "_verbosity", "_live", "_unregister_resize")

    def __init__(
        self,
        caps: Caps,
        stream: TextIO | None = None,
        verbosity: int = 0,
        *,
        live: bool = True,
    ) -> None:
        self._caps = caps
        self._stream = stream if stream is not None else sys.stderr
        self._verbosity = verbosity
        self._live: LiveRegion | None = None
        self._unregister_resize: Callable[[], None] | None = None
        if live and caps.rung != "plain" and verbosity >= 0:
            # `-q` asks for silence on success; a progress pane is the opposite of that.
            self._live = LiveRegion(caps, self._stream)

    # -- lifecycle ---------------------------------------------------------------

    def start(self) -> None:
        """Claim the pane's rows and begin listening for resizes."""
        if self._live is None:
            return
        self._live.install()
        self._unregister_resize = on_resize(self._on_resize)

    def close(self) -> None:
        if self._unregister_resize is not None:
            self._unregister_resize()
            self._unregister_resize = None
        if self._live is not None:
            self._live.uninstall()
        # The stream can already be gone -- a closed pipe, a terminal that vanished.
        with contextlib.suppress(ValueError, OSError):
            self._stream.flush()

    def _on_resize(self, caps: Caps) -> None:
        self._caps = caps
        if self._live is not None:
            self._live.resize(caps)

    # -- output ------------------------------------------------------------------

    def handle(self, event: Event) -> None:
        line = self.render(event) if visible_at(event, self._verbosity) else None
        if line is not None:
            if self._live is not None:
                # At the `simple` rung the pane shares the bottom line, so erase it
                # before a step line lands on top of it.
                self._live.clear_line()
            self._stream.write(truncate(line, self._caps.width) + "\n")
            self._stream.flush()
        if self._live is not None:
            self._live.update(event)
            if isinstance(event, RunFinished):
                # The summary is the last thing printed; give the rows back rather than
                # leave a pane nobody needs sitting under it.
                self._live.uninstall()

    def descend(self) -> HumanSink | PlainSink:
        """One rung down, never up (invariant 5).

        The reporter calls this when a write raises — a resized-away terminal, a closed
        pipe, a console that lied about its capabilities. `simple` still styles;
        `plain` gives up the terminal entirely and cannot fail the same way.
        """
        if self._live is not None:
            # Hand the rows back against the geometry we still believe in, before the
            # replacement claims anything.
            self._live.uninstall()
        lowered = self._caps.descend()
        if lowered.rung == "plain":
            return PlainSink(self._stream, self._verbosity)
        replacement = HumanSink(lowered, self._stream, self._verbosity)
        replacement.start()
        return replacement

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
