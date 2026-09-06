"""E6: parsing and enforcing a project's `[policy]` table."""

from __future__ import annotations

from pathlib import Path

import pytest

from sclpl.errors import PolicyDenied, ValidationError
from sclpl.project import policy
from sclpl.project.context import ProjectContext
from sclpl.project.context import load as load_project


def _project(tmp_path: Path, policy_toml: str = "") -> ProjectContext:
    (tmp_path / "sclpl.toml").write_text(
        f"[project]\nname = 'demo'\n[environments.default]\n{policy_toml}", encoding="utf-8"
    )
    project = load_project(project=tmp_path)
    assert project is not None
    return project


def test_no_policy_table_is_the_unrestricted_default(tmp_path: Path) -> None:
    resolved = policy.parse(_project(tmp_path))
    assert resolved is policy.DEFAULT
    assert not resolved.restricts_hosts
    assert not resolved.restricts_outputs
    assert resolved.overwrite is True
    assert resolved.deny_capabilities == frozenset()


def test_declaring_policy_at_all_defaults_overwrite_to_denied(tmp_path: Path) -> None:
    resolved = policy.parse(_project(tmp_path, "[policy]\nhosts = ['api.example.com']\n"))
    assert resolved.overwrite is False


def test_an_explicit_overwrite_true_is_honored(tmp_path: Path) -> None:
    resolved = policy.parse(_project(tmp_path, "[policy]\noverwrite = true\n"))
    assert resolved.overwrite is True


def test_host_allowlist_matches_case_insensitively_and_by_glob(tmp_path: Path) -> None:
    resolved = policy.parse(_project(tmp_path, "[policy]\nhosts = ['*.Example.com']\n"))
    assert resolved.host_allowed("api.example.com")
    assert resolved.host_allowed("API.EXAMPLE.COM")
    assert not resolved.host_allowed("example.com")
    assert not resolved.host_allowed("evil.invalid")


def test_check_host_raises_policy_denied_naming_the_declared_hosts(tmp_path: Path) -> None:
    resolved = policy.parse(_project(tmp_path, "[policy]\nhosts = ['api.example.com']\n"))
    with pytest.raises(PolicyDenied, match="api.example.com"):
        resolved.check_host("evil.invalid")


def test_output_root_accepts_a_path_underneath_it(tmp_path: Path) -> None:
    (tmp_path / "outputs").mkdir()
    resolved = policy.parse(_project(tmp_path, "[policy]\noutput_roots = ['outputs']\n"))
    resolved.check_output(tmp_path / "outputs" / "report.csv")  # does not raise


def test_output_root_rejects_a_sibling_path(tmp_path: Path) -> None:
    (tmp_path / "outputs").mkdir()
    resolved = policy.parse(_project(tmp_path, "[policy]\noutput_roots = ['outputs']\n"))
    with pytest.raises(PolicyDenied, match="outside"):
        resolved.check_output(tmp_path / "elsewhere" / "report.csv")


def test_output_root_rejects_a_path_traversal_that_walks_back_out(tmp_path: Path) -> None:
    (tmp_path / "outputs").mkdir()
    resolved = policy.parse(_project(tmp_path, "[policy]\noutput_roots = ['outputs']\n"))
    escaping = tmp_path / "outputs" / ".." / ".." / "escaped.csv"
    with pytest.raises(PolicyDenied):
        resolved.check_output(escaping)


def test_output_root_follows_a_symlink_to_its_real_location(tmp_path: Path) -> None:
    real_outside = tmp_path.parent / f"{tmp_path.name}-outside"
    real_outside.mkdir(exist_ok=True)
    link = tmp_path / "outputs"
    try:
        link.symlink_to(real_outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks require elevated privileges on this platform")
    try:
        (tmp_path / "sclpl.toml").write_text(
            "[project]\nname = 'demo'\n[environments.default]\n"
            "[policy]\noutput_roots = ['outputs']\n",
            encoding="utf-8",
        )
        project = load_project(project=tmp_path)
        assert project is not None
        resolved = policy.parse(project)
        # The declared root is the symlink; a file written "under" it actually lands
        # in `real_outside`, which was never declared -- resolving both sides is what
        # catches this rather than comparing the unresolved path strings.
        with pytest.raises(PolicyDenied):
            resolved.check_output(link / "report.csv")
    finally:
        link.unlink(missing_ok=True)


def test_no_output_roots_declared_means_unrestricted(tmp_path: Path) -> None:
    resolved = policy.parse(_project(tmp_path, "[policy]\nhosts = ['api.example.com']\n"))
    resolved.check_output(Path("/anywhere/at/all.csv"))  # does not raise


def test_deny_capabilities_rejects_an_unknown_name(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="unknown capability"):
        policy.parse(_project(tmp_path, "[policy]\ndeny_capabilities = ['not-a-real-one']\n"))


def test_deny_capabilities_accepts_a_known_name(tmp_path: Path) -> None:
    resolved = policy.parse(_project(tmp_path, "[policy]\ndeny_capabilities = ['subprocess']\n"))
    assert resolved.deny_capabilities == frozenset({"subprocess"})


def test_an_unknown_policy_key_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="unknown policy key"):
        policy.parse(_project(tmp_path, "[policy]\nnonsense = true\n"))


def test_hosts_must_be_an_array_of_strings(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="policy.hosts"):
        policy.parse(_project(tmp_path, "[policy]\nhosts = 'api.example.com'\n"))


def test_overwrite_must_be_a_boolean(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="policy.overwrite"):
        policy.parse(_project(tmp_path, "[policy]\noverwrite = 'yes'\n"))
