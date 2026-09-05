"""Workflow identity and lock verification are deterministic and side-effect-free."""

from __future__ import annotations

from pathlib import Path

import pytest

from sclpl.errors import ValidationError
from sclpl.project import context, identity, lock


def _project(tmp_path: Path) -> tuple[context.ProjectContext, Path]:
    root = tmp_path / "project"
    root.mkdir()
    (root / "sclpl.toml").write_text(
        """[project]
schema = 1
default_environment = "default"

[environments.default]
[environments.default.settings]
base_url = "https://example.test"
""",
        encoding="utf-8",
    )
    workflow = root / "orders.sclpll"
    workflow.write_text("@workflow orders\n@step fetch\n  let 1\n", encoding="utf-8")
    loaded = context.load(root)
    assert loaded is not None
    return loaded, workflow


def test_lock_round_trips_and_check_does_not_write(tmp_path: Path) -> None:
    loaded, workflow = _project(tmp_path)
    first = identity.identify("orders", workflow, loaded)

    path = lock.write(loaded, [first])
    before = path.read_bytes()
    lock.verify(loaded, identity.identify("orders", workflow, loaded))

    assert path.read_bytes() == before
    assert lock.read(loaded).workflows["orders"]["source"] == "orders.sclpll"


def test_lock_refuses_source_or_nonsecret_configuration_drift(tmp_path: Path) -> None:
    loaded, workflow = _project(tmp_path)
    lock.write(loaded, [identity.identify("orders", workflow, loaded)])
    workflow.write_text("@workflow orders\n@step fetch\n  let 2\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="lock drift"):
        lock.verify(loaded, identity.identify("orders", workflow, loaded))


def test_lock_never_contains_secret_values(tmp_path: Path) -> None:
    loaded, workflow = _project(tmp_path)
    lock.write(loaded, [identity.identify("orders", workflow, loaded)])

    assert "secret" not in lock.path_for(loaded).read_text(encoding="utf-8").lower()
