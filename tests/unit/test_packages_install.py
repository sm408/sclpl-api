"""H2: validating and atomically installing a package archive."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from sclpl.errors import ValidationError
from sclpl.packages import install as install_mod
from sclpl.packages.build import PACKAGE_MANIFEST, SCHEMA_VERSION


def _write_package(
    path: Path,
    *,
    files: dict[str, bytes] | None = None,
    manifest: dict[str, object] | None = None,
    entry_mode: int | None = None,
) -> None:
    files = files if files is not None else {"workflows/orders.sclpll": b"@workflow orders\n"}
    if manifest is None:
        import hashlib

        entries = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
        canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        manifest = {
            "schema": SCHEMA_VERSION,
            "name": "demo",
            "version": "0.1.0",
            "digest": digest,
            "files": entries,
        }

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(PACKAGE_MANIFEST, json.dumps(manifest))
        for name, data in files.items():
            info = zipfile.ZipInfo(name)
            if entry_mode is not None:
                info.external_attr = entry_mode << 16
            archive.writestr(info, data)


def test_validate_accepts_a_well_formed_package(tmp_path: Path) -> None:
    archive = tmp_path / "demo.sclplpkg"
    _write_package(archive)
    info = install_mod.validate(archive)
    assert (info.name, info.version) == ("demo", "0.1.0")
    assert info.files == ("workflows/orders.sclpll",)


def test_validate_rejects_a_corrupt_archive(tmp_path: Path) -> None:
    archive = tmp_path / "demo.sclplpkg"
    archive.write_bytes(b"not a zip")
    with pytest.raises(ValidationError, match="not a valid package archive"):
        install_mod.validate(archive)


def test_validate_rejects_a_tampered_file(tmp_path: Path) -> None:
    archive = tmp_path / "demo.sclplpkg"
    _write_package(archive)
    # Rewrite one entry's bytes without touching the manifest's recorded digest --
    # simulates tampering or corruption after the archive was built.
    with zipfile.ZipFile(archive) as original:
        manifest = original.read(PACKAGE_MANIFEST)
    with zipfile.ZipFile(archive, "w") as rebuilt:
        rebuilt.writestr(PACKAGE_MANIFEST, manifest)
        rebuilt.writestr("workflows/orders.sclpll", "@workflow tampered\n")
    with pytest.raises(ValidationError, match="does not match its manifest digest"):
        install_mod.validate(archive)


def test_validate_rejects_an_undeclared_entry(tmp_path: Path) -> None:
    archive = tmp_path / "demo.sclplpkg"
    _write_package(archive)
    with zipfile.ZipFile(archive, "a") as reopened:
        reopened.writestr("sneaky.txt", "not in the manifest")
    with pytest.raises(ValidationError, match="undeclared archive entry"):
        install_mod.validate(archive)


@pytest.mark.parametrize(
    "bad_name",
    [
        "../escape.txt",
        "a/../../escape.txt",
        "/absolute.txt",
        "C:/windows.txt",
    ],
)
def test_validate_rejects_path_traversal_and_absolute_entries(
    tmp_path: Path, bad_name: str
) -> None:
    archive = tmp_path / "demo.sclplpkg"
    _write_package(archive, files={bad_name: b"x"})
    with pytest.raises(ValidationError, match="unsafe archive entry name|escapes the install root"):
        install_mod.validate(archive)


def test_validate_rejects_a_symlink_entry(tmp_path: Path) -> None:
    import stat

    archive = tmp_path / "demo.sclplpkg"
    _write_package(
        archive,
        files={"link.txt": b"/etc/passwd"},
        entry_mode=stat.S_IFLNK | 0o777,
    )
    with pytest.raises(ValidationError, match="not a regular file"):
        install_mod.validate(archive)


def test_validate_rejects_a_case_insensitive_collision(tmp_path: Path) -> None:
    archive = tmp_path / "demo.sclplpkg"
    _write_package(archive, files={"Readme.txt": b"a", "readme.txt": b"b"})
    with pytest.raises(ValidationError, match="collide on a case-insensitive filesystem"):
        install_mod.validate(archive)


def test_validate_rejects_a_missing_declared_entry(tmp_path: Path) -> None:
    archive = tmp_path / "demo.sclplpkg"
    _write_package(archive)
    with zipfile.ZipFile(archive) as original:
        manifest = json.loads(original.read(PACKAGE_MANIFEST))
    manifest["files"]["ghost.txt"] = "0" * 64
    with zipfile.ZipFile(archive, "w") as rebuilt:
        rebuilt.writestr(PACKAGE_MANIFEST, json.dumps(manifest))
        rebuilt.writestr("workflows/orders.sclpll", "@workflow orders\n")
    with pytest.raises(ValidationError, match="missing entry"):
        install_mod.validate(archive)


def test_install_places_files_under_name_and_version(tmp_path: Path) -> None:
    archive = tmp_path / "demo.sclplpkg"
    _write_package(archive)
    result = install_mod.install(archive, into=tmp_path / "packages")
    assert result.path == tmp_path / "packages" / "demo" / "0.1.0"
    assert (result.path / "workflows" / "orders.sclpll").read_bytes() == b"@workflow orders\n"
    assert (result.path / PACKAGE_MANIFEST).is_file()


def test_install_refuses_to_overwrite_an_existing_install(tmp_path: Path) -> None:
    archive = tmp_path / "demo.sclplpkg"
    _write_package(archive)
    install_mod.install(archive, into=tmp_path / "packages")
    with pytest.raises(ValidationError, match="already installed"):
        install_mod.install(archive, into=tmp_path / "packages")


def test_failed_install_leaves_no_staging_directory_behind(tmp_path: Path) -> None:
    archive = tmp_path / "demo.sclplpkg"
    _write_package(archive)
    with zipfile.ZipFile(archive, "a") as reopened:
        reopened.writestr("sneaky.txt", "undeclared")

    into = tmp_path / "packages"
    with pytest.raises(ValidationError):
        install_mod.install(archive, into=into)

    assert not into.exists() or list(into.iterdir()) == []
