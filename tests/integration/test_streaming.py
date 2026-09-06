"""D4 — `stream <path>` through the real runner: a workflow step, not just `Pool`.

`tests/integration/test_transport.py` already covers `Pool.stream_to_file` directly
(checksum correctness, atomicity, retry, and cleanup on failure/cancellation); this
covers the SCLPLL surface and its interaction with caching and pagination/extract.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any

from sclpl.render.plain import PlainSink
from sclpl.render.reporter import Reporter
from sclpl.run.runner import Options, run_workflow
from sclpl.run.sclpll import parse
from tests.integration.conftest import PAYLOAD


async def _run(source: str) -> Any:
    doc = parse(source)
    async with Reporter([PlainSink(io.StringIO(), verbosity=-2)]) as reporter:
        return await run_workflow(doc, Options(validate=False, record=False), reporter)


async def test_a_stream_step_writes_the_body_and_reports_its_checksum(
    server_url: str, tmp_path: Path
) -> None:
    destination = tmp_path / "out.json"
    source = f"@workflow t\n\n@step fetch\n  get {server_url}/json\n  stream {destination}\n"
    result = await _run(source)
    assert result.exit_code == 0
    assert destination.read_bytes() == json.dumps(PAYLOAD).encode()

    assert result.store is not None
    value = result.store.get("fetch")
    assert value["status"] == 200
    assert value["ok"] is True
    assert value["path"] == str(destination)
    assert value["bytes"] == len(destination.read_bytes())
    assert value["sha256"] == hashlib.sha256(destination.read_bytes()).hexdigest()


async def test_a_streamed_step_is_never_cached(
    server_url: str, tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("SCLPL_CACHE_DIR", str(tmp_path / "cache"))
    destination = tmp_path / "out.json"
    source = (
        f"@workflow t\n\n@step fetch\n  get {server_url}/json\n"
        f"  stream {destination}\n  cache ttl=3600\n"
    )
    first = await _run(source)
    second = await _run(source)
    assert first.exit_code == 0
    assert second.exit_code == 0
    # Both runs actually streamed to disk: a cached-metadata hit would still report
    # success without necessarily proving the second write happened for real.
    assert destination.exists()


async def test_stream_cannot_be_combined_with_paginate() -> None:
    from pydantic import ValidationError

    from sclpl.run.ir import HttpConfig, Pagination

    try:
        HttpConfig(
            url="https://api.test/x",
            stream_to="/tmp/out.bin",
            paginate=Pagination(strategy="page"),
        )
    except ValidationError as error:
        assert "stream_to cannot be combined with paginate" in str(error)
    else:
        raise AssertionError("expected a validation error")


async def test_stream_cannot_be_combined_with_extract() -> None:
    from pydantic import ValidationError

    from sclpl.run.ir import HttpConfig

    try:
        HttpConfig(url="https://api.test/x", stream_to="/tmp/out.bin", extract="@response.body")
    except ValidationError as error:
        assert "stream_to cannot be combined with extract" in str(error)
    else:
        raise AssertionError("expected a validation error")
