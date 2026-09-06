"""E8: parsing a project's `[outputs]` publication setting."""

from __future__ import annotations

from pathlib import Path

import pytest

from sclpl.errors import ValidationError
from sclpl.project import outputs
from sclpl.project.context import ProjectContext
from sclpl.project.context import load as load_project


def _project(tmp_path: Path, outputs_toml: str = "") -> ProjectContext:
    (tmp_path / "sclpl.toml").write_text(
        f"[project]\nname = 'demo'\n[environments.default]\n{outputs_toml}", encoding="utf-8"
    )
    project = load_project(project=tmp_path)
    assert project is not None
    return project


def test_no_outputs_table_defaults_to_immediate(tmp_path: Path) -> None:
    resolved = outputs.parse(_project(tmp_path))
    assert resolved is outputs.DEFAULT
    assert resolved.publish == "immediate"


def test_an_empty_outputs_table_defaults_to_immediate(tmp_path: Path) -> None:
    resolved = outputs.parse(_project(tmp_path, "[outputs]\n"))
    assert resolved.publish == "immediate"


def test_publish_validated_is_honored(tmp_path: Path) -> None:
    resolved = outputs.parse(_project(tmp_path, "[outputs]\npublish = 'validated'\n"))
    assert resolved.publish == "validated"


def test_an_unknown_publish_value_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="outputs.publish"):
        outputs.parse(_project(tmp_path, "[outputs]\npublish = 'eventually'\n"))


def test_an_unknown_outputs_key_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="unknown outputs key"):
        outputs.parse(_project(tmp_path, "[outputs]\nnonsense = true\n"))
