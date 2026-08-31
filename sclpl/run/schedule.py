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

from sclpl.errors import SclplError
from sclpl.render.events import (
    ResourceWarning,
    RunFinished,
    StepFinished,
    StepStarted,
    ValueFreed,
)
from sclpl.render.reporter import Reporter
from sclpl.run.plan import Node, Plan
from sclpl.values.governor import Governor, human
from sclpl.values.store import ValueStore

#: What a worker calls to run one node. Returns the value the node produced.
Runner = Callable[[Node], Awaitable[Any]]

#: Appended to a control-flow node's id to name the barrier `expand` puts after it.
#: `::` cannot appear in a step id (the IR refuses it), so an injected name can never
#: collide with one someone wrote.
JOIN_SUFFIX = "::join"


@dataclass(slots=True)
class ExpandSpec:
    """One node a running step wants added to the graph beneath it."""

    id: str
    reads: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()
    host: str | None = None
    lane: str | None = None
    weight: float = 1.0


@dataclass(slots=True)
class Limits:
    """Concurrency ceilings. Every one of them is a promise to a remote server."""

    concurrency: int = 16
    host_concurrency: int = 6
    #: Per-tag ceilings, for a rate-limited family of endpoints.
    tags: dict[str, int] = field(default_factory=dict)
    #: Stop admitting new work after the first failure.
    keep_going: bool = False
    #: Bytes a run may hold before it starts writing intermediates to disk. None turns
    #: the governor off entirely, which is for tests and for `--keep-all`.
    memory_budget: int | None = None


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

    def set_tag_limit(self, tag: str, ceiling: int) -> None:
        """Give a tag a ceiling it did not have. Used by a bounded `foreach`.

        A per-loop limit is a per-tag limit with a private name, so it goes through the
        same ordered acquisition as every other ceiling and cannot introduce a new way
        to deadlock. A fourth kind of semaphore would have to argue that separately.
        """
        self._limits.tags.setdefault(tag, ceiling)

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
        "_governor",
        "_ceiling",
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
        budget = self._limits.memory_budget
        self._governor = Governor(budget=budget) if budget else None
        self._ceiling = max(1, self._limits.concurrency)

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
            if self._ready and not self._stopping and self._inflight < self._ceiling:
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
        published = node.publishes
        self._store.put(
            published,
            value,
            readers=self._plan.readers_of(published),
            pinned=not node.dependents,
        )
        self._govern()
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

    def _govern(self) -> None:
        """Sample memory, and give some back if there is pressure.

        Called after a node publishes, which is the moment the store has just grown --
        and the only moment at which spilling can help before the next node adds more.

        Spilling is not freeing: the value stays readable, it just lives on disk until
        something asks for it. A run that would have died holding three times its budget
        instead finishes, slower, which is the trade the budget exists to make.
        """
        if self._governor is None:
            return
        pressure = self._governor.sample(self._store.stats().bytes_live)
        if pressure.level == "ok":
            return

        recovered = self._governor.relieve(self._store, pressure)
        if recovered:
            self._reporter.log(
                "info",
                f"memory at {pressure.describe()}; spilled {human(recovered)} to disk",
            )

        if pressure.level != "hard":
            return

        lowered = self._governor.concurrency_for(self._ceiling, pressure)
        if lowered < self._ceiling:
            # Workers are not stopped -- one already running finishes. The ceiling
            # applies to what is admitted next, which is the only thing still in hand.
            self._reporter.log(
                "warning",
                f"memory at {pressure.describe()}; concurrency {self._ceiling} -> {lowered}",
            )
            self._ceiling = lowered
        if not self._governor.warned:
            self._governor.warned = True
            self._reporter.emit(
                ResourceWarning(kind="memory", current=pressure.used, budget=pressure.budget)
            )

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

    # -- runtime expansion -------------------------------------------------------

    def expand(
        self,
        parent: str,
        specs: list[ExpandSpec],
        *,
        tag_limit: tuple[str, int] | None = None,
    ) -> None:
        """Add a subgraph beneath a running node, and make its dependents wait for it.

        This is invariant 3 and SPEC §12 meeting each other. A `foreach` cannot know how
        many iterations it has until the collection it reads exists, so the graph has to
        grow at runtime -- but growing it *here*, rather than calling `gather` inside the
        step, is what keeps the global concurrency ceiling honest. Twenty iterations
        against a host limited to four take four at a time, exactly as twenty separate
        steps would.

        The wiring, given a parent P with dependents D and new nodes N₁..Nₙ:

        - each Nᵢ waits for P, so it starts as soon as P produces the collection
        - a join node waits for P and every Nᵢ
        - every D now waits for the join instead of for P -- same indegree, later edge

        P then settles normally. Nothing downstream can observe the loop half-finished,
        and nothing had to block a worker to arrange it.
        """
        node = self._plan.nodes[parent]
        join_id = f"{parent}{JOIN_SUFFIX}"
        if tag_limit is not None:
            self._gate.set_tag_limit(*tag_limit)
        made = [spec.id for spec in specs]

        made_set = {spec.id for spec in specs}

        # Hold open everything the new nodes read. The refcount for a binding was fixed
        # when the plan was built, from the nodes that existed then; these did not. Left
        # alone, a value read only by a loop body is freed the moment the parent settles
        # -- which is a failure on a name that is plainly there in the file.
        for spec in specs:
            for name in spec.reads - made_set:
                self._store.retain(name)

        for spec in specs:
            # A spec's `reads` name earlier nodes in the same copy of a body, which is
            # where a body's written order becomes graph edges. Anything else it reads
            # was produced before the parent ran and is already in the store.
            within = spec.reads & made_set
            self._plan.nodes[spec.id] = Node(
                id=spec.id,
                reads=spec.reads,
                needs=frozenset({parent}) | within,
                tags=spec.tags,
                host=spec.host,
                lane=spec.lane,
                weight=spec.weight,
                critical_path=node.critical_path,
            )
            self._plan.order.append(spec.id)
            self._indegree[spec.id] = 1 + len(within)

        # The barrier publishes under the loop's own name, and the loop itself under a
        # private one that nothing reads and the store frees at once. `@loop` downstream
        # is therefore the finished result, and there is no moment at which it is the
        # half-built one -- which is the difference between a loop you can depend on and
        # a race.
        self._plan.nodes[join_id] = Node(
            id=join_id,
            needs=frozenset({parent, *made}),
            dependents=node.dependents,
            critical_path=node.critical_path,
            binds=parent,
        )
        node.binds = f"{parent}{JOIN_SUFFIX}::pending"
        self._plan.order.append(join_id)
        self._indegree[join_id] = 1 + len(made)

        for dependent in node.dependents:
            waiting = self._plan.nodes[dependent]
            waiting.needs = (waiting.needs - {parent}) | {join_id}

        for made_id in made:
            made_node = self._plan.nodes[made_id]
            followers = {
                other.id
                for other in (self._plan.nodes[name] for name in made)
                if made_id in other.needs
            }
            made_node.dependents = frozenset({join_id, *followers})
        node.dependents = frozenset({join_id, *made})

    def joined(self, parent: str) -> list[str]:
        """The ids `expand` created beneath ``parent``, in the order they were made."""
        join_id = f"{parent}{JOIN_SUFFIX}"
        node = self._plan.nodes.get(join_id)
        if node is None:
            return []
        return [name for name in node.needs if name != parent]

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
