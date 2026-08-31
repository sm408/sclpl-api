"""Control flow: turning a body into nodes, once it is known how many there are.

None of these kinds does its own work. Each one answers a question -- how many times,
which branch, once more or not -- and then hands the scheduler the nodes that answer
implies. That is the whole design, and it is what SPEC §12 means by "injected into the
same graph, never a nested `gather`":

- a `gather` inside a step holds a worker and a semaphore slot while its children run,
  so a hundred-element loop against a four-at-a-time host either deadlocks or quietly
  exceeds the limit it was given;
- nodes in the graph are admitted by the same gate as everything else, so the loop is
  simply a hundred more steps and every ceiling still means what it says.

**Names.** A body step written once becomes many nodes, so each gets a decorated id --
`loop::3::fetch`. The decoration is scheduling bookkeeping and never appears in an
expression: inside the body, `@fetch` means *this* iteration's `fetch`, which works
because each iteration carries a `Frame` holding its own bindings, and a frame is
consulted before the global store.

**Results.** The barrier `expand` puts after the iterations publishes the loop's value
under the loop's own name, so `@loop` downstream is the list of results and nothing can
observe it half-built.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sclpl.errors import StepFailed
from sclpl.run.ir import (
    ForeachConfig,
    GateConfig,
    IfConfig,
    ParallelConfig,
    Step,
    WhileConfig,
)
from sclpl.run.schedule import ExpandSpec
from sclpl.values.store import Frame

if TYPE_CHECKING:  # pragma: no cover - import cycle at runtime, fine for typing
    from sclpl.run.execute import Runtime

#: Separates a body step's name from the iteration it belongs to. A step id cannot
#: contain `:`, so a decorated name can never collide with one someone wrote.
MARK = "::"

#: Prefix for the private tag a bounded `foreach` uses. Same reasoning: a tag someone
#: wrote cannot start with `::`.
LOOP_TAG = "::loop:"


@dataclass(slots=True)
class Injected:
    """One node created at runtime, and the scope it runs in."""

    step: Step
    frame: Frame
    #: The loop, branch, or barrier this node belongs to.
    parent: str
    #: Set on the last step of an iteration: its value is the iteration's result.
    result_of: str | None = None
    #: An expression evaluated in the iteration's scope, whose value is the iteration's
    #: result instead of the last step's. Only ever set alongside `result_of`.
    collect: str | None = None


@dataclass(slots=True)
class Expansion:
    """What a control-flow step decided, ready for the scheduler."""

    specs: list[ExpandSpec] = field(default_factory=list)
    injected: dict[str, Injected] = field(default_factory=dict)
    #: Iteration key -> the node whose value is that iteration's result.
    results: dict[str, str] = field(default_factory=dict)
    #: What the control step's own value is, once its copies have run:
    #:
    #: - `list` -- one entry per copy, in the order they were made (`foreach`, `parallel`)
    #: - `one`  -- the single copy's value (`if`: one branch is taken, not many)
    #: - `last` -- the most recent pass's value (`while`: a loop that runs until
    #:   something is true is asking for the state at the end, and the intermediate
    #:   states are what it was getting past)
    produces: str = "list"
    #: What the loop itself produced, for the barrier to publish. `None` means "collect
    #: the iteration results", which is the normal case.
    value: Any = None
    has_value: bool = False
    #: A ceiling on how many of these copies run at once, as (tag, limit). A `foreach`
    #: with `concurrency` sets one; it is a per-tag ceiling with a private name, so it
    #: goes through the same ordered acquisition as every other limit.
    tag_limit: tuple[str, int] | None = None
    #: The scope the copy runs in. A `while` hands this to its continuation, so the next
    #: condition sees what the pass just did -- which is the only way the condition can
    #: ever go false, and therefore the only way the loop can end on its own terms.
    frame: Frame | None = None


def expand_foreach(
    step: Step, config: ForeachConfig, items: list[Any], runtime: Runtime
) -> Expansion:
    """One copy of the body per element.

    An empty collection is not an error and not a skip: the loop ran, over nothing, and
    produced an empty list. A workflow that filtered everything out should get `[]` and
    carry on, not a failure that reads like the API broke.
    """
    if not config.body:
        raise StepFailed(
            f"step {step.id!r} is a foreach with no body",
            remedies=["indent at least one step under it"],
        )

    expansion = Expansion()
    tag: str | None = None
    if config.concurrency is not None:
        tag = f"{LOOP_TAG}{step.id}"
        expansion.tag_limit = (tag, config.concurrency)

    for index, item in enumerate(items):
        frame = Frame(
            values={config.var: item, "index": index},
            parent=runtime.frame,
        )
        _place(
            expansion,
            step,
            config.body,
            f"{index}",
            frame,
            runtime,
            tag=tag,
            collect=config.collect,
        )
    if not items:
        expansion.value = []
        expansion.has_value = True
    return expansion


def expand_branch(step: Step, config: IfConfig, taken: bool, runtime: Runtime) -> Expansion:
    """The branch the condition chose, and only that one.

    A branch with no steps is legitimate -- `when` with no `otherwise` is the common
    shape -- and produces `null` rather than nothing, so a downstream reference to it
    resolves either way.
    """
    body = config.then if taken else config.otherwise
    expansion = Expansion()
    if not body:
        expansion.value = None
        expansion.has_value = True
        return expansion
    expansion.produces = "one"
    _place(expansion, step, body, "then" if taken else "else", Frame(parent=runtime.frame), runtime)
    return expansion


def expand_iteration(
    step: Step, config: WhileConfig, iteration: int, runtime: Runtime
) -> Expansion:
    """One pass of a `while`, plus the node that decides whether there is another.

    The re-check is a node rather than a loop inside the step, for the same reason the
    body is: a `while` whose condition depends on a request must not hold a worker while
    that request runs. The continuation expands again when it runs, so the graph grows
    one iteration at a time and stops the moment the condition goes false.
    """
    if not config.body:
        raise StepFailed(
            f"step {step.id!r} is a while with no body",
            remedies=["indent at least one step under it"],
        )

    expansion = Expansion(produces="last")
    seeded: dict[str, Any] = {"iteration": iteration}
    if iteration == 0:
        # A loop body commonly refers to what the previous pass produced -- that is how
        # a loop makes progress. On the first pass there is no previous one, so the
        # body's own names are bound to null rather than left unresolved. The
        # alternative is an error naming a step that is written two lines below.
        seeded.update({body_step.id: None for body_step in config.body})
    frame = Frame(values=seeded, parent=runtime.frame)
    expansion.frame = frame
    _place(expansion, step, config.body, f"{iteration}", frame, runtime)
    return expansion


def expand_parallel(step: Step, config: ParallelConfig, runtime: Runtime) -> Expansion:
    """Every branch at once. The graph would do this anyway; `parallel` says it out loud.

    Worth having because it is a claim the closure check can verify: branches that
    reference each other are a mistake the reader meant to avoid, and stating the intent
    is what makes catching it possible.
    """
    if not config.branches:
        raise StepFailed(
            f"step {step.id!r} is a parallel with no branches",
            remedies=["indent at least one branch under it"],
        )
    expansion = Expansion()
    for index, branch in enumerate(config.branches):
        if branch:
            _place(expansion, step, branch, f"b{index}", Frame(parent=runtime.frame), runtime)
    return expansion


def gate_reason(config: GateConfig) -> str:
    """A barrier's explanation, for the progress line."""
    return config.reason or "barrier"


