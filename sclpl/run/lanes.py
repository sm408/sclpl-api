"""Where a step actually runs: the event loop, a thread, or a process.

Most work here is waiting on a socket, and the event loop is the right place for that.
Two kinds are not:

- **blocking work** -- a synchronous library call, a large file read. On the loop it
  stalls every other step, including the ones whose responses have already arrived.
- **CPU-bound work** -- a join over a hundred thousand rows. A thread does not help,
  because the GIL means it is the same core; a process does.

**Assignment order** (SPEC section 12): an explicit `lane` on the step wins, then the
callable's own shape, then a size threshold. Nothing here guesses from history yet.

**Why a size threshold.** Sending a value to a process costs a serialisation and a copy,
and for a small payload that costs more than the work it moves. The threshold is what
keeps `sort_by` over ten rows on the event loop where it belongs.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
from collections.abc import Callable
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field
from pickle import PicklingError
from typing import Any

from sclpl.values.ref import size_of

#: Below this a process lane costs more than it saves: the pickle, the copy, and the
#: round trip all scale with the payload, and the work does not.
PROCESS_THRESHOLD = 1 * 1024 * 1024

#: A CPU-bound step is one whose *inputs* are this large and whose function is not
#: async. Below it, thread and loop are indistinguishable and cheaper.
THREAD_THRESHOLD = 64 * 1024

LANES = ("async", "thread", "process", "serial")


@dataclass(slots=True)
class Pools:
    """Thread and process pools, created on first use and closed with the run.

    Neither is created eagerly. A workflow that never leaves the event loop should not
    pay for a process pool it does not use -- on Windows that is a fresh interpreter per
    worker, which is not free.
    """

    max_threads: int = 8
    max_processes: int = field(default_factory=lambda: min(4, os.cpu_count() or 1))
    #: Set once a pool has died. A second attempt would die the same way.
    processes_broken: bool = False
    _threads: concurrent.futures.ThreadPoolExecutor | None = None
    _processes: concurrent.futures.ProcessPoolExecutor | None = None

    def threads(self) -> concurrent.futures.ThreadPoolExecutor:
        if self._threads is None:
            self._threads = concurrent.futures.ThreadPoolExecutor(
                max_workers=self.max_threads, thread_name_prefix="sclpl"
            )
        return self._threads

    def processes(self) -> concurrent.futures.ProcessPoolExecutor | None:
        """The process pool, or None if this machine cannot make one.

        A restricted environment -- a container without `/dev/shm`, a sandbox that
        refuses `fork` -- fails here. That is a reason to run the work on a thread, not
        a reason to fail the run, so the caller falls back.
        """
        if self.processes_broken:
            return None
        if self._processes is None:
            try:
                self._processes = concurrent.futures.ProcessPoolExecutor(
                    max_workers=self.max_processes
                )
            except (OSError, ValueError, ImportError):
                return None
        return self._processes

    def forget_processes(self) -> None:
        """Drop a broken pool. The next caller falls back to a thread."""
        if self._processes is not None:
            self._processes.shutdown(wait=False, cancel_futures=True)
            self._processes = None
        self.processes_broken = True

    def close(self) -> None:
        if self._threads is not None:
            self._threads.shutdown(wait=False, cancel_futures=True)
            self._threads = None
        if self._processes is not None:
            self._processes.shutdown(wait=False, cancel_futures=True)
            self._processes = None


def assign(
    declared: str | None,
    *,
    is_async: bool,
    args: list[Any],
    kwargs: dict[str, Any] | None = None,
) -> str:
    """Which lane this call belongs in.

    An `async def` stays on the loop whatever its arguments look like: it is already
    cooperative, and moving it to a thread would run an event loop inside a thread to no
    purpose.
    """
    if declared in LANES:
        return declared
    if is_async:
        return "async"

    payload = sum(size_of(value) for value in args)
    if kwargs:
        payload += sum(size_of(value) for value in kwargs.values())

    if payload >= PROCESS_THRESHOLD:
        return "process"
    if payload >= THREAD_THRESHOLD:
        return "thread"
    return "async"


async def call(
    lane: str, pools: Pools, function: Callable[..., Any], *args: Any, **kwargs: Any
) -> Any:
    """Invoke ``function`` in ``lane``, awaiting the result.

    A process lane that cannot be created, or a payload that will not pickle, falls back
    to a thread with the reason attached. Falling back is right because the lane is an
    optimisation: the answer does not depend on where it was computed, only the time
    does, and a run that fails because a value would not pickle has lost something real
    to save something that was only ever a preference.
    """
    loop = asyncio.get_running_loop()

    if lane == "serial":
        return function(*args, **kwargs)

    if lane == "process":
        pool = pools.processes()
        if pool is None:
            raise LaneFallback("no process pool is available on this machine")
        try:
            return await loop.run_in_executor(pool, _apply, function, args, kwargs)
        except (TypeError, AttributeError, EOFError, PicklingError) as error:
            # Not picklable -- a closure, a local class, an open handle.
            raise LaneFallback(str(error)) from error
        except BrokenProcessPool as error:
            # A worker died. Every future on this pool is now broken, so the pool is
            # discarded rather than retried: the next process-lane step would fail the
            # same way, and one dead pool should not fail every step after it.
            pools.forget_processes()
            raise LaneFallback(f"the process pool broke ({error})") from error

    if lane == "thread":
        return await loop.run_in_executor(pools.threads(), _apply, function, args, kwargs)

    result = function(*args, **kwargs)
    if asyncio.iscoroutine(result):
        return await result
    return result


class LaneFallback(Exception):
    """The chosen lane could not take the work. The caller retries on a thread."""


def _apply(function: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    """Top-level so it is picklable; a lambda here would defeat the process lane."""
    return function(*args, **kwargs)
