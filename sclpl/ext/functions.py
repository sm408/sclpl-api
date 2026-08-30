"""The `@function` decorator and the registry behind it.

Type hints are load-bearing (SPEC section 10). From the signature alone we generate:

- the JSON Schema, via pydantic's `TypeAdapter`
- the `--help` text and the shell-completion values
- the coercion that lets `"10"` from a JSON file arrive as the `int` the function wants

That last one matters most. A workflow file is text; without coercion every numeric
argument would arrive as a string and every function would have to defend itself.

Both `def` and `async def` are supported. A sync function that touches a `Table` is a
process-lane candidate; the lane assignment in M7 reads what is recorded here.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar, get_type_hints

from sclpl.expr import dispatch
from sclpl.run.errors import TypeDispatchError, ValidationError, did_you_mean

F = TypeVar("F", bound=Callable[..., Any])


@dataclass(slots=True)
class Parameter:
    name: str
    annotation: Any = Any
    default: Any = inspect.Parameter.empty
    keyword_only: bool = False
    variadic: bool = False

    @property
    def required(self) -> bool:
        return self.default is inspect.Parameter.empty and not self.variadic

    def type_name(self) -> str:
        annotation = self.annotation
        if annotation is Any or annotation is inspect.Parameter.empty:
            return "any"
        name = getattr(annotation, "__name__", None)
        return name if isinstance(name, str) else str(annotation).replace("typing.", "")


@dataclass(slots=True)
class Registered:
    """One registered function, with everything derived from its signature."""

    name: str
    call: Callable[..., Any]
    version: int = 1
    summary: str = ""
    parameters: list[Parameter] = field(default_factory=list)
    is_async: bool = False
    lane: str | None = None
    #: Set for the built-ins, so `fn list` can separate them from a user's own.
    builtin: bool = False

    def signature(self) -> str:
        parts: list[str] = []
        for parameter in self.parameters:
            rendered = parameter.name
            if parameter.variadic:
                rendered = f"*{rendered}"
            elif not parameter.required:
                rendered = f"{rendered}={_render_default(parameter.default)}"
            parts.append(rendered)
        return f"{self.name}({', '.join(parts)})"

    def schema(self) -> dict[str, Any]:
        """JSON Schema for the arguments, generated from the annotations."""
        from pydantic import TypeAdapter

        properties: dict[str, Any] = {}
        required: list[str] = []
        for parameter in self.parameters:
            if parameter.variadic:
                continue
            try:
                adapter = TypeAdapter(parameter.annotation)
                properties[parameter.name] = adapter.json_schema()
            except Exception:  # noqa: BLE001 - an exotic annotation is still usable
                properties[parameter.name] = {}
            if parameter.required:
                required.append(parameter.name)
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "title": self.name,
            "description": self.summary,
        }

    def coerce(self, args: list[Any], kwargs: dict[str, Any]) -> tuple[list[Any], dict[str, Any]]:
        """Bring arguments to the types the signature asks for.

        A workflow file has no types beyond JSON's, so `max_pages=1` from SCLPLL and
        `"1"` from a JSON string both have to become the `int` the function declared.
        """
        from pydantic import TypeAdapter
        from pydantic import ValidationError as PydanticError

        by_position = [p for p in self.parameters if not p.keyword_only and not p.variadic]
        out_args: list[Any] = []
        for index, value in enumerate(args):
            parameter = by_position[index] if index < len(by_position) else None
            out_args.append(self._coerce_one(parameter, value, TypeAdapter, PydanticError))

        by_name = {p.name: p for p in self.parameters}
        out_kwargs: dict[str, Any] = {}
        for key, value in kwargs.items():
            parameter = by_name.get(key)
            if parameter is None and not any(p.variadic for p in self.parameters):
                raise self._unknown_keyword(key)
            out_kwargs[key] = self._coerce_one(parameter, value, TypeAdapter, PydanticError)
        return out_args, out_kwargs

    def _coerce_one(
        self, parameter: Parameter | None, value: Any, adapter_type: Any, error_type: Any
    ) -> Any:
        if parameter is None or parameter.annotation in (Any, inspect.Parameter.empty):
            return value
        try:
            return adapter_type(parameter.annotation).validate_python(value)
        except error_type:
            # Coercion is a convenience, not a gate. A value the annotation refuses may
            # still be exactly what the function wants -- a Table where the hint says
            # `Any`-ish -- so pass it through and let the call fail with its own error.
            return value
        except Exception:  # noqa: BLE001 - an un-adaptable annotation is not an error
            return value

    def _unknown_keyword(self, key: str) -> TypeDispatchError:
        names = [p.name for p in self.parameters]
        remedies = []
        suggestion = did_you_mean(key, names)
        if suggestion:
            remedies.append(suggestion)
        remedies.append(f"{self.signature()}")
        return TypeDispatchError(f"{self.name}() has no argument {key!r}", remedies=remedies)


REGISTRY: dict[str, Registered] = {}


def function(
    name: str | None = None,
    *,
    version: int = 1,
    lane: str | None = None,
    builtin: bool = False,
) -> Callable[[F], F]:
    """Register a function so workflows can call it by name.

    ``version`` participates in the cache key, so changing what a function computes
    invalidates the results that came from the old one rather than silently mixing them.
    """

    def register(target: F) -> F:
        resolved = name or target.__name__
        entry = describe(target, resolved, version=version, lane=lane, builtin=builtin)
        if resolved in REGISTRY and REGISTRY[resolved].call is not target:
            raise ValidationError(
                f"two functions are both registered as {resolved!r}",
                remedies=["rename one, or pass an explicit name to @function"],
            )
        REGISTRY[resolved] = entry
        dispatch.generic(resolved, summary=entry.summary)(_wrap(entry))
        return target

    return register


def describe(
    target: Callable[..., Any],
    name: str,
    *,
    version: int = 1,
    lane: str | None = None,
    builtin: bool = False,
) -> Registered:
    """Read everything the registry needs out of a callable's signature."""
    signature = inspect.signature(target)
    try:
        hints = get_type_hints(target)
    except Exception:  # noqa: BLE001 - a forward reference we cannot resolve is fine
        hints = {}

    parameters: list[Parameter] = []
    for parameter in signature.parameters.values():
        if parameter.kind is inspect.Parameter.VAR_KEYWORD:
            continue
        parameters.append(
            Parameter(
                name=parameter.name,
                annotation=hints.get(parameter.name, parameter.annotation),
                default=parameter.default,
                keyword_only=parameter.kind is inspect.Parameter.KEYWORD_ONLY,
                variadic=parameter.kind is inspect.Parameter.VAR_POSITIONAL,
            )
        )

    doc = inspect.getdoc(target) or ""
    return Registered(
        name=name,
        call=target,
        version=version,
        summary=doc.splitlines()[0] if doc else "",
        parameters=parameters,
        is_async=inspect.iscoroutinefunction(target),
        lane=lane,
        builtin=builtin,
    )


