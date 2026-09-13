"""I3: turn one request from a local Postman v2.1 collection into a workflow.

Postman's `{{variable}}` templating is textually identical to SCLPLL's own
interpolation syntax, so a collection/environment variable becomes a `@var`
declaration and every reference to it passes through unchanged. A pre-request
or test script (`event`) is data here, never code: it is listed as an
unsupported diagnostic and never parsed as JavaScript, let alone run. An
environment variable marked `"type": "secret"`, and any credential in a
request's own `auth` block, are extracted the same way I1 extracts a curl
credential -- returned once, in memory, never written into the generated
workflow.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sclpl.errors import ValidationError

SUPPORTED_SCHEMA_PREFIX = "https://schema.getpostman.com/json/collection/v2.1"


@dataclass(frozen=True, slots=True)
class ExtractedAuth:
    kind: str  # "bearer" | "basic" | "api_key"
    secret_name: str
    secret_value: str
    username: str | None = None
    header: str | None = None
    query_name: str | None = None


@dataclass(frozen=True, slots=True)
class Request:
    name: str  # "Folder/Subfolder/Request Name"
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    query: dict[str, str] = field(default_factory=dict)
    body: object | None = None
    auth: ExtractedAuth | None = None
    unsupported: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Collection:
    name: str
    requests: tuple[Request, ...]
    variables: dict[str, str]
    #: Environment variables marked `"type": "secret"` -- named here, but their
    #: values are never read into this object at all, let alone rendered.
    secret_variable_names: tuple[str, ...] = ()


def load(path: Path, *, environment: Path | None = None) -> Collection:
    """Parse a local Postman v2.1 collection, optionally merging an environment file.

    Never fetches anything and never evaluates a script. An environment
    variable's secret value is not returned here -- see `extracted_secrets`.
    """
    raw = _read_json(path)
    schema = raw.get("info", {}).get("schema", "") if isinstance(raw.get("info"), dict) else ""
    if not isinstance(schema, str) or not schema.startswith(SUPPORTED_SCHEMA_PREFIX):
        raise ValidationError(
            f"unsupported or missing Postman collection schema {schema!r}",
            where=str(path),
            remedies=["this importer supports collection format v2.1"],
        )

    variables = _variable_map(raw.get("variable", []))
    secret_names = list(_secret_variable_names(raw.get("variable", [])))
    if environment is not None:
        env_raw = _read_json(environment)
        variables.update(_variable_map(env_raw.get("values", [])))
        secret_names.extend(_secret_variable_names(env_raw.get("values", [])))

    requests: list[Request] = []
    _walk(raw.get("item", []), "", requests)
    info = raw.get("info", {})
    name = info.get("name", path.stem) if isinstance(info, dict) else path.stem
    return Collection(str(name), tuple(requests), variables, tuple(secret_names))


@dataclass(frozen=True, slots=True)
class ImportResult:
    workflow: str
    auth_manifest: str | None
    extracted_secret: tuple[str, str] | None
    warnings: tuple[str, ...]


def render(collection: Collection, request_name: str, *, name: str) -> ImportResult:
    """Render one named request as a complete, runnable `.sclpll` workflow."""
    request = next((r for r in collection.requests if r.name == request_name), None)
    if request is None:
        known = ", ".join(sorted(r.name for r in collection.requests)) or "none"
        raise ValidationError(
            f"no request {request_name!r} in this collection", remedies=[f"known: {known}"]
        )

    var_lines = [f'@var {key} = "{value}"' for key, value in sorted(collection.variables.items())]
    lines = [f'@workflow {name} "Imported from a Postman request"', "", *var_lines]
    lines += [
        "",
        "@output response:json",
        "",
        "@step fetch",
        f"  {request.method.lower()} {request.url}",
    ]

    for key, value in sorted(request.headers.items()):
        lines.append(f"  header {key}: {value}")
    for key, value in sorted(request.query.items()):
        lines.append(f"  query {key}={_query_literal(value)}")
    if request.body is not None:
        lines.append(f"  body {json.dumps(request.body)}")
    if request.auth is not None:
        lines.append("  auth imported")

    lines += [
        "  assert @fetch.status < 400",
        "",
        "@step write -> response",
        "  save_json @fetch.body",
        "",
    ]

    manifest = None
    extracted_secret = None
    if request.auth is not None:
        manifest = _auth_manifest(request.auth)
        extracted_secret = (request.auth.secret_name, request.auth.secret_value)

    warnings = tuple(f"unsupported: {item}" for item in request.unsupported)
    if collection.secret_variable_names:
        names = ", ".join(sorted(collection.secret_variable_names))
        warnings += (
            f"environment secret variable(s) {names} were not imported; "
            "declare them as @var and pass with --var, or wire them into an auth profile",
        )
    return ImportResult("\n".join(lines), manifest, extracted_secret, warnings)


def _auth_manifest(auth: ExtractedAuth) -> str:
    if auth.kind == "bearer":
        return f'[auth.imported]\nkind = "bearer"\nsecret = "{auth.secret_name}"\n'
    if auth.kind == "basic":
        username_line = f'username = "{auth.username}"\n' if auth.username else ""
        return f'[auth.imported]\nkind = "basic"\n{username_line}secret = "{auth.secret_name}"\n'
    location = "query" if auth.query_name else "header"
    target = auth.query_name or auth.header or "X-Api-Key"
    target_key = "query_name" if location == "query" else "header"
    return (
        f'[auth.imported]\nkind = "api_key"\nlocation = "{location}"\n'
        f'{target_key} = "{target}"\nsecret = "{auth.secret_name}"\n'
    )


def _walk(items: Any, prefix: str, out: list[Request]) -> None:
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        item_name = str(item.get("name", "unnamed"))
        full_name = f"{prefix}/{item_name}" if prefix else item_name
        if "item" in item:
            _walk(item["item"], full_name, out)
            continue
        request = item.get("request")
        if isinstance(request, dict):
            out.append(_request(full_name, request, item.get("event", [])))


def _request(name: str, raw: dict[str, Any], events: Any) -> Request:
    unsupported: list[str] = []
    if isinstance(events, list):
        for event in events:
            if isinstance(event, dict) and event.get("listen") in ("prerequest", "test"):
                unsupported.append(f"{event['listen']} script (never executed)")

    method = str(raw.get("method", "GET")).upper()
    url, query = _url(raw.get("url"))
    headers = {
        str(h["key"]): str(h["value"])
        for h in raw.get("header", []) or []
        if isinstance(h, dict) and h.get("key") and not h.get("disabled")
    }

    body = None
    raw_body = raw.get("body")
    if isinstance(raw_body, dict):
        mode = raw_body.get("mode")
        if mode == "raw":
            text = raw_body.get("raw", "")
            try:
                body = json.loads(text) if text else None
            except json.JSONDecodeError:
                body = text
        elif mode == "urlencoded":
            body = {
                e["key"]: e.get("value", "")
                for e in raw_body.get("urlencoded", []) or []
                if isinstance(e, dict) and not e.get("disabled")
            }
        elif mode:
            unsupported.append(f"body mode {mode!r}")

    auth = _extract_auth(raw.get("auth"))

    return Request(name, method, url, headers, query, body, auth, tuple(unsupported))


def _url(raw: Any) -> tuple[str, dict[str, str]]:
    if isinstance(raw, str):
        split = urlsplit(raw)
        query = dict(
            (pair.split("=", 1)[0], pair.split("=", 1)[1]) if "=" in pair else (pair, "")
            for pair in split.query.split("&")
            if pair
        )
        return (raw.split("?", 1)[0] if split.query else raw), query
    if isinstance(raw, dict):
        query = {
            str(q["key"]): str(q.get("value", ""))
            for q in raw.get("query", []) or []
            if isinstance(q, dict) and q.get("key") and not q.get("disabled")
        }
        raw_url = raw.get("raw", "")
        base = raw_url.split("?", 1)[0] if isinstance(raw_url, str) else ""
        return base, query
    return "", {}


def _extract_auth(raw: Any) -> ExtractedAuth | None:
    if not isinstance(raw, dict):
        return None
    kind = raw.get("type")
    if kind == "bearer":
        token = _auth_field(raw, "bearer", "token")
        return ExtractedAuth("bearer", "IMPORTED_BEARER_TOKEN", token) if token else None
    if kind == "basic":
        username = _auth_field(raw, "basic", "username") or ""
        password = _auth_field(raw, "basic", "password") or ""
        return ExtractedAuth("basic", "IMPORTED_PASSWORD", password, username=username)
    if kind == "apikey":
        value = _auth_field(raw, "apikey", "value") or ""
        key = _auth_field(raw, "apikey", "key") or "X-Api-Key"
        location = _auth_field(raw, "apikey", "in") or "header"
        if location == "query":
            return ExtractedAuth("api_key", "IMPORTED_API_KEY", value, query_name=key)
        return ExtractedAuth("api_key", "IMPORTED_API_KEY", value, header=key)
    return None


def _auth_field(raw: dict[str, Any], scheme: str, key: str) -> str | None:
    entries = raw.get(scheme)
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("key") == key:
            value = entry.get("value")
            return str(value) if value is not None else None
    return None


def _variable_map(raw: Any) -> dict[str, str]:
    if not isinstance(raw, list):
        return {}
    return {
        str(item["key"]): str(item.get("value", ""))
        for item in raw
        if isinstance(item, dict) and item.get("key") and item.get("type") != "secret"
    }


def _secret_variable_names(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [
        str(item["key"]) for item in raw if isinstance(item, dict) and item.get("type") == "secret"
    ]


def _query_literal(value: str) -> str:
    if value and value.replace(".", "", 1).isdigit():
        return value
    return json.dumps(value)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValidationError(f"invalid JSON: {error}", where=str(path)) from error
    if not isinstance(raw, dict):
        raise ValidationError("must be a JSON object", where=str(path))
    return raw
