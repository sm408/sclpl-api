"""I5: the offline project CI template."""

from __future__ import annotations

from pathlib import Path

import pytest

from sclpl.cli.project_cmd import ci_template
from sclpl.errors import ValidationError


def test_writes_a_workflow_file_at_the_default_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    ci_template(out=Path(".github/workflows/sclpl-ci.yml"), overwrite=False)
    written = tmp_path / ".github" / "workflows" / "sclpl-ci.yml"
    assert written.is_file()


def test_contains_the_offline_checks_and_no_credentials(tmp_path: Path) -> None:
    out = tmp_path / "ci.yml"
    ci_template(out=out, overwrite=False)
    content = out.read_text(encoding="utf-8")
    assert "workflow lock --check" in content
    assert "project check" in content
    assert "test run" in content
    assert "--junit" in content and "--json" in content and "--html" in content
    # No secret-shaped tokens, and no step calls a live network address.
    for banned in ("secret", "token", "password", "api_key", "http://", "https://"):
        assert banned not in content.lower()


def test_refuses_to_overwrite_by_default(tmp_path: Path) -> None:
    out = tmp_path / "ci.yml"
    out.write_text("existing", encoding="utf-8")
    with pytest.raises(ValidationError, match="already exists"):
        ci_template(out=out, overwrite=False)
    assert out.read_text(encoding="utf-8") == "existing"


def test_overwrite_flag_replaces_an_existing_file(tmp_path: Path) -> None:
    out = tmp_path / "ci.yml"
    out.write_text("existing", encoding="utf-8")
    ci_template(out=out, overwrite=True)
    assert "sclpl checks" in out.read_text(encoding="utf-8")
