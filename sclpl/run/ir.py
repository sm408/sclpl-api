"""The workflow IR — pydantic models, and the canonical form.

JSON and SCLPLL v2 are surfaces over this. Both compile *to* it and both emit *from*
it, and `sclpl fmt` then `sclpl convert` must round-trip byte-identically in either
direction. That property is what keeps the two surfaces from drifting into two
dialects with subtly different semantics.

These models also generate `docs/reference/workflow-schema.md`, so a field's
description is documentation, not a comment.
"""

from __future__ import annotations

from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sclpl.tables.io import Format

JsonValue: TypeAlias = Any

StepKind: TypeAlias = Literal[
    "http", "fn", "use", "let", "foreach", "if", "while", "do_while", "gate", "parallel"
]


Lane: TypeAlias = Literal["async", "thread", "process", "serial"]

Method: TypeAlias = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


class Base(BaseModel):
    """Shared configuration.

    `extra="forbid"` is the important one: a typo'd key is a validation error naming
    the field, not a setting that silently does nothing. That failure mode -- a
    workflow that runs but ignores half of what you wrote -- is the one worth spending
    strictness on.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Port(BaseModel):
    """A declared input or output file."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="How the workflow refers to this file.")
    format: Format = Field(default="auto", description="Inferred from the extension when auto.")
    required: bool = Field(default=True, description="A missing required port fails preflight.")
    default: str | None = Field(default=None, description="Path used when none is supplied.")
    description: str = ""


class Retry(Base):
    """Per-step retry policy. Defaults match `run/retry.py`."""

    max: int = Field(default=0, ge=0, le=20)
    base_delay: float = Field(default=0.5, gt=0)
    max_delay: float = Field(default=30.0, gt=0)
    on: list[int] = Field(default_factory=list, description="Extra statuses to retry.")


class CacheSpec(Base):
    """Whether and how long a step's result is reusable."""

    enabled: bool = True
    ttl: int | None = Field(default=None, ge=0, description="Seconds; null means forever.")
    key: str | None = Field(default=None, description="Override the computed cache key.")


class Limits(Base):
    """Ceilings for a run. Every one is a promise to a remote server."""

    concurrency: int = Field(default=16, ge=1, le=1024)
    host_concurrency: int = Field(default=6, ge=1, le=256)
    timeout: float = Field(default=30.0, gt=0)
    retries: int = Field(default=2, ge=0, le=20)
    max_pages: int | None = Field(default=None, ge=1)
    memory_budget: str | None = Field(default=None, description="e.g. '4G'.")
    tags: dict[str, int] = Field(default_factory=dict, description="Per-tag ceilings.")


class Pagination(Base):
    """How to follow a paginated source."""

    strategy: Literal["cursor", "page", "offset", "link_header", "token"] = "cursor"
    #: Where the next cursor/page token lives in the response.
    cursor_path: str | None = None
    #: The query parameter that carries it.
    param: str | None = None
    into: str | None = Field(default=None, description="Path to the items in each page.")
    max_pages: int | None = Field(default=None, ge=1)
    stop_when: str | None = Field(default=None, description="Expression; true ends paging.")
    concurrent: int = Field(default=1, ge=1, le=64)
    size: int | None = Field(default=None, ge=1, description="Page size, for page/offset.")


class HttpConfig(Base):
    """An HTTP request. Strings may contain `{{expr}}`."""

    method: Method = "GET"
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    query: dict[str, JsonValue] = Field(default_factory=dict)
    body: JsonValue = None
    form: dict[str, JsonValue] | None = None
    auth: str | None = Field(default=None, description="Name of an auth provider.")
    paginate: Pagination | None = None
    timeout: float | None = Field(default=None, gt=0)
    #: Where to take the step's value from: the whole response, or part of it.
    extract: str | None = Field(default=None, description="Expression over the response.")


class FnConfig(Base):
    """A call to a registered function or plugin connector."""

    name: str
    args: list[JsonValue] = Field(default_factory=list)
    kwargs: dict[str, JsonValue] = Field(default_factory=dict)


