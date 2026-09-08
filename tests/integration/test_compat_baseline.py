"""A1 — the compatibility baseline pinned in `docs/cli-rebuild/BASELINE.md`.

These are not ordinary feature tests: they exist to fail loudly the moment someone
removes a command, renumbers an exit code, or reshapes `runs export` JSON, so that
change is recognized as a compatibility decision (and the baseline doc updated
deliberately) rather than slipping through as an incidental refactor.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sclpl import errors
from sclpl.ext.plugins import API_STRING, CAPABILITIES, Plugin
from sclpl.state import db

BASELINE_COMMANDS = [
    "call", "run", "validate", "explain", "graph", "fmt", "convert", "import",
    "list", "show", "remove", "init", "doctor", "completion", "contract", "plugin",
    "project", "env", "test", "workflow", "runs", "secret", "docs",
]  # fmt: skip


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sclpl", *args], capture_output=True, text=True, timeout=60
    )


def test_help_exits_zero_and_names_the_tool() -> None:
    result = run_cli("--help")
    assert result.returncode == 0
    assert "pipeline runner for HTTP APIs" in result.stdout


def test_no_baseline_command_disappeared_even_if_new_ones_arrived() -> None:
    """Each pinned command must remain registered, independent of help styling."""
    missing = [name for name in BASELINE_COMMANDS if run_cli(name, "--help").returncode != 0]
    assert missing == []


def test_exit_codes_keep_their_pinned_numbers() -> None:
    assert errors.EXIT_OK == 0
    assert errors.EXIT_STEP_FAILED == 1
    assert errors.EXIT_USAGE == 2
    assert errors.EXIT_VALIDATION == 3
    assert errors.EXIT_ASSERTION == 4
    assert errors.EXIT_CACHE_MISS == 5
    assert errors.EXIT_UNKNOWN_TARGET == 6
    assert errors.EXIT_INTERRUPTED == 130


def test_runs_export_shape_has_the_pinned_top_level_keys(tmp_path: Path) -> None:
    home = tmp_path / "home"
    with db.History(home) as history:
        run = db.RunRecord(id="aaaa1111", name="run-aaaa1111", workflow="orders", status="ok")
        history.record(run)
        payload = db.export(history, "aaaa1111")
    assert set(payload) == {"run", "tags", "ports", "steps"}
    assert isinstance(payload["tags"], list)
    assert isinstance(payload["ports"], list)
    assert isinstance(payload["steps"], list)


def test_plugin_abi_shape_has_the_pinned_fields() -> None:
    plugin = Plugin(name="example")
    for field in ("name", "version", "api", "capabilities", "source", "module", "contributes"):
        assert hasattr(plugin, field)
    assert plugin.api == API_STRING
    assert isinstance(CAPABILITIES, frozenset)


def test_call_json_mode_emits_the_pinned_event_sequence(server_url: str) -> None:
    result = run_cli("--json", "call", "GET", f"{server_url}/json")
    events = [json.loads(line)["event"] for line in result.stderr.strip().splitlines()]
    assert events == ["run_started", "step_started", "step_finished", "run_finished"]
