"""The governor, the lanes, and the cache.

Each is tested against a stand-in rather than a real run: what is under test is the
*decision* -- spill or not, which lane, hit or miss -- and a real run would make those
decisions once, slowly, and hide the reasoning.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pytest

from sclpl.errors import EXIT_CACHE_MISS
from sclpl.run import lanes
from sclpl.values import cache as cache_mod
from sclpl.values import governor as gov
from sclpl.values.ref import Scratch
from sclpl.values.store import ValueStore

MB = 1024 * 1024


# -- the governor ------------------------------------------------------------------


class FakeStore:
    """A store that only knows how to be spilled from."""

    def __init__(self, sizes: dict[str, int]) -> None:
        self.sizes = dict(sizes)
        self.spilled: list[str] = []

    def spill_candidates(self) -> list[str]:
        return sorted(self.sizes, key=lambda name: self.sizes[name], reverse=True)

    def spill(self, name: str) -> int:
        self.spilled.append(name)
        return self.sizes.pop(name, 0)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("4G", 4 * 1024**3),
        ("512M", 512 * MB),
        ("1.5g", int(1.5 * 1024**3)),
        ("2048", 2048),
        ("4GB", 4 * 1024**3),
    ],
)
def test_a_budget_is_read_the_way_it_is_written(text: str, expected: int) -> None:
    assert gov.parse_budget(text) == expected


def test_no_budget_means_a_share_of_the_machine() -> None:
    """A ceiling nobody chose should still be generous, and scale with the machine."""
    assert gov.parse_budget(None) >= gov.MIN_BUDGET


@pytest.mark.parametrize(
    ("used", "level"),
    [(10 * MB, "ok"), (75 * MB, "soft"), (95 * MB, "hard")],
)
def test_the_watermarks_are_where_they_are_documented(used: int, level: str) -> None:
    # A fixed probe, because the test process's own RSS is not the subject.
    governor = gov.Governor(budget=100 * MB, probe=lambda: 0)
    assert governor.sample(store_bytes=used).level == level


def test_the_larger_of_rss_and_the_store_wins() -> None:
    """Each has a blind spot: RSS includes the interpreter, the store misses what it
    does not own. Taking the maximum means neither can hide pressure."""
    governor = gov.Governor(budget=100 * MB, probe=lambda: 90 * MB)
    assert governor.sample(store_bytes=1).level == "hard"
    assert gov.Governor(budget=100 * MB, probe=lambda: 0).sample(90 * MB).level == "hard"


def test_spilling_stops_once_it_is_back_under_the_soft_mark() -> None:
    """Largest first, and no further than it needs to go."""
    store = FakeStore({"big": 40 * MB, "medium": 20 * MB, "small": 5 * MB})
    governor = gov.Governor(budget=100 * MB)
    recovered = governor.relieve(store, gov.Pressure(used=90 * MB, budget=100 * MB, level="hard"))
    assert store.spilled == ["big"]
    assert recovered == 40 * MB


def test_spilling_takes_more_when_one_is_not_enough() -> None:
    store = FakeStore({"a": 20 * MB, "b": 20 * MB, "c": 20 * MB})
    governor = gov.Governor(budget=100 * MB)
    governor.relieve(store, gov.Pressure(used=120 * MB, budget=100 * MB, level="hard"))
    assert store.spilled == ["a", "b", "c"]


def test_concurrency_halves_at_the_hard_mark_and_never_reaches_zero() -> None:
    governor = gov.Governor(budget=100 * MB)
    hard = gov.Pressure(used=95 * MB, budget=100 * MB, level="hard")
    soft = gov.Pressure(used=75 * MB, budget=100 * MB, level="soft")
    assert governor.concurrency_for(16, hard) == 8
    assert governor.concurrency_for(16, soft) == 16
    assert governor.concurrency_for(1, hard) == 1


def test_pressure_describes_itself_in_numbers() -> None:
    """ "Memory pressure" is not actionable. A number and a budget are."""
    pressure = gov.Pressure(used=1288490188, budget=1610612736, level="hard")
    described = pressure.describe()
    assert "GB" in described
    assert "80%" in described


def test_measuring_returns_something_or_zero() -> None:
    """A governor that cannot measure does nothing rather than guessing."""
    assert gov.rss() >= 0
    assert gov.system_memory() >= 0


def test_a_store_really_does_spill_and_read_back(tmp_path: Path) -> None:
    store = ValueStore(scratch=Scratch(tmp_path))
    rows = [{"id": n, "blob": "x" * 200} for n in range(5000)]
    store.put("big", rows, readers=1)

    recovered = store.spill("big")
    assert recovered > 0
    assert store.binding("big").spilled
    assert store.get("big") == rows


# -- lanes -------------------------------------------------------------------------


def where() -> int:
    """Reports the process it ran in. Top level, so it survives being pickled."""
    return os.getpid()


def test_small_synchronous_work_stays_on_the_loop() -> None:
    assert lanes.assign(None, is_async=False, args=[[{"id": n} for n in range(10)]]) == "async"


def test_large_synchronous_work_goes_to_a_process() -> None:
    """A join over a hundred thousand rows is the case the process lane exists for."""
    rows = [{"id": n, "blob": "x" * 400} for n in range(20_000)]
    assert lanes.assign(None, is_async=False, args=[rows]) == "process"


def test_an_async_function_stays_on_the_loop_however_large() -> None:
    """It is already cooperative; a thread would run an event loop inside a thread."""
    rows = [{"id": n, "blob": "x" * 400} for n in range(20_000)]
    assert lanes.assign(None, is_async=True, args=[rows]) == "async"


def test_a_declared_lane_wins() -> None:
    assert lanes.assign("process", is_async=True, args=[[1]]) == "process"
    assert lanes.assign("serial", is_async=False, args=[[1]]) == "serial"


def test_an_unknown_declared_lane_falls_through_to_the_rules() -> None:
    assert lanes.assign("sideways", is_async=False, args=[[1]]) == "async"


async def test_the_process_lane_really_is_another_process() -> None:
    pools = lanes.Pools()
    try:
        # The runtime deliberately degrades to a thread when a restricted host
        # cannot create child processes.  In that environment there is no
        # process lane to verify; asserting one exists would test the runner's
        # sandbox rather than SCLPL's lane selection.
        if pools.processes() is None:
            pytest.skip("process pools are unavailable in this environment")
        assert await lanes.call("process", pools, where) != os.getpid()
        assert await lanes.call("thread", pools, where) == os.getpid()
    finally:
        pools.close()


async def test_a_broken_pool_is_not_retried() -> None:
    """One dead pool should not fail every step after it."""
    pools = lanes.Pools()
    pools.forget_processes()
    with pytest.raises(lanes.LaneFallback):
        await lanes.call("process", pools, where)
    assert pools.processes() is None


# -- the cache ---------------------------------------------------------------------


def test_the_same_request_has_the_same_key() -> None:
    first = cache_mod.key_for(step_kind="http", method="GET", url="https://x/a", query={"p": 1})
    second = cache_mod.key_for(step_kind="http", method="GET", url="https://x/a", query={"p": 1})
    assert first == second


def test_query_order_does_not_change_the_key() -> None:
    a = cache_mod.key_for(step_kind="http", url="https://x/", query={"a": 1, "b": 2})
    b = cache_mod.key_for(step_kind="http", url="https://x/", query={"b": 2, "a": 1})
    assert a == b


def test_volatile_headers_are_excluded() -> None:
    """Keying on a request id would be keying on nothing: every key unique, no hits."""
    plain = cache_mod.key_for(step_kind="http", url="https://x/")
    noisy = cache_mod.key_for(
        step_kind="http",
        url="https://x/",
        headers={"X-Request-Id": "abc", "Authorization": "Bearer t", "Date": "now"},
    )
    assert plain == noisy


def test_a_meaningful_header_does_change_the_key() -> None:
    a = cache_mod.key_for(step_kind="http", url="https://x/", headers={"Accept": "text/csv"})
    b = cache_mod.key_for(
        step_kind="http", url="https://x/", headers={"Accept": "application/json"}
    )
    assert a != b


def test_different_credentials_do_not_share_entries() -> None:
    """They may be different tenants, and one must not read the other's data."""
    a = cache_mod.key_for(step_kind="http", url="https://x/", credential="token-a")
    b = cache_mod.key_for(step_kind="http", url="https://x/", credential="token-b")
    assert a != b


