"""Project test-manifest discovery keeps test execution inputs explicit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sclpl.errors import ValidationError
from sclpl.project.context import ProjectContext
from sclpl.project.context import load as load_project
from sclpl.testing import discover, load, run


def _project(tmp_path: Path) -> ProjectContext | None:
    (tmp_path / "sclpl.toml").write_text(
        "[project]\nname = 'demo'\n[environments.default]\n", encoding="utf-8"
    )
    return load_project(project=tmp_path)


def test_discovers_and_loads_a_versioned_manifest(tmp_path: Path) -> None:
    project = _project(tmp_path)
    assert project is not None
    tests = tmp_path / "tests"
    tests.mkdir()
    path = tests / "orders.test.toml"
    path.write_text(
        "workflow = 'orders'\nfixture = '../fixtures/orders'\nexpected_exit = 4\n"
        "[inputs]\nregion = 'eu'\n[[assertions]]\nstep = 'orders'\ncontract = 'orders.json'\n"
        "[expected_outputs]\norders = 'snapshot.json'\n",
        encoding="utf-8",
    )
    assert discover(project) == [path]
    manifest = load(path, project)
    assert manifest.workflow == "orders"
    assert manifest.expected_exit == 4
    assert manifest.fixture == tmp_path / "fixtures" / "orders"


def test_rejects_fixture_paths_outside_the_project(tmp_path: Path) -> None:
    project = _project(tmp_path)
    assert project is not None
    path = tmp_path / "escape.test.toml"
    path.write_text("workflow = 'orders'\nfixture = '../../outside'\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="escapes project root"):
        load(path, project)


def test_runs_a_manifest_offline_with_isolated_state(tmp_path: Path) -> None:
    project = _project(tmp_path)
    assert project is not None
    (tmp_path / "workflows").mkdir()
    (tmp_path / "workflows" / "one.sclpll").write_text(
        "@workflow one\n\n@step value\n  let 1\n", encoding="utf-8"
    )
    fixtures = tmp_path / "fixtures" / "one"
    fixtures.mkdir(parents=True)
    (tmp_path / "value.contract.json").write_text('{"type":"integer"}', encoding="utf-8")
    (tmp_path / "value.expected.json").write_text("1", encoding="utf-8")
    path = tmp_path / "one.test.toml"
    path.write_text(
        "workflow = 'one'\nfixture = 'fixtures/one'\n[[assertions]]\n"
        "step = 'value'\ncontract = 'value.contract.json'\n"
        "[expected_outputs]\nvalue = 'value.expected.json'\n",
        encoding="utf-8",
    )
    outcome = run(load(path, project), project)
    assert outcome.result.exit_code == 0
    assert outcome.state_dir.is_relative_to(tmp_path / ".sclpl" / "tests")


# -- snapshots (E4) -----------------------------------------------------------------


def _one_step_project(
    tmp_path: Path, *, expected_value: str
) -> tuple[ProjectContext | None, Path, Path]:
    project = _project(tmp_path)
    (tmp_path / "workflows").mkdir()
    (tmp_path / "workflows" / "one.sclpll").write_text(
        "@workflow one\n\n@step value\n  let 2\n", encoding="utf-8"
    )
    fixtures = tmp_path / "fixtures" / "one"
    fixtures.mkdir(parents=True)
    snapshot = tmp_path / "value.expected.json"
    snapshot.write_text(expected_value, encoding="utf-8")
    manifest_path = tmp_path / "one.test.toml"
    manifest_path.write_text(
        "workflow = 'one'\nfixture = 'fixtures/one'\n"
        "[expected_outputs]\nvalue = 'value.expected.json'\n",
        encoding="utf-8",
    )
    return project, manifest_path, snapshot


def test_a_mismatched_snapshot_fails_with_a_remedy(tmp_path: Path) -> None:
    from sclpl.errors import AssertionFailed

    project, manifest_path, _snapshot = _one_step_project(tmp_path, expected_value="1")
    assert project is not None
    with pytest.raises(AssertionFailed, match="--update-snapshots"):
        run(load(manifest_path, project), project)


def test_update_snapshots_rewrites_the_mismatch_instead_of_failing(tmp_path: Path) -> None:
    project, manifest_path, snapshot = _one_step_project(tmp_path, expected_value="1")
    assert project is not None
    outcome = run(load(manifest_path, project), project, update_snapshots=True)
    assert outcome.result.exit_code == 0
    assert outcome.updated == (snapshot,)
    assert json.loads(snapshot.read_text(encoding="utf-8")) == 2


def test_update_snapshots_reports_nothing_when_already_correct(tmp_path: Path) -> None:
    project, manifest_path, _snapshot = _one_step_project(tmp_path, expected_value="2")
    assert project is not None
    outcome = run(load(manifest_path, project), project, update_snapshots=True)
    assert outcome.result.exit_code == 0
    assert outcome.updated == ()


def test_update_snapshots_write_is_atomic_no_scratch_file_left_behind(tmp_path: Path) -> None:
    project, manifest_path, snapshot = _one_step_project(tmp_path, expected_value="1")
    assert project is not None
    run(load(manifest_path, project), project, update_snapshots=True)
    assert list(snapshot.parent.glob("*.tmp-*")) == []
