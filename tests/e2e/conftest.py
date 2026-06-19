"""
E2E test fixtures for SCLPLAPI CLI testing.

Uses subprocess to run CLI commands and capture output.
Playwright is used for browser-based testing where applicable,
but SCLPLAPI is primarily a CLI/TUI app so most tests use subprocess.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = PROJECT_ROOT / "examples"
FUNCTIONS_DIR = PROJECT_ROOT / "functions"
TOOLS_DIR = PROJECT_ROOT / "tools"


@pytest.fixture
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES_DIR


@pytest.fixture
def functions_dir() -> Path:
    return FUNCTIONS_DIR


@pytest.fixture
def tools_dir() -> Path:
    return TOOLS_DIR


@pytest.fixture
def tmp_db(tmp_path: Path) -> str:
    return str(tmp_path / "test.db")


@pytest.fixture
def run_cli():
    """Fixture that returns a helper to run SCLPLAPI CLI commands.

    Uses app.ui.cli directly to avoid the interactive launcher.
    """

    def _run(args: list[str], timeout: int = 30, cwd: Path | None = None) -> subprocess.CompletedProcess:
        cmd = [sys.executable, "-m", "app.ui.cli"] + args
        env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT), "PYTHONUNBUFFERED": "1"}
        return subprocess.run(
            cmd,
            cwd=str(cwd or PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

    return _run


@pytest.fixture
def run_sclpll_cli():
    """Fixture that returns a helper to run the SCLPLL compiler CLI."""

    def _run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
        cmd = [sys.executable, "-m", "app.core.engine.sclpll_cli"] + args
        return subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        )

    return _run


@pytest.fixture
def run_tool():
    """Fixture that returns a helper to run tools/ scripts."""

    def _run(tool_name: str, args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(TOOLS_DIR / tool_name)] + args
        return subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        )

    return _run


@pytest.fixture
def sample_workflow_json(tmp_path: Path) -> Path:
    """Create a minimal valid workflow.json for testing."""
    workflow = {
        "id": "test-workflow",
        "name": "Test Workflow",
        "description": "A test workflow",
        "variables": {"base_url": "https://httpbin.org"},
        "steps": [
            {
                "id": "step1",
                "name": "Step 1",
                "type": "request",
                "config": {
                    "inline_request": {
                        "method": "GET",
                        "url": "{{base_url}}/get",
                    }
                },
                "output_variable": "result1",
            },
            {
                "id": "step2",
                "name": "Step 2",
                "type": "request",
                "depends_on": ["step1"],
                "config": {
                    "inline_request": {
                        "method": "GET",
                        "url": "{{base_url}}/get",
                    }
                },
            },
        ],
    }
    path = tmp_path / "workflow.json"
    path.write_text(json.dumps(workflow, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def sample_sclpll(tmp_path: Path) -> Path:
    """Create a minimal .sclpll file for testing."""
    content = '''\
@workflow test-workflow "Test Workflow"
    A test workflow for validation

@base_url https://httpbin.org

@step step1 -> result1
    request GET {{base_url}}/get

@step step2 <- step1
    request GET {{base_url}}/get
'''
    path = tmp_path / "test.sclpll"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def invalid_workflow_json(tmp_path: Path) -> Path:
    """Create an invalid workflow.json with circular deps."""
    workflow = {
        "id": "circular-workflow",
        "name": "Circular Workflow",
        "steps": [
            {"id": "a", "name": "A", "type": "request", "depends_on": ["c"],
             "config": {"inline_request": {"method": "GET", "url": "https://example.com"}}},
            {"id": "b", "name": "B", "type": "request", "depends_on": ["a"],
             "config": {"inline_request": {"method": "GET", "url": "https://example.com"}}},
            {"id": "c", "name": "C", "type": "request", "depends_on": ["b"],
             "config": {"inline_request": {"method": "GET", "url": "https://example.com"}}},
        ],
    }
    path = tmp_path / "circular.json"
    path.write_text(json.dumps(workflow, indent=2), encoding="utf-8")
    return path