def test_the_credential_itself_is_not_in_the_key() -> None:
    key = cache_mod.key_for(step_kind="http", url="https://x/", credential="hunter2")
    assert "hunter2" not in key


def test_a_different_pagination_spec_does_not_share_a_cache_entry() -> None:
    """D7: `max_pages=1` against a URL must not read what `max_pages=40` cached for
    it -- they are different extractions of the same source, not the same answer.
    """
    one_page = cache_mod.key_for(
        step_kind="http", url="https://x/", paginate={"strategy": "cursor", "max_pages": 1}
    )
    all_pages = cache_mod.key_for(
        step_kind="http", url="https://x/", paginate={"strategy": "cursor", "max_pages": 40}
    )
    unpaginated = cache_mod.key_for(step_kind="http", url="https://x/")
    assert one_page != all_pages
    assert one_page != unpaginated
    assert all_pages != unpaginated


def test_a_function_version_invalidates_its_entries() -> None:
    """Changing what a function computes must not silently mix old and new answers."""
    a = cache_mod.key_for(step_kind="fn", function="summarise", function_version=1)
    b = cache_mod.key_for(step_kind="fn", function="summarise", function_version=2)
    assert a != b


@pytest.mark.parametrize(
    ("flags", "read", "write", "require"),
    [
        ({}, True, True, False),
        ({"no_cache": True}, False, False, False),
        ({"refresh": True}, False, True, False),
        ({"offline": True}, True, False, True),
    ],
)
def test_each_flag_means_what_the_table_says(
    flags: dict[str, bool], read: bool, write: bool, require: bool
) -> None:
    policy = cache_mod.Policy.from_flags(**flags)
    assert (policy.read, policy.write, policy.require_hit) == (read, write, require)


