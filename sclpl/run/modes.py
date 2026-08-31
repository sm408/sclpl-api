"""Mode resolution: extends chains, selectors, pruning, and the closure check.

Invariant 6: a mode may only **subtract steps and override scalars**. It can never add
a step, change a dependency, or alter an expression. That is enforced structurally --
the resolved set is always a subset of the declared steps, and nothing here touches a
step's config.

The closure check is the part that earns its keep. Pruning a step whose output another
kept step still reads is the mistake people actually make, and discovering it at
validate time with the three ways to fix it beats discovering it forty seconds into a
run with an unresolvable reference.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Any

from sclpl.errors import ValidationError, did_you_mean
from sclpl.run.ir import ModeSpec, WorkflowDoc

#: A selector prefixed with this matches every step carrying the tag.
TAG_PREFIX = "tag:"


@dataclass(slots=True)
class Resolved:
    """The outcome of resolving a mode against a workflow."""

    name: str | None
    keep: set[str] = field(default_factory=set)
    pruned: set[str] = field(default_factory=set)
    vars: dict[str, Any] = field(default_factory=dict)
    limits: dict[str, Any] = field(default_factory=dict)
    stubs: dict[str, Any] = field(default_factory=dict)

    @property
    def is_full(self) -> bool:
        return not self.pruned


def resolve(
    doc: WorkflowDoc,
    mode: str | None,
    *,
    available: set[str] | None = None,
) -> Resolved:
    """Resolve ``mode`` into the set of steps to run.

    ``available`` names values that will exist without a step producing them -- bound
    input ports, and cache entries under `--from-cache`. They satisfy the closure check
    the same way a kept producer does.
    """
    if mode is None:
        mode = doc.default_mode
    if mode is None:
        every = {step.id for step in doc.all_steps()}
        return Resolved(name=None, keep=every)

    spec = _lookup(doc, mode)
    chain = _chain(doc, mode)
    merged = _merge(chain)

    all_ids = [step.id for step in doc.all_steps()]
    keep = _select(doc, merged, all_ids)
    pruned = set(all_ids) - keep

    resolved = Resolved(
        name=mode,
        keep=keep,
        pruned=pruned,
        vars=dict(merged.vars),
        limits=dict(merged.limit),
        stubs=dict(merged.stub),
    )
    _check_closure(doc, resolved, available or set())
    _check_subgraph(doc, resolved)
    del spec
    return resolved


def _lookup(doc: WorkflowDoc, mode: str) -> ModeSpec:
    found = doc.modes.get(mode)
    if found is None:
        remedies = []
        suggestion = did_you_mean(mode, list(doc.modes))
        if suggestion:
            remedies.append(suggestion)
        remedies.append(
            f"declared modes: {', '.join(sorted(doc.modes))}" if doc.modes else "no modes declared"
        )
        raise ValidationError(f"{doc.name} has no mode {mode!r}", remedies=remedies)
    return found


def _chain(doc: WorkflowDoc, mode: str) -> list[ModeSpec]:
    """The extends chain, deepest ancestor first."""
    chain: list[ModeSpec] = []
    seen: list[str] = []
    current: str | None = mode
    while current is not None:
        if current in seen:
            loop = " -> ".join([*seen[seen.index(current) :], current])
            raise ValidationError(
                f"modes extend each other in a loop: {loop}",
                remedies=["break the loop by removing one `extends`"],
            )
        seen.append(current)
        spec = _lookup(doc, current)
        chain.append(spec)
        current = spec.extends
    chain.reverse()
    return chain


def _merge(chain: list[ModeSpec]) -> ModeSpec:
    """Flatten the chain. Later specs override earlier scalars and extend the lists."""
    merged = ModeSpec()
    for spec in chain:
        merged.all = merged.all or spec.all
        merged.include = [*merged.include, *spec.include]
        merged.exclude = [*merged.exclude, *spec.exclude]
        merged.vars = {**merged.vars, **spec.vars}
        merged.limit = {**merged.limit, **spec.limit}
        merged.stub = {**merged.stub, **spec.stub}
        if spec.description:
            merged.description = spec.description
    return merged


def _select(doc: WorkflowDoc, spec: ModeSpec, all_ids: list[str]) -> set[str]:
    """Apply `all`, then `include`, then subtract `exclude`."""
    if spec.all or not spec.include:
        keep = set(all_ids)
    else:
        keep = set()
        for selector in spec.include:
            matched = _match(doc, selector, all_ids)
            if not matched:
                raise _no_match(doc, selector, all_ids, "include")
            keep |= matched

    for selector in spec.exclude:
        matched = _match(doc, selector, all_ids)
        if not matched:
            raise _no_match(doc, selector, all_ids, "exclude")
        keep -= matched
    return keep


def _match(doc: WorkflowDoc, selector: str, all_ids: list[str]) -> set[str]:
    """One selector: an exact id, a glob, or `tag:name`."""
    if selector.startswith(TAG_PREFIX):
        wanted = selector[len(TAG_PREFIX) :]
        return {step.id for step in doc.all_steps() if wanted in step.tags}
    if any(char in selector for char in "*?["):
        return {step_id for step_id in all_ids if fnmatch.fnmatchcase(step_id, selector)}
    return {selector} if selector in all_ids else set()


def _no_match(doc: WorkflowDoc, selector: str, all_ids: list[str], clause: str) -> ValidationError:
    """A selector matching nothing is a typo, not an empty set.

    Treating it as "select nothing" would silently run the wrong subset, which is the
    failure this whole check exists to prevent.
    """
    remedies = []
    if selector.startswith(TAG_PREFIX):
        tags = sorted({tag for step in doc.all_steps() for tag in step.tags})
        suggestion = did_you_mean(selector[len(TAG_PREFIX) :], tags)
        if suggestion:
            remedies.append(suggestion)
        remedies.append(f"tags in use: {', '.join(tags) or 'none'}")
    else:
        suggestion = did_you_mean(selector, all_ids)
        if suggestion:
            remedies.append(suggestion)
        remedies.append(f"steps: {', '.join(all_ids[:8])}")
    return ValidationError(f"{clause} selector {selector!r} matches no step", remedies=remedies)


def _check_closure(doc: WorkflowDoc, resolved: Resolved, available: set[str]) -> None:
    """Every kept step's dependencies must be satisfiable.

    The three remedies are the three real ways out, and naming them is the point: bind
    it as an input, read it from cache, or stub it.
    """
    produced = resolved.keep | available | set(resolved.stubs) | set(doc.vars)

    for step in doc.all_steps():
        if step.id not in resolved.keep:
            continue
        for reference in _references(step):
            if reference in produced:
                continue
            owner = doc.step(reference)
            if owner is None:
                # Not a step at all -- `plan.build` reports unknown references, with
                # better context than we have here.
                continue
            raise ValidationError(
                f"mode {resolved.name!r} prunes {reference!r}, but {step.id!r} still reads it",
                remedies=[
                    f"keep it: add {reference!r} to the mode's include list",
                    f"bind it: declare an input port named {reference!r}",
                    f"stub it: stub {reference}=… in the mode",
                ],
            )


def _references(step: Any) -> set[str]:
    """Every `@name` anywhere in a step's configuration and its clauses."""
    from sclpl.expr.refs import refs_in, refs_in_value

    found: set[str] = set(refs_in_value(step.config))
    for clause in (step.assert_, step.skip_if, step.retry_if):
        if clause:
            found.update(refs_in(clause))
    found.update(step.needs)
    return found


def _check_subgraph(doc: WorkflowDoc, resolved: Resolved) -> None:
    """Invariant 6, checked rather than assumed: the mode only removed things."""
    declared = {step.id for step in doc.all_steps()}
    added = resolved.keep - declared
    if added:
        raise ValidationError(
            f"mode {resolved.name!r} would add steps that are not in the workflow: "
            f"{', '.join(sorted(added))}",
            remedies=["modes may only subtract steps and override scalars"],
        )
