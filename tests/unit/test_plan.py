"""The DAG: dependency inference, cycle detection, and critical paths."""

from __future__ import annotations

import pytest

from sclpl.run.errors import ValidationError
from sclpl.run.plan import StepSpec, build


def spec(step_id: str, reads: str = "", **kwargs: object) -> StepSpec:
    return StepSpec(
        id=step_id,
        reads=frozenset(reads.split()) if reads else frozenset(),
        **kwargs,  # type: ignore[arg-type]
    )


def test_a_reference_creates_the_edge() -> None:
    """Invariant 3. Reading @orders is what makes you depend on orders."""
    plan = build([spec("orders"), spec("report", "orders")])
    assert plan.nodes["report"].needs == {"orders"}
    assert plan.nodes["orders"].dependents == {"report"}


def test_declared_needs_add_an_edge_without_a_reference() -> None:
    """An ordering constraint with no data flow -- write, then read back."""
    plan = build([spec("write"), StepSpec(id="verify", needs=frozenset({"write"}))])
    assert plan.nodes["verify"].needs == {"write"}


def test_external_names_resolve_without_creating_an_edge() -> None:
    """An input port is available from the start; nothing produces it."""
    plan = build([spec("load", "infile")], available=["infile"])
    assert plan.nodes["load"].needs == frozenset()
    assert plan.roots() == ["load"]


def test_an_unknown_reference_is_a_validation_error() -> None:
    with pytest.raises(ValidationError) as caught:
        build([spec("report", "orders")])
    assert "nothing produces it" in str(caught.value)


def test_an_unknown_reference_suggests_a_near_name() -> None:
    with pytest.raises(ValidationError) as caught:
        build([spec("orders"), spec("report", "order")])
    assert "did you mean 'orders'?" in str(caught.value)


def test_duplicate_step_ids_are_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        build([spec("a"), spec("a")])
    assert "both produce" in str(caught.value)


def test_a_cycle_names_the_whole_loop() -> None:
    with pytest.raises(ValidationError) as caught:
        build([spec("a", "c"), spec("b", "a"), spec("c", "b")])
    message = str(caught.value)
    assert "->" in message
    assert message.count("->") >= 2


def test_a_self_reference_is_not_a_cycle() -> None:
    """A step reading its own name is reading its own output binding, not looping."""
    plan = build([spec("a", "a")])
    assert plan.nodes["a"].needs == frozenset()


def test_roots_and_leaves() -> None:
    plan = build([spec("a"), spec("b", "a"), spec("c", "a"), spec("d", "b c")])
    assert plan.roots() == ["a"]
    assert plan.leaves() == ["d"]


def test_readers_are_counted_for_refcounting() -> None:
    plan = build([spec("a"), spec("b", "a"), spec("c", "a")])
    assert plan.readers_of("a") == 2
    assert plan.readers_of("b") == 0


def test_the_critical_path_prefers_the_longest_chain() -> None:
    """`a` feeds a three-deep chain and a one-deep one; the chain must rank higher."""
    plan = build([spec("a"), spec("long1", "a"), spec("long2", "long1"), spec("short", "a")])
    assert plan.nodes["long1"].critical_path > plan.nodes["short"].critical_path


def test_weights_feed_the_critical_path() -> None:
    plan = build([spec("a"), spec("slow", "a", weight=10.0), spec("fast", "a", weight=1.0)])
    assert plan.nodes["slow"].critical_path > plan.nodes["fast"].critical_path


def test_topological_order_respects_dependencies() -> None:
    plan = build([spec("d", "b c"), spec("b", "a"), spec("c", "a"), spec("a")])
    order = plan.topological()
    assert order.index("a") < order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")


def test_topological_order_is_deterministic() -> None:
    steps = [spec("a"), spec("b", "a"), spec("c", "a"), spec("d", "b c")]
    assert build(steps).topological() == build(steps).topological()


def test_hosts_are_collected_for_per_host_limits() -> None:
    plan = build([spec("a", host="api.test"), spec("b", host="other.test"), spec("c")])
    assert plan.hosts() == ("api.test", "other.test")


def test_a_subgraph_drops_edges_to_pruned_nodes() -> None:
    plan = build([spec("a"), spec("b", "a"), spec("c", "b")])
    pruned = plan.subgraph(["b", "c"])
    assert set(pruned.nodes) == {"b", "c"}
    assert pruned.nodes["b"].needs == frozenset()
    assert pruned.roots() == ["b"]


def test_a_subgraph_rescores_critical_paths() -> None:
    plan = build([spec("a"), spec("b", "a"), spec("c", "b")])
    assert plan.subgraph(["b"]).nodes["b"].critical_path == 1.0
