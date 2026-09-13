"""Business acceptance journeys (Batch J1, UNIFIED-UPGRADE-PLAN.md section 7).

Each journey under `examples/journeys/` runs fully offline against a recorded
fixture and demonstrates one required failure case: the thing that must never
happen even when everything upstream looks fine.
"""

from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

JOURNEYS = Path(__file__).resolve().parents[2] / "examples" / "journeys"


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


# -- Journey 1: API-to-CSV reporting -------------------------------------------------

JOURNEY_1 = JOURNEYS / "01-api-to-csv-reporting"


def _run_orders_report(fixture: str, out: Path, *, home: Path) -> subprocess.CompletedProcess[str]:
    return run_cli(
        "run",
        str(JOURNEY_1 / "workflows" / "orders_report.sclpll"),
        "--var",
        "base=http://127.0.0.1:8901",
        "--out",
        f"report={out}",
        "--replay",
        str(JOURNEY_1 / "fixtures" / fixture),
        "--strict-replay",
        "--no-record",
        "--no-cache",
        cwd=JOURNEY_1,
        home=home,
    )


def test_api_to_csv_reporting_publishes_a_validated_report(tmp_path: Path, home: Path) -> None:
    out = tmp_path / "report.csv"
    result = _run_orders_report("orders", out, home=home)
    assert result.returncode == 0, result.stderr
    rows = list(csv.DictReader(io.StringIO(out.read_text(encoding="utf-8"))))
    assert rows == [
        {"id": "1", "customer": "Acme", "total": "100"},
        {"id": "2", "customer": "Beta", "total": "200"},
    ]


def test_api_to_csv_reporting_fails_closed_when_a_required_field_disappears(
    tmp_path: Path, home: Path
) -> None:
    """SPEC 7: "Required field disappears; no trusted final report is published"."""
    out = tmp_path / "report.csv"
    result = _run_orders_report("orders_missing_field", out, home=home)
    assert result.returncode == 4, result.stdout + result.stderr
    assert "null values in: total" in result.stdout + result.stderr
    assert not out.exists()


# -- Journey 2: API reconciliation ---------------------------------------------------

JOURNEY_2 = JOURNEYS / "02-api-reconciliation"


def _run_reconciliation(
    ledger: str, out: Path, *, home: Path
) -> subprocess.CompletedProcess[str]:
    return run_cli(
        "run",
        str(JOURNEY_2 / "workflows" / "reconciliation.sclpll"),
        "--var",
        "base=http://127.0.0.1:8902",
        "--var",
        f"ledger_path=fixtures/{ledger}",
        "--out",
        f"report={out}",
        "--replay",
        str(JOURNEY_2 / "fixtures" / "api"),
        "--strict-replay",
        "--no-record",
        "--no-cache",
        cwd=JOURNEY_2,
        home=home,
    )


def test_api_reconciliation_reports_lineage_for_every_row(tmp_path: Path, home: Path) -> None:
    out = tmp_path / "report.json"
    result = _run_reconciliation("ledger.csv", out, home=home)
    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report == [
        {"id": 1, "api_total": 100, "ledger_total": 100, "origin": "matched"},
        {"id": 2, "api_total": 200, "ledger_total": 205, "origin": "mismatch"},
        {"id": 3, "api_total": None, "ledger_total": 50, "origin": "ledger_only"},
        {"id": 4, "api_total": 75, "ledger_total": None, "origin": "api_only"},
    ]


def test_api_reconciliation_fails_closed_on_a_duplicate_join_key(
    tmp_path: Path, home: Path
) -> None:
    """SPEC 7: "Duplicate/missing join keys trigger explicit validation"."""
    out = tmp_path / "report.json"
    result = _run_reconciliation("ledger_duplicate.csv", out, home=home)
    assert result.returncode == 4, result.stdout + result.stderr
    assert "id is not unique" in result.stdout + result.stderr
    assert not out.exists()


# -- Journey 3: API quality monitoring -----------------------------------------------

JOURNEY_3 = JOURNEYS / "03-api-quality-monitoring"


