"""Executing a step: resolve its config against the store, then do the work.

One dispatch on `kind`, one function per kind. The resolution of `{{...}}` and `@ref`
happens here, at the boundary between a workflow's text and a real call -- which is the
only place invariant 2 permits a value to become a string.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from sclpl.errors import AssertionFailed, SclplError, StepFailed, ValidationError
from sclpl.expr import Context, evaluate, parse, parse_interpolated
from sclpl.expr.eval import _truthy
from sclpl.project import auth as auth_mod
from sclpl.project.auth import Profile as AuthProfile
from sclpl.render.events import StepProgress
from sclpl.render.reporter import Reporter
from sclpl.run import checkpoints as checkpoints_mod
from sclpl.run import control, lanes, paginate
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
from sclpl.run.publication import Ledger
from sclpl.run.retry import RETRY_STATUSES, Retry
from sclpl.run.schedule import ExpandSpec
from sclpl.run.transport import Pool, decode
from sclpl.tables.io import STDIO
from sclpl.values import cache as cache_mod
from sclpl.values.digest import digest as digest_of
from sclpl.values.store import Frame, ValueStore

#: Marks a step the runner decided to skip. Distinct from `None`, which is a real
#: value a step can legitimately produce.
SKIPPED = object()


@dataclass(slots=True)
class StepMetrics:
    """F1: what a step actually cost, accumulated as it runs.

    Not an event -- events are fired and forgotten. This is read back once, after
    the whole run finishes, to fill in the history row (`state/db.py`'s
    `StepRecord`), which is why it lives on `Runtime` rather than being emitted.
    """

    #: Every HTTP attempt this step made, summed across every request it issued --
    #: more than one for a paginated step, and more than one attempt per request
    #: for anything the transport retried.
    attempts: int = 0
    bytes_in: int = 0
    bytes_out: int = 0
    #: Whether this step's value came back from the cache without a request.
    cache_hit: bool = False


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
    #: Output port name -> the path bound to it. A step declaring `-> port` writes
    #: there without the path appearing in the workflow.
    outputs: dict[str, str] = field(default_factory=dict)
    max_pages: int | None = None
    #: Nodes the run grew for itself -- loop iterations, taken branches -- and the scope
    #: each one runs in. Populated by the control-flow kinds, read by the runner.
    injected: dict[str, control.Injected] = field(default_factory=dict)
    #: Where results are reused from, when the policy allows it. None disables it.
    cache: cache_mod.Cache | None = None
    #: Thread and process pools, for the steps that should not run on the loop.
    pools: lanes.Pools = field(default_factory=lanes.Pools)
    #: How a running step adds nodes beneath itself. Supplied by the scheduler.
    expand: Callable[[str, list[ExpandSpec], tuple[str, int] | None], None] | None = None
    #: Iteration key -> the node holding that iteration's result, per control step.
    results: dict[str, dict[str, str]] = field(default_factory=dict)
    #: Loops that finished without expanding, and what they produced instead.
    settled: dict[str, Any] = field(default_factory=dict)
    #: How many times each `while` has gone round, so `max_iterations` can be enforced.
    iterations: dict[str, int] = field(default_factory=dict)
    #: Barrier node -> how to turn its copies' values into the control step's own.
    joins: dict[str, str] = field(default_factory=dict)
    #: Injected node -> what that copy contributed, once `collect` has had its say.
    produced: dict[str, Any] = field(default_factory=dict)
    #: Named auth profiles from the project manifest, by name. Empty outside a project.
    auth_profiles: dict[str, AuthProfile] = field(default_factory=dict)
    #: Node -> a past-TTL cache entry `--http-cache` may revalidate instead of an
    #: outright refetch. Consumed (popped) by `_http` for that one node.
    pending_revalidation: dict[str, cache_mod.Entry] = field(default_factory=dict)
    #: Node -> the ETag/Last-Modified pair its response carried, for `run_step` to
    #: store alongside the value once the step returns.
    cache_validators: dict[str, tuple[str | None, str | None]] = field(default_factory=dict)
    #: E8: set only under `[outputs] publish = "validated"`. A writer stages into
    #: this instead of its real destination; `None` is the pre-existing, unchanged
    #: immediate-write path.
    publication: Ledger | None = None
    #: F1: step id -> what it cost. Keyed by the step's own id, not the graph node
    #: id, since a loop's iterations are one step for this purpose.
    metrics: dict[str, StepMetrics] = field(default_factory=dict)
    #: F5: every paginated step's own `completeness.status` ("complete"/"partial"/
    #: "unknown"), one entry per step that actually paginated. Aggregated into the
    #: run's overall completeness once the run finishes (`runner._completeness_of`).
    completeness: list[str] = field(default_factory=list)
    #: G2: graph node id -> the cache key it resolved to, for every step that had
    #: one. Persisted alongside the step's history row so a later resume can
    #: recompute the same key for a candidate run and compare, instead of guessing
    #: from the step's declared config alone.
    identity_keys: dict[str, str] = field(default_factory=dict)
    #: G3: where this run's own eligible step values are durably checkpointed, so a
    #: *later* run can resume from them. `None` disables it (`--no-record`, or a
    #: caller with nothing to resume into) -- a checkpoint with no history row
    #: naming its run is never reachable by a future `plan_resume` anyway.
    checkpoint_store: checkpoints_mod.Store | None = None
    #: G3: this run's own id, as it will appear in history -- what a checkpoint is
    #: filed under. Set together with `checkpoint_store`; one implies the other.
    run_id: str = ""

    def metric(self, step_id: str) -> StepMetrics:
        return self.metrics.setdefault(step_id, StepMetrics())

    def context(self, frame: Frame | None = None) -> Context:
        return Context(
            store=self.store,
            frame=frame if frame is not None else self.frame,
            vars=self.vars,
        )


async def run_step(step: Step, node: Node, runtime: Runtime, *, node_id: str = "") -> Any:
    """Execute one step and return the value it produced.

    ``node_id`` is the graph name, which differs from the step id for anything the run
    grew for itself -- a loop body copy, or a `while`'s continuation. Control flow needs
    the graph name, because that is what it expands beneath.
    """
    if step.skip_if and await _condition(step.skip_if, runtime, step):
        return SKIPPED

    effective_id = node_id or node.id
    key = await _cache_key(step, runtime)
    if key is not None:
        runtime.identity_keys[effective_id] = key
        hit = runtime.cache.get(key) if runtime.cache else None
        if hit is not None and hit.fresh:
            runtime.reporter.emit(StepProgress(id=step.id, detail="cached", current=1))
            runtime.metric(effective_id).cache_hit = True
            if step.assert_:
                # Still checked. A cached value that no longer satisfies an assertion is
                # exactly the case the assertion exists for.
                await _assert(step, hit.value, runtime)
            _checkpoint(runtime, effective_id, hit.value)
            return hit.value
        if hit is not None and not hit.fresh:
            # Past its TTL, but `--http-cache` allows checking with the server before
            # refetching outright. `_http` consumes this to send a conditional
            # request; a non-HTTP step ignores it (nothing pops it, so it is dropped
            # with the rest of this run's transient state).
            runtime.pending_revalidation[effective_id] = hit
        elif runtime.cache is not None and runtime.cache.policy.require_hit:
            raise cache_mod.Missing(step.id)

    value = await _dispatch(step, node, runtime, effective_id)

    if step.assert_:
        await _assert(step, value, runtime)
    if key is not None and runtime.cache is not None and value is not SKIPPED:
        etag, modified = runtime.cache_validators.pop(effective_id, (None, None))
        runtime.cache.put(
            key, value, ttl=step.cache.ttl, step=step.id, etag=etag, modified=modified
        )
    if key is not None and value is not SKIPPED:
        _checkpoint(runtime, effective_id, value)
    return value


def _checkpoint(runtime: Runtime, effective_id: str, value: Any) -> None:
    """G3: durably file ``value`` under this run's own id, for a *later* resume.

    A no-op without both a store and a run id -- `--no-record`, or a caller (a
    test, `call`) with no history row for a future resume to ever find this
    checkpoint by. `Store.write` itself is the other half of "eligible": an
    unsupported shape (neither `Table` nor JSON) simply is not filed.
    """
    if runtime.checkpoint_store is None or not runtime.run_id:
        return
    runtime.checkpoint_store.write(runtime.run_id, effective_id, value)


async def _cache_key(step: Step, runtime: Runtime) -> str | None:
    """The cache key for this step, or None when it is not cacheable.

    Three things are never cached. **Control flow** produces a graph, not a value, and a
    cached loop would skip the work its own body was the point of. **Writers** have an
    effect the cache cannot reproduce -- a hit would report a file it did not write. And
    anything a step turned off with `cache off`.
    """
    if runtime.cache is None or not runtime.cache.policy.enabled or not step.cache.enabled:
        return None
    if step.kind not in ("http", "fn"):
        return None

    match step.config:
        case HttpConfig() as config:
            if config.stream_to is not None:
                # A writer, like `save`/`read`: a hit would report a file this run
                # never actually wrote, and disk state is not assumed to persist the
                # way a remote response body is.
                return None
            url = await _interpolate(config.url, runtime)
            query = {
                name: await _interpolate(value, runtime) for name, value in config.query.items()
            }
            headers = {
                name: str(await _interpolate(value, runtime))
                for name, value in config.headers.items()
            }
            body = await _resolve(config.body, runtime) if config.body is not None else None
            return cache_mod.key_for(
                step_kind="http",
                method=config.method,
                url=str(url),
                query=query,
                body=body,
                headers=headers,
                credential=config.auth,
                paginate=config.paginate.model_dump() if config.paginate is not None else None,
            )
        case FnConfig() as config:
            if _touches_a_file(config.name):
                return None
            entry = _registered(config.name)
            args = [await _resolve(value, runtime) for value in config.args]
            kwargs = {name: await _resolve(value, runtime) for name, value in config.kwargs.items()}
            return cache_mod.key_for(
                step_kind="fn",
                function=config.name,
                function_version=entry.version if entry else 1,
                inputs=[digest_of(value) for value in (*args, *kwargs.values())],
            )
        case _:
            return None


#: Functions whose answer depends on something the cache key cannot see, or whose point
#: is an effect the cache cannot reproduce.
_UNCACHEABLE = ("save", "read", "glob_read", "convert")


def _touches_a_file(name: str) -> bool:
    """Whether this function's answer depends on the filesystem.

    Two different reasons, one rule. A **writer** has an effect a hit cannot reproduce:
    it would report a path it did not write to. A **reader** is keyed on its path, and a
    path is not its contents -- caching it would serve yesterday's file from today's
    name, which is the worst kind of wrong because it looks right.

    Keying a reader on mtime and size would fix that, but a local file read is neither
    slow nor rate-limited, and the cache exists for things that are.
    """
    return name.startswith(_UNCACHEABLE)


async def _dispatch(step: Step, node: Node, runtime: Runtime, node_id: str) -> Any:
    match step.config:
        case HttpConfig() as config:
            return await _http(step, config, node, runtime, node_id)
        case FnConfig() as config:
            return await _fn(step, config, runtime)
        case LetConfig() as config:
            return await _let(config, runtime)
        case IfConfig() as config:
            return await _if(node_id, step, config, runtime)
        case ForeachConfig() as config:
            return await _foreach(node_id, step, config, runtime)
        case WhileConfig() as config:
            return await _while(node_id, step, config, runtime)
        case ParallelConfig() as config:
            return await _parallel(node_id, step, config, runtime)
        case GateConfig() as config:
            # A barrier does nothing. Its value is that everything before it is in the
            # store by the time anything after it starts, which the graph already
            # guarantees -- the step exists so the author can say where that matters.
            return control.gate_reason(config)
        case UseConfig():
            raise StepFailed(
                f"step {step.id!r} calls another workflow, which is not implemented in this build",
                remedies=["inline the steps for now, or run the two workflows in sequence"],
            )
        case _:
            raise StepFailed(f"step {step.id!r} has an unsupported kind {step.kind!r}")


# -- kinds -----------------------------------------------------------------------


async def _apply_auth(
    step: Step,
    config: HttpConfig,
    url: str,
    headers: dict[str, str],
    query: dict[str, Any],
    body: Any,
    runtime: Runtime,
) -> AuthProfile | None:
    """Resolve `auth <name>` into ``headers``/``query``, mutated in place.

    Refuses rather than silently overwriting when a step also sets the header its own
    auth profile would write: a step that both names `auth bearer` and hand-writes
    `header Authorization: ...` has two ideas about what the request should carry, and
    picking one quietly would hide the other author's intent.
    """
    if config.auth is None:
        return None
    profile = runtime.auth_profiles.get(config.auth)
    if profile is None:
        from sclpl.errors import did_you_mean

        suggestion = did_you_mean(config.auth, runtime.auth_profiles)
        raise ValidationError(
            f"step {step.id!r} uses auth {config.auth!r}, which is not defined",
            remedies=[suggestion]
            if suggestion
            else ["declare it under [auth.<name>] in sclpl.toml"],
        )
    conflict = profile.target_header()
    if conflict and conflict in headers:
        raise ValidationError(
            f"step {step.id!r} sets {conflict!r} itself and also uses auth {config.auth!r}",
            remedies=["remove the manual header, or drop `auth` and keep the header"],
        )
    applied = await auth_mod.apply(profile, method=config.method, url=url, query=query, body=body)
    headers.update(applied.headers)
    query.update(applied.query)
    return profile


async def _http(step: Step, config: HttpConfig, node: Node, runtime: Runtime, node_id: str) -> Any:
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
    proxy = str(await _interpolate(config.proxy, runtime)) if config.proxy else None

    auth_profile = await _apply_auth(step, config, url, headers, query, body, runtime)

    # D3: revalidation is scoped to a single, non-paginated, non-extracted,
    # non-streamed request. A paginated step's cached value is already a merge
    # across pages with no per-page validators tracked; an `extract`ing step's
    # cached value is whatever expression it computed; a streamed step never holds
    # a body to reconstruct at all. All three are refetched outright, as they were
    # before D3.
    revalidatable = config.paginate is None and config.extract is None and config.stream_to is None
    stale = runtime.pending_revalidation.pop(node_id, None) if revalidatable else None
    if stale is not None:
        if stale.etag:
            headers.setdefault("If-None-Match", stale.etag)
        if stale.modified:
            headers.setdefault("If-Modified-Since", stale.modified)

    kwargs: dict[str, Any] = {}
    if headers:
        kwargs["headers"] = headers
    if query:
        kwargs["params"] = {key: _query_value(value) for key, value in query.items()}
    if body is not None:
        kwargs["json"] = body
    if config.timeout is not None:
        kwargs["timeout"] = config.timeout

    retry = Retry(
        max=step.retry.max,
        base_delay=step.retry.base_delay,
        max_delay=step.retry.max_delay,
        statuses=RETRY_STATUSES | frozenset(step.retry.on),
        idempotent=step.retry.idempotent,
    )

    if config.stream_to is not None:
        # D4: a step's value is normally the decoded body; a streamed one is the
        # metadata a caller needs to trust what landed on disk, since the body
        # itself was never held anywhere the workflow could inspect it.
        destination = Path(str(await _interpolate(config.stream_to, runtime)))
        streamed = await runtime.pool.stream_to_file(
            config.method,
            url,
            destination,
            reporter=runtime.reporter,
            step=step.id,
            retry=retry,
            auth=config.auth or "",
            proxy=proxy,
            verify=config.verify,
            **kwargs,
        )
        metric = runtime.metric(node_id)
        metric.attempts += streamed.attempts
        metric.bytes_in += streamed.bytes_written
        return {
            "status": streamed.status,
            "ok": 200 <= streamed.status < 300,
            "headers": streamed.headers,
            "path": str(streamed.path),
            "bytes": streamed.bytes_written,
            "sha256": streamed.sha256,
            "url": streamed.url,
            "elapsed_ms": streamed.duration_ms,
        }

    async def fetch(
        extra_query: dict[str, Any],
        extra_headers: dict[str, str],
        override: str | None,
        *,
        _retried_auth: bool = False,
    ) -> paginate.Page:
        """One request. The paginator supplies what differs between pages."""
        call = dict(kwargs)
        if extra_query:
            merged = {**query, **extra_query}
            call["params"] = {key: _query_value(value) for key, value in merged.items()}
        if extra_headers:
            call["headers"] = {**call.get("headers", {}), **extra_headers}
        attempt = await runtime.pool.request(
            config.method,
            override or url,
            reporter=runtime.reporter,
            step=step.id,
            retry=retry,
            auth=config.auth or "",
            proxy=proxy,
            verify=config.verify,
            **call,
        )
        response = attempt.response
        metric = runtime.metric(node_id)
        metric.attempts += attempt.attempts
        # `response.content` is always safely readable here (httpx has already read
        # the body by the time a non-streaming request returns); `request.content`
        # is not -- a GET's body stream is never marked read, and touching it raises
        # `RequestNotRead`. Bytes sent is a smaller, riskier claim than bytes
        # received, so this only counts the direction that is actually safe to ask.
        metric.bytes_in += len(response.content)
        if (
            response.status_code == 401
            and not _retried_auth
            and auth_profile is not None
            and auth_profile.kind == "oauth2_client_credentials"
        ):
            # A bounded refresh, exactly once: the endpoint rejected the token this
            # profile cached, so the cache is stale (or was always wrong) rather than
            # the request being transiently bad. Looping here would just hide a
            # misconfigured client behind a hang.
            from sclpl.project import oauth

            oauth.invalidate(auth_profile)
            refreshed = await auth_mod.apply(auth_profile, method=config.method, url=url)
            kwargs["headers"] = {**kwargs.get("headers", {}), **refreshed.headers}
            return await fetch(extra_query, extra_headers, override, _retried_auth=True)

        if stale is not None and response.status_code == 304:
            # Confirmed unchanged: the body never has one on a 304, so the value this
            # step produces is the one already on disk, not `decode(response)`. A
            # server is allowed to refresh the validators on a 304 even though the
            # body did not change, so prefer whichever it sent this time.
            if runtime.cache is not None:
                runtime.cache.stats.hits += 1
            runtime.cache_validators[node_id] = (
                response.headers.get("etag", stale.etag),
                response.headers.get("last-modified", stale.modified),
            )
            cached = stale.value
            return paginate.Page(
                body=cached["body"],
                status=cached["status"],
                headers=cached["headers"],
                url=cached["url"],
                elapsed_ms=attempt.duration_ms,
            )

        if runtime.cache is not None and revalidatable:
            runtime.cache_validators[node_id] = (
                response.headers.get("etag"),
                response.headers.get("last-modified"),
            )
        return paginate.Page(
            body=decode(response),
            status=response.status_code,
            headers=dict(response.headers),
            url=str(response.url),
            elapsed_ms=attempt.duration_ms,
        )

    del node
    if config.paginate is None:
        page = await fetch({}, {}, None)
        result = _response(page)
    else:
        result = await _paginated(step, config, fetch, runtime)

    if config.extract:
        return await evaluate(
            parse(config.extract), Context(store=runtime.store, frame=Frame({"response": result}))
        )
    return result


def _response(page: paginate.Page, *, pages: int = 1, truncated: bool = False) -> dict[str, Any]:
    """The shape a step's HTTP result always has, paginated or not.

    One page or forty, `@fetch.status` and `@fetch.body` mean the same thing. The two
    extra fields only appear when paging happened, so an unpaginated step's result is
    byte-for-byte what it was before.
    """
    result: dict[str, Any] = {
        "status": page.status,
        "ok": 200 <= page.status < 300,
        "headers": page.headers,
        "body": page.body,
        "url": page.url,
        "elapsed_ms": page.elapsed_ms,
    }
    if pages != 1 or truncated:
        result["pages"] = pages
        result["truncated"] = truncated
    return result


async def _paginated(
    step: Step, config: HttpConfig, fetch: paginate.Fetch, runtime: Runtime
) -> dict[str, Any]:
    """Follow a paginated source and present the whole of it as one result."""
    assert config.paginate is not None
    spec = config.paginate

    ignored = paginate.unsupported_concurrency(spec)
    if ignored:
        runtime.reporter.log("warning", ignored, step.id)

    async def stop(page: paginate.Page) -> bool:
        if not spec.stop_when:
            return False
        frame = Frame({"response": _response(page), "page": page.body})
        return _truthy(await evaluate(parse(spec.stop_when), runtime.context(frame)))

    def announce(number: int, page: paginate.Page) -> None:
        runtime.reporter.emit(
            StepProgress(
                id=step.id,
                detail="pages",
                current=number,
                total=spec.max_pages if spec.max_pages is not None else runtime.max_pages,
            )
        )

    followed = await paginate.follow(
        spec,
        fetch,
        stop_when=stop if spec.stop_when else None,
        max_pages=runtime.max_pages,
        on_page=announce,
    )

    status = followed.completeness
    runtime.completeness.append(status)
    if status == "partial":
        runtime.reporter.log(
            "warning",
            f"partial: stopped at {followed.count} pages ({followed.reason})",
            step.id,
        )
    elif status == "unknown":
        runtime.reporter.log(
            "info",
            f"unknown: stopped at {followed.count} pages ({followed.reason})",
            step.id,
        )

    last = followed.pages[-1]
    result = _response(last, pages=followed.count, truncated=followed.truncated)
    result["body"] = paginate.merge(followed.pages, spec.into, _extract_path)
    # D7: what this extraction actually covers, distinct from whether it succeeded.
    # Never a claim about the source's real total -- only about this run's own
    # declared scope and what it actually received.
    result["completeness"] = {
        "status": status,
        "reason": followed.reason,
        "pages": followed.count,
        "items_received": followed.items_received,
    }
    return result


def _extract_path(body: Any, path: str) -> Any:
    """Where the items are in one page's body.

    A plain dotted path rather than the expression language: `into` names a location,
    and a page that does not have it has no items rather than an error -- the last page
    of a source that stops sending the key is normal.
    """
    return paginate.dig(body, path.lstrip("@").lstrip("."))


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
    args, kwargs = _bind_output(step, args, kwargs, runtime)
    try:
        return await _in_lane(step, config, args, kwargs, runtime)
    except SclplError:
        # Already carries a message and remedies aimed at the workflow author.
        raise
    except Exception as error:
        # Anything else came out of the function's own internals, where the exception
        # text names Python rather than the workflow. Say which step and which call, so
        # the reader has somewhere to look.
        raise StepFailed(
            f"step {step.id!r} failed inside {config.name}(): {type(error).__name__}: {error}",
            remedies=[f"check what {config.name}() was given -- -vv shows the resolved arguments"],
        ) from error


async def _in_lane(
    step: Step,
    config: FnConfig,
    args: list[Any],
    kwargs: dict[str, Any],
    runtime: Runtime,
) -> Any:
    """Run the call where it belongs: the loop, a thread, or a process.

    The lane is chosen from what the function *is* and how big its arguments are, not
    from what it is called. A `join` over ten rows and a `join` over a hundred thousand
    are the same function and want different places to run.

    A dispatch entry that is not a plain callable -- an operator with overloads -- stays
    on the loop: `dispatch.apply` resolves it, and resolution is not something to send to
    another process.
    """
    from sclpl.expr import dispatch

    entry = _registered(config.name)
    if entry is None:
        return await dispatch.apply(config.name, args, kwargs)

    lane = lanes.assign(step.lane, is_async=entry.is_async, args=args, kwargs=kwargs)
    if lane == "async":
        return await dispatch.apply(config.name, args, kwargs)

    runtime.reporter.emit(StepProgress(id=step.id, detail=lane, current=1))
    try:
        return await lanes.call(lane, runtime.pools, entry.call, *args, **kwargs)
    except lanes.LaneFallback as reason:
        # The lane is an optimisation. Losing the run to save it would be the wrong
        # trade, so the work goes to a thread and the reason is said out loud.
        runtime.reporter.log("debug", f"{step.id}: {lane} lane unavailable ({reason})", step.id)
        return await lanes.call("thread", runtime.pools, entry.call, *args, **kwargs)


def _registered(name: str) -> Any:
    """The catalogue entry for ``name``, if it is one. None for a bare operator."""
    from sclpl.ext.functions import REGISTRY

    entry = REGISTRY.get(name)
    return entry if entry is not None and callable(entry.call) else None


def _bind_output(
    step: Step, args: list[Any], kwargs: dict[str, Any], runtime: Runtime
) -> tuple[list[Any], dict[str, Any]]:
    """Supply the path from the output port a step declares with `-> port`.

    A workflow says what it writes, the caller says where. `save_csv @rows -> report`
    with no path takes it from the binding; a path written in the step still wins, so
    naming a port never silently redirects a file someone spelled out.
    """
    if not step.writes:
        return args, kwargs
    path = runtime.outputs.get(step.writes)
    if path is None:
        raise StepFailed(
            f"step {step.id!r} writes to the port {step.writes!r}, which is not bound",
            remedies=[f"give it a file: --out {step.writes}=<path>"],
        )
    if "path" in kwargs or len(args) >= 2:
        return args, kwargs
    if runtime.publication is not None and path != STDIO:
        # Validated stdout publication needs spooling under a size limit, not a
        # scratch file next to a destination that does not exist -- out of scope
        # for this slice (SPEC 3.5's "stdout spooling limits"); stdout stays
        # immediate even when the project's other outputs are staged.
        path = str(runtime.publication.stage(step.writes, Path(path)))
    return [*args, path], kwargs


async def _let(config: LetConfig, runtime: Runtime) -> Any:
    """Bind the value of an expression.

    A `let` whose expression is a quoted string containing `{{...}}` is a template, not
    a literal. The expression parser is right to read `"a {{b}}"` as a string -- that is
    what it is -- but a step that produced the characters `{{@total}}` would be the
    exact failure the rewrite exists to remove, so the two-step reading happens here:
    evaluate, and if the answer is a string still carrying an interpolation, fill it in.
    """
    if config.expr is None:
        return await _resolve(config.value, runtime)

    value = await evaluate(parse(config.expr), runtime.context())
    if isinstance(value, str) and "{{" in value:
        return await evaluate(parse_interpolated(value), runtime.context())
    return value


async def _if(node: str, step: Step, config: IfConfig, runtime: Runtime) -> Any:
    """Take one branch. The steps in it become nodes; the other branch's never exist."""
    taken = _truthy(await evaluate(parse(config.condition), runtime.context()))
    return _grow(node, control.expand_branch(step, config, taken, runtime), runtime)


