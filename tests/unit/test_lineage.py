"""F3: output lineage -- file digests, and which run produced a given path."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from sclpl.state import db


@pytest.fixture(autouse=True)
def private_home(tmp_path: Path, monkeypatch: Any) -> Path:
    home = tmp_path / "home"
    monkeypatch.setenv("SCLPL_HOME", str(home))
    return home


def record(history: db.History, identifier: str, **overrides: Any) -> db.RunRecord:
    run = db.RunRecord(
        id=identifier,
        name=overrides.pop("name", f"run-{identifier}"),
        workflow=overrides.pop("workflow", "orders"),
        status=overrides.pop("status", "ok"),
        started_at=overrides.pop("started_at", db.now()),
        **overrides,
    )
    history.record(run)
    return run


# -- file_digest ----------------------------------------------------------------


def test_file_digest_is_the_files_sha256(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    path.write_bytes(b"a,b\n1,2\n")
    assert db.file_digest(path) == hashlib.sha256(b"a,b\n1,2\n").hexdigest()


def test_file_digest_of_a_missing_file_is_empty(tmp_path: Path) -> None:
    assert db.file_digest(tmp_path / "absent.csv") == ""


def test_file_digest_changes_when_the_bytes_change(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    path.write_bytes(b"first")
    first = db.file_digest(path)
    path.write_bytes(b"second")
    assert db.file_digest(path) != first


# -- producers_of -----------------------------------------------------------------


def test_producers_of_finds_the_run_that_wrote_a_path(
    private_home: Path, tmp_path: Path
) -> None:
    out = tmp_path / "report.csv"
    with db.History(private_home) as history:
        record(history, "aaaa1111", ports=[("out", "report", str(out), "deadbeef")])
        (found,) = history.producers_of(out)
        assert found["run_id"] == "aaaa1111"
        assert found["digest"] == "deadbeef"


def test_producers_of_matches_a_relative_and_absolute_spelling(
    private_home: Path, tmp_path: Path, monkeypatch: Any
) -> None:
    out = tmp_path / "report.csv"
    with db.History(private_home) as history:
        record(history, "aaaa1111", ports=[("out", "report", str(out), "deadbeef")])
        monkeypatch.chdir(tmp_path)
        (found,) = history.producers_of(Path("report.csv"))
        assert found["run_id"] == "aaaa1111"


def test_producers_of_an_unrelated_path_is_empty(private_home: Path, tmp_path: Path) -> None:
    with db.History(private_home) as history:
        record(history, "aaaa1111", ports=[("out", "report", str(tmp_path / "a.csv"), "x")])
        assert history.producers_of(tmp_path / "b.csv") == []


def test_producers_of_reports_every_run_most_recent_first(
    private_home: Path, tmp_path: Path
) -> None:
    out = tmp_path / "report.csv"
    with db.History(private_home) as history:
        record(
            history,
            "aaaa1111",
            started_at="2026-01-01T00:00:00",
            ports=[("out", "report", str(out), "first")],
        )
        record(
            history,
            "bbbb2222",
            started_at="2026-01-02T00:00:00",
            ports=[("out", "report", str(out), "second")],
        )
        matches = history.producers_of(out)
        assert [row["run_id"] for row in matches] == ["bbbb2222", "aaaa1111"]


def test_producers_of_ignores_input_ports(private_home: Path, tmp_path: Path) -> None:
    src = tmp_path / "input.csv"
    with db.History(private_home) as history:
        record(history, "aaaa1111", ports=[("in", "orders", str(src), "x")])
        assert history.producers_of(src) == []