class LetConfig(Base):
    """A named value computed from an expression."""

    value: JsonValue = None
    expr: str | None = None

    @model_validator(mode="after")
    def _one_source(self) -> LetConfig:
        if self.expr is None and self.value is None:
            raise ValueError("a `let` needs either `expr` or `value`")
        return self


class ForeachConfig(Base):
    """Fan out over a collection.

    The body is injected into the same graph rather than gathered inside the step, so
    the run's concurrency ceiling still means what it says (SPEC section 12).
    """

    over: str = Field(description="Expression yielding the collection.")
    var: str = Field(default="item", description="Name the body binds each element to.")
    body: list[Step] = Field(default_factory=list)
    concurrency: int | None = Field(default=None, ge=1, le=1024)
    collect: str | None = Field(default=None, description="Expression collected per item.")


class IfConfig(Base):
    condition: str
    then: list[Step] = Field(default_factory=list)
    otherwise: list[Step] = Field(default_factory=list)


class WhileConfig(Base):
    condition: str
    body: list[Step] = Field(default_factory=list)
    max_iterations: int = Field(default=1000, ge=1)


class GateConfig(Base):
    """A barrier: everything before it finishes before anything after starts."""

    reason: str = ""


class ParallelConfig(Base):
    """An explicit fan-out of independent branches."""

    branches: list[list[Step]] = Field(default_factory=list)


class UseConfig(Base):
    """Invoke another workflow as a step."""

    workflow: str
    mode: str | None = None
    inputs: dict[str, JsonValue] = Field(default_factory=dict)


StepConfig: TypeAlias = (
    HttpConfig
    | FnConfig
    | LetConfig
    | ForeachConfig
    | IfConfig
    | WhileConfig
    | GateConfig
    | ParallelConfig
    | UseConfig
)

_CONFIG_FOR: dict[str, type[BaseModel]] = {
    "http": HttpConfig,
    "fn": FnConfig,
    "use": UseConfig,
    "let": LetConfig,
    "foreach": ForeachConfig,
    "if": IfConfig,
    "while": WhileConfig,
    "do_while": WhileConfig,
    "gate": GateConfig,
    "parallel": ParallelConfig,
}


class Step(Base):
    """One node of the workflow."""

    id: str = Field(description="Unique; also the name its output binds to.")
    kind: StepKind
    config: StepConfig
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    #: Explicit ordering edges. Unioned with what the expressions reference; a
    #: reference always wins, so this can add an edge but never remove one.
    needs: list[str] = Field(default_factory=list)
    assert_: str | None = Field(default=None, alias="assert")
    skip_if: str | None = None
    retry_if: str | None = None
    retry: Retry = Field(default_factory=Retry)
    cache: CacheSpec = Field(default_factory=CacheSpec)
    lane: Lane | None = Field(default=None, description="Inferred when null.")
    keep: bool = Field(default=False, description="Exempt from disposal.")
    #: The output port this step fills, from `@step name -> port`. A writer that names
    #: a port takes its path from the binding, so the same workflow writes wherever the
    #: caller says without the path being spelled inside it.
    writes: str | None = None

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        if not value:
            raise ValueError("a step id cannot be empty")
        if not (value[0].isalpha() or value[0] == "_"):
            raise ValueError(f"step id {value!r} must start with a letter or underscore")
        if not all(char.isalnum() or char in "_-" for char in value):
            raise ValueError(f"step id {value!r} may only contain letters, digits, '_' and '-'")
        return value

    @model_validator(mode="before")
    @classmethod
    def _coerce_config(cls, data: Any) -> Any:
        """Build the right config model from the step's kind.

        A discriminated union needs a tag inside the config; `kind` sits outside it,
        which reads better in both surfaces. Resolving it here keeps that choice from
        leaking into either one.
        """
        if not isinstance(data, dict):
            return data
        kind = data.get("kind")
        config = data.get("config")
        if isinstance(kind, str) and isinstance(config, dict):
            model = _CONFIG_FOR.get(kind)
            if model is not None:
                data = {**data, "config": model.model_validate(config)}
        return data

    @model_validator(mode="after")
    def _config_matches_kind(self) -> Step:
        expected = _CONFIG_FOR.get(self.kind)
        if expected is not None and not isinstance(self.config, expected):
            raise ValueError(
                f"step {self.id!r} is kind {self.kind!r} but its config is "
                f"{type(self.config).__name__}"
            )
        return self

    def children(self) -> list[Step]:
        """Nested steps, for the kinds that have a body."""
        match self.config:
            case ForeachConfig(body=body) | WhileConfig(body=body):
                return list(body)
            case IfConfig(then=then, otherwise=otherwise):
                return [*then, *otherwise]
            case ParallelConfig(branches=branches):
                return [step for branch in branches for step in branch]
            case _:
                return []


