"""The execution plan: a DAG built from references, with critical-path lengths.

Invariant 3 is enforced here. A step's dependencies are the union of what its
expressions reference and whatever `needs` it declared; a declared list can add an
ordering edge but can never remove one that a reference implies. Hand-maintained
dependency lists drift from the expressions beside them, and the drift is silent.

The critical path is computed once and used to order the ready queue. Scheduling the
longest remaining chain first is what makes the whole graph finish in critical-path
time rather than in the order the steps happened to be written.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from sclpl.errors import ValidationError, did_you_mean


@dataclass(slots=True)
class Node:
    """One step, resolved into the graph."""

    id: str
    #: Names this step reads. Every one is an edge.
    reads: frozenset[str] = frozenset()
    #: Node ids this step must wait for. Derived from `reads` plus declared `needs`.
    needs: frozenset[str] = frozenset()
    #: Node ids waiting on this one.
    dependents: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()
    #: The remote this step talks to, for per-host concurrency. None for local work.
    host: str | None = None
    lane: str | None = None
    #: Longest path from here to a leaf, in estimated units. Higher runs first.
    critical_path: float = 0.0
    #: What one run of this step is expected to cost, for critical-path weighting.
    weight: float = 1.0
    #: The store name this node's value is published under. None means its own id.
    #: A `foreach` publishes nothing useful itself -- the barrier after its iterations
    #: publishes the loop's result under the loop's name -- which is what this is for.
    binds: str | None = None

    @property
    def publishes(self) -> str:
        return self.binds if self.binds is not None else self.id


@dataclass(slots=True)
class Plan:
    """A validated DAG, ready to schedule."""

    nodes: dict[str, Node] = field(default_factory=dict)
    #: Insertion order of the source, kept so diagnostics list steps as written.
    order: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.nodes)

    def __contains__(self, node_id: object) -> bool:
        return node_id in self.nodes

    def __iter__(self) -> Iterable[Node]:
        return iter(self.nodes[node_id] for node_id in self.order)

    def roots(self) -> list[str]:
        """Nodes with nothing to wait for -- where execution starts."""
        return [node_id for node_id in self.order if not self.nodes[node_id].needs]

    def leaves(self) -> list[str]:
        return [node_id for node_id in self.order if not self.nodes[node_id].dependents]

    def readers_of(self, name: str) -> int:
        """How many nodes read ``name``. This is the initial refcount in the store."""
        return sum(1 for node in self.nodes.values() if name in node.reads)

    def hosts(self) -> tuple[str, ...]:
        found = {node.host for node in self.nodes.values() if node.host}
        return tuple(sorted(found))

    def critical_path_length(self) -> float:
        return max((node.critical_path for node in self.nodes.values()), default=0.0)

    def topological(self) -> list[str]:
        """A valid execution order. Used by `explain` and by deterministic tests."""
        indegree = {node_id: len(node.needs) for node_id, node in self.nodes.items()}
        ready = [node_id for node_id in self.order if indegree[node_id] == 0]
        out: list[str] = []
        while ready:
            ready.sort(key=lambda node_id: (-self.nodes[node_id].critical_path, node_id))
            current = ready.pop(0)
            out.append(current)
            for dependent in sorted(self.nodes[current].dependents):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
        return out

    def subgraph(self, keep: Iterable[str]) -> Plan:
        """The plan restricted to ``keep``, with edges to dropped nodes removed.

        Used by mode pruning in M4. Dependencies on dropped nodes are *not* an error
        here -- `modes.py` has already checked closure and knows which of them are
        satisfied by an input port, the cache, or a stub.
        """
        kept = set(keep)
        nodes: dict[str, Node] = {}
        for node_id in self.order:
            if node_id not in kept:
                continue
            node = self.nodes[node_id]
            nodes[node_id] = Node(
                id=node.id,
                reads=node.reads,
                needs=frozenset(need for need in node.needs if need in kept),
                dependents=frozenset(dep for dep in node.dependents if dep in kept),
                tags=node.tags,
                host=node.host,
                lane=node.lane,
                weight=node.weight,
            )
        pruned = Plan(nodes=nodes, order=[node_id for node_id in self.order if node_id in kept])
        _score_critical_paths(pruned)
        return pruned


@dataclass(slots=True)
class StepSpec:
    """What `build` needs to know about a step. The IR in M4 produces these."""

    id: str
    reads: frozenset[str] = frozenset()
    needs: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()
    host: str | None = None
    lane: str | None = None
    weight: float = 1.0
    #: Names this step produces beyond its own id -- `let` bindings inside it.
    produces: frozenset[str] = frozenset()


def build(specs: Iterable[StepSpec], *, available: Iterable[str] = ()) -> Plan:
    """Assemble a validated plan, or raise with what is wrong and how to fix it.

    ``available`` names values that exist without a step producing them: input ports,
    workflow vars, and values restored from cache. A reference to one of those is
    resolvable but creates no edge.
    """
    specs = list(specs)
    external = set(available)

    produced: dict[str, str] = {}
    for spec in specs:
        for name in (spec.id, *spec.produces):
            if name in produced:
                raise ValidationError(
                    f"two steps both produce {name!r}",
                    remedies=[
                        f"first: {produced[name]!r}, second: {spec.id!r}",
                        "step ids must be unique, and so must `let` names",
                    ],
                )
            produced[name] = spec.id

    nodes: dict[str, Node] = {}
    for spec in specs:
        needs: set[str] = set()
        for name in spec.reads:
            if name in external:
                continue
            owner = produced.get(name)
            if owner is None:
                raise _unknown_reference(name, spec.id, produced, external)
            if owner != spec.id:
                needs.add(owner)
        for declared in spec.needs:
            if declared not in produced:
                raise _unknown_dependency(declared, spec.id, produced)
            owner = produced[declared]
            if owner != spec.id:
                needs.add(owner)
        nodes[spec.id] = Node(
            id=spec.id,
            reads=frozenset(name for name in spec.reads if name not in external),
            needs=frozenset(needs),
            tags=spec.tags,
            host=spec.host,
            lane=spec.lane,
            weight=spec.weight,
        )

    for node in nodes.values():
        for need in node.needs:
            target = nodes[need]
            target.dependents = target.dependents | {node.id}

    plan = Plan(nodes=nodes, order=[spec.id for spec in specs])
    _detect_cycle(plan)
    _score_critical_paths(plan)
    return plan


def _unknown_reference(
    name: str,
    step: str,
    produced: Mapping[str, str],
    external: set[str],
) -> ValidationError:
    candidates = list(produced) + sorted(external)
    remedies = []
    suggestion = did_you_mean(name, candidates)
    if suggestion:
        remedies.append(suggestion)
    remedies.append("declare it as an input, or add the step that produces it")
    return ValidationError(
        f"step {step!r} reads @{name}, but nothing produces it", remedies=remedies
    )


def _unknown_dependency(name: str, step: str, produced: Mapping[str, str]) -> ValidationError:
    remedies = []
    suggestion = did_you_mean(name, list(produced))
    if suggestion:
        remedies.append(suggestion)
    remedies.append("`needs` must name a step in this workflow")
    return ValidationError(
        f"step {step!r} declares needs: {name!r}, which does not exist", remedies=remedies
    )


def _detect_cycle(plan: Plan) -> None:
    """Find a cycle and name the whole loop, not just one edge in it."""
    WHITE, GREY, BLACK = 0, 1, 2
    colour = dict.fromkeys(plan.nodes, WHITE)
    stack: list[str] = []

    def visit(node_id: str) -> None:
        colour[node_id] = GREY
        stack.append(node_id)
        for need in sorted(plan.nodes[node_id].needs):
            if colour[need] == GREY:
                loop = stack[stack.index(need) :] + [need]
                raise ValidationError(
                    "these steps depend on each other in a loop: " + " -> ".join(loop),
                    remedies=[
                        "a workflow is a DAG; break the loop by removing one reference",
                        "for repetition use `while` or `foreach` instead",
                    ],
                )
            if colour[need] == WHITE:
                visit(need)
        colour[node_id] = BLACK
        stack.pop()

    for node_id in plan.order:
        if colour[node_id] == WHITE:
            visit(node_id)


def _score_critical_paths(plan: Plan) -> None:
    """Longest weighted path from each node to a leaf.

    Computed bottom-up over a reverse topological order, so each node is scored after
    everything that depends on it.
    """
    for node in plan.nodes.values():
        node.critical_path = 0.0

    order = _reverse_topological(plan)
    for node_id in order:
        node = plan.nodes[node_id]
        downstream = max(
            (plan.nodes[dep].critical_path for dep in node.dependents),
            default=0.0,
        )
        node.critical_path = node.weight + downstream


def _reverse_topological(plan: Plan) -> list[str]:
    outdegree = {node_id: len(node.dependents) for node_id, node in plan.nodes.items()}
    ready = [node_id for node_id, count in outdegree.items() if count == 0]
    out: list[str] = []
    while ready:
        current = ready.pop()
        out.append(current)
        for need in plan.nodes[current].needs:
            outdegree[need] -= 1
            if outdegree[need] == 0:
                ready.append(need)
    return out
