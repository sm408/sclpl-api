"""F1: persisted history actually reflects what the run measured.

Every field this checks already existed in `state/db.py`'s schema before this batch
-- `run_steps.attempts`, `duration_ms`, `cached`, and `runs.bytes_in`/`bytes_out`/
`retries` -- but `runner._remember` never populated them, so a persisted run always
showed `attempts=1`, `duration_ms=0`, `cached=false`, and zero bytes/retries
regardless of what actually happened. These prove the numbers now written are the
real ones, checked against what the local server itself observed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sclpl.state import db
from tests.integration.conftest import ATTEMPTS


def run_cli(*args: str, cwd: Path, home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sclpl", *args],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=cwd,
        env={
            **os.environ,
            "PYTHONPATH": os.getcwd(),
            "SCLPL_HOME": str(home),
            # Isolated from the real machine-wide cache: the second-run/cache-hit
            # test needs this stable *and* private to the test, not shared state
            # a previous test run (or a real invocation) could have left behind.
            "SCLPL_CACHE_DIR": str(home / "cache"),
        },
    )


def test_persisted_attempts_reconcile_with_what_the_server_actually_received(
    tmp_path: Path, server_url: str
) -> None:
    """The accept criterion, stated directly: F1's own "report counts reconcile
    with observed local-server requests."
    """
    home = tmp_path / "home"
    workflow = tmp_path / "wf.sclpll"
    workflow.write_text(
        f"@workflow orders\n\n@step fetch\n  get {server_url}/flaky/2\n  retry 3\n",
        encoding="utf-8",
    )
    result = run_cli("run", str(workflow), cwd=tmp_path, home=home)
    assert result.returncode == 0, result.stderr

    with db.History(home) as history:
        run = history.recent(limit=1, workflow="orders")[0]
        steps = history.steps_of(run["id"])

    (fetch,) = [step for step in steps if step["step_id"] == "fetch"]
    assert fetch["attempts"] == ATTEMPTS["/flaky/2"] == 3
    assert fetch["status"] == "ok"
    assert fetch["duration_ms"] > 0
    assert fetch["lane"] == "async"


def test_a_cache_hit_is_recorded_as_cached_and_a_single_attempt(
    tmp_path: Path, server_url: str
) -> None:
    home = tmp_path / "home"
    workflow = tmp_path / "wf.sclpll"
    workflow.write_text(
        f"@workflow orders\n\n@step fetch\n  get {server_url}/json\n", encoding="utf-8"
    )

    first = run_cli("run", str(workflow), "--name", "first", cwd=tmp_path, home=home)
    assert first.returncode == 0, first.stderr
    second = run_cli("run", str(workflow), "--name", "second", cwd=tmp_path, home=home)
    assert second.returncode == 0, second.stderr

    with db.History(home) as history:
        run = history.recent(limit=1, workflow="orders")[0]
        assert run["name"] == "second"
        steps = history.steps_of(run["id"])

    (fetch,) = [step for step in steps if step["step_id"] == "fetch"]
    assert fetch["cached"]
    assert fetch["attempts"] == 1


def test_bytes_and_retries_are_summed_onto_the_run_record(tmp_path: Path, server_url: str) -> None:
    home = tmp_path / "home"
    workflow = tmp_path / "wf.sclpll"
    workflow.write_text(
        f"@workflow orders\n\n@step fetch\n  get {server_url}/flaky/1\n  retry 3\n",
        encoding="utf-8",
    )
    result = run_cli("run", str(workflow), cwd=tmp_path, home=home)
    assert result.returncode == 0, result.stderr

    with db.History(home) as history:
        run = history.recent(limit=1, workflow="orders")[0]

    assert run["bytes_in"] > 0
    assert run["retries"] == 1  # one retry: two attempts total on /flaky/1
