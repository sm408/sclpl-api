"""Project mutation locks serialize writers and identify an owner on timeout.

C5 extends the same primitive to output ownership: `output_locks` below is what a run
holds over every managed destination for its whole duration, so a competing run
targeting the same file waits or fails with an owner, while one targeting a different
file is never blocked at all.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from sclpl.errors import ValidationError
from sclpl.state.locking import Lock, canonical_path, output_lock_path, output_locks


def test_releasing_a_lock_removes_its_file(tmp_path: Path) -> None:
    """A `.sclpl-lock` file that outlives every run that ever used it just piles up
    beside real outputs forever -- exactly what a user running workflows against a
    real project noticed. Release must not leave it behind.
    """
    path = tmp_path / "mutation.lock"
    with Lock(path):
        assert path.exists()
    assert not path.exists()


def test_lock_times_out_with_owner_details(tmp_path: Path) -> None:
    path = tmp_path / "mutation.lock"
    with Lock(path), pytest.raises(ValidationError, match="current owner: pid="):
        _acquire_immediately(path)


def _acquire_immediately(path: Path) -> None:
    with Lock(path, timeout=0):
        pass


# -- output ownership (C5) -----------------------------------------------------------


def test_two_different_outputs_never_wait_on_each_other(tmp_path: Path) -> None:
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    with output_locks([a], timeout=0), output_locks([b], timeout=0):
        pass  # neither raised: acquiring b did not need a's lock released first


def test_releasing_an_output_lock_removes_its_file(tmp_path: Path) -> None:
    path = tmp_path / "report.csv"
    with output_locks([path]):
        assert output_lock_path(path).exists()
    assert not output_lock_path(path).exists()


def test_the_same_output_is_exclusive(tmp_path: Path) -> None:
    path = tmp_path / "report.csv"
    with output_locks([path]), pytest.raises(ValidationError, match="current owner"):  # noqa: SIM117
        with output_locks([path], timeout=0):
            pass


@pytest.mark.skipif(sys.platform != "win32", reason="case folding is a Windows-filesystem behavior")
def test_case_and_relative_segments_collide_on_the_same_lock(tmp_path: Path) -> None:
    """`Report.CSV` and `./sub/../report.csv` name the same file; the lock must agree."""
    (tmp_path / "sub").mkdir()
    lower = tmp_path / "report.csv"
    upper = tmp_path / "sub" / ".." / "REPORT.CSV"
    assert canonical_path(lower) == canonical_path(upper)
    assert output_lock_path(lower) == output_lock_path(upper)


def test_opposite_lock_orders_never_deadlock_each_other(tmp_path: Path) -> None:
    """One coroutine wants a-then-b; another wants b-then-a. A per-resource lock with
    no fixed acquisition order would let each hold one and wait on the other forever.
    `output_locks` sorts by canonical path first, so both actually try in the same
    order and one simply waits its turn.
    """
    import threading

    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    entered: list[str] = []
    errors: list[BaseException] = []

    def hold(paths: list[Path], label: str) -> None:
        try:
            with output_locks(paths, timeout=5):
                entered.append(label)
                time.sleep(0.1)
        except BaseException as error:  # noqa: BLE001 - surfaced to the test thread
            errors.append(error)

    first = threading.Thread(target=hold, args=([a, b], "first"))
    second = threading.Thread(target=hold, args=([b, a], "second"))
    first.start()
    second.start()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not first.is_alive() and not second.is_alive(), "a deadlock left a thread stuck"
    assert not errors
    assert sorted(entered) == ["first", "second"]


def test_a_separate_process_holding_the_lock_is_a_visible_owner(tmp_path: Path) -> None:
    """The primitive is OS-backed, not an in-process convenience: prove it holds
    across a real second process, per C5's explicit verification requirement.
    """
    path = tmp_path / "shared-output.csv"
    script = (
        "import time\n"
        "from pathlib import Path\n"
        "from sclpl.state.locking import output_locks\n"
        f"with output_locks([Path({str(path)!r})]):\n"
        "    time.sleep(2)\n"
    )
    holder = subprocess.Popen([sys.executable, "-c", script])
    try:
        deadline = time.monotonic() + 2
        saw_contention = False
        while time.monotonic() < deadline:
            try:
                with output_locks([path], timeout=0):
                    pass  # got and released it: the other process has not started yet
            except ValidationError as error:
                if "current owner: pid=" in str(error):
                    saw_contention = True
                    break
            time.sleep(0.02)
        if not saw_contention:
            pytest.fail("never observed the other process holding the lock")
        with pytest.raises(ValidationError, match="current owner: pid="):  # noqa: SIM117
            with output_locks([path], timeout=0.2):
                pass
    finally:
        holder.wait(timeout=5)
    # Released now: this process can take it.
    with output_locks([path], timeout=1):
        pass
