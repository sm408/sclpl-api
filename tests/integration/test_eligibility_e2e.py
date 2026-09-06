"""E7 end to end: `sclpl validate` catches a mode that stubs past a declared
output's own validation, and does not regress a stub that has nothing to do with it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

WORKFLOW = """
@workflow orders

@output report:csv

@mode full
  include producer downstream rows write

@mode stubbed_validated
  include downstream rows write
  stub producer=42

@mode stubbed_unrelated
  include producer downstream rows write extra
  stub extra=1

@step producer
  let 42
  assert true

@step downstream
  let @producer

@step extra
  let 1

@step rows
  let [{"n": @downstream}]

@step write -> report
  save_csv @rows
"""


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sclpl", *args],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": os.getcwd()},
    )


def _workflow(tmp_path: Path) -> Path:
    path = tmp_path / "orders.sclpll"
    path.write_text(WORKFLOW, encoding="utf-8")
    return path


def test_the_full_mode_validates_cleanly(tmp_path: Path) -> None:
    result = run_cli("validate", str(_workflow(tmp_path)), "--mode", "full", cwd=tmp_path)
    assert result.returncode == 0, result.stderr


def test_a_stub_unrelated_to_any_output_still_validates(tmp_path: Path) -> None:
    """Regression: `compile_plan` used to reject a *kept* step that reads a stubbed
    name, even though `resolve`'s own closure check had just accepted it -- a stub
    that has nothing to do with any assertion must keep working.
    """
    result = run_cli(
        "validate", str(_workflow(tmp_path)), "--mode", "stubbed_unrelated", cwd=tmp_path
    )
    assert result.returncode == 0, result.stderr


def test_stubbing_past_an_outputs_own_assertion_fails_validate(tmp_path: Path) -> None:
    result = run_cli(
        "validate", str(_workflow(tmp_path)), "--mode", "stubbed_validated", cwd=tmp_path
    )
    assert result.returncode != 0
    assert "producer" in result.stderr
    assert "report" in result.stderr
