"""B4-B6 end to end: `auth <name>` resolved by the real runner against a real server.

Each test builds a tiny project (`sclpl.toml` plus one workflow) and runs it through
`run_workflow`, the same entrypoint the CLI uses -- so what is under test is the actual
wiring (`runner._auth_profiles`, `execute._apply_auth`), not the `auth`/`oauth`/
`signing` modules in isolation, which `test_auth.py`/`test_signing.py`/`test_oauth.py`
already cover.
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
from sclpl.state import secrets as store


@pytest.fixture(autouse=True)
def no_backends(monkeypatch: Any) -> None:
    monkeypatch.setattr(store, "_keyring", lambda: None)
    monkeypatch.setattr(store, "_fernet", lambda: None)


def _project(tmp_path: Path, auth_toml: str) -> None:
    (tmp_path / "sclpl.toml").write_text(
        f"[project]\nname = 'demo'\n[environments.default]\n{auth_toml}", encoding="utf-8"
    )


async def _run(source: str) -> tuple[Any, list[Any]]:
    doc = parse(source)

    class Recorder:
        def __init__(self) -> None:
            self.events: list[Any] = []

        def handle(self, event: Any) -> None:
            self.events.append(event)

        def close(self) -> None:
            pass

    recorder = Recorder()
    async with Reporter([recorder, PlainSink(io.StringIO(), verbosity=-2)]) as reporter:
        # no_cache: the step cache key does not yet vary by the auth profile's *kind*,
        # only its name (D3's job -- "cached bodies never cross auth identities"), so
        # two tests that both use `auth default` against the same URL could otherwise
        # share a cached response from an on-disk cache that outlives this process.
        options = Options(validate=False, record=False, no_cache=True)
        result = await run_workflow(doc, options, reporter)
    return result, recorder.events


async def test_a_bearer_profile_reaches_the_request(
    tmp_path: Path, monkeypatch: Any, server_url: str
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SCLPL_SECRET_TOKEN", "sk-live-distinctive")
    _project(tmp_path, "[auth.default]\ntype = 'bearer'\nsecret = 'token'\n")
    source = f"@workflow t\n\n@step fetch\n  get {server_url}/echo-auth\n  auth default\n"
    result, _ = await _run(source)
    assert result.exit_code == 0
    body = result.store.get("fetch")["body"]
    assert body["authorization"] == "Bearer sk-live-distinctive"


async def test_an_unknown_auth_profile_is_a_clear_validation_error(
    tmp_path: Path, monkeypatch: Any, server_url: str
) -> None:
    monkeypatch.chdir(tmp_path)
    _project(tmp_path, "[auth.default]\ntype = 'bearer'\nsecret = 'token'\n")
    source = f"@workflow t\n\n@step fetch\n  get {server_url}/echo-auth\n  auth nonexistent\n"
    result, _ = await _run(source)
    assert result.exit_code != 0
    assert any("nonexistent" in str(error) for error in result.outcome.failed.values())


async def test_a_manual_header_and_auth_conflict_is_refused(
    tmp_path: Path, monkeypatch: Any, server_url: str
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SCLPL_SECRET_TOKEN", "sk-live-distinctive")
    _project(tmp_path, "[auth.default]\ntype = 'bearer'\nsecret = 'token'\n")
    source = (
        f"@workflow t\n\n@step fetch\n  get {server_url}/echo-auth\n"
        "  header Authorization: Bearer manual\n  auth default\n"
    )
    result, _ = await _run(source)
    assert result.exit_code != 0
    assert any("also uses auth" in str(error) for error in result.outcome.failed.values())


async def test_hmac_auth_signs_the_request(
    tmp_path: Path, monkeypatch: Any, server_url: str
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SCLPL_SECRET_KEY", "correct-horse-battery-staple")
    _project(tmp_path, "[auth.default]\ntype = 'hmac'\nsecret = 'key'\n")
    source = f"@workflow t\n\n@step fetch\n  get {server_url}/echo-auth\n  auth default\n"
    result, _ = await _run(source)
    assert result.exit_code == 0
    body = result.store.get("fetch")["body"]
    assert body["x-signature"]
    assert body["x-timestamp"]


async def test_auth_does_not_survive_a_cross_origin_redirect(
    tmp_path: Path, monkeypatch: Any, server_url: str
) -> None:
    """httpx strips Authorization on a redirect to a different origin; prove it holds
    for a header this project's own auth profile added, not just client-set ones.
    """
    import threading
    from http.server import ThreadingHTTPServer
    from urllib.parse import quote

    from tests.integration.conftest import Handler

    second = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=second.serve_forever, daemon=True)
    thread.start()
    try:
        other_origin = f"http://127.0.0.1:{second.server_address[1]}"
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("SCLPL_SECRET_TOKEN", "sk-live-distinctive")
        _project(tmp_path, "[auth.default]\ntype = 'bearer'\nsecret = 'token'\n")
        target = quote(f"{other_origin}/echo-auth", safe="")
        source = (
            f"@workflow t\n\n@step fetch\n  get {server_url}/redirect?to={target}\n  auth default\n"
        )
        result, _ = await _run(source)
        assert result.exit_code == 0
        body = result.store.get("fetch")["body"]
        assert body["authorization"] == ""
    finally:
        second.shutdown()
        second.server_close()
        thread.join(timeout=5)


async def test_oauth_auth_refreshes_once_after_a_401(
    tmp_path: Path, monkeypatch: Any, server_url: str
) -> None:
    from sclpl.project import oauth

    oauth._cache.clear()  # noqa: SLF001 - test owns the cache lifetime here
    oauth._locks.clear()  # noqa: SLF001
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SCLPL_SECRET_CID", "client-a")
    monkeypatch.setenv("SCLPL_SECRET_CSECRET", "secret-a")
    _project(
        tmp_path,
        "[auth.default]\ntype = 'oauth2_client_credentials'\n"
        f"token_url = '{server_url}/oauth/token'\n"
        "client_id_secret = 'cid'\nclient_secret_secret = 'csecret'\n",
    )
    source = f"@workflow t\n\n@step fetch\n  get {server_url}/auth-once\n  auth default\n"
    result, _ = await _run(source)
    assert result.exit_code == 0
    body = result.store.get("fetch")["body"]
    assert body["authorization"] == "Bearer tok-2"
