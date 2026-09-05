"""B5 — OAuth2 client credentials.

One process-wide token cache, keyed by token endpoint and client, so that a hundred
concurrent steps sharing an auth profile make one token request rather than a hundred.
The lock is per key: acquiring a token for one profile never blocks a concurrent
acquisition for a different one. A rejection (the token endpoint refusing the client,
or the API refusing the token) invalidates the cache entry and is retried exactly
once by the caller (`sclpl/run/execute.py`) -- never in a loop here, because an
endpoint that keeps saying no is a configuration problem, not a transient one.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

from sclpl.errors import StepFailed

if TYPE_CHECKING:
    from sclpl.project.auth import Profile

#: Refresh this much before the token actually expires, so a request in flight does
#: not present a token that dies mid-request.
SKEW_SECONDS = 30.0


@dataclass(slots=True)
class _Entry:
    token: str
    expires_at: float


_cache: dict[str, _Entry] = {}
_locks: dict[str, asyncio.Lock] = {}


def _cache_key(profile: Profile) -> str:
    return f"{profile.token_url}|{profile.client_id_secret}|{profile.env}"


def invalidate(profile: Profile) -> None:
    """Forget a cached token -- the API just told us it is no longer good."""
    _cache.pop(_cache_key(profile), None)


async def token_for(profile: Profile, *, clock: Callable[[], float] = time.monotonic) -> str:
    """A valid access token, fetching or refreshing one if needed.

    Checked once before the lock (the common case: a valid token already cached) and
    once after acquiring it (another coroutine may have refreshed it while this one
    waited) -- so a valid token never blocks on a lock at all, and two coroutines that
    both saw it expired do one fetch between them, not two.
    """
    key = _cache_key(profile)
    entry = _cache.get(key)
    if entry is not None and entry.expires_at - SKEW_SECONDS > clock():
        return entry.token

    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        entry = _cache.get(key)
        if entry is not None and entry.expires_at - SKEW_SECONDS > clock():
            return entry.token
        entry = await _fetch(profile, clock=clock)
        _cache[key] = entry
        return entry.token


async def _fetch(profile: Profile, *, clock: Callable[[], float]) -> _Entry:
    from sclpl.project.auth import register_secret
    from sclpl.state import secrets as store

    assert profile.token_url and profile.client_id_secret and profile.client_secret_secret
    client_id = store.get(profile.client_id_secret, env=profile.env)
    client_secret = store.get(profile.client_secret_secret, env=profile.env)
    if client_id is None or client_secret is None:
        missing = profile.client_id_secret if client_id is None else profile.client_secret_secret
        raise StepFailed(
            f"no secret named {missing!r}, needed by auth.{profile.name}",
            remedies=[f"sclpl secret set {missing}"],
        )
    register_secret(client_id)
    register_secret(client_secret)

    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    if profile.scope:
        data["scope"] = profile.scope

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(profile.token_url, data=data)
        except httpx.HTTPError as error:
            raise StepFailed(
                f"auth.{profile.name} could not reach its token endpoint: {error}"
            ) from error

    if response.status_code >= 400:
        raise StepFailed(
            f"auth.{profile.name} was rejected by its token endpoint ({response.status_code})",
            remedies=[
                "check the client id/secret",
                "the endpoint's own error: " + response.text[:200],
            ],
        )
    try:
        payload = response.json()
        access_token = str(payload["access_token"])
        expires_in = float(payload.get("expires_in", 3600))
    except (ValueError, KeyError, TypeError) as error:
        raise StepFailed(
            f"auth.{profile.name}'s token endpoint returned an unexpected body"
        ) from error

    register_secret(access_token)
    return _Entry(token=access_token, expires_at=clock() + expires_in)