class ModeSpec(Base):
    """A named subset of the workflow.

    Modes may only *subtract* steps and override scalars (invariant 6). They can never
    add a step, change a dependency, or alter an expression -- enforced in `modes.py`
    by checking the pruned IR is a subgraph of the full one.
    """

    description: str = ""
    all: bool = Field(default=False, description="Start from every step.")
    include: list[str] = Field(default_factory=list, description="Ids, globs, or tag:name.")
    exclude: list[str] = Field(default_factory=list)
    extends: str | None = None
    vars: dict[str, JsonValue] = Field(default_factory=dict)
    limit: dict[str, JsonValue] = Field(default_factory=dict)
    stub: dict[str, JsonValue] = Field(
        default_factory=dict, description="Values standing in for pruned producers."
    )


class WorkflowDoc(Base):
    """A complete workflow. The canonical form both surfaces agree on."""

    name: str
    version: int = Field(default=1, ge=1)
    description: str = ""
    vars: dict[str, JsonValue] = Field(default_factory=dict)
    rules: dict[str, str] = Field(default_factory=dict, description="Named expressions.")
    inputs: list[Port] = Field(default_factory=list)
    outputs: list[Port] = Field(default_factory=list)
    modes: dict[str, ModeSpec] = Field(default_factory=dict)
    default_mode: str | None = None
    limits: Limits = Field(default_factory=Limits)
    steps: list[Step] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _valid_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a workflow needs a name")
        return value.strip()

    @model_validator(mode="after")
    def _consistent(self) -> WorkflowDoc:
        seen: set[str] = set()
        for step in self.all_steps():
            if step.id in seen:
                raise ValueError(f"duplicate step id {step.id!r}")
            seen.add(step.id)

        if self.default_mode is not None and self.default_mode not in self.modes:
            known = ", ".join(sorted(self.modes)) or "none defined"
            raise ValueError(
                f"default_mode {self.default_mode!r} is not a declared mode (have: {known})"
            )

        for mode_name, mode in self.modes.items():
            if mode.extends is not None and mode.extends not in self.modes:
                raise ValueError(
                    f"mode {mode_name!r} extends {mode.extends!r}, which is not declared"
                )

        port_names = [port.name for port in (*self.inputs, *self.outputs)]
        for name in port_names:
            if port_names.count(name) > 1:
                raise ValueError(f"duplicate port name {name!r}")
        return self

    def all_steps(self) -> list[Step]:
        """Every step including nested bodies, depth-first in declaration order."""
        out: list[Step] = []

        def walk(steps: list[Step]) -> None:
            for step in steps:
                out.append(step)
                walk(step.children())

        walk(self.steps)
        return out

    def step(self, step_id: str) -> Step | None:
        for candidate in self.all_steps():
            if candidate.id == step_id:
                return candidate
        return None

    def canonical(self) -> dict[str, Any]:
        """The dict form used for hashing and for the JSON surface.

        Defaults are omitted, so a workflow written by hand and one round-tripped
        through `fmt` produce identical bytes.
        """
        return self.model_dump(mode="json", exclude_defaults=True, by_alias=True)


# Nested step bodies refer to `Step` before it exists at class-creation time.
ForeachConfig.model_rebuild()
IfConfig.model_rebuild()
WhileConfig.model_rebuild()
ParallelConfig.model_rebuild()
Step.model_rebuild()
WorkflowDoc.model_rebuild()
