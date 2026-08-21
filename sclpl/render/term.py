"""ANSI primitives, the capability probe, and guaranteed restoration.

Hand-written on purpose (SPEC decision 7). The live region has to survive a worker pool
writing underneath it, and a terminal left in a broken state is the one bug class users
cannot work around. So: probe once, never climb the ladder back up, never emit a
sequence wider than the terminal, and restore three independent ways.
"""

from __future__ import annotations

import atexit
import contextlib
import importlib
import os
import signal
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from types import FrameType, TracebackType
from typing import Any, Literal, TextIO, TypeAlias

Rung: TypeAlias = Literal["full", "simple", "plain"]

#: Descend-only ladder (invariant 5). Index in this tuple is the only ordering.
LADDER: tuple[Rung, ...] = ("full", "simple", "plain")

ESC = "\x1b"
CSI = f"{ESC}["

HIDE_CURSOR = f"{CSI}?25l"
SHOW_CURSOR = f"{CSI}?25h"
CLEAR_LINE = f"{CSI}2K"
RESET_SCROLL_REGION = f"{CSI}r"
SGR_RESET = f"{CSI}0m"

DEFAULT_SIZE = (80, 24)

_COLORS: dict[str, str] = {
    "dim": "2",
    "bold": "1",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "grey": "90",
}

#: Probed against the stream encoding at startup; the ASCII column is the fallback.
GLYPHS: dict[str, tuple[str, str]] = {
    "ok": ("✔", "+"),
    "fail": ("✘", "x"),
    "skip": ("–", "-"),
    "arrow": ("→", "->"),
    "bullet": ("•", "*"),
    "spinner": ("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏", "|/-\\"),
}


@dataclass(frozen=True, slots=True)
class Caps:
    """What the attached terminal can actually do. Probed once, never re-probed."""

    rung: Rung = "plain"
    color: bool = False
    unicode: bool = False
    width: int = DEFAULT_SIZE[0]
    height: int = DEFAULT_SIZE[1]

    def descend(self) -> Caps:
        """One rung down. Already at ``plain`` is a no-op — the ladder never climbs."""
        index = LADDER.index(self.rung)
        if index == len(LADDER) - 1:
            return self
        lowered: Rung = LADDER[index + 1]
        return replace(self, rung=lowered, color=self.color and lowered != "plain")

    def glyph(self, name: str) -> str:
        fancy, plain = GLYPHS[name]
        return fancy if self.unicode else plain

    def paint(self, text: str, *styles: str) -> str:
        if not self.color or not styles:
            return text
        codes = ";".join(_COLORS[style] for style in styles if style in _COLORS)
        if not codes:
            return text
        return f"{CSI}{codes}m{text}{SGR_RESET}"


def probe(stream: TextIO | None = None) -> Caps:
    """Decide the rung once, from the environment and the stream.

    Order matters: an explicit ``SCLPL_RENDER`` wins, then anything that says "this is
    not an interactive terminal", then the colour and glyph questions.
    """
    stream = stream if stream is not None else sys.stderr
    forced = _forced_rung()

    if not _isatty(stream):
        # Piped or redirected: data, not a display. Honour a forced rung only when it
        # descends — forcing `full` into a pipe would write escape codes to a file.
        return Caps(rung="plain", color=False, unicode=_supports_unicode(stream))

    if os.environ.get("TERM", "") == "dumb":
        return Caps(rung="plain")

    if os.environ.get("CI"):
        # CI logs are read after the fact and have no cursor. One line per event.
        return Caps(rung="plain", color=False, unicode=_supports_unicode(stream))

    if sys.platform == "win32" and not _enable_windows_vt(stream):
        return Caps(rung="plain", color=False, unicode=_supports_unicode(stream))

    width, height = _size()
    caps = Caps(
        rung=forced or "full",
        color=_supports_color(),
        unicode=_supports_unicode(stream),
        width=width,
        height=height,
    )
    if width < 40 or height < 8:
        # Too small for a live region to be anything but noise.
        caps = replace(caps, rung="plain", color=caps.color)
    return caps


def _forced_rung() -> Rung | None:
    value = os.environ.get("SCLPL_RENDER", "").strip().lower()
    if value in LADDER:
        # `value in LADDER` narrows to Rung for the reader; mypy needs the cast-free
        # form below.
        for rung in LADDER:
            if rung == value:
                return rung
    return None


def _isatty(stream: TextIO) -> bool:
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):
        return False


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("COLORTERM"):
        return True
    term = os.environ.get("TERM", "")
    return term not in ("", "dumb")


