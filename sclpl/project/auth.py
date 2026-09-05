"""Named auth profiles: one provider interface behind `auth <name>` in a workflow step.

B4/B6 of the unified upgrade. A step names a profile (`sclpl/run/ir.py`'s
`HttpConfig.auth`); this module turns that name into headers/query parameters applied
once, right before the request goes out, with every resolved secret registered for
redaction (`sclpl.render.reporter.active_reporter`) so it never appears in a safe
context dump, cached key, or history row. OAuth2 (B5) is a separate module
(`sclpl.project.oauth`) because it needs a token cache and network access that the
other kinds do not; this module dispatches to it rather than importing httpx itself.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Any

from sclpl.errors import ValidationError
from sclpl.render.redact import TooShortToRedact
from sclpl.render.reporter import active_reporter
from sclpl.state import secrets as store

#: Kinds resolved here, without network access. `oauth2_client_credentials` is
#: dispatched to `sclpl.project.oauth`; `hmac` to `sclpl.project.signing`.
_STATIC_KINDS = frozenset({"bearer", "basic", "api_key", "header"})
_KNOWN_KINDS = _STATIC_KINDS | {"oauth2_client_credentials", "hmac"}


@dataclass(frozen=True, slots=True)
class Profile:
    """One `[auth.<name>]` table, validated but not yet resolved."""

    name: str
    kind: str
    env: str = "default"
    #: bearer/header/hmac: the credential itself. api_key: same. basic: the password.
    secret: str | None = None
    #: basic only: a literal username, or a secret name for one that must not be
    #: written to the manifest in the clear.
    username: str | None = None
    username_secret: str | None = None
    #: header/api_key: which header or query parameter carries the value.
    header: str | None = None
    query_name: str | None = None
    #: api_key: "header" (default) or "query".
    location: str = "header"
    #: header/hmac: text placed before the resolved value, e.g. "Bearer ".
    prefix: str = ""
    #: oauth2_client_credentials
    token_url: str | None = None
    client_id_secret: str | None = None
    client_secret_secret: str | None = None
    scope: str | None = None
    #: hmac
    timestamp_header: str = "X-Timestamp"
    algorithm: str = "sha256"

    def target_header(self) -> str | None:
        """The header name this profile writes, for duplicate-auth detection."""
        if self.kind == "bearer":
            return "Authorization"
        if self.kind == "basic":
            return "Authorization"
        if self.kind == "api_key" and self.location == "header":
            return self.header or "X-Api-Key"
        if self.kind == "header":
            return self.header
        if self.kind == "oauth2_client_credentials":
            return "Authorization"
        return None


@dataclass(frozen=True, slots=True)
class Applied:
    """Headers and query parameters to merge into an outgoing request."""

    headers: dict[str, str] = field(default_factory=dict)
    query: dict[str, Any] = field(default_factory=dict)


def parse_profiles(manifest: dict[str, Any], *, default_env: str = "default") -> dict[str, Profile]:
    """Every `[auth.<name>]` table in a project manifest, validated up front.

    Validated at load time rather than first use: a typo in a profile a workflow
    never calls should still fail `project check`, not surface as a confusing 500
    the first time someone exercises that code path. ``default_env`` is the project's
    currently selected environment, so switching `--env staging` moves both the secret
    namespace and the auth profiles that read it, unless a profile pins its own.
    """
    raw = manifest.get("auth", {})
    if not isinstance(raw, dict):
        raise ValidationError("auth must be a table")
    profiles: dict[str, Profile] = {}
    for name, table in raw.items():
        if not isinstance(table, dict):
            raise ValidationError(f"auth.{name} must be a table")
        profiles[name] = _parse_one(name, table, default_env)
    return profiles


def _parse_one(name: str, table: dict[str, Any], default_env: str) -> Profile:
    kind = table.get("type")
    if kind not in _KNOWN_KINDS:
        raise ValidationError(
            f"auth.{name} has unknown type {kind!r}",
            remedies=[f"known types: {', '.join(sorted(_KNOWN_KINDS))}"],
        )
    profile = Profile(
        name=name,
        kind=kind,
        env=table.get("env", default_env),
        secret=table.get("secret"),
        username=table.get("username"),
        username_secret=table.get("username_secret"),
        header=table.get("header"),
        query_name=table.get("name"),
        location=table.get("location", "header"),
        prefix=table.get("prefix", ""),
        token_url=table.get("token_url"),
        client_id_secret=table.get("client_id_secret"),
        client_secret_secret=table.get("client_secret_secret"),
        scope=table.get("scope"),
        timestamp_header=table.get("timestamp_header", "X-Timestamp"),
        algorithm=table.get("algorithm", "sha256"),
    )
    _validate_required(profile)
    return profile


def _validate_required(profile: Profile) -> None:
    missing: list[str] = []
    if profile.kind == "bearer" and not profile.secret:
        missing.append("secret")
    elif profile.kind == "basic":
        if not profile.secret:
            missing.append("secret (the password)")
        if not profile.username and not profile.username_secret:
            missing.append("username or username_secret")
    elif profile.kind == "api_key":
        if not profile.secret:
            missing.append("secret")
        if profile.location not in ("header", "query"):
            raise ValidationError(f"auth.{profile.name}.location must be 'header' or 'query'")
        if profile.location == "query" and not profile.query_name:
            missing.append("name (the query parameter)")
    elif profile.kind == "header":
        if not profile.header:
            missing.append("header")
        if not profile.secret:
            missing.append("secret")
    elif profile.kind == "oauth2_client_credentials":
        if not profile.token_url:
            missing.append("token_url")
        if not profile.client_id_secret:
            missing.append("client_id_secret")
        if not profile.client_secret_secret:
            missing.append("client_secret_secret")
    elif profile.kind == "hmac" and not profile.secret:
        missing.append("secret")
    if missing:
        raise ValidationError(f"auth.{profile.name} is missing {', '.join(missing)}")


def _secret(name: str, *, env: str, label: str) -> str:
    value = store.get(name, env=env)
    if value is None:
        raise ValidationError(
            f"no secret named {name!r}, needed as the {label} for an auth profile",
            remedies=[f"sclpl secret set {name}", f"or set SCLPL_SECRET_{name.upper()}"],
        )
    register_secret(value)
    return value


def register_secret(value: str) -> None:
    """Feed a resolved credential to the active reporter, the moment it exists."""
    reporter = active_reporter()
    if reporter is not None:
        with contextlib.suppress(TooShortToRedact):
            reporter.secret(value)


async def apply(
    profile: Profile,
    *,
    method: str,
    url: str,
    query: dict[str, Any] | None = None,
    body: Any = None,
) -> Applied:
    """Resolve ``profile`` into headers/query for one outgoing request.

    Network-touching kinds (`oauth2_client_credentials`) and signing kinds (`hmac`,
    which needs the request's own method/url/body to sign) are dispatched to their own
    modules; everything else is a pure lookup.
    """
    if profile.kind == "bearer":
        assert profile.secret is not None
        token = _secret(profile.secret, env=profile.env, label="bearer token")
        return Applied(headers={"Authorization": f"Bearer {token}"})

    if profile.kind == "basic":
        import base64

        assert profile.secret is not None
        password = _secret(profile.secret, env=profile.env, label="password")
        username = profile.username
        if profile.username_secret:
            username = _secret(profile.username_secret, env=profile.env, label="username")
        if username is None:
            raise ValidationError(f"auth.{profile.name} has no username")
        token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        return Applied(headers={"Authorization": f"Basic {token}"})

    if profile.kind == "api_key":
        assert profile.secret is not None
        value = _secret(profile.secret, env=profile.env, label="api key")
        if profile.location == "query":
            assert profile.query_name is not None
            return Applied(query={profile.query_name: value})
        header = profile.header or "X-Api-Key"
        return Applied(headers={header: value})

    if profile.kind == "header":
        assert profile.secret is not None and profile.header is not None
        value = _secret(profile.secret, env=profile.env, label="header value")
        return Applied(headers={profile.header: f"{profile.prefix}{value}"})

    if profile.kind == "oauth2_client_credentials":
        from sclpl.project import oauth

        token = await oauth.token_for(profile)
        return Applied(headers={"Authorization": f"Bearer {token}"})

    if profile.kind == "hmac":
        from sclpl.project import signing

        return Applied(
            headers=signing.sign(profile, method=method, url=url, query=query, body=body)
        )

    raise ValidationError(  # pragma: no cover
        f"auth.{profile.name} has unhandled type {profile.kind!r}"
    )