def _wrap(entry: Registered) -> Callable[..., Any]:
    """The callable the dispatch table holds: coerce, then call."""

    def invoke(*args: Any, **kwargs: Any) -> Any:
        coerced_args, coerced_kwargs = entry.coerce(list(args), kwargs)
        try:
            return entry.call(*coerced_args, **coerced_kwargs)
        except TypeError as error:
            message = str(error)
            if entry.name in message or "argument" in message:
                raise TypeDispatchError(
                    f"{entry.name}() was called wrongly: {message}",
                    remedies=[entry.signature()],
                ) from error
            raise

    invoke.__name__ = entry.name
    invoke.__doc__ = entry.summary
    return invoke


def lookup(name: str) -> Registered:
    entry = REGISTRY.get(name)
    if entry is None:
        remedies = []
        suggestion = did_you_mean(name, list(REGISTRY))
        if suggestion:
            remedies.append(suggestion)
        remedies.append("run 'sclpl fn list' to see everything available")
        raise TypeDispatchError(f"no function named {name!r}", remedies=remedies)
    return entry


def names(*, builtin: bool | None = None) -> list[str]:
    if builtin is None:
        return sorted(REGISTRY)
    return sorted(name for name, entry in REGISTRY.items() if entry.builtin is builtin)


def _render_default(value: Any) -> str:
    if isinstance(value, str):
        return repr(value)
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
