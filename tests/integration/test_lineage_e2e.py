"""F3 end to end: `sclpl runs which <path>`, through the real CLI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

WRITER = """
@workflow writer

@output report:csv

@step rows
  let [{"n": 1}]

@step write -> report
  save_csv @rows
"""


def run_cli(*args: str, cwd: Path, home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sclpl", *args],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": os.getcwd(), "SCLPL_HOME": str(home)},
    )


def test_runs_which_resolves_the_producing_run(tmp_path: Path) -> None:
    home = tmp_path / "home"
    workflow = tmp_path / "wf.sclpll"
    workflow.write_text(WRITER, encoding="utf-8")
    out = tmp_path / "report.csv"
    result = run_cli(
        "run", str(workflow), str(out), "--name", "writer-run", cwd=tmp_path, home=home
    )
    assert result.returncode == 0, result.stderr

    which = run_cli("runs", "which", str(out), cwd=tmp_path, home=home)
    assert which.returncode == 0, which.stderr
    assert "writer-run" in which.stdout
    assert "modified since" not in which.stderr
    assert "ambiguous" not in which.stderr


def test_runs_which_detects_a_later_modification(tmp_path: Path) -> None:
    home = tmp_path / "home"
    workflow = tmp_path / "wf.sclpll"
    workflow.write_text(WRITER, encoding="utf-8")
    out = tmp_path / "report.csv"
    result = run_cli(
        "run", str(workflow), str(out), "--name", "writer-run", cwd=tmp_path, home=home
    )
    assert result.returncode == 0, result.stderr

    out.write_text("tampered\n", encoding="utf-8")

    which = run_cli("runs", "which", str(out), cwd=tmp_path, home=home)
    assert which.returncode == 0, which.stderr
    assert "modified since this run" in which.stderr


def test_runs_which_reports_ambiguity_across_two_runs(tmp_path: Path) -> None:
    home = tmp_path / "home"
    workflow = tmp_path / "wf.sclpll"
    workflow.write_text(WRITER, encoding="utf-8")
    out = tmp_path / "report.csv"

    first = run_cli("run", str(workflow), str(out), "--name", "run-one", cwd=tmp_path, home=home)
    assert first.returncode == 0, first.stderr
    second = run_cli("run", str(workflow), str(out), "--name", "run-two", cwd=tmp_path, home=home)
    assert second.returncode == 0, second.stderr

    which = run_cli("runs", "which", str(out), cwd=tmp_path, home=home)
    assert which.returncode == 0, which.stderr
    assert "ambiguous: 2 runs" in which.stderr
    assert "run-one" in which.stdout
    assert "run-two" in which.stdout


def test_runs_which_on_a_path_no_run_ever_produced_fails_clearly(tmp_path: Path) -> None:
    home = tmp_path / "home"
    which = run_cli("runs", "which", str(tmp_path / "never.csv"), cwd=tmp_path, home=home)
    assert which.returncode != 0
    assert "no recorded run produced" in which.stderr
