"""IR to Plan: collect every reference, and hand the graph to the scheduler.

This is where invariant 3 becomes concrete. Every string in a step's configuration is
scanned for `@name` references, and their union with the declared `needs` is what the
DAG is built from. A step that reads `@orders` depends on `orders` whether or not
anybody wrote it down.
"""

from __future__ import annotations

from typing import Any

import httpx

from sclpl.expr.refs import refs_in_value
from sclpl.run.ir import (
    FnConfig,
    ForeachConfig,
    HttpConfig,
    IfConfig,
    Step,
    WhileConfig,
    WorkflowDoc,
)
from sclpl.run.plan import Plan, StepSpec, build

#: Rough cost of one step of each kind, for critical-path weighting. Only the ratios
#: matter: an HTTP request dominates a local expression by orders of magnitude, and
#: scheduling should reflect that before it has any measurements to go on.
WEIGHTS: dict[str, float] = {
    "http": 10.0,
    "fn": 2.0,
    "use": 10.0,
    "let": 0.1,
    "foreach": 5.0,
    "if": 0.1,
    "while": 5.0,
    "do_while": 5.0,
    "gate": 0.1,
    "parallel": 1.0,
}


def compile_plan(
    doc: WorkflowDoc,
    *,
    keep: set[str] | None = None,
    available: set[str] | None = None,
) -> Plan:
    """Build the executable graph for ``doc``, restricted to ``keep`` if given."""
    steps = [step for step in doc.all_steps() if keep is None or step.id in keep]
    external = set(available or set()) | set(doc.vars) | set(doc.rules)

    specs = [_spec(step, doc) for step in steps]
    return build(specs, available=external)


def _spec(step: Step, doc: WorkflowDoc) -> StepSpec:
    return StepSpec(
        id=step.id,
        reads=frozenset(references(step)),
        needs=frozenset(step.needs),
        tags=frozenset(step.tags),
        host=host_of(step),
        lane=step.lane,
        weight=WEIGHTS.get(step.kind, 1.0),
        produces=frozenset(child.id for child in step.children()),
    )


def references(step: Step) -> set[str]:
    """Every `@name` reachable in a step's configuration and its clauses.

    Nested bodies are deliberately excluded: a child step is its own node with its own
    references, and folding them into the parent would make the parent depend on things
    only the child needs.
    """
    found: set[str] = set()
    _scan(_config_without_bodies(step), found)
    for clause in (step.assert_, step.skip_if, step.retry_if):
        if clause:
            _scan(clause, found)
    return found


def _config_without_bodies(step: Step) -> Any:
    """The step's config with nested step lists removed."""
    match step.config:
        case ForeachConfig() as config:
            return {"over": config.over, "collect": config.collect}
        case WhileConfig() as config:
            return {"condition": config.condition}
        case IfConfig() as config:
            return {"condition": config.condition}
        case _:
            return step.config.model_dump()


def _scan(value: Any, found: set[str]) -> None:
    found.update(refs_in_value(value))


def host_of(step: Step) -> str | None:
    """The remote a step talks to, for per-host concurrency.

    A URL built from an interpolation has no host until the value is known. Guessing
    would put the step in the wrong bucket, so it goes in the unbucketed one and is
    governed by the global ceiling alone.
    """
    if not isinstance(step.config, HttpConfig):
        return None
    url = step.config.url
    if "{{" in url:
        prefix = url.split("{{", 1)[0]
        if "://" not in prefix:
            return None
        url = prefix
    try:
        return httpx.URL(url).host or None
    except (httpx.InvalidURL, ValueError):
        return None


def hosts(doc: WorkflowDoc) -> tuple[str, ...]:
    found = {host for host in (host_of(step) for step in doc.all_steps()) if host}
    return tuple(sorted(found))


def function_names(doc: WorkflowDoc) -> set[str]:
    """Every function or connector the workflow calls. Preflight checks they exist."""
    return {step.config.name for step in doc.all_steps() if isinstance(step.config, FnConfig)}