def _place(
    expansion: Expansion,
    parent: Step,
    body: list[Step],
    key: str,
    frame: Frame,
    runtime: Runtime,
    *,
    tag: str | None = None,
    collect: str | None = None,
) -> None:
    """Add one copy of ``body`` under ``key``, sharing one frame.

    The steps of an iteration share a frame, which is how `@earlier` inside a body means
    this iteration's `earlier`. Ordering within the copy is the order they were written:
    each waits for the one before it, because a body is a sequence, and inferring edges
    from references would let two steps of one iteration interleave in a way the author
    did not write.
    """
    del runtime
    previous: str | None = None
    for step in body:
        node_id = f"{parent.id}{MARK}{key}{MARK}{step.id}"
        expansion.specs.append(
            ExpandSpec(
                # A body is a sequence, so each step waits for the one before it. The
                # reference scan cannot see that: two steps that share no names still
                # have an order, and it is the one they were written in. Between copies
                # there is no such edge -- iteration 3 never waits for iteration 2.
                id=node_id,
                reads=reads_of(step) | ({previous} if previous else frozenset()),
                tags=frozenset(step.tags) | ({tag} if tag else frozenset()),
                host=_host_of(step),
                lane=step.lane,
                weight=1.0,
            )
        )
        expansion.injected[node_id] = Injected(step=step, frame=frame, parent=parent.id)
        previous = node_id
    if previous is not None:
        expansion.results[key] = previous
        expansion.injected[previous].result_of = key
        expansion.injected[previous].collect = collect


def _host_of(step: Step) -> str | None:
    from sclpl.run.compile_plan import host_of

    return host_of(step)


def reads_of(step: Step) -> frozenset[str]:
    """What a body step reads, so the scheduler can hold those values open.

    Most of these resolve from the iteration's frame -- the loop variable, a sibling
    step -- and only the ones that are actually in the store get held. The store treats
    a name it does not know as nothing to do.
    """
    from sclpl.run.compile_plan import references

    return frozenset(references(step))
