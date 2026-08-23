"""Executing a step: resolve its config against the store, then do the work.

One dispatch on `kind`, one function per kind. The resolution of `{{...}}` and `@ref`
happens here, at the boundary between a workflow's text and a real call -- which is the
only place invariant 2 permits a value to become a string.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sclpl.expr import Context, evaluate, parse, parse_interpolated
from sclpl.expr.eval import _truthy
from sclpl.render.events import StepProgress
from sclpl.render.reporter import Reporter
from sclpl.run.errors import AssertionFailed, StepFailed, ValidationError
from sclpl.run.ir import (
    FnConfig,
    ForeachConfig,
    GateConfig,
    HttpConfig,
    IfConfig,
    LetConfig,
    ParallelConfig,
    Step,
    UseConfig,
    WhileConfig,
    WorkflowDoc,
)
from sclpl.run.plan import Node
from sclpl.run.retry import Retry
from sclpl.run.transport import Pool, decode
from sclpl.values.store import Frame, ValueStore

#: Marks a step the runner decided to skip. Distinct from `None`, which is a real
#: value a step can legitimately produce.
SKIPPED = object()


@dataclass(slots=True)
class Runtime:
    """Everything a step needs in order to run."""

    doc: WorkflowDoc
    store: ValueStore
    reporter: Reporter
    pool: Pool
    vars: dict[str, Any] = field(default_factory=dict)
    frame: Frame = field(default_factory=Frame)
    #: Values standing in for pruned producers, from the mode's `stub` block.
    stubs: dict[str, Any] = field(default_factory=dict)
    max_pages: int | None = None

    def context(self, frame: Frame | None = None) -> Context:
        return Context(
            store=self.store,
            frame=frame if frame is not None else self.frame,
            vars=self.vars,
        )


async def run_step(step: Step, node: Node, runtime: Runtime) -> Any:
    """Execute one step and return the value it produced."""
    if step.skip_if and await _condition(step.skip_if, runtime, step):
        return SKIPPED

    value = await _dispatch(step, node, runtime)

    if step.assert_:
        await _assert(step, value, runtime)
    return value


async def _dispatch(step: Step, node: Node, runtime: Runtime) -> Any:
    match step.config:
        case HttpConfig() as config:
            return await _http(step, config, node, runtime)
        case FnConfig() as config:
            return await _fn(step, config, runtime)
        case LetConfig() as config:
            return await _let(config, runtime)
        case IfConfig() as config:
            return await _if(config, runtime)
        case GateConfig():
            return None
        case ForeachConfig() | WhileConfig() | ParallelConfig() | UseConfig():
            # These expand into the graph in M6; until then the planner never emits
            # them as leaf work, so reaching here is a bug rather than a user error.
            raise StepFailed(
                f"step {step.id!r} is a {step.kind}, which needs the control-flow "
                "expansion that lands in M6"
            )
        case _:
            raise StepFailed(f"step {step.id!r} has an unsupported kind {step.kind!r}")


# -- kinds -----------------------------------------------------------------------


async def _http(step: Step, config: HttpConfig, node: Node, runtime: Runtime) -> Any:
    url = await _interpolate(config.url, runtime)
    if not isinstance(url, str) or "://" not in url:
        raise StepFailed(
            f"step {step.id!r} resolved to {url!r}, which is not an absolute URL",
            remedies=[
                f"the template was {config.url!r}",
                "check the values it interpolates are what you expect (-vv shows them)",
            ],
        )

    headers = {
        name: str(await _interpolate(value, runtime)) for name, value in config.headers.items()
    }
    query = {name: await _interpolate(value, runtime) for name, value in config.query.items()}
    body = await _resolve(config.body, runtime) if config.body is not None else None

    kwargs: dict[str, Any] = {}
    if headers:
        kwargs["headers"] = headers
    if query:
        kwargs["params"] = {key: _query_value(value) for key, value in query.items()}
    if body is not None:
        kwargs["json"] = body
    if config.timeout is not None:
        kwargs["timeout"] = config.timeout

    retry = Retry(max=step.retry.max, base_delay=step.retry.base_delay)
    attempt = await runtime.pool.request(
        config.method,
        url,
        reporter=runtime.reporter,
        step=step.id,
        retry=retry,
        **kwargs,
    )
    response = attempt.response
    result = {
        "status": response.status_code,
        "ok": 200 <= response.status_code < 300,
        "headers": dict(response.headers),
        "body": decode(response),
        "url": str(response.url),
        "elapsed_ms": attempt.duration_ms,
    }
    del node
    if config.extract:
        return await evaluate(
            parse(config.extract), Context(store=runtime.store, frame=Frame({"response": result}))
        )
    return result


def _query_value(value: Any) -> Any:
    """httpx wants scalars or lists of scalars; render anything else."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_query_value(item) for item in value]
    from sclpl.expr import stringify

    return stringify(value)


