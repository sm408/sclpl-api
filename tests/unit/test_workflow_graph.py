"""Mermaid graph output follows the already-validated execution plan."""

from sclpl.cli.workflow_cmd import _mermaid
from sclpl.run.plan import Node, Plan


def test_mermaid_graph_uses_stable_node_and_edge_order() -> None:
    plan = Plan(
        nodes={
            "first": Node("first", dependents=frozenset({"second"})),
            "second": Node("second", needs=frozenset({"first"})),
        },
        order=["first", "second"],
    )
    assert _mermaid(plan) == 'graph TD\n  first["first"]\n  second["second"]\n  first --> second'
