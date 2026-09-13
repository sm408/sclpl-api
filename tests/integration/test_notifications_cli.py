"""I4, end to end through the real CLI: delivery is recorded, and never rewrites
the run's own result (Journey 3, UNIFIED-UPGRADE-PLAN.md section 7).
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

WORKFLOW = """
@workflow probe "A trivial workflow that always succeeds"

@step done
  let {"ok": true}
"""


def run_cli(*args: str, cwd: Path, home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sclpl", *args],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=cwd,
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
            "SCLPL_RENDER": "plain",
            "SCLPL_HOME": str(home),
            "SCLPL_CACHE_DIR": str(home / "cache"),
        },
    )


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path / "home"


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length) if length else b""
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def receiver() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/hook"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _project(tmp_path: Path, notification_url: str) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "probe.sclpll").write_text(WORKFLOW, encoding="utf-8")
    (project / "sclpl.toml").write_text(
        "[project]\nname = 'probe'\n[environments.default]\n\n"
        "[notifications.n]\n"
        'kind = "webhook"\n'
        "enabled = true\n"
        f'url = "{notification_url}"\n'
        'on = ["run_finished"]\n',
        encoding="utf-8",
    )
    return project


def test_a_delivered_notification_is_recorded_in_the_run_log(
    tmp_path: Path, home: Path, receiver: str
) -> None:
    project = _project(tmp_path, receiver)
    result = run_cli("run", "probe.sclpll", cwd=project, home=home)
    assert result.returncode == 0, result.stderr
    assert "notification n: delivered" in result.stderr


def test_an_undeliverable_notification_is_recorded_but_never_rewrites_the_result(
    tmp_path: Path, home: Path
) -> None:
    """SPEC 7: "delivery failure is separately recorded" -- the run still exits 0."""
    # Nothing listens here: a closed local port refuses the connection immediately,
    # so the test does not wait out real retry backoff.
    project = _project(tmp_path, "http://127.0.0.1:1/hook")
    result = run_cli("run", "probe.sclpll", cwd=project, home=home)
    assert result.returncode == 0, result.stderr
    assert "notification n: failed" in result.stderr
