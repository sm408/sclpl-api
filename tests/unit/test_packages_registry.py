"""H4: a client for a versioned static package index (local directory or HTTPS)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from sclpl.errors import CacheMiss, ValidationError
from sclpl.packages import registry


def _local_registry(
    tmp_path: Path, *, name: str = "demo", version: str = "1.0.0", data: bytes = b"payload"
) -> Path:
    base = tmp_path / "registry"
    base.mkdir()
    (base / f"{name}-{version}.sclplpkg").write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    index = {
        "schema": registry.SCHEMA_VERSION,
        "packages": {name: {version: {"digest": digest, "url": f"{name}-{version}.sclplpkg"}}},
    }
    (base / registry.INDEX_NAME).write_text(json.dumps(index), encoding="utf-8")
    return base


def test_load_index_reads_a_local_directory_registry(tmp_path: Path) -> None:
    base = _local_registry(tmp_path)
    entries = registry.load_index(str(base))
    assert ("demo", "1.0.0") in entries
    assert entries[("demo", "1.0.0")].url == "demo-1.0.0.sclplpkg"


def test_load_index_refuses_a_missing_index(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="no index.json"):
        registry.load_index(str(tmp_path / "empty"))


def test_fetch_downloads_and_verifies_from_a_local_registry(tmp_path: Path) -> None:
    base = _local_registry(tmp_path, data=b"the real payload")
    result = registry.fetch(str(base), "demo", "1.0.0", cache=tmp_path / "cache")
    assert result.path.read_bytes() == b"the real payload"
    assert result.digest == hashlib.sha256(b"the real payload").hexdigest()


def test_fetch_caches_so_a_second_call_does_not_recopy(tmp_path: Path) -> None:
    base = _local_registry(tmp_path)
    cache = tmp_path / "cache"
    first = registry.fetch(str(base), "demo", "1.0.0", cache=cache)
    (base / "demo-1.0.0.sclplpkg").unlink()  # registry now unreachable for the artifact
    second = registry.fetch(str(base), "demo", "1.0.0", cache=cache)
    assert first.path == second.path


def test_fetch_refuses_an_unknown_name_or_version(tmp_path: Path) -> None:
    base = _local_registry(tmp_path)
    with pytest.raises(ValidationError, match="not in the registry index"):
        registry.fetch(str(base), "demo", "9.9.9", cache=tmp_path / "cache")


def test_fetch_refuses_when_the_artifact_does_not_match_its_declared_digest(tmp_path: Path) -> None:
    base = _local_registry(tmp_path)
    index_path = base / registry.INDEX_NAME
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["packages"]["demo"]["1.0.0"]["digest"] = "0" * 64
    index_path.write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(ValidationError, match="does not match the registry's declared digest"):
        registry.fetch(str(base), "demo", "1.0.0", cache=tmp_path / "cache")


def test_fetch_offline_uses_the_cache_without_touching_the_registry(tmp_path: Path) -> None:
    base = _local_registry(tmp_path, data=b"cached payload")
    cache = tmp_path / "cache"
    registry.fetch(str(base), "demo", "1.0.0", cache=cache)

    result = registry.fetch("/does/not/exist", "demo", "1.0.0", cache=cache, offline=True)

    assert result.path.read_bytes() == b"cached payload"
    assert result.digest == hashlib.sha256(b"cached payload").hexdigest()


def test_fetch_offline_without_a_cached_copy_is_a_cache_miss(tmp_path: Path) -> None:
    with pytest.raises(CacheMiss):
        registry.fetch("/does/not/exist", "demo", "1.0.0", cache=tmp_path / "cache", offline=True)


def test_is_url_distinguishes_https_from_local_paths() -> None:
    assert registry._is_url("https://registry.example/pkgs")
    assert registry._is_url("http://registry.example/pkgs")
    assert not registry._is_url("/local/registry")
    assert not registry._is_url("C:/local/registry")


def test_https_index_and_download_send_the_bearer_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    digest = hashlib.sha256(b"remote payload").hexdigest()
    index_payload = {
        "schema": registry.SCHEMA_VERSION,
        "packages": {"demo": {"1.0.0": {"digest": digest, "url": "demo-1.0.0.sclplpkg"}}},
    }
    seen_headers: list[dict[str, str]] = []

    class FakeResponse:
        def __init__(self, payload: object) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> object:
            return self._payload

        def iter_bytes(self) -> Iterator[bytes]:
            yield b"remote payload"

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *exc_info: object) -> None:
            return None

    def fake_get(url: str, *, headers: dict[str, str], follow_redirects: bool) -> FakeResponse:
        seen_headers.append(headers)
        return FakeResponse(index_payload)

    def fake_stream(
        method: str, url: str, *, headers: dict[str, str], follow_redirects: bool
    ) -> FakeResponse:
        seen_headers.append(headers)
        return FakeResponse(None)

    monkeypatch.setenv(registry.TOKEN_ENV, "secret-token")
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "stream", fake_stream)

    result = registry.fetch(
        "https://registry.example/pkgs", "demo", "1.0.0", cache=tmp_path / "cache"
    )

    assert result.path.read_bytes() == b"remote payload"
    assert all(h.get("Authorization") == "Bearer secret-token" for h in seen_headers)