def _supports_unicode(stream: TextIO) -> bool:
    encoding = getattr(stream, "encoding", None) or "ascii"
    try:
        "".join(fancy for fancy, _ in GLYPHS.values()).encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def _size() -> tuple[int, int]:
    try:
        size = os.get_terminal_size()
    except OSError:
        return DEFAULT_SIZE
    width = size.columns if size.columns > 0 else DEFAULT_SIZE[0]
    height = size.lines if size.lines > 0 else DEFAULT_SIZE[1]
    return width, height


def _enable_windows_vt(stream: TextIO) -> bool:
    """Turn on ENABLE_VIRTUAL_TERMINAL_PROCESSING. False means: drop to plain.

    Everything here is reached dynamically. The Windows-only names do not exist in the
    type stubs for any other platform, and this file must type-check on the Linux CI
    runner as well as run on Windows.
    """
    try:
        import ctypes

        windll = getattr(ctypes, "WinDLL", None)
        if windll is None:
            return False
        wintypes = importlib.import_module("ctypes.wintypes")

        handle_id = -12 if stream is sys.stderr else -11  # STD_ERROR / STD_OUTPUT
        kernel32 = windll("kernel32", use_last_error=True)
        handle = kernel32.GetStdHandle(handle_id)
        if handle in (0, -1):
            return False
        mode = wintypes.DWORD()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        enable_vt = 0x0004
        if mode.value & enable_vt:
            return True
        return bool(kernel32.SetConsoleMode(handle, mode.value | enable_vt))
    except Exception:
        return False


def display_width(text: str) -> int:
    """Printable width, ignoring SGR sequences.

    Deliberately not a full east-asian-width implementation: we truncate rather than
    align, so being one column conservative costs nothing and pulling in a table does.
    """
    width = 0
    in_escape = False
    for char in text:
        if in_escape:
            if char.isalpha():
                in_escape = False
            continue
        if char == ESC:
            in_escape = True
            continue
        width += 1
    return width


def truncate(text: str, width: int, *, ellipsis: str = "…") -> str:
    """Cut ``text`` to ``width`` printable columns. Never wrap (invariant: no wrap).

    Wrapping is what destroys a live region: a line that wraps occupies two rows and
    every subsequent cursor movement is off by one.
    """
    if width <= 0:
        return ""
    if display_width(text) <= width:
        return text
    if len(ellipsis) >= width:
        ellipsis = ""
    budget = width - len(ellipsis)
    out: list[str] = []
    taken = 0
    in_escape = False
    for char in text:
        if in_escape:
            out.append(char)
            if char.isalpha():
                in_escape = False
            continue
        if char == ESC:
            out.append(char)
            in_escape = True
            continue
        if taken >= budget:
            break
        out.append(char)
        taken += 1
    return "".join(out) + ellipsis + SGR_RESET


def scroll_region(top: int, bottom: int) -> str:
    """DECSTBM. Rows are 1-indexed and inclusive, as the terminal counts them."""
    return f"{CSI}{top};{bottom}r"


def move_to(row: int, column: int = 1) -> str:
    return f"{CSI}{row};{column}H"


class TerminalGuard:
    """Restores the terminal three ways: ``finally``, ``atexit``, and signals.

    Any one of them is enough, and running all three is safe because restoration is
    idempotent. The signal handlers chain to whatever was installed before, so this
    does not swallow a `Ctrl-C` the application still needs to see.
    """

    __slots__ = ("_stream", "_caps", "_restored", "_previous", "_armed")

    def __init__(self, caps: Caps, stream: TextIO | None = None) -> None:
        self._caps = caps
        self._stream = stream if stream is not None else sys.stderr
        self._restored = False
        self._armed = False
        self._previous: dict[int, Any] = {}

    def __enter__(self) -> TerminalGuard:
        self.arm()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.restore()

    def arm(self) -> None:
        if self._armed or self._caps.rung == "plain":
            return
        self._armed = True
        atexit.register(self.restore)
        for signum in (signal.SIGINT, signal.SIGTERM):
            try:
                self._previous[signum] = signal.getsignal(signum)
                signal.signal(signum, self._on_signal)
            except (ValueError, OSError):
                # Not the main thread, or the platform has no such signal.
                self._previous.pop(signum, None)

    def restore(self) -> None:
        if self._restored:
            return
        self._restored = True
        if not self._armed:
            return
        try:
            self._stream.write(RESET_SCROLL_REGION + SHOW_CURSOR + SGR_RESET + "\n")
            self._stream.flush()
        except (ValueError, OSError):
            pass
        for signum, handler in self._previous.items():
            with contextlib.suppress(ValueError, OSError):
                signal.signal(signum, handler)
        self._previous.clear()

    def _on_signal(self, signum: int, frame: FrameType | None) -> None:
        self.restore()
        previous = self._previous.get(signum, signal.SIG_DFL)
        if callable(previous):
            handler: Callable[[int, FrameType | None], Any] = previous
            handler(signum, frame)
        elif previous == signal.SIG_DFL:
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)
