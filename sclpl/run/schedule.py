"""The scheduler: a ready queue, not barrier waves.

Defect 2 from the plan lives here. The engine this replaces ran steps in waves and
waited for every step in a wave to finish before starting the next, so one slow request
held back everything behind it regardless of whether anything actually depended on it.
Here a node is admitted the moment its last dependency lands, so the graph finishes in
critical-path time.

Two rules keep it from deadlocking or thrashing:

**Semaphores are acquired in a fixed global order** -- global, then host, then tags in
sorted order. Two workers can never hold the pair a third needs in the opposite order,
so no arrangement of hosts and tags can deadlock.

**Fan-out is injected into the same graph.** A `foreach` in M6 adds its expansion as
nodes here rather than calling `gather` inside a step, so the global concurrency ceiling
means what it says even when a loop is running.
"""

from __future__ import annotations

import asyncio
import contextlib
import heapq
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sclpl.render.events import RunFinished, StepFinished, StepStarted, ValueFreed
from sclpl.render.reporter import Reporter
from sclpl.run.errors import SclplError
from sclpl.run.plan import Node, Plan
from sclpl.values.store import ValueStore

#: What a worker calls to run one node. Returns the value the node produced.
Runner = Callable[[Node], Awaitable[Any]]


@dataclass(slots=True)
class Limits:
    """Concurrency ceilings. Every one of them is a promise to a remote server."""

    concurrency: int = 16
    host_concurrency: int = 6
    #: Per-tag ceilings, for a rate-limited family of endpoints.
    tags: dict[str, int] = field(default_factory=dict)
    #: Stop admitting new work after the first failure.
    keep_going: bool = False


@dataclass(slots=True)
class Outcome:
    """What a finished run produced."""

    status: str = "ok"
    started: list[str] = field(default_factory=list)
    succeeded: list[str] = field(default_factory=list)
    failed: dict[str, BaseException] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)
    duration_ms: int = 0

    @property
    def ok(self) -> bool:
        return not self.failed

    def counts(self) -> dict[str, int]:
        return {
            "steps": len(self.succeeded),
            "failed": len(self.failed),
            "skipped": len(self.skipped),
        }


class _Gate:
    """The ordered semaphore set.

    Acquisition order is fixed and global: the process-wide ceiling, then the host, then
    each tag in sorted order. Releasing happens in reverse. This is the whole deadlock
    argument -- there is no second order for a cycle to form in.
    """

    __slots__ = ("_global", "_hosts", "_tags", "_limits")

    def __init__(self, limits: Limits) -> None:
        self._limits = limits
        self._global = asyncio.Semaphore(max(1, limits.concurrency))
        self._hosts: dict[str, asyncio.Semaphore] = {}
        self._tags: dict[str, asyncio.Semaphore] = {}

    def _host(self, host: str) -> asyncio.Semaphore:
        existing = self._hosts.get(host)
        if existing is None:
            existing = asyncio.Semaphore(max(1, self._limits.host_concurrency))
            self._hosts[host] = existing
        return existing

    def _tag(self, tag: str) -> asyncio.Semaphore | None:
        ceiling = self._limits.tags.get(tag)
        if ceiling is None:
            return None
        existing = self._tags.get(tag)
        if existing is None:
            existing = asyncio.Semaphore(max(1, ceiling))
            self._tags[tag] = existing
        return existing

    def set_host_limit(self, host: str, ceiling: int) -> None:
        """Adaptive concurrency lowers a host's ceiling; it never raises it above the cap."""
        ceiling = max(1, min(ceiling, self._limits.host_concurrency))
        self._hosts[host] = asyncio.Semaphore(ceiling)

    @contextlib.asynccontextmanager
    async def hold(self, node: Node) -> Any:
        wanted: list[asyncio.Semaphore] = [self._global]
        if node.host:
            wanted.append(self._host(node.host))
        for tag in sorted(node.tags):
            semaphore = self._tag(tag)
            if semaphore is not None:
                wanted.append(semaphore)

        acquired: list[asyncio.Semaphore] = []
        try:
            for semaphore in wanted:
                await semaphore.acquire()
                acquired.append(semaphore)
            yield
        finally:
            for semaphore in reversed(acquired):
                semaphore.release()


