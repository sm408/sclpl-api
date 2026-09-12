from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import BinaryIO

import pytest

from sclpl.errors import EXIT_CACHE_MISS, CacheMiss
from sclpl.ext.resources import ResourceCapabilities, ResourceInfo, ResourceUnavailable
from sclpl.state.resource_cache import ResourceCache


class MemoryProvider:
    scheme = "memory"

    def __init__(self, data: bytes, revision: str = "v1") -> None:
        self.data, self.revision = data, revision
        self.downloads = 0
        self.stats = 0

    def capabilities(self) -> ResourceCapabilities:
        return ResourceCapabilities(revisions=True)

    def normalize(self, uri: str) -> str:
        return uri

    def resolve(self, base_uri: str, reference: str) -> str:
        return f"{base_uri.rstrip('/')}/{reference}"

    def stat(self, uri: str) -> ResourceInfo:
        self.stats += 1
        return ResourceInfo(uri=uri, size=len(self.data), revision=self.revision)

    def download(self, uri: str, target: BinaryIO) -> ResourceInfo:
        self.downloads += 1
        target.write(self.data)
        return ResourceInfo(uri=uri, size=len(self.data), revision=self.revision)

    def exists(self, uri: str) -> bool:
        return True

    def list(self, uri: str) -> Iterable[ResourceInfo]:
        return []

    def upload(
        self,
        source: BinaryIO,
        uri: str,
        *,
        overwrite: bool = False,
        expected_revision: str | None = None,
    ) -> ResourceInfo:
        del source, overwrite, expected_revision
        return ResourceInfo(uri=uri, revision=self.revision)

    def display_uri(self, uri: str) -> str:
        return uri


def test_resource_cache_reuses_a_revision_and_serves_offline_without_network(
    tmp_path: Path,
) -> None:
    cache = ResourceCache(tmp_path / "cache")
    provider = MemoryProvider(b"first", "v1")
    uri = "memory://account/container/input.csv?sig=secret"

    first = tmp_path / "first.csv"
    cache.materialize(provider, uri, first)
    second = tmp_path / "second.csv"
    cache.materialize(provider, uri, second)
    offline = tmp_path / "offline.csv"
    info = cache.materialize(provider, uri, offline, require_hit=True)

    assert first.read_bytes() == second.read_bytes() == offline.read_bytes() == b"first"
    assert provider.downloads == 1
    assert provider.stats == 2
    assert info.revision == "v1"
    assert info.checksum == f"sha256:{cache.get(uri, 'v1').path.name}"  # type: ignore[union-attr]
    assert "sig=secret" not in (tmp_path / "cache" / "index.json").read_text(encoding="utf-8")


def test_resource_cache_keeps_distinct_revisions(tmp_path: Path) -> None:
    cache = ResourceCache(tmp_path / "cache")
    provider = MemoryProvider(b"first", "v1")
    uri = "memory://account/container/input.csv"
    cache.materialize(provider, uri, tmp_path / "v1.csv")
    provider.data, provider.revision = b"second", "v2"
    cache.materialize(provider, uri, tmp_path / "v2.csv")

    first = cache.get(uri, "v1")
    second = cache.get(uri, "v2")
    assert first is not None and second is not None
    assert first.path.read_bytes() == b"first"
    assert second.path.read_bytes() == b"second"


def test_resource_cache_offline_miss_has_the_standard_cache_exit_code(tmp_path: Path) -> None:
    with pytest.raises(CacheMiss) as raised:
        ResourceCache(tmp_path / "cache").materialize(
            MemoryProvider(b"never fetched"),
            "memory://account/c/input.csv",
            tmp_path / "input",
            require_hit=True,
        )
    assert raised.value.exit_code == EXIT_CACHE_MISS
    assert "without --offline" in str(raised.value)


