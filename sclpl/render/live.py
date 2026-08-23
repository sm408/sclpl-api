"""The live region: a fixed pane at the bottom of the terminal.

This is the part decision 7 was really about. The region has to stay intact while a
worker pool writes step lines above it, survive a resize, and leave the terminal exactly
as it was found on any exit path including `Ctrl-C`.

How it works, at the `full` rung:

- A DECSTBM scroll region covers rows 1..(height - k). Everything the sink prints
  scrolls inside that window; the bottom k rows are ours and never scroll.
- Painting the pane is: save cursor, jump to the pane, clear and write each row, restore
  cursor. The cursor ends where the scrolling text left it, so the next step line lands
  in the right place.
- Repaint is bounded to `MAX_FPS`. Between frames, events only mutate state. A run
  emitting a thousand progress events a second must not issue a thousand repaints.

At the `simple` rung there is no scroll region: the pane is repainted in place with
`\\r` and erase-line, which works on terminals that do not honour DECSTBM.

At `plain` there is no pane at all.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TextIO

from sclpl.render.events import (
    Event,
    ResourceWarning,
    RunFinished,
    RunStarted,
    StepFinished,
    StepProgress,
    StepRetrying,
    StepStarted,
)
from sclpl.render.plain import format_duration, plural
from sclpl.render.term import (
    CLEAR_LINE,
    HIDE_CURSOR,
    RESET_SCROLL_REGION,
    SHOW_CURSOR,
    Caps,
    move_to,
    scroll_region,
    truncate,
)

#: Repaints per second. Ten is past the point where a person perceives separate frames,
#: and far below the point where the terminal becomes the bottleneck.
MAX_FPS = 10.0
_FRAME = 1.0 / MAX_FPS

#: Rows the pane occupies: a blank separator, the bar, and the instrument line.
PANE_HEIGHT = 3

#: Beyond this many in-flight steps, list a count instead of names. A pane that grows
#: with concurrency is a pane that pushes the scroll region off the screen.
MAX_ACTIVE_SHOWN = 3

_BLOCKS = " ▏▎▍▌▋▊▉█"


@dataclass(slots=True)
class Progress:
    """One step's current progress, for the pane."""

    detail: str = ""
    current: int = 0
    total: int | None = None


@dataclass(slots=True)
class State:
    """Everything the pane draws. Mutated by events, read by the painter."""

    workflow: str = ""
    mode: str | None = None
    total: int = 0
    done: int = 0
    failed: int = 0
    cached: int = 0
    retries: int = 0
    freed_bytes: int = 0
    started_at: float = field(default_factory=time.monotonic)
    active: dict[str, Progress] = field(default_factory=dict)
    finished: bool = False
    warning: str = ""

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started_at

    @property
    def fraction(self) -> float:
        if self.total <= 0:
            return 0.0
        return min(1.0, (self.done + self.failed) / self.total)

    def apply(self, event: Event) -> bool:
        """Fold an event into the state. True when the pane needs a repaint."""
        match event:
            case RunStarted():
                self.workflow = event.workflow
                self.mode = event.mode
                self.total = event.steps_total
                self.started_at = time.monotonic()
                return True
            case StepStarted():
                self.active[event.id] = Progress()
                return True
            case StepProgress():
                self.active[event.id] = Progress(event.detail, event.current, event.total)
                return True
            case StepFinished():
                self.active.pop(event.id, None)
                if event.status == "failed":
                    self.failed += 1
                else:
                    self.done += 1
                if event.cached:
                    self.cached += 1
                return True
            case StepRetrying():
                self.retries += 1
                return True
            case ResourceWarning():
                self.warning = f"{event.kind} {event.current}/{event.budget}"
                return True
            case RunFinished():
                self.finished = True
                self.active.clear()
                return True
            case _:
                return False