class Scheduler:
    """Runs a plan, admitting each node the moment its dependencies land."""

    __slots__ = (
        "_plan",
        "_store",
        "_reporter",
        "_limits",
        "_gate",
        "_ready",
        "_indegree",
        "_outcome",
        "_stopping",
        "_counter",
        "_wakeup",
        "_inflight",
    )

    def __init__(
        self,
        plan: Plan,
        store: ValueStore,
        reporter: Reporter,
        limits: Limits | None = None,
    ) -> None:
        self._plan = plan
        self._store = store
        self._reporter = reporter
        self._limits = limits if limits is not None else Limits()
        self._gate = _Gate(self._limits)
        self._ready: list[tuple[float, int, str]] = []
        self._indegree: dict[str, int] = {}
        self._outcome = Outcome()
        self._stopping = False
        self._counter = 0
        self._wakeup = asyncio.Event()
        self._inflight = 0

    async def run(self, runner: Runner) -> Outcome:
        """Execute every node, or stop early on failure unless `keep_going`."""
        started_at = time.perf_counter()
        self._indegree = {
            node_id: len(self._plan.nodes[node_id].needs) for node_id in self._plan.order
        }
        for node_id in self._plan.roots():
            self._push(node_id)

        workers = max(1, self._limits.concurrency)
        cancelled = False
        try:
            async with asyncio.TaskGroup() as group:
                for index in range(workers):
                    group.create_task(self._worker(runner), name=f"sclpl-worker-{index}")
        except* asyncio.CancelledError:
            # Ctrl-C, or a governor stepping in. Everything in flight was cancelled by
            # the TaskGroup; record what did not run rather than leaving it unexplained.
            self._outcome.status = "cancelled"
            cancelled = True
        except* Exception as group_error:
            for error in group_error.exceptions:
                self._reporter.log("error", str(error))
            self._outcome.status = "failed"

        if cancelled and _we_were_cancelled():
            # This task was the one cancelled, so the cancellation has to keep going.
            # Swallowing it would leave `asyncio.run` believing the run finished
            # normally, and Ctrl-C would appear to do nothing. Raised out here rather
            # than inside the `except*` block, which would re-wrap it in a group.
            raise asyncio.CancelledError

        never_ran = [
            node_id
            for node_id in self._plan.order
            if node_id not in self._outcome.succeeded and node_id not in self._outcome.failed
        ]
        self._outcome.skipped.extend(
            node_id for node_id in never_ran if node_id not in self._outcome.skipped
        )
        if self._outcome.failed and self._outcome.status == "ok":
            self._outcome.status = "failed"
        self._outcome.duration_ms = int((time.perf_counter() - started_at) * 1000)
        return self._outcome

    # -- the worker loop ---------------------------------------------------------

    async def _worker(self, runner: Runner) -> None:
        while True:
            node_id = await self._take()
            if node_id is None:
                return
            node = self._plan.nodes[node_id]
            try:
                await self._execute(node, runner)
            finally:
                self._inflight -= 1
                self._wakeup.set()

    async def _take(self) -> str | None:
        """The next admissible node, or None when the run is over.

        Waits rather than spins: a worker with nothing to do sleeps until another
        finishes and either pushes work or empties the graph.
        """
        while True:
            if self._ready and not self._stopping:
                _, _, node_id = heapq.heappop(self._ready)
                self._inflight += 1
                return node_id
            if self._inflight == 0:
                # Nothing running and nothing ready: either done, or stopping.
                return None
            self._wakeup.clear()
            await self._wakeup.wait()

    async def _execute(self, node: Node, runner: Runner) -> None:
        self._outcome.started.append(node.id)
        self._reporter.emit(StepStarted(id=node.id, kind="step", lane=_lane_of(node)))
        started = time.perf_counter()
        try:
            async with self._gate.hold(node):
                value = await runner(node)
        except asyncio.CancelledError:
            self._reporter.emit(
                StepFinished(id=node.id, status="cancelled", duration_ms=_ms(started))
            )
            raise
        except (SclplError, Exception) as error:  # noqa: BLE001 - one step must not kill the run
            self._outcome.failed[node.id] = error
            self._reporter.emit(
                StepFinished(
                    id=node.id,
                    status="failed",
                    duration_ms=_ms(started),
                    summary=_summarise(error),
                )
            )
            self._reporter.log("error", str(error), node.id)
            if not self._limits.keep_going:
                self._stopping = True
                self._wakeup.set()
            return

        # A leaf is pinned: nothing downstream reads it, but it is what the run
        # produced. "No consumer in the graph" is not the same as "nobody wants it",
        # and freeing the answer the moment it arrives is not a memory saving.
        self._store.put(
            node.id,
            value,
            readers=self._plan.readers_of(node.id),
            pinned=not node.dependents,
        )
        self._outcome.succeeded.append(node.id)
        self._reporter.emit(
            StepFinished(
                id=node.id,
                status="ok",
                duration_ms=_ms(started),
                summary=_describe(value),
            )
        )
        self._settle(node)

    def _settle(self, node: Node) -> None:
        """Release what this node consumed, then admit whatever it unblocked."""
        for name in node.reads:
            freed = self._store.release(name)
            if freed is not None:
                self._reporter.emit(ValueFreed(name=freed.name, bytes=freed.bytes))
        for dependent in sorted(node.dependents):
            self._indegree[dependent] -= 1
            if self._indegree[dependent] == 0:
                self._push(dependent)
        self._wakeup.set()

    def _push(self, node_id: str) -> None:
        """Queue a node, ordered by remaining critical path -- longest chain first."""
        node = self._plan.nodes[node_id]
        self._counter += 1
        heapq.heappush(self._ready, (-node.critical_path, self._counter, node_id))
        self._wakeup.set()


