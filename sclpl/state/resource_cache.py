"""Provider-neutral, content-addressed cache for materialized remote resources."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from uuid import uuid4

from sclpl.errors import CacheMiss
from sclpl.ext.resources import ResourceInfo, ResourceProvider
from sclpl.state.db import default_root


@dataclass(frozen=True, slots=True)
class CachedResource:
    path: Path
    revision: str | None
    size: int

    @property
    def checksum(self) -> str:
        """The SHA-256 address is also the verified cache integrity checksum."""
        return f"sha256:{self.path.name}"


class ResourceCache:
    """A private cache keyed by a hashed URI and opaque provider revision.

    The index deliberately never records logical URIs. This lets a provider accept a
    signed URI without preserving its query string in a user-readable cache manifest.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or default_root() / "resources"
        self._blobs = self.root / "blobs"
        self._index_path = self.root / "index.json"

    def materialize(
        self,
        provider: ResourceProvider,
        uri: str,
        target: Path,
        *,
        read: bool = True,
        write: bool = True,
        require_hit: bool = False,
    ) -> ResourceInfo:
        """Copy a cached object or download it, respecting the run cache policy."""
        if require_hit:
            cached = self.get(uri)
            if cached is None:
                raise self._miss(uri)
            self._copy(cached.path, target)
            return ResourceInfo(
                uri=uri,
                size=cached.size,
                revision=cached.revision,
                checksum=cached.checksum,
            )

        expected: ResourceInfo | None = None
        if read and provider.capabilities().revisions:
            expected = provider.stat(uri)
            if expected.revision is not None:
                cached = self.get(uri, expected.revision)
                if cached is not None:
                    self._copy(cached.path, target)
                    return ResourceInfo(
                        uri=uri,
                        size=expected.size if expected.size is not None else cached.size,
                        modified=expected.modified,
                        revision=expected.revision,
                        content_type=expected.content_type,
                        metadata=expected.metadata,
                        checksum=cached.checksum,
                    )

        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("wb") as handle:
                info = provider.download(uri, handle)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        if write:
            cached = self.put(uri, target, info.revision)
            return replace(info, checksum=cached.checksum)
        return info

    def get(self, uri: str, revision: str | None = None) -> CachedResource | None:
        entry = self._index().get(self._key(uri))
        if not isinstance(entry, dict):
            return None
        version = self._revision_key(revision) if revision is not None else entry.get("latest")
        versions = entry.get("versions")
        if not isinstance(version, str) or not isinstance(versions, dict):
            return None
        value = versions.get(version)
        if not isinstance(value, dict):
            return None
        blob = value.get("blob")
        size = value.get("size")
        if not isinstance(blob, str) or not isinstance(size, int):
            return None
        path = self._blobs / blob
        if not path.is_file() or self._digest(path) != blob:
            return None
        stored_revision = value.get("revision")
        if stored_revision is not None and not isinstance(stored_revision, str):
            return None
        return CachedResource(path, stored_revision, size)

    def put(self, uri: str, source: Path, revision: str | None) -> CachedResource:
        self._blobs.mkdir(parents=True, exist_ok=True)
        temporary = self._blobs / f".{uuid4().hex}.tmp"
        digest = hashlib.sha256()
        with source.open("rb") as reader, temporary.open("wb") as writer:
            for chunk in iter(lambda: reader.read(65536), b""):
                digest.update(chunk)
                writer.write(chunk)
        blob = digest.hexdigest()
        cached_path = self._blobs / blob
        if cached_path.is_file() and self._digest(cached_path) == blob:
            temporary.unlink(missing_ok=True)
        else:
            temporary.replace(cached_path)
        size = cached_path.stat().st_size
        index = self._index()
        key = self._key(uri)
        version = self._revision_key(revision)
        raw_entry = index.get(key)
        if isinstance(raw_entry, dict):
            entry: dict[str, object] = raw_entry
        else:
            entry = {"versions": {}}
            index[key] = entry
        raw_versions = entry.get("versions")
        if isinstance(raw_versions, dict):
            versions: dict[str, object] = raw_versions
        else:
            versions = {}
            entry["versions"] = versions
        versions[version] = {"blob": blob, "revision": revision, "size": size}
        entry["latest"] = version
        self._write_index(index)
        return CachedResource(cached_path, revision, size)

    def _index(self) -> dict[str, object]:
        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_index(self, index: dict[str, object]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.root / f".{uuid4().hex}-index.tmp"
        temporary.write_text(json.dumps(index, sort_keys=True), encoding="utf-8")
        temporary.replace(self._index_path)

    @staticmethod
    def _key(uri: str) -> str:
        return hashlib.sha256(uri.encode("utf-8")).hexdigest()

    @staticmethod
    def _revision_key(revision: str | None) -> str:
        return revision or ""

    @staticmethod
    def _copy(source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    @staticmethod
    def _digest(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as reader:
            for chunk in iter(lambda: reader.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _miss(uri: str) -> CacheMiss:
        del uri
        return CacheMiss(
            "remote resource is not cached and --offline forbids downloading it",
            remedies=["run once without --offline to cache the remote workflow or input"],
        )