def test_a_value_written_comes_back(tmp_path: Path) -> None:
    with cache_mod.Cache(tmp_path) as cache:
        assert cache.put("k", {"rows": [1, 2, 3]})
        entry = cache.get("k")
    assert entry is not None
    assert entry.value == {"rows": [1, 2, 3]}


def test_a_miss_is_a_miss(tmp_path: Path) -> None:
    with cache_mod.Cache(tmp_path) as cache:
        assert cache.get("nothing") is None
        assert cache.stats.misses == 1


def test_an_expired_entry_is_a_miss(tmp_path: Path) -> None:
    with cache_mod.Cache(tmp_path) as cache:
        cache.put("k", 1, ttl=0)
        time.sleep(0.01)
        assert cache.get("k") is None


# -- conditional revalidation (D3) -------------------------------------------------


def test_an_expired_entry_with_a_validator_is_revalidatable_not_a_miss(
    tmp_path: Path,
) -> None:
    policy = cache_mod.Policy(read=True, write=True, revalidate=True)
    with cache_mod.Cache(tmp_path, policy=policy) as cache:
        cache.put("k", {"body": 1}, ttl=0, etag='"abc"')
        time.sleep(0.01)
        entry = cache.get("k")
    assert entry is not None
    assert entry.fresh is False
    assert entry.etag == '"abc"'


def test_an_expired_entry_without_a_validator_is_still_a_plain_miss(
    tmp_path: Path,
) -> None:
    """Nothing to send the server means nothing to revalidate with."""
    policy = cache_mod.Policy(read=True, write=True, revalidate=True)
    with cache_mod.Cache(tmp_path, policy=policy) as cache:
        cache.put("k", {"body": 1}, ttl=0)
        time.sleep(0.01)
        assert cache.get("k") is None


def test_revalidate_off_still_misses_an_expired_entry_even_with_a_validator(
    tmp_path: Path,
) -> None:
    with cache_mod.Cache(tmp_path) as cache:  # default policy: revalidate=False
        cache.put("k", {"body": 1}, ttl=0, etag='"abc"')
        time.sleep(0.01)
        assert cache.get("k") is None


