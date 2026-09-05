"""B4 — named auth profiles: parsing, resolution, and redaction.

Network-touching kinds (`oauth2_client_credentials`, and the request-shape parts of
`hmac`) are covered in `test_oauth.py` and `test_signing.py`; this file is the pure
bearer/basic/api_key/header path plus the shared parsing and validation.
"""

from __future__ import annotations

import io
from typing import Any

import pytest

from sclpl.errors import ValidationError
from sclpl.project import auth
from sclpl.render.plain import PlainSink
from sclpl.render.reporter import Reporter
from sclpl.state import secrets as store


@pytest.fixture(autouse=True)
def no_backends(monkeypatch: Any) -> None:
    monkeypatch.setattr(store, "_keyring", lambda: None)
    monkeypatch.setattr(store, "_fernet", lambda: None)


def manifest(**profiles: dict[str, Any]) -> dict[str, Any]:
    return {"auth": profiles}


# -- parsing --------------------------------------------------------------------------


def test_an_unknown_type_is_refused() -> None:
    with pytest.raises(ValidationError, match="unknown type"):
        auth.parse_profiles(manifest(default={"type": "carrier-pigeon"}))


def test_bearer_requires_a_secret() -> None:
    with pytest.raises(ValidationError, match="missing secret"):
        auth.parse_profiles(manifest(default={"type": "bearer"}))


def test_basic_requires_a_password_and_a_username() -> None:
    with pytest.raises(ValidationError, match="username"):
        auth.parse_profiles(manifest(default={"type": "basic", "secret": "pw"}))


def test_api_key_query_requires_a_parameter_name() -> None:
    with pytest.raises(ValidationError, match="name"):
        auth.parse_profiles(
            manifest(default={"type": "api_key", "secret": "k", "location": "query"})
        )


def test_default_env_falls_back_to_the_projects_selected_environment() -> None:
    profiles = auth.parse_profiles(
        manifest(default={"type": "bearer", "secret": "tok"}), default_env="staging"
    )
    assert profiles["default"].env == "staging"


def test_a_profile_can_pin_its_own_env_regardless_of_default() -> None:
    profiles = auth.parse_profiles(
        manifest(default={"type": "bearer", "secret": "tok", "env": "prod"}),
        default_env="staging",
    )
    assert profiles["default"].env == "prod"


# -- resolution -------------------------------------------------------------------------


async def test_bearer_produces_an_authorization_header(monkeypatch: Any) -> None:
    monkeypatch.setenv("SCLPL_SECRET_TOK", "sk-live-distinctive")
    profile = auth.parse_profiles(manifest(default={"type": "bearer", "secret": "tok"}))["default"]
    applied = await auth.apply(profile, method="GET", url="https://api.test/x")
    assert applied.headers == {"Authorization": "Bearer sk-live-distinctive"}


async def test_basic_encodes_username_and_password(monkeypatch: Any) -> None:
    import base64

    monkeypatch.setenv("SCLPL_SECRET_PW", "hunter2-distinctive")
    profile = auth.parse_profiles(
        manifest(default={"type": "basic", "secret": "pw", "username": "svc"})
    )["default"]
    applied = await auth.apply(profile, method="GET", url="https://api.test/x")
    expected = base64.b64encode(b"svc:hunter2-distinctive").decode()
    assert applied.headers == {"Authorization": f"Basic {expected}"}


async def test_api_key_in_query(monkeypatch: Any) -> None:
    monkeypatch.setenv("SCLPL_SECRET_K", "sk-live-distinctive")
    profile = auth.parse_profiles(
        manifest(default={"type": "api_key", "secret": "k", "location": "query", "name": "api_key"})
    )["default"]
    applied = await auth.apply(profile, method="GET", url="https://api.test/x")
    assert applied.query == {"api_key": "sk-live-distinctive"}
    assert applied.headers == {}


async def test_custom_header_with_a_prefix(monkeypatch: Any) -> None:
    monkeypatch.setenv("SCLPL_SECRET_TOK", "sk-live-distinctive")
    profile = auth.parse_profiles(
        manifest(
            default={
                "type": "header",
                "secret": "tok",
                "header": "X-Custom",
                "prefix": "Token ",
            }
        )
    )["default"]
    applied = await auth.apply(profile, method="GET", url="https://api.test/x")
    assert applied.headers == {"X-Custom": "Token sk-live-distinctive"}


async def test_a_missing_secret_names_it() -> None:
    profile = auth.parse_profiles(manifest(default={"type": "bearer", "secret": "nope"}))["default"]
    with pytest.raises(ValidationError, match="nope"):
        await auth.apply(profile, method="GET", url="https://api.test/x")


async def test_resolved_value_is_registered_for_redaction(monkeypatch: Any) -> None:
    monkeypatch.setenv("SCLPL_SECRET_TOK", "sk-live-distinctive")
    profile = auth.parse_profiles(manifest(default={"type": "bearer", "secret": "tok"}))["default"]
    async with Reporter([PlainSink(io.StringIO(), verbosity=-2)]) as reporter:
        await auth.apply(profile, method="GET", url="https://api.test/x")
        assert "sk-live-distinctive" not in reporter.scrub("token was sk-live-distinctive")


def test_target_header_identifies_what_each_kind_would_write() -> None:
    bearer = auth.Profile(name="b", kind="bearer", secret="t")
    assert bearer.target_header() == "Authorization"
    header = auth.Profile(name="h", kind="header", secret="t", header="X-Thing")
    assert header.target_header() == "X-Thing"
    query_key = auth.Profile(name="q", kind="api_key", secret="t", location="query", query_name="k")
    assert query_key.target_header() is None
