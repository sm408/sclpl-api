"""F2 end to end: `sclpl runs report` and `sclpl runs diff`, through the real CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def run_cli(*args: str, cwd: Path, home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sclpl", *args],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": os.getcwd(), "SCLPL_HOME": str(home)},
    )


@pytest.fixture
def one_run(tmp_path: Path, server_url: str) -> tuple[Path, Path]:
    """A project directory and a home dir with one recorded run named `orders-run`."""
    home = tmp_path / "home"
    workflow = tmp_path / "wf.sclpll"
    workflow.write_text(
        f"@workflow orders\n\n@step fetch\n  get {server_url}/json\n", encoding="utf-8"
    )
    result = run_cli("run", str(workflow), "--name", "orders-run", cwd=tmp_path, home=home)
    assert result.returncode == 0, result.stderr
    return tmp_path, home


def test_runs_report_text_shows_the_workflow_and_status(one_run: tuple[Path, Path]) -> None:
    cwd, home = one_run
    result = run_cli("runs", "report", "orders-run", cwd=cwd, home=home)
    assert result.returncode == 0, result.stderr
    assert "orders" in result.stdout
    assert "ok" in result.stdout


def test_runs_report_json_is_valid_and_has_the_run_fields(one_run: tuple[Path, Path]) -> None:
    cwd, home = one_run
    result = run_cli("runs", "report", "orders-run", "--format", "json", cwd=cwd, home=home)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["workflow"] == "orders"
    assert payload["status"] == "ok"
    assert payload["steps"][0]["step_id"] == "fetch"


def test_runs_report_html_is_self_contained_and_escapes_content(
    one_run: tuple[Path, Path],
) -> None:
    cwd, home = one_run
    into = cwd / "report.html"
    result = run_cli(
        "runs", "report", "orders-run", "--format", "html", "--into", str(into), cwd=cwd, home=home
    )
    assert result.returncode == 0, result.stderr
    page = into.read_text(encoding="utf-8")
    assert "<title>" in page
    assert "<script" not in page
    assert "http://" not in page and "https://" not in page


def test_runs_diff_between_different_workflows_warns(tmp_path: Path, server_url: str) -> None:
    home = tmp_path / "home"
    orders = tmp_path / "orders.sclpll"
    orders.write_text(
        f"@workflow orders\n\n@step fetch\n  get {server_url}/json\n", encoding="utf-8"
    )
    refunds = tmp_path / "refunds.sclpll"
    refunds.write_text(
        f"@workflow refunds\n\n@step fetch\n  get {server_url}/json\n", encoding="utf-8"
    )

    first = run_cli("run", str(orders), "--name", "run-a", cwd=tmp_path, home=home)
    assert first.returncode == 0, first.stderr
    second = run_cli("run", str(refunds), "--name", "run-b", cwd=tmp_path, home=home)
    assert second.returncode == 0, second.stderr

    result = run_cli("runs", "diff", "run-a", "run-b", cwd=tmp_path, home=home)
    assert result.returncode == 0, result.stderr
    assert "different workflow or environment" in result.stderr


def test_runs_diff_between_two_runs_of_the_same_workflow_does_not_warn(
    tmp_path: Path, server_url: str
) -> None:
    home = tmp_path / "home"
    workflow = tmp_path / "wf.sclpll"
    workflow.write_text(
        f"@workflow orders\n\n@step fetch\n  get {server_url}/json\n", encoding="utf-8"
    )

    first = run_cli("run", str(workflow), "--name", "run-a", cwd=tmp_path, home=home)
    assert first.returncode == 0, first.stderr
    second = run_cli("run", str(workflow), "--name", "run-b", cwd=tmp_path, home=home)
    assert second.returncode == 0, second.stderr

    result = run_cli("runs", "diff", "run-a", "run-b", cwd=tmp_path, home=home)
    assert result.returncode == 0, result.stderr
    assert "different workflow or environment" not in result.stderr