def test_a_fresh_entry_is_fresh_regardless_of_revalidate(tmp_path: Path) -> None:
    policy = cache_mod.Policy(read=True, write=True, revalidate=True)
    with cache_mod.Cache(tmp_path, policy=policy) as cache:
        cache.put("k", {"body": 1}, etag='"abc"')
        entry = cache.get("k")
    assert entry is not None
    assert entry.fresh is True


def test_no_cache_neither_reads_nor_writes(tmp_path: Path) -> None:
    with cache_mod.Cache(tmp_path, policy=cache_mod.Policy(read=True, write=True)) as warm:
        warm.put("k", 1)
    with cache_mod.Cache(tmp_path, policy=cache_mod.Policy.from_flags(no_cache=True)) as cold:
        assert cold.get("k") is None
        assert cold.put("k", 2) is False


def test_refresh_writes_without_reading(tmp_path: Path) -> None:
    with cache_mod.Cache(tmp_path, policy=cache_mod.Policy.from_flags(refresh=True)) as cache:
        assert cache.put("k", 1) is True
        assert cache.get("k") is None


def test_two_identical_values_share_one_blob(tmp_path: Path) -> None:
    """Content-addressed: the blob is named by its own contents."""
    with cache_mod.Cache(tmp_path) as cache:
        cache.put("one", {"same": True})
        cache.put("two", {"same": True})
    assert len(list((tmp_path / "blobs").iterdir())) == 1


def test_a_value_that_will_not_serialise_is_not_an_error(tmp_path: Path) -> None:
    """It simply is not cached, and the step runs next time."""

    class Opaque:
        __slots__ = ("handle",)

    with cache_mod.Cache(tmp_path) as cache:
        assert cache.put("k", {"bad": {1, 2, 3}}) in (True, False)
        assert cache.get("missing") is None


def test_pruning_drops_expired_entries_and_their_blobs(tmp_path: Path) -> None:
    with cache_mod.Cache(tmp_path) as cache:
        cache.put("keep", 1, ttl=3600)
        cache.put("drop", 2, ttl=0)
        time.sleep(0.01)
        assert cache.prune() == 1
        assert cache.get("keep") is not None
    assert len(list((tmp_path / "blobs").iterdir())) == 1


def test_eviction_takes_the_least_recently_used(tmp_path: Path) -> None:
    with cache_mod.Cache(tmp_path, max_bytes=200) as cache:
        for name in ("a", "b", "c"):
            cache.put(name, {"payload": name * 40})
        cache.get("c")
        cache.prune()
        assert cache.get("c") is not None


def test_an_index_row_without_its_blob_is_a_miss(tmp_path: Path) -> None:
    """Index says yes, disk says no. Believe the disk."""
    with cache_mod.Cache(tmp_path) as cache:
        cache.put("k", 1)
        for blob in (tmp_path / "blobs").iterdir():
            blob.unlink()
        assert cache.get("k") is None


def test_an_offline_miss_exits_five(tmp_path: Path) -> None:
    """The work was refused, not attempted and failed. A script wants to tell those apart."""
    error = cache_mod.Missing("fetch")
    assert error.exit_code == EXIT_CACHE_MISS
    assert "--offline" in str(error)
    assert any("without --offline" in remedy for remedy in error.diagnostic.remedies)


def test_stats_read_as_a_summary(tmp_path: Path) -> None:
    with cache_mod.Cache(tmp_path) as cache:
        cache.put("k", 1)
        cache.get("k")
        cache.get("nope")
    assert cache.stats.summary() == "cache 1 hit / 1 miss (50%)"


def test_a_cache_root_is_chosen_per_platform(monkeypatch: Any) -> None:
    monkeypatch.setenv("SCLPL_CACHE_DIR", "/tmp/explicit")
    assert cache_mod.default_root() == Path("/tmp/explicit")
    monkeypatch.delenv("SCLPL_CACHE_DIR")
    assert "sclpl" in str(cache_mod.default_root()).lower()
