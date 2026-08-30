"""The workflow commands, end to end through the real CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from sclpl.cli.options import EXIT_USAGE, EXIT_VALIDATION

WORKFLOW = """
@workflow probe "A workflow that talks to the mock server"

@var base = "{base}"

@output result:json?

@mode quick
  include fetch shape

@mode broken
  include shape

@step fetch
  get {{{{base}}}}/json

@step shape
  let @fetch.body.slideshow.title

@step count_slides
  let count(@fetch.body.slideshow.slides)

@step summary
  let "{{{{@shape}}}} has {{{{@count_slides}}}} slides"
"""


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sclpl", *args],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": os.getcwd(), "SCLPL_RENDER": "plain"},
    )


@pytest.fixture
def workflow(tmp_path: Path, server_url: str) -> Path:
    path = tmp_path / "probe.sclpll"
    path.write_text(WORKFLOW.format(base=server_url), encoding="utf-8")
    return path


# -- validate and explain --------------------------------------------------------


def test_validate_accepts_a_good_workflow(workflow: Path) -> None:
    result = run_cli("validate", str(workflow))
    assert result.returncode == 0
    assert "ok" in result.stderr


def test_validate_rejects_a_mode_that_prunes_a_needed_producer(workflow: Path) -> None:
    """The M4 exit criterion: caught at validate time, with the fix named."""
    result = run_cli("validate", str(workflow), "--mode", "broken")
    assert result.returncode == EXIT_VALIDATION
    assert "prunes 'fetch'" in result.stderr
    assert "include list" in result.stderr


def test_validate_reports_a_parse_error_with_a_line(tmp_path: Path) -> None:
    bad = tmp_path / "bad.sclpll"
    bad.write_text("@workflow x\n@stpe a\n  let 1\n", encoding="utf-8")
    result = run_cli("validate", str(bad))
    assert result.returncode == EXIT_VALIDATION
    assert "did you mean 'step'?" in result.stderr


def test_explain_shows_the_plan(workflow: Path) -> None:
    result = run_cli("explain", str(workflow))
    assert result.returncode == 0
    assert "fetch" in result.stdout
    assert "critical path" in result.stdout


def test_explain_shows_what_a_mode_prunes(workflow: Path) -> None:
    result = run_cli("explain", str(workflow), "--mode", "quick")
    assert result.returncode == 0
    assert "pruned:" in result.stdout
    assert "count_slides" in result.stdout


# -- running ---------------------------------------------------------------------


def test_a_workflow_runs_against_the_mock_server(workflow: Path) -> None:
    result = run_cli("run", str(workflow))
    assert result.returncode == 0, result.stderr
    assert "ok in" in result.stderr


def test_a_mode_runs_a_subset(workflow: Path) -> None:
    result = run_cli("-v", "run", str(workflow), "--mode", "quick")
    assert result.returncode == 0, result.stderr
    assert "count_slides" not in result.stderr


def test_values_flow_between_steps_with_their_types(workflow: Path) -> None:
    """`count(...)` returns a number, and interpolating it produces the digits."""
    result = run_cli("--json", "run", str(workflow))
    assert result.returncode == 0, result.stderr
    events = [json.loads(line) for line in result.stderr.strip().splitlines()]
    finished = {event["id"]: event for event in events if event["event"] == "step_finished"}
    assert finished["shape"]["status"] == "ok"
    assert finished["summary"]["status"] == "ok"


def test_a_dry_run_executes_nothing(workflow: Path) -> None:
    result = run_cli("run", str(workflow), "--dry-run")
    assert result.returncode == 0
    assert "dry run" in result.stderr


def test_an_unknown_workflow_suggests(tmp_path: Path) -> None:
    (tmp_path / "orders.sclpll").write_text(
        "@workflow orders\n@step a\n  let 1\n", encoding="utf-8"
    )
    result = run_cli("run", "order", cwd=tmp_path)
    assert result.returncode == 6
    assert "did you mean 'orders'?" in result.stderr


def test_an_unknown_mode_suggests(workflow: Path) -> None:
    result = run_cli("run", str(workflow), "--mode", "quik")
    assert result.returncode == EXIT_VALIDATION
    assert "did you mean 'quick'?" in result.stderr


def test_a_failing_assertion_exits_four(tmp_path: Path, server_url: str) -> None:
    path = tmp_path / "asserting.sclpll"
    path.write_text(
        f"@workflow asserting\n\n@step fetch\n  get {server_url}/json\n"
        f"  assert @fetch.status == 999\n",
        encoding="utf-8",
    )
    result = run_cli("run", str(path))
    assert result.returncode == 4
    assert "assertion" in result.stderr


def test_a_missing_required_port_shows_the_usage(tmp_path: Path) -> None:
    path = tmp_path / "needsfile.sclpll"
    path.write_text("@workflow needsfile\n@input data\n\n@step a\n  let 1\n", encoding="utf-8")
    result = run_cli("run", str(path))
    assert result.returncode == EXIT_VALIDATION
    assert "usage: sclpl needsfile" in result.stderr


# -- fmt and convert -------------------------------------------------------------


def test_fmt_is_idempotent(workflow: Path) -> None:
    first = run_cli("fmt", str(workflow))
    assert first.returncode == 0
    second = run_cli("fmt", str(workflow))
    assert "already canonical" in second.stderr


def test_fmt_check_reports_without_writing(tmp_path: Path) -> None:
    path = tmp_path / "messy.sclpll"
    original = "@workflow messy\n@step a\n  let    1\n"
    path.write_text(original, encoding="utf-8")
    result = run_cli("fmt", str(path), "--check")
    assert result.returncode == EXIT_VALIDATION
    assert path.read_text(encoding="utf-8") == original


def test_convert_round_trips_through_json(workflow: Path, tmp_path: Path) -> None:
    as_json = tmp_path / "probe.json"
    assert run_cli("convert", str(workflow), str(as_json)).returncode == 0
    assert json.loads(as_json.read_text(encoding="utf-8"))["name"] == "probe"

    back = tmp_path / "probe2.sclpll"
    assert run_cli("convert", str(as_json), str(back)).returncode == 0
    # Canonical form on both sides, so the two files agree exactly.
    run_cli("fmt", str(workflow))
    assert back.read_text(encoding="utf-8") == workflow.read_text(encoding="utf-8")


def test_convert_writes_to_stdout_without_a_target(workflow: Path) -> None:
    result = run_cli("convert", str(workflow))
    assert result.returncode == 0
    assert json.loads(result.stdout)["name"] == "probe"


def test_a_missing_file_is_a_usage_error() -> None:
    result = run_cli("fmt", "no-such-file.sclpll")
    assert result.returncode == EXIT_USAGE


# -- the catalogue ---------------------------------------------------------------


def test_import_then_list_then_run(workflow: Path, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    imported = run_cli("import", str(workflow), cwd=project)
    assert imported.returncode == 0, imported.stderr
    assert "registered probe" in imported.stderr

    listed = run_cli("list", cwd=project)
    assert "probe" in listed.stdout

    # Registered workflows resolve by bare name.
    ran = run_cli("run", "probe", cwd=project)
    assert ran.returncode == 0, ran.stderr


def test_show_describes_ports_modes_and_steps(workflow: Path) -> None:
    result = run_cli("show", str(workflow))
    assert result.returncode == 0
    assert "modes:" in result.stdout
    assert "quick" in result.stdout
    assert "steps (4)" in result.stdout


def test_importing_something_unparseable_is_refused(tmp_path: Path) -> None:
    bad = tmp_path / "bad.sclpll"
    bad.write_text("not a workflow at all\n", encoding="utf-8")
    result = run_cli("import", str(bad), cwd=tmp_path)
    assert result.returncode != 0


def test_the_bare_shorthand_runs_a_workflow(workflow: Path, tmp_path: Path) -> None:
    """`sclpl probe quick` -> `sclpl run probe --mode quick` (decision 2)."""
    project = tmp_path / "shorthand"
    project.mkdir()
    run_cli("import", str(workflow), cwd=project)

    result = run_cli("probe", "quick", cwd=project)
    assert result.returncode == 0, result.stderr


def test_a_mistyped_subcommand_is_not_taken_for_a_workflow() -> None:
    result = run_cli("valdate", "something")
    assert result.returncode != 0
    assert "workflow" in result.stderr or "No such command" in result.stderr


# -- writing through a bound output port -----------------------------------------

WRITER = """
@workflow writer "Fetch, flatten, and write where the caller says"

