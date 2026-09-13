"""H3: inspecting, verifying, diffing, and removing installed packages."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from sclpl.errors import ValidationError
from sclpl.packages import install as install_mod
from sclpl.packages import lifecycle
from sclpl.packages.build import PACKAGE_MANIFEST, SCHEMA_VERSION


def _archive(path: Path, name: str, version: str, files: dict[str, bytes]) -> Path:
    entries = {relative: hashlib.sha256(data).hexdigest() for relative, data in files.items()}
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
        for relative, data in files.items():
            archive.writestr(relative, data)
    return path


def test_list_installed_is_empty_for_a_fresh_root(tmp_path: Path) -> None:
    assert lifecycle.list_installed(tmp_path / "packages") == []


def test_list_and_describe_reflect_an_install(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    archive = _archive(tmp_path / "a.sclplpkg", "demo", "1.0.0", {"a.txt": b"hi"})
    install_mod.install(archive, into=root)

    installed = lifecycle.list_installed(root)
    assert [(item.name, item.version) for item in installed] == [("demo", "1.0.0")]

    manifest = lifecycle.describe(root, "demo", "1.0.0")
    assert manifest["name"] == "demo"
    assert manifest["files"] == {"a.txt": hashlib.sha256(b"hi").hexdigest()}


def test_describe_refuses_an_unknown_install(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="is not installed"):
        lifecycle.describe(tmp_path / "packages", "demo", "9.9.9")


def test_verify_passes_for_an_untouched_install(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    archive = _archive(tmp_path / "a.sclplpkg", "demo", "1.0.0", {"a.txt": b"hi"})
    install_mod.install(archive, into=root)
    lifecycle.verify(root, "demo", "1.0.0")  # raises on failure


def test_verify_detects_a_file_modified_after_install(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    archive = _archive(tmp_path / "a.sclplpkg", "demo", "1.0.0", {"a.txt": b"hi"})
    install_mod.install(archive, into=root)
    (root / "demo" / "1.0.0" / "a.txt").write_bytes(b"modified after install")
    with pytest.raises(ValidationError, match="no longer matches its installed digest"):
        lifecycle.verify(root, "demo", "1.0.0")


def test_verify_detects_a_file_removed_after_install(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    archive = _archive(tmp_path / "a.sclplpkg", "demo", "1.0.0", {"a.txt": b"hi"})
    install_mod.install(archive, into=root)
    (root / "demo" / "1.0.0" / "a.txt").unlink()
    with pytest.raises(ValidationError, match="is missing a.txt"):
        lifecycle.verify(root, "demo", "1.0.0")


def test_diff_reports_added_removed_and_changed_files(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    old = _archive(tmp_path / "old.sclplpkg", "demo", "1.0.0", {"a.txt": b"one", "b.txt": b"keep"})
    new = _archive(
        tmp_path / "new.sclplpkg",
        "demo",
        "2.0.0",
        {"a.txt": b"two", "b.txt": b"keep", "c.txt": b"new"},
    )
    install_mod.install(old, into=root)
    install_mod.install(new, into=root)

    changes = lifecycle.diff(root, "demo", "1.0.0", "2.0.0")

    assert changes.added == ("c.txt",)
    assert changes.removed == ()
    assert changes.changed == ("a.txt",)
    assert not changes.is_empty


def test_remove_deletes_an_installed_version(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    archive = _archive(tmp_path / "a.sclplpkg", "demo", "1.0.0", {"a.txt": b"hi"})
    install_mod.install(archive, into=root)
    lifecycle.remove(root, "demo", "1.0.0")
    assert lifecycle.list_installed(root) == []


def test_remove_refuses_a_version_pinned_by_the_current_project(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    archive = _archive(tmp_path / "a.sclplpkg", "demo", "1.0.0", {"a.txt": b"hi"})
    install_mod.install(archive, into=root)
    with pytest.raises(ValidationError, match="required by the current project"):
        lifecycle.remove(root, "demo", "1.0.0", required_by={"demo": "1.0.0"})
    assert lifecycle.list_installed(root) != []


def test_remove_force_overrides_a_pin(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    archive = _archive(tmp_path / "a.sclplpkg", "demo", "1.0.0", {"a.txt": b"hi"})
    install_mod.install(archive, into=root)
    lifecycle.remove(root, "demo", "1.0.0", required_by={"demo": "1.0.0"}, force=True)
    assert lifecycle.list_installed(root) == []


def test_remove_allows_a_different_pinned_version(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    archive = _archive(tmp_path / "a.sclplpkg", "demo", "1.0.0", {"a.txt": b"hi"})
    install_mod.install(archive, into=root)
    lifecycle.remove(root, "demo", "1.0.0", required_by={"demo": "2.0.0"})
    assert lifecycle.list_installed(root) == []
