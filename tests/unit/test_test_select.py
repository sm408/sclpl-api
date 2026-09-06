"""E4 -- which test manifests a `--changed --base REF` run actually needs.

Builds a real git repository per test: what is under test is `git diff`/`git
ls-files` behavior through subprocess, not a mock of it.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from sclpl.project.context import load as load_project
from sclpl.testing import load
from sclpl.testing.select import changed_paths, select

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t.test",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t.test",
}


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **_GIT_ENV},
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _two_workflow_project(root: Path) -> Any:
    _write(root / "sclpl.toml", "[project]\nname = 'demo'\n[environments.default]\n")
    _write(root / "workflows" / "a.sclpll", "@workflow a\n\n@step value\n  let 1\n")
    _write(root / "workflows" / "b.sclpll", "@workflow b\n\n@step value\n  let 2\n")
    (root / "fixtures" / "a").mkdir(parents=True)
    (root / "fixtures" / "b").mkdir(parents=True)
    _write(root / "a.test.toml", "workflow = 'a'\nfixture = 'fixtures/a'\n")
    _write(root / "b.test.toml", "workflow = 'b'\nfixture = 'fixtures/b'\n")
    return load_project(project=root)


def _commit(root: Path, message: str) -> None:
    _git("add", "-A", cwd=root)
    _git("commit", "-m", message, cwd=root)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git("init", "-q", cwd=tmp_path)
    return tmp_path


def test_no_git_repository_selects_everything(tmp_path: Path) -> None:
    project = _two_workflow_project(tmp_path)
    a = load(tmp_path / "a.test.toml", project)
    b = load(tmp_path / "b.test.toml", project)
    assert changed_paths("HEAD", cwd=tmp_path) is None
    assert select([a, b], project, base="HEAD") == [a, b]


def test_an_unknown_base_ref_selects_everything(repo: Path) -> None:
    project = _two_workflow_project(repo)
    _commit(repo, "base")
    a = load(repo / "a.test.toml", project)
    b = load(repo / "b.test.toml", project)
    assert changed_paths("no-such-ref", cwd=repo) is None
    assert select([a, b], project, base="no-such-ref") == [a, b]


def test_only_the_manifest_whose_workflow_changed_is_selected(repo: Path) -> None:
    project = _two_workflow_project(repo)
    _commit(repo, "base")
    a = load(repo / "a.test.toml", project)
    b = load(repo / "b.test.toml", project)

    _write(repo / "workflows" / "a.sclpll", "@workflow a\n\n@step value\n  let 99\n")
    _commit(repo, "change a")

    assert select([a, b], project, base="HEAD~1") == [a]


def test_a_change_to_a_manifests_own_fixture_selects_it(repo: Path) -> None:
    project = _two_workflow_project(repo)
    _commit(repo, "base")
    a = load(repo / "a.test.toml", project)
    b = load(repo / "b.test.toml", project)

    _write(repo / "fixtures" / "a" / "GET_x_0.json", "{}")
    _commit(repo, "add a fixture")

    assert select([a, b], project, base="HEAD~1") == [a]


def test_an_untracked_file_still_counts_as_changed(repo: Path) -> None:
    project = _two_workflow_project(repo)
    _commit(repo, "base")
    a = load(repo / "a.test.toml", project)
    b = load(repo / "b.test.toml", project)

    _write(repo / "fixtures" / "a" / "GET_x_0.json", "{}")  # never committed

    assert select([a, b], project, base="HEAD") == [a]


def test_a_shared_function_change_selects_every_manifest(repo: Path) -> None:
    project = _two_workflow_project(repo)
    _write(repo / "functions" / "shared.py", "def f():\n    return 1\n")
    _commit(repo, "base")
    a = load(repo / "a.test.toml", project)
    b = load(repo / "b.test.toml", project)

    _write(repo / "functions" / "shared.py", "def f():\n    return 2\n")
    _commit(repo, "change shared function")

    assert select([a, b], project, base="HEAD~1") == [a, b]


def test_a_project_manifest_change_selects_every_manifest(repo: Path) -> None:
    project = _two_workflow_project(repo)
    _commit(repo, "base")
    a = load(repo / "a.test.toml", project)
    b = load(repo / "b.test.toml", project)

    _write(
        repo / "sclpl.toml",
        "[project]\nname = 'demo'\n[environments.default]\n[environments.staging]\n",
    )
    _commit(repo, "add an environment")

    assert select([a, b], project, base="HEAD~1") == [a, b]


def test_an_unrelated_change_selects_nothing(repo: Path) -> None:
    project = _two_workflow_project(repo)
    _commit(repo, "base")
    a = load(repo / "a.test.toml", project)
    b = load(repo / "b.test.toml", project)

    _write(repo / "README.md", "hello")
    _commit(repo, "add a readme")

    assert select([a, b], project, base="HEAD~1") == []