async def _foreach(node: str, step: Step, config: ForeachConfig, runtime: Runtime) -> Any:
    """Fan out over a collection, one copy of the body per element."""
    items = await evaluate(parse(config.over), runtime.context())
    if isinstance(items, dict):
        # Looping over an object means its entries, which is what a reader expects.
        # Treating it as one element would be a loop that runs once and looks fine.
        items = [{"key": key, "value": value} for key, value in items.items()]
    if not isinstance(items, list):
        raise StepFailed(
            f"step {step.id!r} loops over {config.over}, which is "
            f"{type(items).__name__}, not a collection",
            remedies=["check the path -- -vv shows what it resolved to"],
        )
    return _grow(node, control.expand_foreach(step, config, items, runtime), runtime)


async def _while(node: str, step: Step, config: WhileConfig, runtime: Runtime) -> Any:
    """Run the body while the condition holds, one iteration of graph at a time.

    Each pass injects its body *and* a continuation node that re-evaluates the
    condition. The continuation expands in turn, so the chain grows exactly as far as
    the condition allows and no worker is held waiting for it. Because `expand` hands a
    node's dependents to the barrier it creates, the first pass's barrier inherits the
    whole chain -- nothing downstream can start until the loop is genuinely done.

    `do_while` differs in one place only: the first pass is unconditional. That is the
    right shape for "fetch, then decide whether to fetch again", where the thing the
    condition asks about does not exist until the body has run once.

    A loop produces its **last** pass's value, not a list of them. A loop that runs
    until something is true is asking for the state at the end; the intermediate states
    are what it was getting past.
    """
    passes = runtime.iterations.get(step.id, 0)
    if passes >= config.max_iterations:
        raise StepFailed(
            f"step {step.id!r} hit max_iterations ({config.max_iterations})",
            remedies=[
                "raise max_iterations if the loop is meant to run that long",
                "check that the condition goes false -- it is re-evaluated each pass",
            ],
        )

    unconditional = step.kind == "do_while" and passes == 0
    if not unconditional and not _truthy(await _loop_condition(config, runtime, passes)):
        return runtime.settled.get(step.id)

    runtime.iterations[step.id] = passes + 1
    expansion = control.expand_iteration(step, config, passes, runtime)
    # Named by pass number rather than by nesting: a chain of continuations would
    # otherwise read `climb::again::again::again`, which is a progress line nobody can
    # scan. The step id is stable across the chain, so the count is enough.
    again = f"{step.id}{control.MARK}pass{passes + 1}"
    # The continuation re-evaluates the condition, so it reads whatever the condition
    # reads. Recording that is what keeps those values alive for the next pass.
    expansion.specs.append(ExpandSpec(id=again, reads=control.reads_of(step), weight=0.1))
    expansion.injected[again] = control.Injected(
        step=step, frame=expansion.frame or runtime.frame, parent=step.id
    )
    return _grow(node, expansion, runtime)