async def execute(
    plan: Plan,
    runner: Runner,
    reporter: Reporter,
    *,
    store: ValueStore | None = None,
    limits: Limits | None = None,
    workflow: str = "workflow",
) -> Outcome:
    """Run a plan and report the outcome. The one entry point callers need."""
    store = store if store is not None else ValueStore()
    scheduler = Scheduler(plan, store, reporter, limits)
    outcome = await scheduler.run(runner)
    reporter.emit(
        RunFinished(
            status=outcome.status,  # type: ignore[arg-type]
            duration_ms=outcome.duration_ms,
            counts=outcome.counts(),
            exit_code=0 if outcome.ok else 1,
        )
    )
    return outcome


def _we_were_cancelled() -> bool:
    """Whether the enclosing task itself is being cancelled.

    Distinguishes Ctrl-C from a cancellation the scheduler raised internally: the first
    has to keep propagating, the second is ours to absorb.
    """
    current = asyncio.current_task()
    return current is not None and bool(current.cancelling())


def _lane_of(node: Node) -> Any:
    return node.lane or "async"


def _ms(since: float) -> int:
    return int((time.perf_counter() - since) * 1000)


def _summarise(error: BaseException) -> str:
    if isinstance(error, SclplError):
        return error.diagnostic.message
    return f"{type(error).__name__}: {error}"


def _describe(value: Any) -> str:
    """A one-line summary of what a step produced, for the step line."""
    match value:
        case None:
            return ""
        case list() | tuple():
            count = len(value)
            return f"{count} item{'' if count == 1 else 's'}"
        case dict():
            return f"{len(value)} field{'' if len(value) == 1 else 's'}"
        case str():
            return f"{len(value)} chars"
        case _:
            rows = getattr(value, "row_count", None)
            if isinstance(rows, int):
                return f"{rows} row{'' if rows == 1 else 's'}"
            return ""


__all__ = ["Limits", "Outcome", "Runner", "Scheduler", "execute"]
