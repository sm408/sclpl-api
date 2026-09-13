"""I2: turn one operation of a local OpenAPI 3.x document into a workflow.

JSON documents only for this pass -- YAML would need a new dependency, which is
a deliberate scope boundary (docs/cli-rebuild/UPGRADE-PROGRESS.md), not an
oversight. A `$ref` is resolved only against the same in-memory document
(`#/components/...`); anything else (a remote URL, a sibling file) is refused
outright -- resolving one would mean this importer making its own network or
filesystem call before the user ever runs anything, which is exactly the
implicit-fetch behavior this batch exists to disable.

An imported request/response schema is carried here only to shape the
generated workflow (which fields exist, which are required); it is never
treated as a verified contract snapshot -- those come only from observing a
real response (E-series), and conflating the two would let an unverified spec
claim contract-test confidence it has not earned.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sclpl.errors import ValidationError

SUPPORTED_MAJOR_VERSION = "3"
_PARAMETER_LOCATIONS = ("path", "query", "header")
_METHODS = ("get", "post", "put", "patch", "delete")


@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    location: str  # "path" | "query" | "header"
    required: bool
    default: object | None = None


@dataclass(frozen=True, slots=True)
class Operation:
    operation_id: str
    method: str
    path: str
    parameters: tuple[Parameter, ...]
    request_body_example: object | None
    security_scheme: str | None
    unsupported: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Document:
    version: str
    base_url: str | None
    operations: tuple[Operation, ...]
    security_schemes: dict[str, dict[str, Any]]


def load(path: Path) -> Document:
    """Parse a local JSON OpenAPI 3.x document. Never fetches or reads anything else."""
    if path.suffix.lower() in (".yaml", ".yml"):
        raise ValidationError(
            "YAML OpenAPI documents are not supported",
            where=str(path),
            remedies=["convert the spec to JSON first"],
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValidationError(f"invalid JSON: {error}", where=str(path)) from error
    if not isinstance(raw, dict):
        raise ValidationError("an OpenAPI document must be a JSON object", where=str(path))

    version = raw.get("openapi")
    if not isinstance(version, str) or not version.startswith(f"{SUPPORTED_MAJOR_VERSION}."):
        raise ValidationError(
            f"unsupported OpenAPI version {version!r}",
            where=str(path),
            remedies=["this importer supports OpenAPI 3.x documents"],
        )

    schemes = raw.get("components", {})
    security_schemes = schemes.get("securitySchemes", {}) if isinstance(schemes, dict) else {}
    if not isinstance(security_schemes, dict):
        security_schemes = {}

    paths = raw.get("paths")
    if not isinstance(paths, dict):
        raise ValidationError("document has no 'paths'", where=str(path))

    operations: list[Operation] = []
    for route, item in paths.items():
        if not isinstance(item, dict):
            continue
        shared = item.get("parameters", [])
        shared = shared if isinstance(shared, list) else []
        for method in _METHODS:
            spec = item.get(method)
            if isinstance(spec, dict):
                operations.append(_operation(raw, route, method, spec, shared, path))

    return Document(version, _base_url(raw), tuple(operations), security_schemes)


@dataclass(frozen=True, slots=True)
class ImportResult:
    workflow: str
    warnings: tuple[str, ...]


def render(document: Document, operation_id: str, *, name: str) -> ImportResult:
    """Render one operation as a complete, runnable `.sclpll` workflow."""
    operation = next((o for o in document.operations if o.operation_id == operation_id), None)
    if operation is None:
        known = ", ".join(sorted(o.operation_id for o in document.operations)) or "none"
        raise ValidationError(
            f"no operation {operation_id!r} in this document", remedies=[f"known: {known}"]
        )

    base = document.base_url or "https://api.example.invalid"
    url_template = operation.path
    var_declarations: list[str] = []
    request_lines: list[str] = []

    def declare_var(param_name: str) -> None:
        var_declarations.append(
            f'@var {param_name} = "<{param_name}>"  # required: --var {param_name}=...'
        )

    for param in operation.parameters:
        if param.location != "path":
            continue
        declare_var(param.name)
        url_template = url_template.replace("{" + param.name + "}", f"{{{{{param.name}}}}}")

    for param in operation.parameters:
        if param.location == "header":
            value = param.default if param.default is not None else f"<{param.name}>"
            request_lines.append(f"  header {param.name}: {value}")
        elif param.location == "query":
            if param.default is not None:
                request_lines.append(f"  query {param.name}={_literal(param.default)}")
            elif param.required:
                declare_var(param.name)
                request_lines.append(f"  query {param.name}={{{{{param.name}}}}}")

    lines = [
        f'@workflow {name} "Imported from an OpenAPI operation"',
        "",
        f'@var base = "{base}"',
        *var_declarations,
        "",
        "@output response:json",
        "",
        "@step fetch",
        f"  {operation.method.lower()} {{{{base}}}}{url_template}",
        *request_lines,
    ]

    if operation.request_body_example is not None:
        lines.append(f"  body {json.dumps(operation.request_body_example)}")
    if operation.security_scheme is not None:
        lines.append(f"  auth {operation.security_scheme}")

    lines += [
        "  assert @fetch.status < 400",
        "",
        "@step write -> response",
        "  save_json @fetch.body",
        "",
    ]
    warnings = tuple(f"unsupported OpenAPI construct: {item}" for item in operation.unsupported)
    return ImportResult("\n".join(lines), warnings)


def _operation(
    raw: dict[str, Any],
    route: str,
    method: str,
    spec: dict[str, Any],
    shared_params: list[Any],
    source: Path,
) -> Operation:
    unsupported: list[str] = []
    operation_id = spec.get("operationId") or f"{method}_{route}".replace("/", "_").strip("_")

    parameters: list[Parameter] = []
    for raw_param in (*shared_params, *spec.get("parameters", [])):
        resolved = _resolve(raw, raw_param, source, unsupported)
        if not isinstance(resolved, dict):
            continue
        location = resolved.get("in")
        if location not in _PARAMETER_LOCATIONS:
            if location is not None:
                unsupported.append(f"parameter in {location!r}")
            continue
        schema = resolved.get("schema", {})
        default = schema.get("default") if isinstance(schema, dict) else None
        parameters.append(
            Parameter(resolved["name"], location, bool(resolved.get("required")), default)
        )

    body_example = None
    request_body = spec.get("requestBody")
    if isinstance(request_body, dict):
        content = request_body.get("content", {})
        json_media = content.get("application/json") if isinstance(content, dict) else None
        if isinstance(json_media, dict):
            body_example = json_media.get("example")
            if body_example is None:
                body_example = _example_from_schema(
                    json_media.get("schema", {}), raw, source, unsupported
                )
        elif content:
            unsupported.append(f"request body media type(s): {', '.join(sorted(content))}")

    security_scheme = None
    security = spec.get("security")
    if isinstance(security, list) and security:
        first = security[0]
        if isinstance(first, dict) and first:
            security_scheme = next(iter(first))

    for extra in ("callbacks", "links"):
        if extra in spec:
            unsupported.append(f"{extra} on {method.upper()} {route}")

    return Operation(
        operation_id,
        method.upper(),
        route,
        tuple(parameters),
        body_example,
        security_scheme,
        tuple(unsupported),
    )


def _resolve(raw: dict[str, Any], value: Any, source: Path, unsupported: list[str]) -> Any:
    del unsupported  # a non-local $ref is refused outright, below, not merely diagnosed
    if not isinstance(value, dict) or "$ref" not in value:
        return value
    ref = value["$ref"]
    if not isinstance(ref, str) or not ref.startswith("#/"):
        raise ValidationError(
            f"refusing a non-local $ref {ref!r}",
            where=str(source),
            remedies=["only #/... references within the same document are resolved"],
        )
    node: Any = raw
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            raise ValidationError(f"unresolvable $ref {ref!r}", where=str(source))
        node = node[part]
    return node


def _example_from_schema(
    schema: Any, raw: dict[str, Any], source: Path, unsupported: list[str]
) -> object | None:
    schema = _resolve(raw, schema, source, unsupported)
    if not isinstance(schema, dict):
        return None
    if "example" in schema:
        return cast(object, schema["example"])
    if schema.get("type") == "object":
        properties = schema.get("properties", {})
        if isinstance(properties, dict) and properties:
            return {
                key: _example_from_schema(value, raw, source, unsupported)
                for key, value in properties.items()
            }
    return None


def _base_url(raw: dict[str, Any]) -> str | None:
    servers = raw.get("servers")
    if isinstance(servers, list) and servers:
        first = servers[0]
        if isinstance(first, dict) and isinstance(first.get("url"), str):
            return cast(str, first["url"])
    return None


def _literal(value: object) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return json.dumps(str(value))
