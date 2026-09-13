"""E6 end to end: project `[policy]` enforced by the real runner and the real CLI.

Host allowlist cases go through `run_workflow` directly against the real local
server (`test_auth_e2e.py`'s pattern): what matters is that the denial happens
before any bytes cross the wire, which is only visible with a real socket, not a
mocked transport. Output-root and overwrite cases go through the actual `sclpl run`
subprocess, because those are decided in `run_workflow` before the scheduler starts,
and the CLI is what wires a project's `[policy]` table to that call in the first
place.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest

from sclpl.render.plain import PlainSink
from sclpl.render.reporter import Reporter
from sclpl.run.runner import Options, run_workflow
from sclpl.run.sclpll import parse
from tests.integration.conftest import ATTEMPTS


def _project(tmp_path: Path, policy_toml: str = "") -> None:
    (tmp_path / "sclpl.toml").write_text(
        f"[project]\nname = 'demo'\n[environments.default]\n{policy_toml}", encoding="utf-8"
    )


async def _run(source: str) -> Any:
    doc = parse(source)
    async with Reporter([PlainSink(io.StringIO(), verbosity=-2)]) as reporter:
        options = Options(validate=False, record=False, no_cache=True)
        return await run_workflow(doc, options, reporter)


# -- host allowlist, including redirects -------------------------------------------


async def test_a_request_to_an_allowed_host_succeeds(
    tmp_path: Path, monkeypatch: Any, server_url: str
) -> None:
    monkeypatch.chdir(tmp_path)
    host = server_url.split("://", 1)[1].split(":", 1)[0]
    _project(tmp_path, f"[policy]\nhosts = ['{host}']\n")
    source = f"@workflow t\n\n@step fetch\n  get {server_url}/json\n"
    result = await _run(source)
    assert result.exit_code == 0, result.outcome.failed if result.outcome else None


async def test_a_request_to_a_host_outside_the_allowlist_is_denied(
    tmp_path: Path, monkeypatch: Any, server_url: str
) -> None:
    monkeypatch.chdir(tmp_path)
    _project(tmp_path, "[policy]\nhosts = ['api.example.com']\n")
    source = f"@workflow t\n\n@step fetch\n  get {server_url}/empty\n"
    result = await _run(source)
    assert result.exit_code != 0
    (error,) = result.outcome.failed.values()
    assert "not in the project's allowed hosts" in str(error)


async def test_a_redirect_to_a_host_outside_the_allowlist_is_denied(
    tmp_path: Path, monkeypatch: Any, server_url: str
) -> None:
    """The allowlist has to see every hop, not just the URL the step wrote.

    `server_url` is on `127.0.0.1`; the redirect target is the same physical server
    reached through the literal hostname `localhost` instead -- a different host
    string, which is exactly what an allowlist keyed on the request's own host would
    otherwise wave through if it only checked the original request.
    """
    monkeypatch.chdir(tmp_path)
    host = server_url.split("://", 1)[1].split(":", 1)[0]
    port = server_url.rsplit(":", 1)[1]
    other_host_same_server = f"http://localhost:{port}"
    _project(tmp_path, f"[policy]\nhosts = ['{host}']\n")
    target = quote(f"{other_host_same_server}/empty", safe="")
    source = f"@workflow t\n\n@step fetch\n  get {server_url}/redirect?to={target}\n"
    result = await _run(source)
    assert result.exit_code != 0
    (error,) = result.outcome.failed.values()
    assert "not in the project's allowed hosts" in str(error)


async def test_a_denied_request_is_not_retried_and_does_not_reach_the_server(
    tmp_path: Path, monkeypatch: Any, server_url: str
) -> None:
    """A policy denial is not a transport failure: it must not consume the retry
    budget, and the request it blocks must never actually leave the process.
    """
    monkeypatch.chdir(tmp_path)
    _project(tmp_path, "[policy]\nhosts = ['api.example.com']\n")
    path = "/flaky/0"
    source = f"@workflow t\n\n@step fetch\n  get {server_url}{path}\n  retry 3\n"
    result = await _run(source)
    assert result.exit_code != 0
    assert path not in ATTEMPTS


# -- output roots ---------------------------------------------------------------


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sclpl", *args],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=cwd,
        env={
            **os.environ,
            "PYTHONPATH": os.getcwd(),
            "SCLPL_CACHE_DIR": str(cwd / ".sclpl-test-cache"),
        },
    )


WRITER = """
@workflow writer "Writes wherever the caller says"

@output report:csv

@step rows
  let [{"a": 1}]

@step write -> report
  save_csv @rows
