"""H5: staging a registry index.json and its artifacts for publishing."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from sclpl.errors import ValidationError
from sclpl.packages import registry, release
from sclpl.packages.build import PACKAGE_MANIFEST, SCHEMA_VERSION


def _archive(path: Path, name: str, version: str, data: bytes = b"payload") -> Path:
    entries = {"a.txt": hashlib.sha256(data).hexdigest()}
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    manifest = {
        "schema": SCHEMA_VERSION,
        "name": name,
        "version": version,
        "digest": digest,
        "files": entries,
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(PACKAGE_MANIFEST, json.dumps(manifest))
        archive.writestr("a.txt", data)
    return path


def test_build_index_stages_artifacts_and_an_index(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    a = _archive(source / "demo-1.0.0.sclplpkg", "demo", "1.0.0")
    out = tmp_path / "staged"

    result = release.build_index([a], out=out)

    assert result.entries == (("demo", "1.0.0"),)
    assert (out / "demo-1.0.0.sclplpkg").is_file()
    index = json.loads(result.index_path.read_text(encoding="utf-8"))
    assert index["packages"]["demo"]["1.0.0"]["url"] == "demo-1.0.0.sclplpkg"


def test_build_index_refuses_two_archives_for_the_same_version_with_different_bytes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    # Same declared name/version, genuinely different content -- two independent,
    # equally well-formed archives disagreeing about what "demo 1.0.0" is.
    first = _archive(source / "a.sclplpkg", "demo", "1.0.0", data=b"one")
    second = _archive(source / "b.sclplpkg", "demo", "1.0.0", data=b"two")

    with pytest.raises(ValidationError, match="built twice with different content"):
        release.build_index([first, second], out=tmp_path / "staged")


def test_build_index_allows_rebuilding_identical_content(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    first = _archive(source / "a.sclplpkg", "demo", "1.0.0", data=b"same")
    second = _archive(source / "b.sclplpkg", "demo", "1.0.0", data=b"same")

    result = release.build_index([first, second], out=tmp_path / "staged")

    assert result.entries == (("demo", "1.0.0"),)


def test_staged_index_round_trips_through_the_registry_client(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _archive(source / "demo-1.0.0.sclplpkg", "demo", "1.0.0", data=b"round trip")
    out = tmp_path / "staged"
    release.build_index([source / "demo-1.0.0.sclplpkg"], out=out)

    fetched = registry.fetch(str(out), "demo", "1.0.0", cache=tmp_path / "cache")

    assert fetched.path.read_bytes() == (out / "demo-1.0.0.sclplpkg").read_bytes()
