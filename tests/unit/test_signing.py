"""B6 — HMAC signing: canonical form and byte-exact vectors.

A signer whose canonical string moves under it is a signer nobody can reproduce
against; these pin the exact bytes signed so a future refactor that changes them is
caught here rather than as a mysterious signature mismatch against a real vendor.
"""

from __future__ import annotations

import hashlib
import hmac as hmac_lib
from typing import Any

import pytest

from sclpl.errors import ValidationError
from sclpl.project import auth, signing
from sclpl.state import secrets as store


@pytest.fixture(autouse=True)
def no_backends(monkeypatch: Any) -> None:
    monkeypatch.setattr(store, "_keyring", lambda: None)
    monkeypatch.setattr(store, "_fernet", lambda: None)


def test_canonical_string_is_method_path_query_body_digest_timestamp() -> None:
    message = signing.canonical_string(
        method="post",
        path="/v1/orders",
        query={"b": 2, "a": 1},
        body={"total": 10},
        timestamp="1700000000",
    )
    expected_digest = hashlib.sha256(b'{"total":10}').hexdigest()
    assert message == f"POST\n/v1/orders\na=1&b=2\n{expected_digest}\n1700000000"


def test_an_empty_body_still_has_a_stable_digest() -> None:
    message = signing.canonical_string(method="GET", path="/x", query={}, body=None, timestamp="1")
    assert message == f"GET\n/x\n\n{hashlib.sha256(b'').hexdigest()}\n1"


def test_byte_exact_signature_vector(monkeypatch: Any) -> None:
    """One fixed vector, so a canonicalization change is caught immediately."""
    monkeypatch.setenv("SCLPL_SECRET_KEY", "correct-horse-battery-staple")
    profile = auth.Profile(name="signed", kind="hmac", secret="key")
    headers = signing.sign(
        profile,
        method="GET",
        url="https://api.test/v1/things?z=1",
        query={"z": 1},
        body=None,
        clock=lambda: 1700000000.0,
    )
    message = signing.canonical_string(
        method="GET", path="/v1/things", query={"z": 1}, body=None, timestamp="1700000000"
    )
    expected = hmac_lib.new(
        b"correct-horse-battery-staple", message.encode(), hashlib.sha256
    ).hexdigest()
    assert headers == {"X-Timestamp": "1700000000", "X-Signature": expected}


def test_a_custom_header_and_prefix_are_honored(monkeypatch: Any) -> None:
    monkeypatch.setenv("SCLPL_SECRET_KEY", "correct-horse-battery-staple")
    profile = auth.Profile(
        name="signed",
        kind="hmac",
        secret="key",
        header="X-My-Sig",
        prefix="sig=",
        timestamp_header="X-My-Time",
    )
    headers = signing.sign(profile, method="GET", url="https://api.test/x", clock=lambda: 5.0)
    assert set(headers) == {"X-My-Time", "X-My-Sig"}
    assert headers["X-My-Sig"].startswith("sig=")


def test_an_unsupported_algorithm_is_refused(monkeypatch: Any) -> None:
    monkeypatch.setenv("SCLPL_SECRET_KEY", "x-distinctive-enough")
    profile = auth.Profile(name="signed", kind="hmac", secret="key", algorithm="sha1")
    with pytest.raises(ValidationError, match="unsupported algorithm"):
        signing.sign(profile, method="GET", url="https://api.test/x")


def test_a_missing_signing_secret_is_a_clear_error() -> None:
    profile = auth.Profile(name="signed", kind="hmac", secret="absent")
    with pytest.raises(ValidationError, match="absent"):
        signing.sign(profile, method="GET", url="https://api.test/x")


def test_two_calls_a_moment_apart_get_different_timestamps_and_signatures(
    monkeypatch: Any,
) -> None:
    """A signature over a reused timestamp is indistinguishable from a replay."""
    monkeypatch.setenv("SCLPL_SECRET_KEY", "correct-horse-battery-staple")
    profile = auth.Profile(name="signed", kind="hmac", secret="key")
    clocks = iter([100.0, 200.0])
    tick = lambda: next(clocks)  # noqa: E731
    first = signing.sign(profile, method="GET", url="https://api.test/x", clock=tick)
    second = signing.sign(profile, method="GET", url="https://api.test/x", clock=tick)
    assert first != second
