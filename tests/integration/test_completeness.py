"""D7 — extraction completeness, through the real runner against a real server.

`conftest.py`'s `/paged` route serves 30 items in pages of 10 (three pages to
exhaustion); `tests/unit/test_paginate.py` already covers the classification logic
directly, so this proves it reaches an actual step's produced value.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from sclpl.render.plain import PlainSink
from sclpl.render.reporter import Reporter
from sclpl.run.runner import Options, run_workflow
from sclpl.run.sclpll import parse


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setenv("SCLPL_CACHE_DIR", str(tmp_path / "cache"))


async def _run(source: str) -> Any:
    doc = parse(source)
    async with Reporter([PlainSink(io.StringIO(), verbosity=-2)]) as reporter:
        return await run_workflow(doc, Options(validate=False, record=False), reporter)


async def test_full_pagination_is_complete_with_every_item_received(server_url: str) -> None:
    source = (
        f"@workflow t\n\n@step fetch\n  get {server_url}/paged\n"
        "  paginate cursor cursor_path=next param=cursor max_pages=40\n"
    )
    result = await _run(source)
    assert result.exit_code == 0
    assert result.store is not None
    completeness = result.store.get("fetch")["completeness"]
    assert completeness["status"] == "complete"
    assert completeness["pages"] == 3
    assert completeness["items_received"] == 30


async def test_a_declared_max_pages_short_of_exhaustion_is_still_complete(
    server_url: str,
) -> None:
    """The workflow asked for exactly one page; getting exactly one is not a failure."""
    source = (
        f"@workflow t\n\n@step fetch\n  get {server_url}/paged\n"
        "  paginate cursor cursor_path=next param=cursor max_pages=1\n"
    )
    result = await _run(source)
    assert result.exit_code == 0
    assert result.store is not None
    completeness = result.store.get("fetch")["completeness"]
    assert completeness["status"] == "complete"
    assert completeness["pages"] == 1
    assert completeness["items_received"] == 10