class _NotifyHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length) if length else b""
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def quality_receiver() -> Iterator[None]:
    """The journey's committed `sclpl.toml` fires its webhook at this fixed port."""
    server = ThreadingHTTPServer(("127.0.0.1", 8903), _NotifyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _run_quality_check(fixture: str, out: Path, *, home: Path) -> subprocess.CompletedProcess[str]:
    return run_cli(
        "run",
        str(JOURNEY_3 / "workflows" / "quality_check.sclpll"),
        "--var",
        "base=http://127.0.0.1:8904",
        "--out",
        f"report={out}",
        "--replay",
        str(JOURNEY_3 / "fixtures" / fixture),
        "--strict-replay",
        "--no-record",
        "--no-cache",
        cwd=JOURNEY_3,
        home=home,
    )


def test_api_quality_monitoring_passes_quietly_when_the_schema_holds(
    tmp_path: Path, home: Path
) -> None:
    out = tmp_path / "report.json"
    result = _run_quality_check("orders_ok", out, home=home)
    assert result.returncode == 0, result.stderr
    assert "notification" not in result.stderr
    assert json.loads(out.read_text(encoding="utf-8")) == {"checked_rows": 2, "status": "ok"}


def test_api_quality_monitoring_fails_and_notifies_on_a_breaking_change(
    tmp_path: Path, home: Path, quality_receiver: None
) -> None:
    """SPEC 7: "Breaking schema change fails CI"; the webhook fires and is delivered."""
    out = tmp_path / "report.json"
    result = _run_quality_check("orders_breaking", out, home=home)
    assert result.returncode == 4, result.stdout + result.stderr
    assert "missing column: total" in result.stdout + result.stderr
    assert "notification quality_alert: delivered" in result.stderr
    assert not out.exists()


def test_api_quality_monitoring_delivery_failure_does_not_change_the_result(
    tmp_path: Path, home: Path
) -> None:
    """SPEC 7: "delivery failure is separately recorded" -- exit code is unaffected
    by whether anything was listening for the notification."""
    out = tmp_path / "report.json"
    result = _run_quality_check("orders_breaking", out, home=home)
    assert result.returncode == 4, result.stdout + result.stderr
    assert "notification quality_alert: failed" in result.stderr
    assert not out.exists()


# -- Journey 4: Lightweight ingestion ------------------------------------------------

JOURNEY_4 = JOURNEYS / "04-lightweight-ingestion"


def _run_ingest(fixture: str, out: Path, *, home: Path) -> subprocess.CompletedProcess[str]:
    return run_cli(
        "run",
        str(JOURNEY_4 / "workflows" / "ingest.sclpll"),
        "--var",
        "base=http://127.0.0.1:8905",
        "--out",
        f"dataset={out}",
        "--replay",
        str(JOURNEY_4 / "fixtures" / fixture),
        "--strict-replay",
        "--no-record",
        "--no-cache",
        cwd=JOURNEY_4,
        home=home,
    )


def _parquet_row_count(path: Path) -> int:
    import pyarrow.parquet as pq

    return int(pq.read_table(path).num_rows)


def test_lightweight_ingestion_publishes_a_complete_dataset(tmp_path: Path, home: Path) -> None:
    out = tmp_path / "dataset.parquet"
    result = _run_ingest("records_full", out, home=home)
    assert result.returncode == 0, result.stderr
    assert "published: dataset" in result.stderr
    assert _parquet_row_count(out) == 3


def test_lightweight_ingestion_never_lets_an_incomplete_run_masquerade_as_complete(
    tmp_path: Path, home: Path
) -> None:
    """SPEC 7: "Interrupted output is not mistaken for a completed dataset"."""
    out = tmp_path / "dataset.parquet"

    # A prior good run already published three rows.
    first = _run_ingest("records_full", out, home=home)
    assert first.returncode == 0, first.stderr
    assert _parquet_row_count(out) == 3

    # A later run that only sees two records fails its row-count gate. The
    # writer step still ran and produced a value, but the run as a whole did
    # not succeed, so the staged output is discarded rather than published.
    second = _run_ingest("records_incomplete", out, home=home)
    assert second.returncode == 4, second.stdout + second.stderr
    assert "expected at least 3 rows, found 2" in second.stdout + second.stderr
    assert "discarded staged output(s): dataset" in second.stderr

    # The destination is exactly what the last good run left -- not touched,
    # not truncated, not silently replaced with the two-row attempt.
    assert _parquet_row_count(out) == 3


# -- Journey 5: Integration regression testing ---------------------------------------

JOURNEY_5 = JOURNEYS / "05-integration-regression-testing"


@pytest.fixture
def installed_journey_5(tmp_path: Path, home: Path) -> Path:
    """A real `package build` + `package install` round trip, not a shortcut."""
    archive = tmp_path / "pkg.sclplpkg"
    build = run_cli(
        "package",
        "build",
        "--project",
        str(JOURNEY_5),
        "--out",
        str(archive),
        cwd=JOURNEY_5,
        home=home,
    )
    assert build.returncode == 0, build.stderr

    deployed = tmp_path / "deployed"
    install = run_cli(
        "package", "install", str(archive), "--into", str(deployed), cwd=JOURNEY_5, home=home
    )
    assert install.returncode == 0, install.stderr

    return deployed / "integration-regression-testing" / "1.0.0"


def _run_installed_regression(
    project: Path, out: Path, *, home: Path, fixture_dir: str = "fixtures/orders"
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "sclpl",
            "run",
            "workflows/regression.sclpll",
            "--var",
            "base=http://127.0.0.1:8906",
            "--out",
            f"rows={out}",
            "--replay",
            fixture_dir,
            "--strict-replay",
            "--no-record",
            "--no-cache",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=project,
        env={
            **os.environ,
            "SCLPL_SECRET_DEMO_TOKEN": "secret-token-xyz",
            "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
            "SCLPL_RENDER": "plain",
            "SCLPL_HOME": str(home),
            "SCLPL_CACHE_DIR": str(home / "cache"),
        },
    )


def test_installed_package_replays_auth_retry_and_pagination_offline(
    tmp_path: Path, home: Path, installed_journey_5: Path
) -> None:
    """SPEC 7: "Installed package replays pagination, errors, auth references,
    and output snapshots offline"."""
    out = tmp_path / "rows.csv"
    result = _run_installed_regression(installed_journey_5, out, home=home)
    assert result.returncode == 0, result.stderr
    rows = list(csv.DictReader(io.StringIO(out.read_text(encoding="utf-8"))))
    assert rows == [
        {"id": "1", "total": "100"},
        {"id": "2", "total": "200"},
        {"id": "3", "total": "300"},
    ]


def test_installed_package_fails_before_side_effects_on_a_missing_fixture(
    tmp_path: Path, home: Path, installed_journey_5: Path
) -> None:
    """SPEC 7: "Missing fixture ... fails before side effects"."""
    (installed_journey_5 / "fixtures" / "orders").rename(
        installed_journey_5 / "fixtures" / "orders_hidden"
    )
    out = tmp_path / "rows.csv"
    result = _run_installed_regression(installed_journey_5, out, home=home)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "fixture mismatch" in result.stdout + result.stderr
    assert not out.exists()
