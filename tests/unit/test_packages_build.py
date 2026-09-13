"""H1: bundling a project's declared surface into one reproducible archive."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from sclpl.errors import ValidationError
from sclpl.packages import build as build_mod
from sclpl.project.context import ProjectContext
from sclpl.project.context import load as load_project


def _project(tmp_path: Path, extra_toml: str = "") -> ProjectContext:
    (tmp_path / "workflows").mkdir()
    (tmp_path / "workflows" / "orders.sclpll").write_text("@workflow orders\n", encoding="utf-8")
    (tmp_path / "sclpl.toml").write_text(
        "[project]\nname = 'demo'\n[environments.default]\n" + extra_toml, encoding="utf-8"
    )
    project = load_project(project=tmp_path)
    assert project is not None
    return project


def test_build_requires_package_name(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="package.name"):
        build_mod.build(_project(tmp_path))


def test_build_requires_package_version(tmp_path: Path) -> None:
    project = _project(tmp_path, "[package]\nname = 'demo'\n")
    with pytest.raises(ValidationError, match="package.version"):
        build_mod.build(project)


def test_build_bundles_declared_workflows_and_manifest(tmp_path: Path) -> None:
    project = _project(tmp_path, "[package]\nname = 'demo'\nversion = '0.1.0'\n")
    result = build_mod.build(project)
    assert "workflows/orders.sclpll" in result.files
    assert "sclpl.toml" in result.files
    assert result.name == "demo"
    assert result.version == "0.1.0"


def test_build_is_byte_identical_across_repeated_builds(tmp_path: Path) -> None:
    project = _project(tmp_path, "[package]\nname = 'demo'\nversion = '0.1.0'\n")
    first = build_mod.build(project, out=tmp_path / "one.sclplpkg")
    second = build_mod.build(project, out=tmp_path / "two.sclplpkg")
    assert first.digest == second.digest
    assert first.path.read_bytes() == second.path.read_bytes()


def test_build_excludes_hidden_files_and_pycache(tmp_path: Path) -> None:
    project = _project(tmp_path, "[package]\nname = 'demo'\nversion = '0.1.0'\n")
    (tmp_path / "workflows" / ".secret").write_text("shh", encoding="utf-8")
    cache = tmp_path / "workflows" / "__pycache__"
    cache.mkdir()
    (cache / "orders.cpython-311.pyc").write_bytes(b"\x00")

    result = build_mod.build(project)

    assert not any(name.startswith("workflows/.") for name in result.files)
    assert not any("__pycache__" in name for name in result.files)


def test_build_excludes_env_and_key_files(tmp_path: Path) -> None:
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets" / ".env").write_text("TOKEN=x", encoding="utf-8")
    (tmp_path / "secrets" / "client.pem").write_text("cert", encoding="utf-8")
    project = _project(
        tmp_path,
        "[package]\nname = 'demo'\nversion = '0.1.0'\ninclude = ['secrets/*']\n",
    )

    result = build_mod.build(project)

    assert not any(name.startswith("secrets/") for name in result.files)


def test_build_excludes_declared_output_roots_even_when_included(tmp_path: Path) -> None:
    (tmp_path / "generated").mkdir()
    (tmp_path / "generated" / "report.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    project = _project(
        tmp_path,
        "[package]\nname = 'demo'\nversion = '0.1.0'\ninclude = ['generated/*']\n"
        "[policy]\noutput_roots = ['generated']\n",
    )

    result = build_mod.build(project)

    assert not any(name.startswith("generated/") for name in result.files)


def test_build_manifest_lists_every_file_digest(tmp_path: Path) -> None:
    project = _project(tmp_path, "[package]\nname = 'demo'\nversion = '0.1.0'\n")
    result = build_mod.build(project)

    with zipfile.ZipFile(result.path) as archive:
        manifest = json.loads(archive.read(build_mod.PACKAGE_MANIFEST))

    assert manifest["name"] == "demo"
    assert manifest["version"] == "0.1.0"
    assert manifest["digest"] == result.digest
    assert set(manifest["files"]) == set(result.files)
    assert all(isinstance(value, str) and len(value) == 64 for value in manifest["files"].values())


def test_build_defaults_output_to_dist_directory(tmp_path: Path) -> None:
    project = _project(tmp_path, "[package]\nname = 'demo'\nversion = '0.1.0'\n")
    result = build_mod.build(project)
    assert result.path == tmp_path / "dist" / "demo-0.1.0.sclplpkg"
    assert result.path.is_file()
