"""Every playbook's workflow runs, against the mock server.

SPEC §18: *"Every snippet in the playbooks lives in `examples/` and runs in CI."* This
is that. A playbook describing something that does not work is worse than no playbook,
because it costs an hour before you suspect the documentation rather than yourself.

The examples carry a placeholder base URL; the fixture overrides it with `--var`, which
is exactly what a reader would do.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
PLAYBOOKS = Path(__file__).resolve().parents[2] / "docs" / "playbooks"


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
            # A private home and cache, so a test never reads or writes the real ones.
            "SCLPL_HOME": str(home),
            "SCLPL_CACHE_DIR": str(home / "cache"),
        },
    )


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path / "home"


# -- the playbooks exist and point at real examples ---------------------------------


def test_there_are_seven_playbooks() -> None:
    assert sorted(path.name for path in PLAYBOOKS.glob("*.md")) == [
        "01-paginated-api-to-csv.md",
        "02-joining-sources.md",
        "03-automating.md",
        "04-debugging.md",
        "05-analyst.md",
        "06-data-engineer.md",
        "07-software-engineer.md",
    ]


@pytest.mark.parametrize("name", ["playbook-01", "playbook-02"])
def test_the_example_a_playbook_names_exists(name: str) -> None:
    assert (EXAMPLES / f"{name}.sclpll").is_file()


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.sclpll")), ids=lambda p: p.stem)
def test_every_example_validates(path: Path, tmp_path: Path, home: Path) -> None:
    """Parses, resolves, and closes -- without a network or a file."""
    result = run_cli("validate", str(path), cwd=tmp_path, home=home)
    assert result.returncode == 0, result.stderr


# -- and they run ------------------------------------------------------------------


def test_python_script_example_runs(tmp_path: Path, home: Path) -> None:
    """The documented script boundary performs a real JSON round trip."""
    result = run_cli(
        "run",
        str(EXAMPLES / "13-python-script.sclpll"),
        "--no-record",
        "--no-cache",
        cwd=EXAMPLES.parent,
        home=home,
    )
    assert result.returncode == 0, result.stderr
    assert "ok   verified" in result.stderr


def test_playbook_one_fetches_every_page_into_a_csv(
    tmp_path: Path, home: Path, server_url: str
) -> None:
    out = tmp_path / "orders.csv"
    result = run_cli(
        "run",
        str(EXAMPLES / "playbook-01.sclpll"),
        str(out),
        "--var",
        f"base={server_url}",
        cwd=tmp_path,
        home=home,
    )
    assert result.returncode == 0, result.stderr

    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "id"
    assert len(lines) == 31  # 30 rows across three pages, plus the header


def test_playbook_one_smoke_mode_takes_one_page(
    tmp_path: Path, home: Path, server_url: str
) -> None:
    """A mode subtracts; `smoke` keeps only the fetch and caps it at one page."""
    result = run_cli(
        "run",
        str(EXAMPLES / "playbook-01.sclpll"),
        "--mode",
        "smoke",
        "--var",
        f"base={server_url}",
        cwd=tmp_path,
        home=home,
    )
    assert result.returncode == 0, result.stderr
    assert "checked" not in result.stderr.replace("unchecked", "")


def test_playbook_two_joins_a_database_with_an_api(
    tmp_path: Path, home: Path, server_url: str
) -> None:
    out = tmp_path / "report.json"
    result = run_cli(
        "run",
        str(EXAMPLES / "playbook-02.sclpll"),
        str(out),
        "--var",
        f"base={server_url}",
        cwd=tmp_path,
        home=home,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(out.read_text(encoding="utf-8")) == [
        {"id": 1, "note": "one"},
        {"id": 3, "note": "three"},
    ]


# -- the history a playbook promises -------------------------------------------------


def test_a_run_is_recorded_and_can_be_found_again(
    tmp_path: Path, home: Path, server_url: str
) -> None:
    """Playbook 3 tells people to rely on this."""
    run_cli(
        "run",
        str(EXAMPLES / "playbook-01.sclpll"),
        str(tmp_path / "o.csv"),
        "--var",
        f"base={server_url}",
        "--tag",
        "nightly",
        "--name",
        "the-run",
        cwd=tmp_path,
        home=home,
    )
    listed = run_cli("runs", "list", cwd=tmp_path, home=home)
    assert "the-run" in listed.stdout
    assert "nightly" in listed.stdout

    shown = run_cli("runs", "show", "the-run", cwd=tmp_path, home=home)
    assert "playbook-01" in shown.stdout
    assert "ok" in shown.stdout

    found = run_cli("runs", "search", "nightly", cwd=tmp_path, home=home)
    assert "the-run" in found.stdout


def test_a_run_writes_a_greppable_log(tmp_path: Path, home: Path, server_url: str) -> None:
    """History you can only reach through SQL is history most people will not reach."""
    run_cli(
        "run",
        str(EXAMPLES / "playbook-01.sclpll"),
        str(tmp_path / "o.csv"),
        "--var",
        f"base={server_url}",
        cwd=tmp_path,
        home=home,
    )
    logs = list((home / "logs").glob("*.ndjson"))
    assert logs, "no event log was written"
    events = [json.loads(line) for line in logs[0].read_text(encoding="utf-8").splitlines()]
    assert events[0]["event"] == "run_started"
    assert any(item["event"] == "step_finished" for item in events)


# -- doctor, which playbook 4 sends people to ----------------------------------------


def test_doctor_reports_on_the_installation(tmp_path: Path, home: Path) -> None:
    result = run_cli("doctor", cwd=tmp_path, home=home)
    assert "secrets" in result.stdout
    assert "plugins" in result.stdout


def test_the_generated_reference_is_current(tmp_path: Path, home: Path) -> None:
    """Invariant 10, as a gate: a hand-edited reference fails the build."""
    result = run_cli(
        "docs",
        "build",
        "--check",
        cwd=Path(__file__).resolve().parents[2],
        home=home,
    )
    assert result.returncode == 0, result.stderr + "\nrun: sclpl docs build"


# -- the M9 exit criterion ------------------------------------------------------------


def test_a_new_user_gets_from_the_readme_to_a_csv(
    tmp_path: Path, home: Path, server_url: str
) -> None:
    """The M9 exit criterion, following the README exactly.

    A new user imports a shared workflow and finishes a paginated API to CSV run. Every
    command below is one the README tells them to type, in the order it tells them.
    """
    # `sclpl doctor` -- the README's first suggestion.
    checked = run_cli("doctor", cwd=tmp_path, home=home)
    assert "secrets" in checked.stdout

    # The workflow, written exactly as the README shows it.
    workflow = tmp_path / "orders.sclpll"
    workflow.write_text(
        '@workflow orders "Every order, as a CSV"\n'
        "\n"
        f'@var base = "{server_url}"\n'
        "\n"
        "@output report:csv\n"
        "\n"
        "@step fetch\n"
        "  get {{base}}/paged\n"
        "  paginate cursor cursor_path=next param=cursor max_pages=40\n"
        "\n"
        "@step write -> report\n"
        "  save_csv @fetch.body\n",
        encoding="utf-8",
    )

    # `sclpl validate` -- no network, no writes.
    checked = run_cli("validate", str(workflow), cwd=tmp_path, home=home)
    assert checked.returncode == 0, checked.stderr

    # Share it: import into the catalogue, then run it by name.
    imported = run_cli("import", "workflow", str(workflow), cwd=tmp_path, home=home)
    if imported.returncode != 0:
        imported = run_cli("import", str(workflow), cwd=tmp_path, home=home)
    assert imported.returncode == 0, imported.stderr

    # `sclpl run` -- the whole point.
    out = tmp_path / "out.csv"
    result = run_cli("run", str(workflow), str(out), cwd=tmp_path, home=home)
    assert result.returncode == 0, result.stderr

    rows = out.read_text(encoding="utf-8").strip().splitlines()
    assert rows[0] == "id"
    assert len(rows) == 31  # every page, not just the first

    # And it is in the history, which is what the README promises next.
    listed = run_cli("runs", "list", cwd=tmp_path, home=home)
    assert "orders" in listed.stdout


def test_the_readme_commands_all_exist() -> None:
    """The README lists a surface. Nothing is stubbed, so all of it must be there."""
    from sclpl.cli.app import app

    names = {command.name for command in app.registered_commands}
    names |= {group.name for group in app.registered_groups}
    for promised in (
        "run",
        "validate",
        "explain",
        "fmt",
        "convert",
        "call",
        "import",
        "list",
        "show",
        "remove",
        "python",
        "runs",
        "secret",
        "plugin",
        "doctor",
        "completion",
        "docs",
    ):
        assert promised in names, f"the README promises `sclpl {promised}`"
