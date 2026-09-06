"""E8: staging, atomic per-file publish, discard, and the generation manifest."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from sclpl.run.publication import Ledger, discard, publish
from sclpl.state.db import default_root


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCLPL_HOME", str(tmp_path / "home"))


def test_stage_returns_a_same_directory_sibling(tmp_path: Path) -> None:
    destination = tmp_path / "out" / "report.csv"
    ledger = Ledger()
    scratch = ledger.stage("report", destination)
    assert scratch.parent == destination.parent
    assert scratch.name != destination.name
    assert "report.csv" in scratch.name


def test_stage_is_idempotent_per_port(tmp_path: Path) -> None:
    destination = tmp_path / "report.csv"
    ledger = Ledger()
    first = ledger.stage("report", destination)
    second = ledger.stage("report", destination)
    assert first == second


def test_publish_moves_every_staged_file_to_its_real_destination(tmp_path: Path) -> None:
    destination = tmp_path / "out" / "report.csv"
    destination.parent.mkdir()
    ledger = Ledger()
    scratch = ledger.stage("report", destination)
    scratch.write_text("a,b\n1,2\n", encoding="utf-8")

    result = publish(ledger, workflow="orders", run_id="run1")

    assert result.published == ("report",)
    assert result.ok
    assert destination.read_text(encoding="utf-8") == "a,b\n1,2\n"
    assert not scratch.exists()


def test_publish_writes_a_generation_manifest_naming_every_published_file(tmp_path: Path) -> None:
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    ledger = Ledger()
    ledger.stage("a", a).write_text("1", encoding="utf-8")
    ledger.stage("b", b).write_text("2", encoding="utf-8")

    result = publish(ledger, workflow="orders", run_id="run1")

    assert result.manifest_path is not None
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["workflow"] == "orders"
    assert manifest["run_id"] == "run1"
    assert manifest["generation"] == result.generation
    assert set(manifest["files"]) == {"a", "b"}
    assert manifest["files"]["a"] == str(a)


def test_publish_leaves_no_manifest_when_nothing_was_staged() -> None:
    result = publish(Ledger(), workflow="orders", run_id="run1")
    assert result.published == ()
    assert result.manifest_path is None
    assert result.generation is None


def test_publish_replaces_an_existing_destination_atomically(tmp_path: Path) -> None:
    destination = tmp_path / "report.csv"
    destination.write_text("old", encoding="utf-8")
    ledger = Ledger()
    ledger.stage("report", destination).write_text("new", encoding="utf-8")

    result = publish(ledger, workflow="orders", run_id="run1")

    assert result.published == ("report",)
    assert destination.read_text(encoding="utf-8") == "new"


def test_discard_removes_staged_files_and_touches_nothing_real(tmp_path: Path) -> None:
    destination = tmp_path / "report.csv"
    destination.write_text("previous run's good output", encoding="utf-8")
    ledger = Ledger()
    scratch = ledger.stage("report", destination)
    scratch.write_text("this run's unvalidated attempt", encoding="utf-8")

    discarded = discard(ledger)

    assert discarded == ("report",)
    assert not scratch.exists()
    assert destination.read_text(encoding="utf-8") == "previous run's good output"


def test_discard_on_an_already_missing_scratch_file_does_not_raise(tmp_path: Path) -> None:
    ledger = Ledger()
    ledger.stage("report", tmp_path / "report.csv")
    # Never actually written -- a step that failed before it could write at all.
    assert discard(ledger) == ("report",)


def test_a_failed_replace_is_reported_as_interrupted_not_silently_dropped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "report.csv"
    ledger = Ledger()
    ledger.stage("report", destination).write_text("data", encoding="utf-8")

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", _boom)
    result = publish(ledger, workflow="orders", run_id="run1")

    assert result.interrupted == ("report",)
    assert not result.ok
    assert result.published == ()


def test_manifest_lives_under_the_shared_publications_root(tmp_path: Path) -> None:
    destination = tmp_path / "report.csv"
    ledger = Ledger()
    ledger.stage("report", destination).write_text("data", encoding="utf-8")
    result = publish(ledger, workflow="orders", run_id="run1")
    assert result.manifest_path == default_root() / "publications" / "orders.json"
