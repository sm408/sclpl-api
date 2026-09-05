"""B6 — HMAC request signing.

One documented canonical form, so a byte-exact test vector means something: method,
path, a deterministic query string, a body digest, and a timestamp, joined by newlines
and signed with HMAC-SHA256. Vendor-specific schemes are a different `algorithm`
dispatched from `sign`, not a rewrite of the canonicalization -- there is exactly one
canonical form here because a second one is how two auth profiles disagree about what
was actually signed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from sclpl.errors import ValidationError

if TYPE_CHECKING:
    from sclpl.project.auth import Profile


def canonical_string(
    *, method: str, path: str, query: dict[str, Any], body: Any, timestamp: str
) -> str:
    """The exact bytes signed. Exposed so vendor extensions can reuse it verbatim."""
    ordered_query = "&".join(f"{key}={query[key]}" for key in sorted(query))
    body_digest = hashlib.sha256(_body_bytes(body)).hexdigest()
    return "\n".join([method.upper(), path, ordered_query, body_digest, timestamp])


def _body_bytes(body: Any) -> bytes:
    if body is None:
        return b""
    if isinstance(body, (bytes, bytearray)):
        return bytes(body)
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(
    profile: Profile,
    *,
    method: str,
    url: str,
    query: dict[str, Any] | None = None,
    body: Any = None,
    clock: Callable[[], float] = time.time,
) -> dict[str, str]:
    """Headers to add for this one request: a timestamp and its signature.

    A fresh timestamp every call, never reused across a retry -- a signature over a
    stale timestamp a server has already seen is indistinguishable from a replay.
    """
    from sclpl.project.auth import register_secret
    from sclpl.state import secrets as store

    if profile.algorithm != "sha256":
        raise ValidationError(
            f"auth.{profile.name} uses unsupported algorithm {profile.algorithm!r}",
            remedies=["only 'sha256' is implemented"],
        )
    assert profile.secret is not None
    key = store.get(profile.secret, env=profile.env)
    if key is None:
        raise ValidationError(f"no secret named {profile.secret!r}, needed to sign requests")
    register_secret(key)

    path = urlsplit(url).path or "/"
    timestamp = str(int(clock()))
    message = canonical_string(
        method=method, path=path, query=query or {}, body=body, timestamp=timestamp
    )
    signature = hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        profile.timestamp_header: timestamp,
        (profile.header or "X-Signature"): f"{profile.prefix}{signature}",
    }