class LiveRegion:
    """Owns the bottom rows of the terminal. One instance, one writer.

    Never writes on its own initiative -- the reporter's single pump task calls every
    method here, which is what keeps invariant 4 true with a pane in play.
    """

    __slots__ = ("_caps", "_stream", "_state", "_last_paint", "_installed", "_rows", "_dirty")

    def __init__(self, caps: Caps, stream: TextIO) -> None:
        self._caps = caps
        self._stream = stream
        self._state = State()
        self._last_paint = 0.0
        self._installed = False
        self._rows = 0
        self._dirty = False

    @property
    def state(self) -> State:
        return self._state

    @property
    def height(self) -> int:
        return PANE_HEIGHT if self._caps.rung == "full" else 1

    # -- lifecycle ---------------------------------------------------------------

    def install(self) -> None:
        """Claim the bottom rows. Idempotent, and a no-op below the `full` rung."""
        if self._installed or self._caps.rung != "full":
            return
        self._installed = True
        self._rows = self._caps.height
        # Reserve the pane by scrolling the existing content up, then fence it off.
        self._write("\n" * self.height)
        self._write(scroll_region(1, max(1, self._rows - self.height)))
        self._write(move_to(max(1, self._rows - self.height), 1))
        self._write(HIDE_CURSOR)

    def uninstall(self) -> None:
        """Give the rows back. Safe to call more than once, and on any exit path."""
        if not self._installed:
            return
        self._installed = False
        self._write(RESET_SCROLL_REGION)
        self._write(move_to(self._rows, 1) + CLEAR_LINE)
        self._write(SHOW_CURSOR)

    def resize(self, caps: Caps) -> None:
        """Re-fence after SIGWINCH.

        Tear down against the old geometry first: a scroll region set for 40 rows on a
        terminal that now has 20 leaves the cursor somewhere the pane does not own.
        """
        was_installed = self._installed
        self.uninstall()
        self._caps = caps
        if was_installed:
            self.install()
            self.paint(force=True)

    # -- painting ----------------------------------------------------------------

    def update(self, event: Event) -> None:
        """Fold in an event and repaint if the frame budget allows."""
        if self._state.apply(event):
            self._dirty = True
            self.paint()

    def paint(self, *, force: bool = False) -> None:
        """Draw the pane, at most `MAX_FPS` times a second unless forced."""
        if self._caps.rung == "plain" or not self._dirty and not force:
            return
        now = time.monotonic()
        if not force and now - self._last_paint < _FRAME:
            return
        self._last_paint = now
        self._dirty = False
        if self._caps.rung == "full":
            self._paint_full()
        else:
            self._paint_simple()

    def _paint_full(self) -> None:
        if not self._installed:
            return
        rows = self._compose()
        top = max(1, self._rows - self.height + 1)
        out = ["\x1b7"]  # save cursor
        for offset, row in enumerate(rows):
            out.append(move_to(top + offset, 1))
            out.append(CLEAR_LINE)
            out.append(truncate(row, self._caps.width))
        out.append("\x1b8")  # restore cursor
        self._write("".join(out))

    def _paint_simple(self) -> None:
        """No scroll region: repaint one line in place.

        The step lines above will scroll this away and it will be redrawn on the next
        frame. That flicker is the price of not having DECSTBM.
        """
        line = truncate(self._bar_line(), self._caps.width)
        self._write("\r" + CLEAR_LINE + line)

    def clear_line(self) -> None:
        """Erase the in-place line before something else writes at the `simple` rung."""
        if self._caps.rung == "simple":
            self._write("\r" + CLEAR_LINE)

    def _compose(self) -> list[str]:
        """The pane's rows, each already fitted to the terminal.

        Truncation happens here rather than at paint time so that every caller gets
        rows that obey the no-wrap rule -- a wrapped pane row occupies two terminal
        rows and every later cursor move is off by one.
        """
        rows = ["", self._bar_line(), self._instrument_line()]
        return [truncate(row, self._caps.width) for row in rows]

    def _bar_line(self) -> str:
        caps = self._caps
        state = self._state
        done = state.done + state.failed
        if state.total > 0:
            bar = self._bar(state.fraction, 24)
            counts = f"{done}/{state.total}"
        else:
            bar = self._bar(0.0, 24)
            counts = str(done)
        # Elide a long name rather than let it push the bar off the line: the bar and
        # the counts are what the pane is for.
        name = truncate(state.workflow or "run", max(8, caps.width // 3))
        label = caps.paint(name, "bold")
        if state.mode:
            label += caps.paint(f" [{state.mode}]", "cyan")
        elapsed = caps.paint(format_duration(int(state.elapsed * 1000)), "grey")
        return f" {label} {bar} {counts}  {elapsed}"

    def _instrument_line(self) -> str:
        caps = self._caps
        state = self._state
        parts: list[str] = []
        if state.active:
            parts.append(self._active_summary())
        if state.failed:
            parts.append(caps.paint(f"{state.failed} failed", "red"))
        if state.retries:
            parts.append(caps.paint(f"{state.retries} retried", "yellow"))
        if state.cached:
            parts.append(caps.paint(f"{state.cached} cached", "cyan"))
        if state.warning:
            parts.append(caps.paint(f"! {state.warning}", "yellow"))
        if not parts:
            parts.append(caps.paint("waiting", "grey"))
        return "  " + caps.paint("·", "grey").join(f" {part} " for part in parts)

    def _active_summary(self) -> str:
        state = self._state
        names = list(state.active)
        if len(names) > MAX_ACTIVE_SHOWN:
            return self._caps.paint(plural(len(names), "step") + " running", "grey")
        rendered: list[str] = []
        for name in names:
            progress = state.active[name]
            if progress.total:
                rendered.append(f"{name} {progress.current}/{progress.total}")
            elif progress.current:
                rendered.append(f"{name} {progress.current}")
            else:
                rendered.append(name)
        return self._caps.paint(", ".join(rendered), "grey")

    def _bar(self, fraction: float, width: int) -> str:
        """A proportional bar, using sub-cell blocks when Unicode is available."""
        if not self._caps.unicode:
            filled = int(fraction * width)
            body = "#" * filled + "-" * (width - filled)
            return self._caps.paint(f"[{body}]", "green" if fraction >= 1 else "blue")
        exact = fraction * width
        whole = int(exact)
        remainder = exact - whole
        partial = _BLOCKS[int(remainder * (len(_BLOCKS) - 1))] if whole < width else ""
        body = "█" * whole + partial
        body = body.ljust(width, "░")
        return self._caps.paint(body, "green" if fraction >= 1 else "blue")

    def _write(self, text: str) -> None:
        try:
            self._stream.write(text)
            self._stream.flush()
        except (ValueError, OSError):
            # The terminal went away. The sink's descend path handles the rest.
            self._installed = False