def test_resource_cache_detects_corruption_and_repairs_it_online(tmp_path: Path) -> None:
    cache = ResourceCache(tmp_path / "cache")
    provider = MemoryProvider(b"trusted", "v1")
    uri = "memory://account/c/input.csv"
    cache.materialize(provider, uri, tmp_path / "first")
    cached = cache.get(uri, "v1")
    assert cached is not None
    cached.path.write_bytes(b"corrupt")

    with pytest.raises(CacheMiss):
        cache.materialize(provider, uri, tmp_path / "offline", require_hit=True)

    repaired = tmp_path / "repaired"
    info = cache.materialize(provider, uri, repaired)
    assert repaired.read_bytes() == b"trusted"
    assert info.checksum is not None and info.checksum.startswith("sha256:")


def test_resource_cache_rejects_a_provider_checksum_mismatch(tmp_path: Path) -> None:
    class ChecksummedMemory(MemoryProvider):
        def download(self, uri: str, target: BinaryIO) -> ResourceInfo:
            target.write(self.data)
            return ResourceInfo(uri=uri, revision=self.revision, checksum="sha256:deadbeef")

    target = tmp_path / "input"
    with pytest.raises(ResourceUnavailable, match="checksum"):
        ResourceCache(tmp_path / "cache").materialize(
            ChecksummedMemory(b"actual"), "memory://account/c/input.csv", target
        )
    assert not target.exists()


def test_resource_cache_resumes_a_revision_pinned_partial_download(tmp_path: Path) -> None:
    class ResumableMemory(MemoryProvider):
        def __init__(self) -> None:
            super().__init__(b"abcdefgh", "v1")
            self.offsets: list[int] = []
            self.fail_once = True

        def capabilities(self) -> ResourceCapabilities:
            return ResourceCapabilities(revisions=True, resumable_downloads=True)

        def download_range(
            self,
            uri: str,
            target: BinaryIO,
            *,
            offset: int,
            expected_revision: str,
        ) -> ResourceInfo:
            assert expected_revision == self.revision
            self.offsets.append(offset)
            if self.fail_once:
                self.fail_once = False
                target.write(self.data[offset : offset + 3])
                raise ResourceUnavailable("connection interrupted")
            target.write(self.data[offset:])
            return ResourceInfo(uri=uri, size=len(self.data), revision=self.revision)

    cache = ResourceCache(tmp_path / "cache")
    provider = ResumableMemory()
    uri = "memory://account/c/large.csv"
    with pytest.raises(ResourceUnavailable):
        cache.materialize(provider, uri, tmp_path / "first")

    completed = tmp_path / "completed"
    cache.materialize(provider, uri, completed)
    assert completed.read_bytes() == b"abcdefgh"
    assert provider.offsets == [0, 3]


def test_resource_cache_discards_a_corrupt_partial_after_checksum_mismatch(
    tmp_path: Path,
) -> None:
    class BadThenGoodResumable(MemoryProvider):
        def __init__(self) -> None:
            super().__init__(b"abcdefgh", "v1")
            self.offsets: list[int] = []
            self.fail_once = True

        def capabilities(self) -> ResourceCapabilities:
            return ResourceCapabilities(revisions=True, resumable_downloads=True)

        def download_range(
            self,
            uri: str,
            target: BinaryIO,
            *,
            offset: int,
            expected_revision: str,
        ) -> ResourceInfo:
            assert expected_revision == self.revision
            self.offsets.append(offset)
            target.write(self.data[offset:])
            if self.fail_once:
                self.fail_once = False
                return ResourceInfo(
                    uri=uri,
                    size=len(self.data),
                    revision=self.revision,
                    checksum="sha256:deadbeef",
                )
            return ResourceInfo(uri=uri, size=len(self.data), revision=self.revision)

    cache = ResourceCache(tmp_path / "cache")
    provider = BadThenGoodResumable()
    uri = "memory://account/c/large.csv"

    with pytest.raises(ResourceUnavailable, match="checksum"):
        cache.materialize(provider, uri, tmp_path / "first")

    completed = tmp_path / "completed"
    cache.materialize(provider, uri, completed)
    assert completed.read_bytes() == b"abcdefgh"
    # A poisoned partial that keeps its offset would retry from len(data) forever and
    # never repair; the corrupt partial must be discarded so the retry restarts at 0.
    assert provider.offsets == [0, 0]
