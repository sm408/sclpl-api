"""#13 -- a supervisor's CTRL_BREAK_EVENT stops a Windows `sclpl run` gracefully.

`CTRL_BREAK_EVENT` is the only console event one process can send to another in a
separate process group, so it is how every launcher and service wrapper on Windows
asks a child to stop. It has to land on the same path as a local Ctrl-C: in-flight
steps cancelled, nothing half-written left behind, the run recorded as cancelled,
and `EXIT_INTERRUPTED` rather than the OS's own `STATUS_CONTROL_C_EXIT`.

The child is parked mid-step on a socket that accepts and never answers, so the
break arrives while the event loop is blocked in its I/O wait -- the case an earlier
attempt at this could not make reliable.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from sclpl.errors import EXIT_INTERRUPTED
from sclpl.state import db

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="CTRL_BREAK_EVENT is Windows-only")

if sys.platform == "win32":
    NEW_GROUP = subprocess.CREATE_NEW_PROCESS_GROUP
    BREAK = signal.CTRL_BREAK_EVENT
else:  # never reached: the test is skipped off Windows
    NEW_GROUP = BREAK = 0

WORKFLOW = """
@workflow hang "Waits on a server that never answers"

@var base = "{base}"

@output report:csv

@step fetch
  get {{{{base}}}}/never

@step rows
  let @fetch.body.slides

@step write -> report
  save_csv @rows
"""


def test_ctrl_break_takes_the_graceful_interrupt_path(tmp_path: Path) -> None:
    with socket.create_server(("127.0.0.1", 0)) as listener:
        port = listener.getsockname()[1]
        workflow = tmp_path / "hang.sclpll"
        workflow.write_text(WORKFLOW.format(base=f"http://127.0.0.1:{port}"), encoding="utf-8")
        out = tmp_path / "out.csv"
        home = tmp_path / "home"
        child = subprocess.Popen(
            [sys.executable, "-m", "sclpl", "run", str(workflow), str(out)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                **os.environ,
                "PYTHONPATH": os.getcwd(),
                "SCLPL_HOME": str(home),
                "SCLPL_CACHE_DIR": str(tmp_path / "cache"),
            },
            creationflags=NEW_GROUP,
        )
        try:
            # The child is provably inside the `fetch` step once it has connected.
            listener.settimeout(60)
            connection, _ = listener.accept()
            with connection:
                child.send_signal(BREAK)
                _, stderr = child.communicate(timeout=60)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)

    assert child.returncode == EXIT_INTERRUPTED, stderr.decode(errors="replace")
    assert not out.exists()
    # The C5 lock sidecar outlives every run by design; anything else is a leftover.
    leftovers = [p.name for p in tmp_path.glob("out.csv*") if not p.name.endswith(".sclpl-lock")]
    assert leftovers == [], "no staged or partial output may remain"
    with db.History(home) as history:
        runs = [(row["status"], row["exit_code"]) for row in history.recent()]
    assert runs == [("cancelled", EXIT_INTERRUPTED)]
