"""F5: `--require-complete` against a real paginated source.

The hard safety net (`paginate.HARD_CEILING`) is what actually produces a
"partial" run when nobody declared a bound -- 10,000 pages by default, which a
real integration test cannot afford to fetch. Lowered here the same way
`test_paginate.py`'s own unit tests already do, against the real `/paged` server
route `test_completeness.py` (D7) uses.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from sclpl.errors import EXIT_INCOMPLETE
from sclpl.render.plain import PlainSink
from sclpl.render.reporter import Reporter
from sclpl.run import paginate
from sclpl.run.runner import Options, run_workflow
from sclpl.run.sclpll import parse
from sclpl.state import db


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setenv("SCLPL_CACHE_DIR", str(tmp_path / "cache"))


async def _run(source: str, **options: Any) -> Any:
    doc = parse(source)
    async with Reporter([PlainSink(io.StringIO(), verbosity=-2)]) as reporter:
        return await run_workflow(doc, Options(validate=False, **options), reporter)


def run_cli(*args: str, cwd: Path, home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sclpl", *args],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": os.getcwd(), "SCLPL_HOME": str(home)},
    )


async def test_require_complete_does_not_fail_a_fully_complete_run(server_url: str) -> None:
    source = f"@workflow t\n\n@step fetch\n  get {server_url}/json\n"
    result = await _run(source, record=False, require_complete=True)
    assert result.exit_code == 0


async def test_require_complete_fails_a_partial_run_with_exit_incomplete(
    server_url: str, monkeypatch: Any
) -> None:
    monkeypatch.setattr(paginate, "HARD_CEILING", 1)
    source = (
        f"@workflow t\n\n@step fetch\n  get {server_url}/paged\n"
        "  paginate cursor cursor_path=next param=cursor\n"
    )
    result = await _run(source, record=False, require_complete=True)
    assert result.exit_code == EXIT_INCOMPLETE
    assert result.store is not None
    assert result.store.get("fetch")["completeness"]["status"] == "partial"


async def test_a_partial_run_without_require_complete_still_exits_zero(
    server_url: str, monkeypatch: Any
) -> None:
    monkeypatch.setattr(paginate, "HARD_CEILING", 1)
    source = (
        f"@workflow t\n\n@step fetch\n  get {server_url}/paged\n"
        "  paginate cursor cursor_path=next param=cursor\n"
    )
    result = await _run(source, record=False, require_complete=False)
    assert result.exit_code == 0


async def test_require_complete_does_not_override_a_real_step_failure(server_url: str) -> None:
    """A step that actually failed keeps its own exit code -- EXIT_INCOMPLETE is
    only for a run that would otherwise have succeeded.
    """
    source = "@workflow t\n\n@step fetch\n  let 1\n  assert result == 2\n"
    result = await _run(source, record=False, require_complete=True)
    assert result.exit_code != 0
    assert result.exit_code != EXIT_INCOMPLETE


def test_an_ordinary_run_persists_complete_and_n_slash_a_through_the_real_cli(
    tmp_path: Path, server_url: str, monkeypatch: Any
) -> None:
    """Through the real CLI and a real `History` database, so this proves the
    fields actually reach persisted storage -- not just the in-process `Result`
    the direct-call tests above check.
    """
    monkeypatch.setenv("SCLPL_CACHE_DIR", str(tmp_path / "cache2"))
    home = tmp_path / "home"
    workflow = tmp_path / "wf.sclpll"
    workflow.write_text(
        f"@workflow orders\n\n@step fetch\n  get {server_url}/json\n", encoding="utf-8"
    )
    result = run_cli("run", str(workflow), "--name", "orders-run", cwd=tmp_path, home=home)
    assert result.returncode == 0, result.stderr

    with db.History(home) as history:
        run = history.recent(limit=1, workflow="orders")[0]
        assert run["completeness"] == "complete"
        assert run["publication"] == "n/a"
