"""Business acceptance journeys (Batch J1, UNIFIED-UPGRADE-PLAN.md section 7).

Each journey under `examples/journeys/` runs fully offline against a recorded
fixture and demonstrates one required failure case: the thing that must never
happen even when everything upstream looks fine.
"""

from __future__ import annotations

import csv
import io
import os
import subprocess
import sys
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
