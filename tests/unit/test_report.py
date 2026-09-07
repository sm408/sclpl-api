"""F2: text/JSON/HTML run summaries -- unknown fields, and untrusted content."""

from __future__ import annotations

import json
import sqlite3

import pytest

from sclpl.render.report import render_html, render_json, render_text


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE runs (id TEXT, name TEXT, workflow TEXT, env TEXT, status TEXT, "
        "exit_code INTEGER, duration_ms INTEGER, bytes_in INTEGER, retries INTEGER)"
    )
    conn.execute(
        "CREATE TABLE steps (step_id TEXT, status TEXT, lane TEXT, duration_ms INTEGER, "
        "attempts INTEGER, cached INTEGER, error TEXT)"
    )
    return conn


def _run(conn: sqlite3.Connection, **overrides: object) -> sqlite3.Row:
    defaults = {
        "id": "abc123",
        "name": "orders-0907",
        "workflow": "orders",
        "env": "default",
        "status": "ok",
        "exit_code": 0,
        "duration_ms": 150,
        "bytes_in": 1024,
        "retries": 0,
    }
    defaults.update(overrides)
    conn.execute(
        "INSERT INTO runs VALUES (:id, :name, :workflow, :env, :status, :exit_code, "
        ":duration_ms, :bytes_in, :retries)",
        defaults,
    )
    row: sqlite3.Row = conn.execute("SELECT * FROM runs").fetchone()
    return row


def _step(conn: sqlite3.Connection, **overrides: object) -> sqlite3.Row:
    defaults = {
        "step_id": "fetch",
        "status": "ok",
        "lane": "async",
        "duration_ms": 50,
        "attempts": 1,
        "cached": 0,
        "error": "",
    }
    defaults.update(overrides)
    conn.execute(
        "INSERT INTO steps VALUES (:step_id, :status, :lane, :duration_ms, "
        ":attempts, :cached, :error)",
        defaults,
    )
    row: sqlite3.Row = conn.execute(
        "SELECT * FROM steps WHERE step_id = ?", (defaults["step_id"],)
    ).fetchone()
    return row


@pytest.fixture
def conn() -> sqlite3.Connection:
    return _connect()


def test_a_real_zero_duration_step_and_a_real_measurement_both_render(
    conn: sqlite3.Connection,
) -> None:
    run = _run(conn, duration_ms=150)
    step = _step(conn, duration_ms=50, attempts=3)
    text = render_text(run, [step], [])
    assert "attempts=3" in text
    assert "duration=50ms" in text


def test_a_step_with_an_unmeasured_duration_shows_unknown_not_a_fake_zero(
    conn: sqlite3.Connection,
) -> None:
    """A run recorded before F1 wrote real numbers left `duration_ms` at the
    schema's own default (`0`) -- indistinguishable from a real zero-length step
    by value alone, so it must not be reported as a real measurement.
    """
    step = _step(conn, attempts=1, duration_ms=0)
    run = _run(conn)
    payload = render_json(run, [step], [])
    assert payload["steps"][0]["duration_ms"] is None
    text = render_text(run, [step], [])
    assert "duration=—" in text


def test_a_genuinely_multi_attempt_step_is_never_shown_as_unknown(
    conn: sqlite3.Connection,
) -> None:
    step = _step(conn, attempts=3, duration_ms=200)
    run = _run(conn)
    payload = render_json(run, [step], [])
    assert payload["steps"][0]["attempts"] == 3
    assert payload["steps"][0]["duration_ms"] == 200


def test_json_report_round_trips_through_json_dumps(conn: sqlite3.Connection) -> None:
    run = _run(conn)
    step = _step(conn)
    payload = render_json(run, [step], ["nightly"])
    # Must actually be JSON-serializable -- sqlite3.Row values, not the Row itself.
    text = json.dumps(payload)
    assert json.loads(text)["tags"] == ["nightly"]


def test_html_report_escapes_a_malicious_error_string(conn: sqlite3.Connection) -> None:
    run = _run(conn)
    step = _step(conn, error="<script>alert(document.cookie)</script>")
    page = render_html(run, [step], [])
    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page


def test_html_report_escapes_a_malicious_workflow_or_run_name(conn: sqlite3.Connection) -> None:
    run = _run(conn, name="<img src=x onerror=alert(1)>")
    page = render_html(run, [], [])
    assert "<img src=x" not in page
    assert "&lt;img" in page


def test_html_report_has_no_external_scripts_or_stylesheets(conn: sqlite3.Connection) -> None:
    run = _run(conn)
    page = render_html(run, [_step(conn)], [])
    assert "<script" not in page
    assert "http://" not in page
    assert "https://" not in page
    assert '<link rel="stylesheet"' not in page


def test_html_report_is_valid_enough_to_have_a_title_and_a_table(conn: sqlite3.Connection) -> None:
    run = _run(conn)
    page = render_html(run, [_step(conn)], [])
    assert "<title>" in page
    assert "<table>" in page
