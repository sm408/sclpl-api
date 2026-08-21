"""Terminal primitives: the ladder, truncation, and restoration.

The pty snapshot tests arrive with the live region in M3. These cover the pieces that
the live region will depend on being correct.
"""

from __future__ import annotations

import io

import pytest

from sclpl.render.term import (
    LADDER,
    RESET_SCROLL_REGION,
    SGR_RESET,
    SHOW_CURSOR,
    Caps,
    TerminalGuard,
    display_width,
    probe,
    truncate,
)


class FakeTty(io.StringIO):
    """A stream that claims to be a terminal."""

    # A class attribute, because `encoding` is a read-only property on the C
    # implementation. The probe reads it to choose the glyph set.
    encoding = "utf-8"

    def isatty(self) -> bool:
        return True


class AsciiTty(FakeTty):
    """A terminal that cannot encode the Unicode glyphs."""

    encoding = "ascii"


def test_ladder_only_descends() -> None:
    caps = Caps(rung="full", color=True)
    simple = caps.descend()
    assert simple.rung == "simple"
    plain = simple.descend()
    assert plain.rung == "plain"
    # The floor is absorbing: there is no way back up (invariant 5).
    assert plain.descend().rung == "plain"
    assert LADDER == ("full", "simple", "plain")


def test_descending_to_plain_drops_colour() -> None:
    assert Caps(rung="simple", color=True).descend().color is False


def test_truncate_never_exceeds_width() -> None:
    assert display_width(truncate("x" * 200, 20)) <= 20


def test_short_text_is_untouched() -> None:
    assert truncate("hello", 20) == "hello"


def test_truncate_ignores_escape_sequences_when_measuring() -> None:
    """A styled line has 9 printable columns even though the string is far longer."""
    styled = f"\x1b[32m{'a' * 9}\x1b[0m"
    assert display_width(styled) == 9
    assert truncate(styled, 20) == styled


def test_truncate_keeps_escapes_and_resets_style() -> None:
    styled = f"\x1b[32m{'a' * 50}\x1b[0m"
    cut = truncate(styled, 10)
    assert display_width(cut) <= 10
    assert cut.endswith(SGR_RESET)


def test_pipes_get_the_plain_rung() -> None:
    """Redirected output is data, not a display."""
    assert probe(io.StringIO()).rung == "plain"


def test_dumb_terminal_gets_plain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM", "dumb")
    assert probe(FakeTty()).rung == "plain"


def test_ci_gets_plain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("CI", "1")
    assert probe(FakeTty()).rung == "plain"


def test_no_color_is_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    assert probe(FakeTty()).color is False


def test_ascii_stream_falls_back_to_ascii_glyphs() -> None:
    assert probe(AsciiTty()).unicode is False


def test_paint_is_a_no_op_without_colour() -> None:
    assert Caps(rung="plain", color=False).paint("x", "red") == "x"


def test_guard_restores_the_terminal() -> None:
    stream = FakeTty()
    with TerminalGuard(Caps(rung="full", color=True), stream):
        pass
    written = stream.getvalue()
    assert RESET_SCROLL_REGION in written
    assert SHOW_CURSOR in written


def test_restore_is_idempotent() -> None:
    stream = FakeTty()
    guard = TerminalGuard(Caps(rung="full"), stream)
    guard.arm()
    guard.restore()
    first = stream.getvalue()
    guard.restore()
    assert stream.getvalue() == first


def test_plain_rung_writes_no_escapes() -> None:
    """Nothing was taken over, so nothing may be emitted to hand it back."""
    stream = FakeTty()
    with TerminalGuard(Caps(rung="plain"), stream):
        pass
    assert stream.getvalue() == ""