"""


@pytest.fixture
def writer(tmp_path: Path) -> Path:
    path = tmp_path / "writer.sclpll"
    path.write_text(WRITER, encoding="utf-8")
    return path


def test_an_output_inside_the_declared_root_is_allowed(writer: Path, tmp_path: Path) -> None:
    _project(tmp_path, "[policy]\noutput_roots = ['outputs']\n")
    (tmp_path / "outputs").mkdir()
    result = run_cli("run", str(writer), "outputs/report.csv", "--no-record", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "outputs" / "report.csv").exists()


def test_an_output_outside_the_declared_root_is_denied_before_any_write(
    writer: Path, tmp_path: Path
) -> None:
    _project(tmp_path, "[policy]\noutput_roots = ['outputs']\n")
    (tmp_path / "outputs").mkdir()
    (tmp_path / "elsewhere").mkdir()
    result = run_cli("run", str(writer), "elsewhere/report.csv", "--no-record", cwd=tmp_path)
    assert result.returncode != 0
    assert "outside the project's declared output roots" in result.stderr
    assert not (tmp_path / "elsewhere" / "report.csv").exists()


def test_a_path_traversal_out_of_the_declared_root_is_denied(writer: Path, tmp_path: Path) -> None:
    _project(tmp_path, "[policy]\noutput_roots = ['outputs']\n")
    (tmp_path / "outputs").mkdir()
    escaping = "outputs/../escaped.csv"
    result = run_cli("run", str(writer), escaping, "--no-record", cwd=tmp_path)
    assert result.returncode != 0
    assert "outside the project's declared output roots" in result.stderr
    assert not (tmp_path / "escaped.csv").exists()


def test_validate_is_unaffected_by_an_output_roots_policy(writer: Path, tmp_path: Path) -> None:
    """`validate` never binds concrete output paths (it takes no positional files),
    so a declared `output_roots` policy has nothing to check yet -- this pins that
    E6's preflight change is a no-op here rather than a crash on the `None` binding
    `validate` always has.
    """
    _project(tmp_path, "[policy]\noutput_roots = ['outputs']\n")
    result = run_cli("validate", str(writer), cwd=tmp_path)
    assert result.returncode == 0, result.stderr


# -- overwrite --------------------------------------------------------------------


def test_overwrite_is_denied_by_default_once_a_policy_table_exists(
    writer: Path, tmp_path: Path
) -> None:
    _project(tmp_path, "[policy]\nhosts = ['ignored.invalid']\n")
    out = tmp_path / "report.csv"
    out.write_text("stale", encoding="utf-8")
    result = run_cli("run", str(writer), str(out), "--no-record", cwd=tmp_path)
    assert result.returncode != 0
    assert "refusing to overwrite" in result.stderr
    assert out.read_text(encoding="utf-8") == "stale"


def test_overwrite_flag_replaces_it_anyway(writer: Path, tmp_path: Path) -> None:
    _project(tmp_path, "[policy]\nhosts = ['ignored.invalid']\n")
    out = tmp_path / "report.csv"
    out.write_text("stale", encoding="utf-8")
    result = run_cli("run", str(writer), str(out), "--no-record", "--overwrite", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert out.read_text(encoding="utf-8") != "stale"


def test_policy_overwrite_true_allows_it_without_the_flag(writer: Path, tmp_path: Path) -> None:
    _project(tmp_path, "[policy]\noverwrite = true\n")
    out = tmp_path / "report.csv"
    out.write_text("stale", encoding="utf-8")
    result = run_cli("run", str(writer), str(out), "--no-record", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert out.read_text(encoding="utf-8") != "stale"


def test_a_project_with_no_policy_table_still_overwrites_by_default(
    writer: Path, tmp_path: Path
) -> None:
    """No `[policy]` table at all must behave exactly as it always has -- this is an
    opt-in feature, not a new default that would fail an existing project on upgrade.
    """
    _project(tmp_path)
    out = tmp_path / "report.csv"
    out.write_text("stale", encoding="utf-8")
    result = run_cli("run", str(writer), str(out), "--no-record", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert out.read_text(encoding="utf-8") != "stale"


def test_a_standalone_run_with_no_project_still_overwrites_by_default(
    writer: Path, tmp_path: Path
) -> None:
    out = tmp_path / "report.csv"
    out.write_text("stale", encoding="utf-8")
    result = run_cli("run", str(writer), str(out), "--no-record", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert out.read_text(encoding="utf-8") != "stale"


# -- project check surfaces the resolved policy ------------------------------------


def test_project_check_reports_the_resolved_policy(tmp_path: Path) -> None:
    _project(
        tmp_path,
        "[policy]\nhosts = ['api.example.com']\noutput_roots = ['outputs']\n"
        "deny_capabilities = ['subprocess']\n",
    )
    result = run_cli("project", "check", "--json", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["policy"]["hosts"] == ["api.example.com"]
    assert payload["policy"]["overwrite"] is False
    assert payload["policy"]["deny_capabilities"] == ["subprocess"]


def test_project_check_fails_clearly_on_a_malformed_policy_table(tmp_path: Path) -> None:
    _project(tmp_path, "[policy]\nhosts = 'not-an-array'\n")
    result = run_cli("project", "check", cwd=tmp_path)
    assert result.returncode != 0
    assert "policy.hosts" in result.stderr


# -- capability denial audit --------------------------------------------------------


def test_a_project_declared_capability_denial_reaches_plugin_list(tmp_path: Path) -> None:
    """Audits the existing, pre-E6 enforcement point (plugin activation denies a
    capability before importing the plugin module) actually receives a project's
    own `[policy] deny_capabilities`, not only `--deny-capability` on the command
    line.
    """
    _project(tmp_path, "[policy]\ndeny_capabilities = ['fs:write']\n")
    result = run_cli("plugin", "list", "--refused", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "fs" in result.stdout
    assert "fs:write" in result.stdout
    assert "this run denied" in result.stdout
