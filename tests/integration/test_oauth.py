"""B5 — OAuth2 client credentials against a real local token endpoint.

`conftest.py`'s `/oauth/token` issues an incrementing `tok-N` and counts issuances per
client, which is what lets these prove *sharing*, not just correctness: a hundred
concurrent callers of a still-valid token must see one issuance, not a hundred.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from sclpl.errors import StepFailed
from sclpl.project import auth, oauth
from sclpl.state import secrets as store
from tests.integration.conftest import OAUTH_ISSUED


@pytest.fixture(autouse=True)
def no_backends(monkeypatch: Any) -> None:
    monkeypatch.setattr(store, "_keyring", lambda: None)
    monkeypatch.setattr(store, "_fernet", lambda: None)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    oauth._cache.clear()  # noqa: SLF001 - tests own the module's cache lifetime
    oauth._locks.clear()  # noqa: SLF001


def profile_for(server_url: str, *, ttl: int | None = None) -> auth.Profile:
    token_url = f"{server_url}/oauth/token"
    if ttl is not None:
        token_url += f"?ttl={ttl}"
    return auth.Profile(
        name="oauth",
        kind="oauth2_client_credentials",
        token_url=token_url,
        client_id_secret="cid",
        client_secret_secret="csecret",
    )


async def test_a_valid_client_gets_a_token(server_url: str, monkeypatch: Any) -> None:
    monkeypatch.setenv("SCLPL_SECRET_CID", "client-a")
    monkeypatch.setenv("SCLPL_SECRET_CSECRET", "secret-a")
    token = await oauth.token_for(profile_for(server_url))
    assert token == "tok-1"


async def test_an_invalid_client_is_a_clear_failure(server_url: str, monkeypatch: Any) -> None:
    monkeypatch.setenv("SCLPL_SECRET_CID", "wrong")
    monkeypatch.setenv("SCLPL_SECRET_CSECRET", "also-wrong")
    with pytest.raises(StepFailed, match="rejected"):
        await oauth.token_for(profile_for(server_url))


async def test_a_cached_token_is_reused_without_a_second_request(
    server_url: str, monkeypatch: Any
) -> None:
    monkeypatch.setenv("SCLPL_SECRET_CID", "client-a")
    monkeypatch.setenv("SCLPL_SECRET_CSECRET", "secret-a")
    profile = profile_for(server_url)
    first = await oauth.token_for(profile)
    second = await oauth.token_for(profile)
    assert first == second
    assert OAUTH_ISSUED["client-a"] == 1


async def test_concurrent_callers_share_one_issuance(server_url: str, monkeypatch: Any) -> None:
    monkeypatch.setenv("SCLPL_SECRET_CID", "client-a")
    monkeypatch.setenv("SCLPL_SECRET_CSECRET", "secret-a")
    profile = profile_for(server_url)
    tokens = await asyncio.gather(*(oauth.token_for(profile) for _ in range(20)))
    assert len(set(tokens)) == 1
    assert OAUTH_ISSUED["client-a"] == 1


async def test_an_expired_token_is_refreshed(server_url: str, monkeypatch: Any) -> None:
    monkeypatch.setenv("SCLPL_SECRET_CID", "client-a")
    monkeypatch.setenv("SCLPL_SECRET_CSECRET", "secret-a")
    profile = profile_for(server_url, ttl=3600)
    # token_for calls clock() once to fetch, then up to twice to check expiry before
    # refetching: [issue at t=0, expiry check, expiry check inside the lock, refetch].
    clock = iter([0.0, 10_000.0, 10_000.0, 10_000.0])
    first = await oauth.token_for(profile, clock=lambda: next(clock))
    second = await oauth.token_for(profile, clock=lambda: next(clock))
    assert first == "tok-1"
    assert second == "tok-2"
    assert OAUTH_ISSUED["client-a"] == 2


async def test_invalidate_forces_the_next_call_to_refetch(
    server_url: str, monkeypatch: Any
) -> None:
    monkeypatch.setenv("SCLPL_SECRET_CID", "client-a")
    monkeypatch.setenv("SCLPL_SECRET_CSECRET", "secret-a")
    profile = profile_for(server_url)
    await oauth.token_for(profile)
    oauth.invalidate(profile)
    await oauth.token_for(profile)
    assert OAUTH_ISSUED["client-a"] == 2


async def test_auth_apply_reflects_an_invalidated_and_refreshed_token(
    server_url: str, monkeypatch: Any
) -> None:
    """The 401-triggered retry-once policy lives in `execute.py`; here, that the
    profile-level primitive it depends on -- invalidate, then resolve again -- works.
    """
    monkeypatch.setenv("SCLPL_SECRET_CID", "client-a")
    monkeypatch.setenv("SCLPL_SECRET_CSECRET", "secret-a")
    profile = profile_for(server_url)
    applied = await auth.apply(profile, method="GET", url=f"{server_url}/echo-auth")
    assert applied.headers == {"Authorization": "Bearer tok-1"}
    oauth.invalidate(profile)
    applied_again = await auth.apply(profile, method="GET", url=f"{server_url}/echo-auth")
    assert applied_again.headers == {"Authorization": "Bearer tok-2"}
