"""Secrets and run history.

The secrets tests care most about what happens when there is **nowhere safe to put
one**. That is defect 4, and the whole point of the module is that it refuses rather
than degrading -- so the refusal is the behaviour worth pinning hardest.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from sclpl.errors import ValidationError
from sclpl.state import db, secrets


@pytest.fixture(autouse=True)
def private_home(tmp_path: Path, monkeypatch: Any) -> Path:
    """Never touch the real `~/.sclpl` from a test."""
    home = tmp_path / "home"
    monkeypatch.setenv("SCLPL_HOME", str(home))
    return home


@pytest.fixture
def no_backends(monkeypatch: Any) -> None:
    """A machine with neither a keyring nor cryptography."""
    monkeypatch.setattr(secrets, "_keyring", lambda: None)
    monkeypatch.setattr(secrets, "_fernet", lambda: None)


@pytest.fixture
def file_backend(monkeypatch: Any) -> None:
    """No keyring, so the encrypted file gets its turn."""
    monkeypatch.setattr(secrets, "_keyring", lambda: None)
    if secrets._fernet() is None:
        pytest.skip("cryptography is not installed")


# -- the refusal, which is the point -------------------------------------------------


def test_with_nowhere_safe_it_refuses_rather_than_storing(no_backends: None) -> None:
    """Defect 4. The predecessor fell back to base64 and said nothing."""
    with pytest.raises(secrets.NoSecureStorage) as caught:
        secrets.put("token", "hunter2")
    message = str(caught.value)
    assert "will not fall back to anything weaker" in message
    assert "nothing is stored" in message


def test_the_refusal_names_both_ways_out(no_backends: None) -> None:
    """ "No secure storage available" without an install command is a dead end."""
    with pytest.raises(secrets.NoSecureStorage) as caught:
        secrets.put("token", "hunter2")
    message = str(caught.value)
    assert "sclpl[keyring]" in message
    assert "sclpl[crypto]" in message


def test_with_nowhere_safe_nothing_is_written(no_backends: None, private_home: Path) -> None:
    with pytest.raises(secrets.NoSecureStorage):
        secrets.put("token", "hunter2")
    assert not (private_home / "secrets.enc").exists()


def test_the_backend_reports_itself_honestly(no_backends: None) -> None:
    assert secrets.backend().name == "none"


# -- the encrypted file --------------------------------------------------------------


def test_a_secret_round_trips(file_backend: None) -> None:
    secrets.put("api-token", "hunter2")
    assert secrets.get("api-token") == "hunter2"


def test_the_secret_is_not_on_disk_in_plaintext(file_backend: None, private_home: Path) -> None:
    secrets.put("api-token", "a-very-distinctive-value")
    raw = (private_home / "secrets.enc").read_bytes()
    assert b"a-very-distinctive-value" not in raw


def test_environments_are_separate_namespaces(file_backend: None) -> None:
    secrets.put("token", "prod-value")
    secrets.put("token", "staging-value", env="staging")
    assert secrets.get("token") == "prod-value"
    assert secrets.get("token", env="staging") == "staging-value"


def test_listing_gives_names_only(file_backend: None) -> None:
    secrets.put("one", "a")
    secrets.put("two", "b")
    listed = secrets.names()
    assert listed == ["one", "two"]
    assert "a" not in listed


def test_deleting_a_secret(file_backend: None) -> None:
    secrets.put("gone", "value")
    assert secrets.delete("gone") is True
    assert secrets.get("gone") is None
    assert secrets.delete("gone") is False


def test_a_name_cannot_smuggle_an_environment(file_backend: None) -> None:
    with pytest.raises(ValidationError) as caught:
        secrets.put("staging/token", "x")
    assert "--env" in str(caught.value)


def test_the_environment_is_read_when_nothing_is_stored(monkeypatch: Any) -> None:
    """For CI, where there is no keyring and the secret arrives as a variable anyway."""
    monkeypatch.setattr(secrets, "_keyring", lambda: None)
    monkeypatch.setattr(secrets, "_fernet", lambda: None)
    monkeypatch.setenv("SCLPL_SECRET_CI_TOKEN", "from-the-environment")
    assert secrets.get("ci-token") == "from-the-environment"


def test_reading_from_the_environment_is_not_storing_weakly(monkeypatch: Any) -> None:
    """Where a secret is read from and where it is stored are different questions."""
    monkeypatch.setattr(secrets, "_keyring", lambda: None)
    monkeypatch.setattr(secrets, "_fernet", lambda: None)
    monkeypatch.setenv("SCLPL_SECRET_X", "value")
    assert secrets.get("x") == "value"
    with pytest.raises(secrets.NoSecureStorage):
        secrets.put("x", "value")


def test_resolving_several_names_at_once(file_backend: None) -> None:
    """All of them before the run, not the third of four after two requests."""
    secrets.put("a", "1")
    secrets.put("b", "2")
    assert secrets.resolve(["a", "b"]) == {"a": "1", "b": "2"}


def test_a_missing_secret_names_it_and_suggests_a_neighbour(file_backend: None) -> None:
    secrets.put("api-token", "x")
    with pytest.raises(ValidationError) as caught:
        secrets.resolve(["api-tokn"])
    message = str(caught.value)
    assert "api-tokn" in message
    assert "api-token" in message


# -- history --------------------------------------------------------------------------


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


def test_a_run_is_stored_and_found_again(private_home: Path) -> None:
    with db.History(private_home) as history:
        record(history, "aaaa1111")
        assert history.find("aaaa1111")["name"] == "run-aaaa1111"


def test_a_run_is_found_by_name(private_home: Path) -> None:
    with db.History(private_home) as history:
        record(history, "aaaa1111", name="nightly")
        assert history.find("nightly")["id"] == "aaaa1111"


def test_recent_breaks_a_started_at_tie_by_insertion_order(private_home: Path) -> None:
    """`started_at` has one-second resolution -- two runs finishing in the same tick
    (easy on a fast machine, not just in theory) must still order deterministically:
    the one recorded second is the more recent one, not whatever a tied `ORDER BY`
    happened to return.
    """
    with db.History(private_home) as history:
        same_second = db.now()
        record(history, "aaaa1111", name="first", started_at=same_second)
        record(history, "bbbb2222", name="second", started_at=same_second)
        assert history.recent(limit=1)[0]["name"] == "second"
        assert history.recent(limit=1, workflow="orders")[0]["name"] == "second"


def test_a_unique_prefix_is_enough(private_home: Path) -> None:
    """Nobody wants to type eight hex characters correctly."""
    with db.History(private_home) as history:
        record(history, "abc12345")
        assert history.find("abc")["id"] == "abc12345"


def test_an_ambiguous_prefix_lists_the_candidates(private_home: Path) -> None:
    with db.History(private_home) as history:
        record(history, "abc11111")
        record(history, "abc22222")
        with pytest.raises(ValidationError) as caught:
            history.find("abc")
        assert "matches 2 runs" in str(caught.value)


def test_an_unknown_run_suggests_a_neighbour(private_home: Path) -> None:
    with db.History(private_home) as history:
        record(history, "aaaa1111", name="nightly")
        with pytest.raises(ValidationError) as caught:
            history.find("nightlyy")
        assert "nightly" in str(caught.value)


def test_steps_and_tags_are_kept(private_home: Path) -> None:
    with db.History(private_home) as history:
        record(
            history,
            "aaaa1111",
            tags=["nightly", "prod"],
            steps=[
                db.StepRecord(step_id="fetch", status="ok", duration_ms=12),
                db.StepRecord(step_id="write", status="failed", error="disk full"),
            ],
        )
        assert history.tags_of("aaaa1111") == ["nightly", "prod"]
        steps = history.steps_of("aaaa1111")
        assert [step["step_id"] for step in steps] == ["fetch", "write"]
        assert steps[1]["error"] == "disk full"


def test_search_finds_a_run_by_the_error_it_failed_with(private_home: Path) -> None:
    """Which is what you have when something broke and you do not know its name."""
    with db.History(private_home) as history:
        record(
            history,
            "aaaa1111",
            status="failed",
            steps=[db.StepRecord(step_id="fetch", status="failed", error="connection refused")],
        )
        assert [row["id"] for row in history.search("connection refused")] == ["aaaa1111"]


def test_search_finds_a_run_by_tag(private_home: Path) -> None:
    with db.History(private_home) as history:
        record(history, "aaaa1111", tags=["nightly"])
        assert [row["id"] for row in history.search("nightly")] == ["aaaa1111"]


# -- retention -------------------------------------------------------------------------


def test_pruning_keeps_the_most_recent(private_home: Path) -> None:
    with db.History(private_home) as history:
        for index in range(8):
            record(history, f"run{index:04d}", started_at=f"2026-01-0{index + 1}T00:00:00Z")
        dropped = history.prune(keep=5)
        assert len(dropped) == 3
        assert len(history.recent(50)) == 5


def test_a_pinned_run_survives_and_does_not_count(private_home: Path) -> None:
    """A pin means "keep this", not "spend the budget on this"."""
    with db.History(private_home) as history:
        for index in range(6):
            record(history, f"run{index:04d}", started_at=f"2026-01-0{index + 1}T00:00:00Z")
        history.pin("run0000")
        history.pin("run0001")
        history.prune(keep=2)

        kept = {row["id"] for row in history.recent(50)}
        assert "run0000" in kept
        assert "run0001" in kept
        assert len(kept) == 4  # two pinned, plus the two most recent unpinned


def test_unpinning(private_home: Path) -> None:
    with db.History(private_home) as history:
        record(history, "aaaa1111")
        history.pin("aaaa1111")
        history.pin("aaaa1111", pinned=False)
        history.prune(keep=0)
        assert history.recent(50) == []


def test_pruning_removes_the_log_too(private_home: Path) -> None:
    with db.History(private_home) as history:
        record(history, "aaaa1111")
        history.log_path("aaaa1111").write_text("{}\n", encoding="utf-8")
        history.prune(keep=0)
        assert not history.log_path("aaaa1111").exists()


# -- F4: pruning leaves a retained run completely intact ----------------------------


def test_pruning_leaves_every_row_of_a_surviving_run_untouched(private_home: Path) -> None:
    """ "Pruning one run cannot break another retained run" -- checked across every
    table a run's data actually lives in, not just the `runs` row itself.
    """
    with db.History(private_home) as history:
        survivor = db.RunRecord(
            id="keep0001",
            name="keep-me",
            workflow="orders",
            status="ok",
            # Strictly after every "doomed" run below (which run through
            # 2026-01-05) -- a tie here would depend on tie-breaking order rather
            # than on what this test is actually about.
            started_at="2026-01-06T00:00:00Z",
            tags=["nightly"],
            ports=[("out", "report", "report.csv", "abc123")],
            steps=[db.StepRecord(step_id="fetch", status="ok", attempts=2)],
        )
        history.record(survivor)
        history.log_path("keep0001").write_text("{}\n", encoding="utf-8")
        for index in range(5):
            record(history, f"doomed{index:04d}", started_at=f"2026-01-0{index + 1}T00:00:00Z")

        dropped = history.prune(keep=1)

        assert "keep0001" not in dropped
        assert history.find("keep0001")["name"] == "keep-me"
        assert history.tags_of("keep0001") == ["nightly"]
        ports = history.ports_of("keep0001")
        assert len(ports) == 1 and ports[0]["digest"] == "abc123"
        steps = history.steps_of("keep0001")
        assert len(steps) == 1 and steps[0]["attempts"] == 2
        assert history.log_path("keep0001").exists()


def test_a_crashed_run_left_at_status_running_is_pruned_like_any_other_row(
    private_home: Path,
) -> None:
    """`_remember_start` (`run/runner.py`) writes a `status="running"` row before a
    single step executes; a process that dies before `_remember` ever runs leaves
    exactly this behind. It must not be special-cased or get stuck forever.
    """
    with db.History(private_home) as history:
        record(history, "crashed1", status="running", started_at="2026-01-01T00:00:00Z")
        for index in range(5):
            record(history, f"newer{index:04d}", started_at=f"2026-01-0{index + 2}T00:00:00Z")

        dropped = history.prune(keep=5)

        assert "crashed1" in dropped
        with pytest.raises(ValidationError):
            history.find("crashed1")


def test_a_reader_is_not_blocked_by_a_writer_in_wal_mode(private_home: Path) -> None:
    """F4's "concurrent readers": a second connection to the same history must be
    able to read while the first still holds it open, not fail with a locked error.
    """
    with db.History(private_home) as writer:
        record(writer, "aaaa1111")
        with db.History(private_home) as reader:
            assert reader.find("aaaa1111")["id"] == "aaaa1111"
        record(writer, "bbbb2222")
        with db.History(private_home) as reader:
            assert len(reader.recent(10)) == 2


# -- diff and export ---------------------------------------------------------------------


def test_diff_puts_what_matters_first(private_home: Path) -> None:
    """A run that failed where the other succeeded is the answer to "what changed"."""
    with db.History(private_home) as history:
        record(history, "aaaa1111", status="ok", exit_code=0, duration_ms=100)
        record(history, "bbbb2222", status="failed", exit_code=1, duration_ms=110)
        lines = db.diff(history.find("aaaa1111"), history.find("bbbb2222"))
        assert "status" in lines[0]
        assert "duration" in lines[-1]


def test_two_identical_runs_differ_in_nothing(private_home: Path) -> None:
    with db.History(private_home) as history:
        record(history, "aaaa1111", duration_ms=10)
        record(history, "bbbb2222", duration_ms=10)
        assert db.diff(history.find("aaaa1111"), history.find("bbbb2222")) == []


def test_export_is_the_whole_run(private_home: Path) -> None:
    with db.History(private_home) as history:
        record(
            history,
            "aaaa1111",
            tags=["nightly"],
            steps=[db.StepRecord(step_id="fetch", status="ok")],
            ports=[("out", "report", "out.csv", "")],
        )
        payload = db.export(history, "aaaa1111")
    assert payload["run"]["id"] == "aaaa1111"
    assert payload["tags"] == ["nightly"]
    assert payload["steps"][0]["step_id"] == "fetch"
    assert payload["ports"][0]["path"] == "out.csv"


# -- naming ------------------------------------------------------------------------------


def test_a_default_name_is_readable_and_sortable() -> None:
    from datetime import UTC, datetime

    when = datetime(2026, 8, 21, 14, 32, tzinfo=UTC)
    assert db.default_name("orders", "partial", when) == "orders-partial-0821-1432"
    assert db.default_name("orders", None, when) == "orders-0821-1432"


def test_two_runs_of_the_same_workflow_get_different_ids() -> None:
    assert db.run_id("orders", 1.0) != db.run_id("orders", 2.0)
