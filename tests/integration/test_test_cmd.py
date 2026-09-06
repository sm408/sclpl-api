"""E4/E3 — `sclpl test run`, through the real CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sclpl", *args],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": os.getcwd()},
    )


def _project(root: Path) -> Path:
    (root / "sclpl.toml").write_text(
        "[project]\nname = 'demo'\n[environments.default]\n", encoding="utf-8"
    )
    (root / "workflows").mkdir()
    (root / "workflows" / "one.sclpll").write_text(
        "@workflow one\n\n@step value\n  let 1\n", encoding="utf-8"
    )
    (root / "fixtures" / "one").mkdir(parents=True)
    (root / "tests").mkdir()
    snapshot = root / "tests" / "value.expected.json"
    snapshot.write_text("1", encoding="utf-8")
    (root / "tests" / "one.test.toml").write_text(
        "workflow = 'one'\nfixture = '../fixtures/one'\n"
        "[expected_outputs]\nvalue = 'value.expected.json'\n",
        encoding="utf-8",
    )
    return snapshot


def test_running_with_no_path_discovers_and_runs_every_manifest(tmp_path: Path) -> None:
    _project(tmp_path)
    result = run_cli("test", "run", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "passed" in result.stderr


def test_update_snapshots_rewrites_a_mismatch_and_exits_zero(tmp_path: Path) -> None:
    snapshot = _project(tmp_path)
    snapshot.write_text("999", encoding="utf-8")
    result = run_cli("test", "run", "--update-snapshots", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "updated" in result.stderr
    assert json.loads(snapshot.read_text()) == 1


def test_a_real_mismatch_without_update_exits_nonzero(tmp_path: Path) -> None:
    snapshot = _project(tmp_path)
    snapshot.write_text("999", encoding="utf-8")
    result = run_cli("test", "run", cwd=tmp_path)
    assert result.returncode != 0
    assert "--update-snapshots" in result.stderr


def test_changed_without_a_git_repository_still_runs_everything(tmp_path: Path) -> None:
    _project(tmp_path)
    result = run_cli("test", "run", "--changed", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "passed" in result.stderr
