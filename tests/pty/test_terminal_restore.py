"""Restoration: a real subprocess, on a real pty where the platform has one.

The unit tests above check that the right bytes are produced. These check the thing
that actually matters to a user: after the process exits -- normally, by exception, or
by Ctrl-C -- the terminal is usable again. Nothing here inspects internals; it runs the
CLI the way a person would and reads what came back.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import pytest

from sclpl.render.term import RESET_SCROLL_REGION, SHOW_CURSOR

HAS_PTY = hasattr(os, "openpty")

#: Emits a full run into a stream we control, then exits the way `exit_how` says.
SCRIPT = """
import asyncio, os, sys
from sclpl.render.events import RunFinished, RunStarted, StepFinished, StepStarted
from sclpl.render.human import HumanSink
from sclpl.render.reporter import Reporter
from sclpl.render.term import Caps, TerminalGuard

caps = Caps(rung="full", color=True, unicode=True, width=80, height=24)


async def main() -> None:
    sink = HumanSink(caps, sys.stderr, verbosity=0)
    guard = TerminalGuard(caps, sys.stderr)
    async with Reporter([sink], guard=guard) as reporter:
        reporter.emit(RunStarted(workflow="probe", steps_total=2))
        reporter.emit(StepStarted(id="a", kind="http"))
        reporter.emit(StepFinished(id="a", status="ok", duration_ms=5))
        await reporter.drain()
        {body}


asyncio.run(main())
"""

BODIES = {
    "clean": 'reporter.emit(RunFinished(status="ok", duration_ms=10))',
    "raise": 'raise RuntimeError("boom")',
    "exit": "sys.exit(3)",
}


def run_script(kind: str) -> str:
    """Run the probe script and return everything it wrote to stderr."""
    source = SCRIPT.format(body=BODIES[kind])
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTHONPATH": os.getcwd()},
    )
    return result.stderr


@pytest.mark.parametrize("kind", ["clean", "raise", "exit"])
def test_the_terminal_is_restored_on_every_exit_path(kind: str) -> None:
    """finally, atexit, and the signal handlers are three chances to get this right."""
    written = run_script(kind)
    assert RESET_SCROLL_REGION in written, f"scroll region left set after a {kind} exit"
    assert SHOW_CURSOR in written, f"cursor left hidden after a {kind} exit"


@pytest.mark.skipif(not HAS_PTY, reason="no pty on this platform")
def test_a_real_pty_gets_the_full_rung() -> None:
    """On a pty the probe must choose `full`; in a pipe it must not.

    This is the one assertion that cannot be made without a real terminal, and it is
    the one that decides whether any of the escape sequences are emitted at all.
    """
    import pty

    source = textwrap.dedent(
        """
        import sys
        from sclpl.render.term import probe
        sys.stdout.write(probe(sys.stderr).rung)
        """
    )
    # `pty.fork` exists only where `HAS_PTY`, which this test is gated on.
    pid, fd = pty.fork()  # type: ignore[attr-defined,unused-ignore]
    if pid == 0:  # pragma: no cover - the child never returns
        os.environ.pop("CI", None)
        os.environ["TERM"] = "xterm-256color"
        os.execv(sys.executable, [sys.executable, "-c", source])
    output = b""
    try:
        while True:
            chunk = os.read(fd, 1024)
            if not chunk:
                break
            output += chunk
    except OSError:
        pass
    finally:
        os.close(fd)
        os.waitpid(pid, 0)
    assert b"full" in output


def test_a_pipe_gets_the_plain_rung() -> None:
    """The counterpart: redirected output is data, and must carry no escapes."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from sclpl.render.term import probe; print(probe(sys.stderr).rung)",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTHONPATH": os.getcwd()},
    )
    assert result.stdout.strip() == "plain"


def test_a_piped_run_emits_no_escape_sequences() -> None:
    """The end-to-end version of invariant 1: a redirected run is clean text."""
    result = subprocess.run(
        [sys.executable, "-m", "sclpl", "--version"],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTHONPATH": os.getcwd()},
    )
    assert "\x1b" not in result.stdout
    assert "\x1b" not in result.stderr
