"""C5 — output ownership, through the real CLI and real separate processes.

`test_locking.py` already proves the primitive holds across processes; these prove
the runner actually uses it: a `sclpl run` writing to a file another process holds
waits for it, while one writing somewhere else is never slowed down by that at all.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

WRITER = """
@workflow writer "Writes wherever the caller says"

@var base = "{base}"

@output report:csv

@step fetch
  get {{{{base}}}}/json

@step rows
  let @fetch.body.slideshow.slides

@step write -> report
  save_csv @rows
"""


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sclpl", *args],
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "PYTHONPATH": os.getcwd()},
    )


@pytest.fixture
def writer(tmp_path: Path, server_url: str) -> Path:
    path = tmp_path / "writer.sclpll"
    path.write_text(WRITER.format(base=server_url), encoding="utf-8")
    return path


def _hold_lock(path: Path, seconds: float) -> subprocess.Popen[bytes]:
    script = (
        "import time\n"
        "from pathlib import Path\n"
        "from sclpl.state.locking import output_locks\n"
        f"with output_locks([Path({str(path)!r})]):\n"
        f"    time.sleep({seconds})\n"
    )
    return subprocess.Popen([sys.executable, "-c", script])


def test_a_run_waits_for_a_locked_output_held_by_another_process(
    writer: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out.csv"
    holder = _hold_lock(out, seconds=1.5)
    try:
        started = time.monotonic()
        result = run_cli("run", str(writer), str(out), "--no-record")
        elapsed = time.monotonic() - started
    finally:
        holder.wait(timeout=5)
    assert result.returncode == 0, result.stderr
    assert out.exists()
    # Waited for the other process rather than writing concurrently or failing.
    assert elapsed >= 1.0


def test_a_run_is_not_slowed_by_a_lock_on_a_different_output(writer: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.csv"
    unrelated = tmp_path / "unrelated.csv"
    holder = _hold_lock(unrelated, seconds=5.0)
    try:
        started = time.monotonic()
        result = run_cli("run", str(writer), str(out), "--no-record")
        elapsed = time.monotonic() - started
    finally:
        holder.kill()
        holder.wait(timeout=5)
    assert result.returncode == 0, result.stderr
    assert out.exists()
    assert elapsed < 4.0
