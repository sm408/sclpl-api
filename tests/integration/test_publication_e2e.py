"""E8 end to end: `[outputs] publish = "validated"` through the real `sclpl run` CLI.

The one property that actually matters (SPEC 3.5): a writer branch with no data
relationship to a failing assertion branch must not get its file published anyway
just because it happens to run first or run cleanly on its own.
"""

from __future__ import annotations

import json
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

INDEPENDENT_BRANCHES = """
@workflow orders

@output report:csv

@step validated
  let 1
  assert result == 2

@step rows
  let [{"n": 1}]

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
        env={**os.environ, "PYTHONPATH": os.getcwd(), "SCLPL_HOME": str(cwd / ".home")},
    )


def _project(root: Path, outputs_toml: str) -> None:
    (root / "sclpl.toml").write_text(
        f"[project]\nname = 'demo'\n[environments.default]\n{outputs_toml}", encoding="utf-8"
    )


def _workflow(root: Path, source: str) -> Path:
    path = root / "wf.sclpll"
    path.write_text(source, encoding="utf-8")
    return path


def test_immediate_is_unaffected_by_no_outputs_table(tmp_path: Path) -> None:
    """No `[outputs]` table at all -- and no project either -- must behave exactly
    as it always has: unchanged, this batch is additive.
    """
    workflow = _workflow(tmp_path, WRITER)
    out = tmp_path / "report.csv"
    result = run_cli("run", str(workflow), str(out), "--no-record", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert out.exists()


def test_validated_publication_writes_the_real_file_on_success(tmp_path: Path) -> None:
    _project(tmp_path, "[outputs]\npublish = 'validated'\n")
    workflow = _workflow(tmp_path, WRITER)
    out = tmp_path / "report.csv"
    result = run_cli("run", str(workflow), str(out), "--no-record", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert out.exists()
    assert "n" in out.read_text(encoding="utf-8")
    # No scratch file left behind next to the real destination.
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".report.csv.staged-")]
    assert leftovers == []


def test_validated_publication_leaves_no_file_and_no_scratch_on_failure(tmp_path: Path) -> None:
    _project(tmp_path, "[outputs]\npublish = 'validated'\n")
    workflow = _workflow(
        tmp_path,
        "@workflow orders\n\n@output report:csv\n\n"
        '@step rows\n  let [{"n": 1}]\n\n'
        "@step write -> report\n  save_csv @rows\n"
        "@step boom\n  let 1\n  assert result == 2\n",
    )
    out = tmp_path / "report.csv"
    result = run_cli("run", str(workflow), str(out), "--no-record", "--keep-going", cwd=tmp_path)
    assert result.returncode != 0
    assert not out.exists()
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".report.csv.staged-")]
    assert leftovers == []


def test_validated_publication_preserves_the_last_good_output_on_a_later_failure(
    tmp_path: Path,
) -> None:
    """SPEC 3.5: "preserve the last valid output when validation fails." A second,
    failing run must not touch what a first, successful run already published.
    """
    _project(tmp_path, "[outputs]\npublish = 'validated'\n")
    good = _workflow(tmp_path, WRITER)
    out = tmp_path / "report.csv"
    first = run_cli("run", str(good), str(out), "--no-record", cwd=tmp_path)
    assert first.returncode == 0, first.stderr
    original = out.read_text(encoding="utf-8")

    broken = _workflow(
        tmp_path,
        "@workflow orders\n\n@output report:csv\n\n"
        '@step rows\n  let [{"n": 99}]\n\n'
        "@step write -> report\n  save_csv @rows\n"
        "@step boom\n  let 1\n  assert result == 2\n",
    )
    second = run_cli("run", str(broken), str(out), "--no-record", "--keep-going", cwd=tmp_path)
    assert second.returncode != 0
    assert out.read_text(encoding="utf-8") == original


def test_an_independent_export_is_not_published_when_a_sibling_assertion_fails(
    tmp_path: Path,
) -> None:
    """The actual accept criterion: `write` has no data dependency on `validated` at
    all, and finishes cleanly on its own -- but the run as a whole still fails, and
    the default validated-publication policy must refuse to publish anything from it.
    """
    _project(tmp_path, "[outputs]\npublish = 'validated'\n")
    workflow = _workflow(tmp_path, INDEPENDENT_BRANCHES)
    out = tmp_path / "report.csv"
    result = run_cli("run", str(workflow), str(out), "--no-record", "--keep-going", cwd=tmp_path)
    assert result.returncode != 0
    assert not out.exists(), "an independent, successful export branch got published anyway"


def test_publish_writes_a_generation_manifest(tmp_path: Path) -> None:
    _project(tmp_path, "[outputs]\npublish = 'validated'\n")
    workflow = _workflow(tmp_path, WRITER)
    out = tmp_path / "report.csv"
    result = run_cli("run", str(workflow), str(out), "--no-record", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    manifest_path = tmp_path / ".home" / "publications" / "writer.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["files"]["report"] == str(out)
