"""Project test-manifest discovery keeps test execution inputs explicit."""

from __future__ import annotations

import pytest

from sclpl.errors import ValidationError
from sclpl.project.context import load as load_project
from sclpl.testing import discover, load


def _project(tmp_path):
    (tmp_path / "sclpl.toml").write_text(
        "[project]\nname = 'demo'\n[environments.default]\n", encoding="utf-8"
    )
    return load_project(project=tmp_path)


def test_discovers_and_loads_a_versioned_manifest(tmp_path) -> None:
    project = _project(tmp_path)
    assert project is not None
    tests = tmp_path / "tests"
    tests.mkdir()
    path = tests / "orders.test.toml"
    path.write_text(
        "workflow = 'orders'\nfixture = '../fixtures/orders'\nexpected_exit = 4\n"
        "[inputs]\nregion = 'eu'\n[[assertions]]\npath = '$.id'\n"
        "[expected_outputs]\norders = 'snapshot.json'\n",
        encoding="utf-8",
    )
    assert discover(project) == [path]
    manifest = load(path, project)
    assert manifest.workflow == "orders"
    assert manifest.expected_exit == 4
    assert manifest.fixture == tmp_path / "fixtures" / "orders"


def test_rejects_fixture_paths_outside_the_project(tmp_path) -> None:
    project = _project(tmp_path)
    assert project is not None
    path = tmp_path / "escape.test.toml"
    path.write_text("workflow = 'orders'\nfixture = '../../outside'\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="escapes project root"):
        load(path, project)