async def _loop_condition(config: WhileConfig, runtime: Runtime, passes: int) -> Any:
    """Evaluate a loop's condition, with the body's own names in scope.

    Before the first pass those names have no value, and an unresolved reference would
    be an error naming a step that is right there in the file. Binding them to null
    instead lets a loop be written the way it reads -- `while is_null(@page) or
    @page.body.has_more` -- and keeps a genuine typo an error, because a name the body
    does not produce is still unresolved.
    """
    context = runtime.context()
    if passes == 0:
        pending = Frame(
            values={step.id: None for step in config.body},
            parent=runtime.frame,
        )
        context = runtime.context(pending)
    return await evaluate(parse(config.condition), context)


async def _parallel(node: str, step: Step, config: ParallelConfig, runtime: Runtime) -> Any:
    """Run every branch at once."""
    return _grow(node, control.expand_parallel(step, config, runtime), runtime)


def _grow(node: str, expansion: control.Expansion, runtime: Runtime) -> Any:
    """Hand an expansion to the scheduler, or settle it when there is nothing to add."""
    if expansion.has_value:
        return expansion.value
    if runtime.expand is None:  # pragma: no cover - the runner always supplies one
        raise StepFailed(f"node {node!r} cannot expand outside a scheduled run")

    runtime.injected.update(expansion.injected)
    runtime.results[node] = expansion.results
    runtime.joins[node] = expansion.produces
    runtime.expand(node, expansion.specs, expansion.tag_limit)
    return None


