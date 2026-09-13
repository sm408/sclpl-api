"""I1: turn a copied `curl` command into a `.sclpll` workflow, as data.

Nothing here runs a shell or `curl` itself -- `sclpl.importers.shell` tokenizes the
command text, and this module only ever inspects the resulting argv. A credential
found in the command (an `Authorization` header, or `-u user:pass`) is extracted
into a named `[auth.<name>]` profile reference in the generated workflow; its
value is returned once, in memory, for the caller to register with a secret
store -- it is never written into the generated workflow or manifest text.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlsplit

from sclpl.errors import ValidationError
from sclpl.importers import shell

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")

#: Flags accepted with no effect on the generated request -- curl behaviors that
#: are either always true for an ordinary HTTP client (follow redirects) or purely
#: about curl's own terminal output (verbosity), not the request itself.
_NOOP_FLAGS = {
    "-L",
    "--location",
    "--compressed",
    "-s",
    "--silent",
    "-v",
    "--verbose",
    "-#",
    "--progress-bar",
}
#: Flags that change something this importer cannot represent -- reported back
#: as an actionable diagnostic rather than silently dropped or guessed at.
_UNSUPPORTED_WITH_ARG = {"-o", "--output", "--cacert", "--cert", "--key", "-w", "--write-out"}
_UNSUPPORTED_NO_ARG = {"-i", "--include", "-k", "--insecure", "-I", "--head"}


@dataclass(frozen=True, slots=True)
class ExtractedAuth:
    """A credential pulled out of the command, never written to disk here."""

    kind: str  # "bearer" | "basic" | "header"
    secret_name: str
    secret_value: str
    username: str | None = None
    header: str | None = None
    prefix: str = ""


@dataclass(frozen=True, slots=True)
class ParsedRequest:
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    query: dict[str, str] = field(default_factory=dict)
    body: object | None = None
    body_kind: str | None = None  # "json" | "form" | "raw"
    auth: ExtractedAuth | None = None
    unsupported: tuple[str, ...] = ()


def parse(command: str, *, dialect: str | None = None) -> ParsedRequest:
    """Parse a `curl` command string into data. Raises on anything not curl."""
    resolved_dialect = dialect or shell.detect_dialect(command)
    tokens = shell.tokenize(command, dialect=resolved_dialect)
    if not tokens or tokens[0].lower() not in ("curl", "curl.exe"):
        raise ValidationError(
            "not a curl command", remedies=["paste the full command, starting with curl"]
        )

    method: str | None = None
    url: str | None = None
    headers: dict[str, str] = {}
    data_parts: list[str] = []
    form_fields: dict[str, str] = {}
    used_form = False
    used_get_promotion = False
    unsupported: list[str] = []
    auth: ExtractedAuth | None = None

    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token in _NOOP_FLAGS:
            index += 1
            continue
        if token in _UNSUPPORTED_NO_ARG:
            unsupported.append(token)
            index += 1
            continue
        if token in _UNSUPPORTED_WITH_ARG:
            unsupported.append(f"{token} {tokens[index + 1]}" if index + 1 < len(tokens) else token)
            index += 2
            continue
        if token in ("-X", "--request"):
            method = tokens[index + 1].upper()
            index += 2
            continue
        if token in ("-H", "--header"):
            name, _, value = tokens[index + 1].partition(":")
            headers[name.strip()] = value.strip()
            index += 2
            continue
        if token in ("-d", "--data", "--data-raw", "--data-binary", "--data-ascii"):
            data_parts.append(tokens[index + 1])
            index += 2
            continue
        if token in ("-F", "--form"):
            field_name, _, value = tokens[index + 1].partition("=")
            form_fields[field_name] = value
            used_form = True
            index += 2
            continue
        if token in ("-u", "--user"):
            username, _, password = tokens[index + 1].partition(":")
            auth = ExtractedAuth("basic", "IMPORTED_PASSWORD", password, username=username)
            index += 2
            continue
        if token in ("-G", "--get"):
            used_get_promotion = True
            index += 1
            continue
        if token in ("-x", "--proxy"):
            # Recorded as an unsupported diagnostic rather than silently applied:
            # sclpl's proxy config is project/environment-scoped, not per-request.
            unsupported.append(f"{token} {tokens[index + 1]}" if index + 1 < len(tokens) else token)
            index += 2
            continue
        if not token.startswith("-") and url is None:
            url = token
            index += 1
            continue
        unsupported.append(token)
        index += 1

    if url is None:
        raise ValidationError("no URL found in the curl command")

    if auth is None:
        auth, headers = _extract_header_auth(headers)

    split = urlsplit(url)
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    bare_url = url if not split.query else url.split("?", 1)[0]

    body: object | None = None
    body_kind: str | None = None
    if used_form:
        body, body_kind = dict(form_fields), "form"
        if method is None:
            method = "POST"
    elif data_parts:
        joined = "&".join(data_parts)
        if used_get_promotion:
            query.update(parse_qsl(joined, keep_blank_values=True))
        else:
            try:
                body, body_kind = json.loads(joined), "json"
            except json.JSONDecodeError:
                body, body_kind = joined, "raw"
            if method is None:
                method = "POST"

    if method is None:
        method = "GET"
    if method not in METHODS:
        unsupported.append(f"-X {method}")
        method = "GET"

    return ParsedRequest(
        method, bare_url, headers, query, body, body_kind, auth, tuple(unsupported)
    )


def _extract_header_auth(headers: dict[str, str]) -> tuple[ExtractedAuth | None, dict[str, str]]:
    remaining = dict(headers)
    raw = remaining.pop("Authorization", None) or remaining.pop("authorization", None)
    if raw is None:
        return None, remaining
    scheme, _, value = raw.partition(" ")
    if scheme.lower() == "bearer" and value:
        return ExtractedAuth("bearer", "IMPORTED_BEARER_TOKEN", value), remaining
    if scheme.lower() == "basic" and value:
        try:
            decoded = base64.b64decode(value).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return ExtractedAuth(
                "header", "IMPORTED_AUTH_HEADER", raw, header="Authorization"
            ), remaining
        username, _, password = decoded.partition(":")
        return ExtractedAuth("basic", "IMPORTED_PASSWORD", password, username=username), remaining
    return (
        ExtractedAuth(
            "header", "IMPORTED_AUTH_HEADER", value, header="Authorization", prefix=f"{scheme} "
        ),
        remaining,
    )


@dataclass(frozen=True, slots=True)
class ImportResult:
    """A ready-to-save workflow, plus what a human still has to do by hand."""

    workflow: str
    #: A `[auth.imported]` TOML table to add to the project manifest, or None.
    auth_manifest: str | None
    #: (secret name, secret value) extracted from the command -- report this to
    #: the caller once; never write it to the workflow, the manifest, or a log.
    extracted_secret: tuple[str, str] | None
    warnings: tuple[str, ...]


def render(parsed: ParsedRequest, *, name: str) -> ImportResult:
    """Render a parsed request as one complete, runnable `.sclpll` workflow."""
    lines = [
        f'@workflow {name} "Imported from a curl command"',
        "",
        "@output response:json",
        "",
        "@step fetch",
        f"  {parsed.method.lower()} {parsed.url}",
    ]
    for key, value in sorted(parsed.headers.items()):
        lines.append(f"  header {key}: {value}")
    for key, value in sorted(parsed.query.items()):
        lines.append(f"  query {key}={_query_literal(value)}")
    if parsed.body is not None:
        lines.append(f"  body {json.dumps(parsed.body)}")

    auth_manifest = None
    extracted_secret = None
    if parsed.auth is not None:
        lines.append("  auth imported")
        auth_manifest = _render_auth_manifest(parsed.auth)
        extracted_secret = (parsed.auth.secret_name, parsed.auth.secret_value)

    lines += [
        "  assert @fetch.status < 400",
        "",
        "@step write -> response",
        "  save_json @fetch.body",
        "",
    ]

    warnings = tuple(f"unsupported curl option: {item}" for item in parsed.unsupported)
    if parsed.body_kind == "form":
        warnings += ("form fields were modeled as a JSON object body, not multipart/form-data",)
    return ImportResult("\n".join(lines), auth_manifest, extracted_secret, warnings)


def _query_literal(value: str) -> str:
    if value and (value.isdigit() or _looks_like_float(value)):
        return value
    return json.dumps(value)


def _looks_like_float(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def _render_auth_manifest(auth: ExtractedAuth) -> str:
    if auth.kind == "bearer":
        return f'[auth.imported]\nkind = "bearer"\nsecret = "{auth.secret_name}"\n'
    if auth.kind == "basic":
        username_line = f'username = "{auth.username}"\n' if auth.username else ""
        return f'[auth.imported]\nkind = "basic"\n{username_line}secret = "{auth.secret_name}"\n'
    return (
        f'[auth.imported]\nkind = "header"\nheader = "{auth.header}"\n'
        f'prefix = "{auth.prefix}"\nsecret = "{auth.secret_name}"\n'
    )
