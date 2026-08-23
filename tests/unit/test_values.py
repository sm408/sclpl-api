"""The value store: typed bindings, refcounts, digests, and spill."""

from __future__ import annotations

import pytest

from sclpl.values import Scratch, ValueStore, digest, size_of
from sclpl.values.ref import spill
from sclpl.values.store import BindingNotFound, BindingReleased, Frame

# -- typed values ----------------------------------------------------------------


def test_values_come_back_as_the_type_they_went_in_as() -> None:
    """Invariant 2. The store this replaces stringified everything."""
    store = ValueStore()
    for name, value in [
        ("i", 42),
        ("f", 1.5),
        ("s", "text"),
        ("b", True),
        ("n", None),
        ("l", [1, 2]),
        ("d", {"a": 1}),
    ]:
        store.put(name, value, readers=1)
        assert store.get(name) is value or store.get(name) == value
        assert type(store.get(name)) is type(value)


def test_the_same_object_comes_back_not_a_copy() -> None:
    store = ValueStore()
    payload = {"nested": {"deep": [1, 2, 3]}}
    store.put("a", payload, readers=1)
    assert store.get("a") is payload


# -- refcounts -------------------------------------------------------------------


def test_a_binding_is_freed_by_its_last_reader() -> None:
    store = ValueStore()
    store.put("a", "x" * 100, readers=2)
    assert store.release("a") is None  # one consumer left
    freed = store.release("a")
    assert freed is not None
    assert freed.name == "a"
    assert freed.bytes > 0


def test_a_pinned_binding_survives_its_readers() -> None:
    store = ValueStore()
    store.put("a", [1], readers=1, pinned=True)
    assert store.release("a") is None
    assert store.get("a") == [1]


def test_unpinning_frees_when_nothing_is_left() -> None:
    store = ValueStore()
    store.put("a", [1], readers=0, pinned=True)
    assert store.unpin("a") is not None


def test_keep_all_disables_disposal() -> None:
    store = ValueStore(keep_all=True)
    store.put("a", [1], readers=1)
    assert store.release("a") is None
    assert store.get("a") == [1]


def test_a_value_nothing_reads_is_freed_immediately() -> None:
    """A step run purely for its side effect produces exactly this."""
    store = ValueStore()
    store.put("a", "x" * 1000, readers=0)
    assert not store.has("a")


def test_reading_a_freed_binding_names_it() -> None:
    """The tombstone case: a planner bug should not surface as KeyError."""
    store = ValueStore()
    store.put("a", [1], readers=1)
    store.release("a")
    with pytest.raises(BindingReleased) as caught:
        store.get("a")
    assert "'a'" in str(caught.value)


def test_reading_an_unknown_binding_suggests() -> None:
    store = ValueStore()
    store.put("orders", [1], readers=1)
    with pytest.raises(BindingNotFound) as caught:
        store.get("order")
    assert "did you mean 'orders'?" in str(caught.value)


def test_releasing_an_unknown_name_is_quiet() -> None:
    """A pruned graph can leave releases for steps that never ran."""
    assert ValueStore().release("nothing") is None


def test_stats_track_what_was_freed() -> None:
    store = ValueStore()
    store.put("a", "x" * 10_000, readers=1)
    assert store.stats().live == 1
    store.release("a")
    assert store.stats().live == 0
    assert store.stats().bytes_freed > 0


# -- digests ---------------------------------------------------------------------


def test_equal_values_share_a_digest() -> None:
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})
    assert digest([1, 2, 3]) == digest([1, 2, 3])


def test_different_values_differ() -> None:
    assert digest([1, 2]) != digest([2, 1])
    assert digest({"a": 1}) != digest({"a": 2})


def test_types_are_part_of_the_digest() -> None:
    """A cache hit on the wrong type is worse than a miss."""
    assert digest(1) != digest("1")
    assert digest(1) != digest(1.0)
    assert digest(True) != digest(1)
    assert digest(None) != digest("")


def test_digests_are_stable_across_calls() -> None:
    payload = {"list": [1, {"nested": True}], "when": "2026-08-22"}
    assert digest(payload) == digest(payload)


def test_sets_digest_regardless_of_iteration_order() -> None:
    assert digest({1, 2, 3}) == digest({3, 2, 1})


# -- size estimation -------------------------------------------------------------


def test_size_grows_with_content() -> None:
    assert size_of("x" * 1000) > size_of("x")
    assert size_of([0] * 1000) > size_of([0])


def test_size_of_an_empty_container_is_small() -> None:
    assert size_of([]) < 200


# -- spill -----------------------------------------------------------------------


def test_a_spilled_value_rehydrates_unchanged(tmp_path) -> None:  # type: ignore[no-untyped-def]
    scratch = Scratch(tmp_path)
    payload = {"rows": [{"id": index} for index in range(100)]}
    reference = spill("big", payload, scratch)
    assert reference.path.exists()
    assert reference.load() == payload


def test_rehydration_is_memoised(tmp_path) -> None:  # type: ignore[no-untyped-def]
    scratch = Scratch(tmp_path)
    reference = spill("a", [1, 2, 3], scratch)
    assert reference.load() is reference.load()


def test_dropping_a_reference_removes_the_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    scratch = Scratch(tmp_path)
    reference = spill("a", [1], scratch)
    path = reference.path
    reference.drop()
    assert not path.exists()


def test_the_store_spills_and_reads_back(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = ValueStore(scratch=Scratch(tmp_path))
    payload = [{"index": index, "pad": "x" * 100} for index in range(2000)]
    store.put("big", payload, readers=1)
    recovered = store.spill("big")
    assert recovered > 0
    assert store.binding("big").spilled
    assert store.get("big") == payload


def test_small_values_are_not_worth_spilling(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = ValueStore(scratch=Scratch(tmp_path))
    store.put("small", [1, 2, 3], readers=1)
    assert store.spill("small") == 0


def test_spill_candidates_come_largest_first(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = ValueStore(scratch=Scratch(tmp_path))
    store.put("small", ["x" * 100_000], readers=1)
    store.put("large", ["x" * 500_000], readers=1)
    assert store.spill_candidates()[0] == "large"


def test_scratch_cleans_up(tmp_path) -> None:  # type: ignore[no-untyped-def]
    scratch = Scratch(tmp_path)
    path = scratch.path
    assert path.exists()
    scratch.close()
    assert not path.exists()


# -- frames ----------------------------------------------------------------------


def test_a_frame_shadows_its_parent() -> None:
    outer = Frame({"x": 1, "y": 2})
    inner = outer.child(x=99)
    assert inner.get("x") == 99
    assert inner.get("y") == 2


def test_a_frame_reports_what_it_can_see() -> None:
    inner = Frame({"a": 1}).child(b=2)
    assert set(inner.names()) == {"a", "b"}


def test_a_missing_name_raises() -> None:
    with pytest.raises(KeyError):
        Frame().get("nothing")