async def run_injected(node_id: str, runtime: Runtime) -> Any:
    """Run a node the graph grew for itself, in the scope it belongs to."""
    entry = runtime.injected[node_id]
    scoped = replace(runtime, frame=entry.frame)
    value = await run_step(entry.step, Node(id=node_id), scoped, node_id=node_id)
    if value is SKIPPED:
        return value

    # An iteration's steps see each other by their written names, not their decorated
    # ones: `@fetch` inside a loop body means this iteration's `fetch`.
    entry.frame.values[entry.step.id] = value

    if entry.result_of is not None:
        result = value
        if entry.collect:
            # `collect` says what an iteration contributes. Evaluated after the body has
            # bound its names, so it can refer to any of them -- which is the point:
            # `collect @one.body.id` keeps the ids and discards the responses.
            result = await evaluate(parse(entry.collect), scoped.context(entry.frame))
        runtime.produced[node_id] = result
        runtime.settled[entry.parent] = result
    return value


def collect(parent: str, runtime: Runtime) -> Any:
    """What a finished control step produced, gathered from the copies it made.

    Order is the order the copies were made -- element order for a `foreach`, branch
    order for a `parallel` -- never the order they happened to finish in. A loop whose
    results came back shuffled would be a loop nobody could use.
    """
    produces = runtime.joins.pop(parent, "list")
    results = runtime.results.pop(parent, {})

    if produces == "last":
        made = (runtime.injected[node] for node in results.values() if node in runtime.injected)
        owner = next((entry.parent for entry in made), parent)
        return runtime.settled.get(owner)

    values = [
        runtime.produced.pop(results[key], None) for key in sorted(results, key=_iteration_order)
    ]

    if produces == "one":
        return values[0] if values else None
    return values


def _iteration_order(key: str) -> tuple[int, str]:
    """Numeric keys sort numerically: pass 10 comes after pass 9, not after pass 1."""
    return (int(key), "") if key.isdigit() else (0, key)


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
