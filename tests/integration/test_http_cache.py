"""D3 — conditional HTTP caching, through the real runner against a real server.

`/etag` in conftest.py answers 304 when the request's `If-None-Match` matches its
current version, and 200 with a fresh body/ETag otherwise -- a test mutates
`ETAG_STATE` directly to simulate the origin changing between two runs.
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
from tests.integration.conftest import ETAG_STATE


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setenv("SCLPL_CACHE_DIR", str(tmp_path / "cache"))


async def _run(source: str, **overrides: Any) -> Any:
    doc = parse(source)
    async with Reporter([PlainSink(io.StringIO(), verbosity=-2)]) as reporter:
        options = Options(validate=False, record=False, http_cache=True, **overrides)
        return await run_workflow(doc, options, reporter)


def _workflow(server_url: str) -> str:
    return f"@workflow t\n\n@step fetch\n  get {server_url}/etag\n  cache ttl=0\n"


async def test_an_unchanged_resource_is_served_from_cache_via_a_304(
    server_url: str,
) -> None:
    source = _workflow(server_url)
    first = await _run(source)
    assert first.exit_code == 0
    assert first.store.get("fetch")["body"] == {"n": 1}

    second = await _run(source)
    assert second.exit_code == 0
    assert second.store.get("fetch")["body"] == {"n": 1}
    assert second.store.get("fetch")["status"] == 200  # reconstructed, not a raw 304


async def test_a_changed_resource_replaces_the_cached_value(server_url: str) -> None:
    source = _workflow(server_url)
    first = await _run(source)
    assert first.store.get("fetch")["body"] == {"n": 1}

    ETAG_STATE["version"] = "v2"
    ETAG_STATE["n"] = 2
    second = await _run(source)
    assert second.exit_code == 0
    assert second.store.get("fetch")["body"] == {"n": 2}


async def test_revalidation_reaches_the_server_only_once_per_run(
    server_url: str, monkeypatch: Any
) -> None:
    """A 304 still means one request went out; caching means *not fetching blind*,
    not skipping the network on a stale entry altogether.
    """
    calls: list[str] = []
    from sclpl.run.transport import Pool

    original = Pool.request

    async def counting(self: Pool, method: str, url: str, **kwargs: Any) -> Any:
        calls.append(url)
        return await original(self, method, url, **kwargs)

    monkeypatch.setattr(Pool, "request", counting)
    source = _workflow(server_url)
    await _run(source)
    await _run(source)
    assert len(calls) == 2  # one real request per run, even though the second hit


async def test_without_http_cache_a_stale_entry_is_an_outright_refetch(
    server_url: str,
) -> None:
    """The default flag path never sees `stale`: an expired entry is a plain miss,
    exactly as it behaved before D3.
    """
    doc = parse(_workflow(server_url))
    async with Reporter([PlainSink(io.StringIO(), verbosity=-2)]) as reporter:
        options = Options(validate=False, record=False, http_cache=False)
        first = await run_workflow(doc, options, reporter)
    assert first.store is not None
    assert first.store.get("fetch")["body"] == {"n": 1}

    ETAG_STATE["version"] = "v2"
    ETAG_STATE["n"] = 2
    doc2 = parse(_workflow(server_url))
    async with Reporter([PlainSink(io.StringIO(), verbosity=-2)]) as reporter2:
        options2 = Options(validate=False, record=False, http_cache=False)
        second = await run_workflow(doc2, options2, reporter2)
    assert second.store is not None
    assert second.store.get("fetch")["body"] == {"n": 2}


async def test_a_fresh_entry_never_touches_the_network_at_all(
    server_url: str, monkeypatch: Any
) -> None:
    calls: list[str] = []
    from sclpl.run.transport import Pool

    original = Pool.request

    async def counting(self: Pool, method: str, url: str, **kwargs: Any) -> Any:
        calls.append(url)
        return await original(self, method, url, **kwargs)

    monkeypatch.setattr(Pool, "request", counting)
    source = f"@workflow t\n\n@step fetch\n  get {server_url}/etag\n  cache ttl=3600\n"
    await _run(source)
    await _run(source)
    assert len(calls) == 1  # second run served entirely from cache: still fresh