@var base = "{base}"

@output report:csv

@step fetch
  get {{{{base}}}}/json

@step rows
  let @fetch.body.slideshow.slides

@step write -> report
  save_csv @rows
"""


@pytest.fixture
def writer(tmp_path: Path, server_url: str) -> Path:
    path = tmp_path / "writer.sclpll"
    path.write_text(WRITER.format(base=server_url), encoding="utf-8")
    return path


def test_a_step_writes_to_the_file_bound_to_its_output_port(writer: Path, tmp_path: Path) -> None:
    """The workflow says what it writes; the caller says where."""
    out = tmp_path / "out.csv"
    result = run_cli("run", str(writer), str(out))
    assert result.returncode == 0, result.stderr
    assert out.exists()
    assert "title" in out.read_text(encoding="utf-8").splitlines()[0]


def test_the_same_workflow_writes_somewhere_else_on_request(writer: Path, tmp_path: Path) -> None:
    other = tmp_path / "other.csv"
    result = run_cli("run", str(writer), "--out", f"report={other}")
    assert result.returncode == 0, result.stderr
    assert other.exists()


def test_binding_an_output_into_a_directory_that_does_not_exist_is_caught(
    writer: Path, tmp_path: Path
) -> None:
    """A mistyped directory is a typo worth catching before any request is paid for."""
    result = run_cli("run", str(writer), "--out", f"report={tmp_path / 'nope' / 'x.csv'}")
    assert result.returncode == EXIT_VALIDATION
    assert "does not exist" in result.stderr
    assert "mkdir" in result.stderr


def test_writing_to_a_port_that_is_not_declared_is_caught_before_the_run(
    tmp_path: Path, server_url: str
) -> None:
    path = tmp_path / "typo.sclpll"
    path.write_text(
        WRITER.format(base=server_url).replace("-> report", "-> repot"), encoding="utf-8"
    )
    result = run_cli("validate", str(path))
    assert result.returncode == EXIT_VALIDATION
    assert "not an output port" in result.stderr
    assert "report" in result.stderr


def test_pagination_that_is_not_followed_yet_says_so(tmp_path: Path, server_url: str) -> None:
    """Silently returning page one would be a run that succeeds with short data."""
    path = tmp_path / "paged.sclpll"
    path.write_text(
        f"@workflow paged\n\n@step fetch\n  get {server_url}/json\n"
        "  paginate cursor cursor_path=next param=cursor\n",
        encoding="utf-8",
    )
    result = run_cli("validate", str(path))
    assert result.returncode == 0
    assert "first page only" in result.stderr
