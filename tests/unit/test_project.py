"""Project discovery, schema validation, and environment precedence."""

from __future__ import annotations

from pathlib import Path

import pytest

from sclpl.errors import ValidationError
from sclpl.project import context


def _write(root: Path, text: str) -> None:
    root.mkdir()
    (root / "sclpl.toml").write_text(text, encoding="utf-8")


MANIFEST = """[project]
schema = 1
default_environment = "default"

[project.settings]
limit = 10

[workflows]
paths = ["workflows"]

[environments.default]
[environments.default.settings]
url = "https://default.example"

[environments.staging]
[environments.staging.settings]
url = "https://staging.example"
"""


def test_discovers_nearest_project_and_resolves_relative_paths(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _write(root, MANIFEST)
    nested = root / "nested" / "more"
    nested.mkdir(parents=True)

    loaded = context.load(nested)

    assert loaded is not None
    assert loaded.root == root
    assert loaded.workflow_dirs == [root / "workflows"]
    assert loaded.settings == {"limit": 10, "url": "https://default.example"}


def test_environment_precedence_is_explicit_then_environment_then_local_then_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    _write(root, MANIFEST)
    selection = root / context.SELECTION
    selection.parent.mkdir()
    selection.write_text("staging\n", encoding="utf-8")

    local = context.load(root)
    assert local is not None
    assert local.environment_source == "local selection"
    monkeypatch.setenv("SCLPL_ENV", "default")
    from_environment = context.load(root)
    assert from_environment is not None
    assert from_environment.environment_source == "SCLPL_ENV"
    explicit = context.load(root, env="staging")
    assert explicit is not None
    assert explicit.environment_source == "--env"


def test_unknown_key_schema_and_escaping_path_are_refused(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _write(root, "unexpected = true\n\n" + MANIFEST)
    with pytest.raises(ValidationError, match="unknown manifest key"):
        context.load(root)

    (root / "sclpl.toml").write_text(
        MANIFEST.replace('paths = ["workflows"]', 'paths = ["../"]'), encoding="utf-8"
    )
    loaded = context.load(root)
    assert loaded is not None
    with pytest.raises(ValidationError, match="escapes"):
        _ = loaded.workflow_dirs


def test_plugin_settings_merge_base_and_selected_environment(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _write(
        root,
        MANIFEST
        + """
[plugins.azure_blob]
endpoint_suffix = "blob.core.windows.net"
max_concurrency = "2"

[plugins.azure_blob.profiles.prod]
endpoint_suffix = "blob.core.usgovcloudapi.net"

[environments.staging.plugins.azure_blob]
profile = "prod"
max_concurrency = "8"
""",
    )
    loaded = context.load(root, env="staging")
    assert loaded is not None
    assert loaded.plugin_settings == {
        "azure_blob": {
            "endpoint_suffix": "blob.core.windows.net",
            "max_concurrency": "8",
            "profile": "prod",
            "profiles": {"prod": {"endpoint_suffix": "blob.core.usgovcloudapi.net"}},
        }
    }


def test_plugin_configuration_refuses_secret_values(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _write(root, MANIFEST + "\n[plugins.azure_blob]\naccount_key = 'not-allowed'\n")
    with pytest.raises(ValidationError, match="may not contain secrets"):
        context.load(root)
