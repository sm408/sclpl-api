"""E8: staging, atomic per-file publish, discard, and the generation manifest."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from sclpl.run.publication import Ledger, _write_pending, discard, publish, recover
from sclpl.state.db import default_root, file_digest


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


# -- G4: recovering an interrupted publish -------------------------------------------


def test_a_normal_publish_leaves_no_pending_record_to_recover(tmp_path: Path) -> None:
    destination = tmp_path / "report.csv"
    ledger = Ledger()
    ledger.stage("report", destination).write_text("data", encoding="utf-8")
    publish(ledger, workflow="orders", run_id="run1")

    assert recover("orders").found is False


def test_recover_with_nothing_pending_reports_not_found() -> None:
    assert recover("never-published").found is False


def test_recover_finishes_a_generation_that_crashed_before_any_file_moved(
    tmp_path: Path,
) -> None:
    """The crash this whole mechanism exists for: the intent record landed, but
    the process died before `publish()`'s own loop replaced a single file.
    """
    destination = tmp_path / "report.csv"
    ledger = Ledger()
    ledger.stage("report", destination).write_text("this generation's data", encoding="utf-8")
    _write_pending(ledger, "orders", "run1", "run1-deadbeef")
    assert not destination.exists()  # publish() itself never ran

    report = recover("orders")

    assert report.found
    assert report.completed == ("report",)
    assert report.already_committed == ()
    assert report.tampered == ()
    assert not report.ambiguous
    assert destination.read_text(encoding="utf-8") == "this generation's data"
    assert report.manifest_path is not None
    manifest = json.loads(report.manifest_path.read_text(encoding="utf-8"))
    assert manifest["generation"] == "run1-deadbeef"
    assert manifest["files"]["report"] == str(destination)
    # The intent record itself is gone: this generation has a real outcome now.
    assert recover("orders").found is False


def test_recover_recognizes_a_port_that_already_committed_before_the_crash(
    tmp_path: Path,
) -> None:
    """One file replaced, then the crash -- before the *next* one. `recover()`
    must not re-move a file that is already sitting at its real destination
    (there is no scratch file left to move it from in the first place).
    """
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    ledger = Ledger()
    scratch_a = ledger.stage("a", a)
    scratch_a.write_text("a-data", encoding="utf-8")
    ledger.stage("b", b).write_text("b-data", encoding="utf-8")
    _write_pending(ledger, "orders", "run1", "run1-deadbeef")
    # Simulate publish()'s own loop having gotten exactly this far: "a" moved,
    # "b" did not, then the process died.
    os.replace(scratch_a, a)

    report = recover("orders")

    assert report.completed == ("b",)
    assert report.already_committed == ("a",)
    assert report.tampered == ()
    assert a.read_text(encoding="utf-8") == "a-data"
    assert b.read_text(encoding="utf-8") == "b-data"
    manifest = json.loads(report.manifest_path.read_text(encoding="utf-8"))  # type: ignore[union-attr]
    assert set(manifest["files"]) == {"a", "b"}


def test_recover_reports_a_committed_destination_that_no_longer_matches_as_tampered(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "report.csv"
    ledger = Ledger()
    scratch = ledger.stage("report", destination)
    scratch.write_text("original", encoding="utf-8")
    _write_pending(ledger, "orders", "run1", "run1-deadbeef")
    os.replace(scratch, destination)
    # Something else changed the destination after the crash but before recovery.
    destination.write_text("changed by someone else", encoding="utf-8")
    pending_path = default_root() / "publications" / "orders.run1-deadbeef.pending.json"
    assert (
        file_digest(destination)
        != json.loads(pending_path.read_text(encoding="utf-8"))["ports"]["report"]["digest"]
    )

    report = recover("orders")

    assert report.tampered == ("report",)
    assert report.completed == ()
    assert report.already_committed == ()
    assert not report.ok
    # A tampered port is not claimed in the manifest as a trustworthy publish.
    assert report.manifest_path is None


def test_recover_refuses_a_stale_generation_a_newer_publish_has_superseded(
    tmp_path: Path,
) -> None:
    """A resume (or a plain rerun) completed a whole new, later generation after
    the crash. Finishing the old, interrupted one now would risk overwriting
    it -- reported as ambiguous, and nothing is touched.
    """
    old_destination = tmp_path / "report.csv"
    old_ledger = Ledger()
    old_ledger.stage("report", old_destination).write_text("stale", encoding="utf-8")
    _write_pending(old_ledger, "orders", "run1", "run1-deadbeef")

    new_ledger = Ledger()
    new_ledger.stage("report", old_destination).write_text("fresh", encoding="utf-8")
    publish(new_ledger, workflow="orders", run_id="run2")
    assert old_destination.read_text(encoding="utf-8") == "fresh"

    report = recover("orders")

    assert report.found
    assert report.ambiguous
    assert report.completed == ()
    assert old_destination.read_text(encoding="utf-8") == "fresh"  # untouched
    # The stale record survives -- it is the only evidence, until someone looks.
    assert (default_root() / "publications" / "orders.run1-deadbeef.pending.json").is_file()
