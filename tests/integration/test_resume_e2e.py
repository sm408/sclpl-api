"""G3: resume execution -- reusing a prior run's checkpoints for real, through the
actual CLI. G2's own tests cover the planning logic in isolation; this proves the
wiring: a real failed run's succeeded step is never re-fetched on resume, the new
run is linked to its parent, and a refused step blocks resume until acknowledged.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from sclpl.state import db

WORKFLOW = """
@workflow resumable "One step that succeeds, one that always fails to decode"

@var base = "{base}"

@step a
  get {{{{base}}}}/json

@step b
  get {{{{base}}}}/not-json
"""

NON_IDEMPOTENT_WORKFLOW = """
@workflow resumable_write "A GET that succeeds feeding a POST to an unreachable host"

@var base = "{base}"
@var dead = "http://127.0.0.1:1"

@step a
  get {{{{base}}}}/json

@step submit
  post {{{{dead}}}}/submit
  retry 0
  body {{"ref": "{{{{@a}}}}"}}
"""


def run_cli(*args: str, home: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PYTHONPATH": os.getcwd(),
        "SCLPL_RENDER": "plain",
        "SCLPL_HOME": str(home),
        "SCLPL_CACHE_DIR": str(home / "cache"),
    }
    return subprocess.run(
        [sys.executable, "-m", "sclpl", *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


@pytest.fixture
def workflow(tmp_path: Path, server_url: str) -> Path:
    path = tmp_path / "resumable.sclpll"
    path.write_text(WORKFLOW.format(base=server_url), encoding="utf-8")
    return path


@pytest.fixture
def write_workflow(tmp_path: Path, server_url: str) -> Path:
    path = tmp_path / "resumable_write.sclpll"
    path.write_text(NON_IDEMPOTENT_WORKFLOW.format(base=server_url), encoding="utf-8")
    return path


def test_resume_reuses_the_succeeded_step_and_reruns_only_the_failed_one(
    workflow: Path, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    first = run_cli("run", str(workflow), "--name", "attempt1", home=home)
    assert first.returncode != 0, first.stderr

    with db.History(home) as history:
        parent = history.find("attempt1")
        parent_id = parent["id"]
        parent_steps = {row["step_id"]: row for row in history.steps_of(parent_id)}
    assert parent_steps["a"]["status"] == "ok"
    assert parent_steps["b"]["status"] == "failed"

    # --no-cache: the only way "a" can be skipped this time is the checkpoint,
    # not D3's ordinary response cache (which would also skip a re-fetch on its
    # own and so would not prove anything about *this* feature).
    second = run_cli(
        "run",
        str(workflow),
        "--name",
        "attempt2",
        "--resume-from",
        parent_id,
        "--no-cache",
        home=home,
    )
    assert second.returncode != 0, second.stderr
    assert "resuming from" in second.stderr
    assert "1 reused, 1 to run" in second.stderr

    with db.History(home) as history:
        child = history.find("attempt2")
        assert child["parent_run_id"] == parent_id
        child_steps = {row["step_id"]: row for row in history.steps_of(child["id"])}
    # "a" was never scheduled this run at all -- reused, not merely fast.
    assert "a" not in child_steps
    assert child_steps["b"]["status"] == "failed"


def test_resuming_from_an_unrelated_workflow_reruns_everything(
    workflow: Path, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    first = run_cli("run", str(workflow), "--name", "attempt1", home=home)
    assert first.returncode != 0, first.stderr

    with db.History(home) as history:
        parent_id = history.find("attempt1")["id"]

    other = tmp_path / "other.sclpll"
    other_source = WORKFLOW.format(base="http://127.0.0.1:1").replace("resumable", "other")
    other.write_text(other_source, encoding="utf-8")
    result = run_cli("run", str(other), "--resume-from", parent_id, "--dry-run", home=home)
    assert result.returncode == 0, result.stderr
    assert "0 reused" in result.stderr


def test_a_refused_non_idempotent_write_blocks_resume_until_forced(
    write_workflow: Path, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    first = run_cli("run", str(write_workflow), "--name", "attempt1", home=home)
    assert first.returncode != 0, first.stderr

    with db.History(home) as history:
        parent_id = history.find("attempt1")["id"]
        parent_steps = {row["step_id"]: row for row in history.steps_of(parent_id)}
    assert parent_steps["a"]["status"] == "ok"
    assert parent_steps["submit"]["status"] == "failed"

    blocked = run_cli(
        "run",
        str(write_workflow),
        "--name",
        "attempt2",
        "--resume-from",
        parent_id,
        "--no-cache",
        home=home,
    )
    assert blocked.returncode != 0
    assert "resume refused" in blocked.stderr
    assert "submit" in blocked.stderr
    assert "--force-resume" in blocked.stderr
    with db.History(home) as history:
        # A refused resume never even starts: no "attempt2" row was ever written.
        rows = history.recent(10)
    assert not any(row["name"] == "attempt2" for row in rows)

    forced = run_cli(
        "run",
        str(write_workflow),
        "--name",
        "attempt3",
        "--resume-from",
        parent_id,
        "--force-resume",
        "submit",
        "--no-cache",
        home=home,
    )
    assert forced.returncode != 0, forced.stderr  # the dead host is still unreachable
    assert "resuming from" in forced.stderr
    with db.History(home) as history:
        child = history.find("attempt3")
        child_steps = {row["step_id"]: row for row in history.steps_of(child["id"])}
    assert "a" not in child_steps  # reused
    assert child_steps["submit"]["status"] == "failed"  # rerun, as forced
