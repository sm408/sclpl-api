"""`sclpl call` — the M0 exit criterion, and the stdout/stderr split it guarantees."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from sclpl.errors import EXIT_STEP_FAILED, EXIT_USAGE


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the real CLI in a subprocess, so stdout and stderr are genuinely separate."""
    return subprocess.run(
        [sys.executable, "-m", "sclpl", *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_body_goes_to_stdout(server_url: str) -> None:
    result = run_cli("call", "GET", f"{server_url}/json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["slideshow"]["title"] == "Sample"


def test_progress_goes_to_stderr(server_url: str) -> None:
    """Invariant 1: stdout is data, stderr is interface."""
    result = run_cli("call", "GET", f"{server_url}/json")
    json.loads(result.stdout)  # stdout parses as JSON: nothing else was mixed in
    assert "200 OK" in result.stderr


def test_quiet_says_nothing_on_success(server_url: str) -> None:
    result = run_cli("-q", "call", "GET", f"{server_url}/json")
    assert result.returncode == 0
    assert result.stderr == ""
    assert json.loads(result.stdout)  # the data still arrives


def test_verbose_adds_the_step_line(server_url: str) -> None:
    default = run_cli("call", "GET", f"{server_url}/json")
    verbose = run_cli("-v", "call", "GET", f"{server_url}/json")
    assert len(verbose.stderr.splitlines()) > len(default.stderr.splitlines())


def test_json_mode_emits_ndjson_on_stderr(server_url: str) -> None:
    result = run_cli("--json", "call", "GET", f"{server_url}/json")
    assert result.returncode == 0
    events = [json.loads(line) for line in result.stderr.strip().splitlines()]
    assert [event["event"] for event in events] == [
        "run_started",
        "step_started",
        "step_finished",
        "run_finished",
    ]
    assert events[-1]["status"] == "ok"
    # The body is still data on stdout, untouched by the machine view.
    assert json.loads(result.stdout)["slideshow"]["title"] == "Sample"


def test_headers_are_sent(server_url: str) -> None:
    result = run_cli("call", "GET", f"{server_url}/echo-header", "-H", "X-Probe: hello")
    assert json.loads(result.stdout)["x-probe"] == "hello"


def test_a_bad_header_is_a_usage_error(server_url: str) -> None:
    result = run_cli("call", "GET", f"{server_url}/json", "-H", "nonsense")
    assert result.returncode == EXIT_USAGE
    assert "expected 'Name: value'" in result.stderr


def test_an_unknown_method_is_a_usage_error(server_url: str) -> None:
    result = run_cli("call", "FETCH", f"{server_url}/json")
    assert result.returncode == EXIT_USAGE
    assert "unknown method" in result.stderr


def test_a_relative_url_is_a_usage_error() -> None:
    result = run_cli("call", "GET", "httpbin.org/json")
    assert result.returncode == EXIT_USAGE
    assert "absolute URL" in result.stderr


def test_a_transport_failure_exits_one() -> None:
    result = run_cli("call", "GET", "http://127.0.0.1:9/unreachable")
    assert result.returncode == EXIT_STEP_FAILED
    assert "FAIL" in result.stderr


def test_an_http_error_status_is_still_delivered(server_url: str) -> None:
    """A 500 is a response, not a transport failure: the body belongs on stdout."""
    result = run_cli("call", "GET", f"{server_url}/boom")
    assert result.returncode == 0
    assert result.stdout.strip() == "server error"
    assert "500" in result.stderr


def test_an_empty_body_writes_nothing_to_stdout(server_url: str) -> None:
    result = run_cli("call", "GET", f"{server_url}/empty")
    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.parametrize("flag", ["--plain", "--no-color"])
def test_render_flags_are_accepted(server_url: str, flag: str) -> None:
    result = run_cli(flag, "call", "GET", f"{server_url}/json")
    assert result.returncode == 0
    assert "\x1b" not in result.stderr


def test_bare_invocation_prints_help_and_exits_two() -> None:
    result = run_cli()
    assert result.returncode == EXIT_USAGE
    assert "Usage:" in result.stdout


def test_version() -> None:
    result = run_cli("--version")
    assert result.returncode == 0
    assert result.stdout.startswith("sclpl ")
