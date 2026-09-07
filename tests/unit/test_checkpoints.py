"""G1: durable checkpoints -- eligible/ineligible types, and the two-phase
write/commit that makes "reusable" mean something.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from sclpl.run.checkpoints import Store
from sclpl.tables.base import Table

pytest.importorskip("pandas")


@pytest.fixture
def store(tmp_path: Path) -> Any:
    with Store(tmp_path) as opened:
        yield opened


# -- eligibility --------------------------------------------------------------------


def test_a_dict_is_eligible(store: Store) -> None:
    assert store.eligible({"a": 1})


def test_a_table_is_eligible(store: Store) -> None:
    assert store.eligible(Table.from_records([{"a": 1}]))


def test_a_set_is_not_eligible(store: Store) -> None:
    """JSON has no honest representation for a set -- refused, not stringified."""
    assert not store.eligible({1, 2, 3})


def test_an_arbitrary_object_is_not_eligible(store: Store) -> None:
    class Unserializable:
        pass

    assert not store.eligible(Unserializable())


# -- write and read back --------------------------------------------------------


def test_a_json_eligible_value_round_trips_exactly(store: Store) -> None:
    value = {"orders": [1, 2, 3], "total": 3, "ok": True, "note": None}
    checkpoint = store.write("run1", "fetch", value)
    assert checkpoint is not None
    assert checkpoint.format == "json"
    assert store.read("run1", "fetch") == value


def test_a_table_round_trips_as_parquet(store: Store) -> None:
    table = Table.from_records([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}])
    checkpoint = store.write("run1", "rows", table)
    assert checkpoint is not None
    assert checkpoint.format == "parquet"
    back = store.read("run1", "rows")
    assert isinstance(back, Table)
    assert back.to_records() == table.to_records()


def test_an_unsupported_value_is_never_checkpointed(store: Store) -> None:
    class Unserializable:
        pass

    assert store.write("run1", "weird", Unserializable()) is None
    assert store.read("run1", "weird") is None


def test_reading_a_step_that_was_never_written_is_none(store: Store) -> None:
    assert store.read("run1", "never") is None


def test_writing_twice_replaces_the_checkpoint(store: Store) -> None:
    store.write("run1", "fetch", {"v": 1})
    store.write("run1", "fetch", {"v": 2})
    assert store.read("run1", "fetch") == {"v": 2}


# -- durability: only a committed row makes a checkpoint reusable -------------------


def test_a_blob_on_disk_with_no_committed_row_is_not_reusable(store: Store, tmp_path: Path) -> None:
    """The "process died between blob write and DB commit" case: a file exists
    exactly where a checkpoint would put one, but nothing durable ever named it.
    """
    orphan = tmp_path / "run1" / "fetch.json"
    orphan.parent.mkdir(parents=True)
    orphan.write_text('{"v": "never committed"}', encoding="utf-8")
    assert store.read("run1", "fetch") is None


def test_no_scratch_file_is_left_behind_after_a_successful_write(
    store: Store, tmp_path: Path
) -> None:
    store.write("run1", "fetch", {"v": 1})
    leftovers = list((tmp_path / "run1").glob(".*.tmp-*"))
    assert leftovers == []


def test_a_blob_modified_after_being_checkpointed_is_rejected(store: Store, tmp_path: Path) -> None:
    """A digest mismatch means the file on disk is not what was actually
    checkpointed -- tampered with, or corrupted -- and must not be trusted.
    """
    checkpoint = store.write("run1", "fetch", {"v": 1})
    assert checkpoint is not None
    checkpoint.path.write_text('{"v": "tampered"}', encoding="utf-8")
    assert store.read("run1", "fetch") is None


def test_a_deleted_blob_with_a_committed_row_is_not_reusable(store: Store, tmp_path: Path) -> None:
    checkpoint = store.write("run1", "fetch", {"v": 1})
    assert checkpoint is not None
    checkpoint.path.unlink()
    assert store.read("run1", "fetch") is None


# -- step ids that are not, by themselves, valid filenames --------------------------


def test_a_dynamic_loop_iteration_id_round_trips(store: Store) -> None:
    """A loop body's real node id is `parent::0::inner` (`control.MARK` is `::`),
    which Windows refuses outright as a filename -- `:` is reserved for drive
    letters there. The step id stored and compared is untouched; only the blob's
    own filename on disk needs to be safe.
    """
    step_id = "details::0::one"
    checkpoint = store.write("run1", step_id, {"v": 1})
    assert checkpoint is not None
    assert ":" not in checkpoint.path.name
    assert store.read("run1", step_id) == {"v": 1}
    assert store.exists("run1", step_id)


# -- discard --------------------------------------------------------------------


def test_discard_removes_every_checkpoint_and_blob_for_a_run(store: Store, tmp_path: Path) -> None:
    store.write("run1", "a", {"v": 1})
    store.write("run1", "b", {"v": 2})
    store.write("run2", "a", {"v": 3})

    store.discard("run1")

    assert store.read("run1", "a") is None
    assert store.read("run1", "b") is None
    assert store.read("run2", "a") == {"v": 3}
    assert list((tmp_path / "run1").glob("*")) == []