async def _fn(step: Step, config: FnConfig, runtime: Runtime) -> Any:
    from sclpl.expr import dispatch

    args = [await _resolve(arg, runtime) for arg in config.args]
    kwargs = {name: await _resolve(value, runtime) for name, value in config.kwargs.items()}
    if not dispatch.has(config.name):
        raise StepFailed(
            f"step {step.id!r} calls {config.name!r}, which is not registered",
            remedies=["run 'sclpl fn list' to see what is available"],
        )
    return await dispatch.apply(config.name, args, kwargs)


async def _let(config: LetConfig, runtime: Runtime) -> Any:
    if config.expr is not None:
        return await evaluate(parse(config.expr), runtime.context())
    return await _resolve(config.value, runtime)


async def _if(config: IfConfig, runtime: Runtime) -> Any:
    """Evaluate the condition; the branches themselves are graph nodes (M6)."""
    return await evaluate(parse(config.condition), runtime.context())


# -- resolution ------------------------------------------------------------------


async def _resolve(value: Any, runtime: Runtime) -> Any:
    """Resolve a config value, keeping its type (invariant 2).

    A string that is exactly one `{{expr}}` or `@ref` yields the typed value; a string
    with text around it is interpolated to a string, which is the boundary the
    invariant names.
    """
    if isinstance(value, str):
        return await _interpolate(value, runtime)
    if isinstance(value, dict):
        return {key: await _resolve(item, runtime) for key, item in value.items()}
    if isinstance(value, list):
        return [await _resolve(item, runtime) for item in value]
    return value


async def _interpolate(text: Any, runtime: Runtime) -> Any:
    if not isinstance(text, str):
        return text
    if "{{" not in text and not text.lstrip().startswith("@"):
        return text
    return await evaluate(parse_interpolated(text), runtime.context())


async def _condition(clause: str, runtime: Runtime, step: Step) -> bool:
    expression = runtime.doc.rules.get(clause, clause)
    try:
        return _truthy(await evaluate(parse(expression), runtime.context()))
    except ValidationError as error:
        raise StepFailed(
            f"step {step.id!r}: {error.diagnostic.message}",
            where=error.diagnostic.where,
            remedies=error.diagnostic.remedies,
        ) from error


async def _assert(step: Step, value: Any, runtime: Runtime) -> None:
    """Check a step's assertion against what it produced.

    The output is in scope twice: as `result`, and under the step's own name. The
    binding is not in the store yet -- it lands after the assertion passes -- so
    without this `assert @fetch.status == 200` inside `fetch` would fail with "nothing
    produces @fetch", which is both true and useless. Both spellings work because both
    are natural: `result` when the rule is shared, the step's name when it is not.
    """
    clause = step.assert_ or ""
    expression = runtime.doc.rules.get(clause, clause)
    frame = runtime.frame.child(result=value, **{step.id: value})
    outcome = await evaluate(parse(expression), runtime.context(frame))
    if not _truthy(outcome):
        named = f" ({clause})" if clause in runtime.doc.rules else ""
        raise AssertionFailed(
            f"step {step.id!r} failed its assertion{named}",
            where=expression,
            remedies=[
                f"it evaluated to {outcome!r}",
                "run with -vv to see the values it was checking",
            ],
        )


def report_progress(
    runtime: Runtime, step_id: str, detail: str, current: int, total: int | None
) -> None:
    runtime.reporter.emit(StepProgress(id=step_id, detail=detail, current=current, total=total))
