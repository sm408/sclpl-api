"""Content hashing.

A digest identifies a value by what it *is*, not where it came from. That is what lets
the cache key in SPEC section 12 be stable across runs and machines, and what lets a
rerun notice that an input changed.

The canonical form must be deterministic: dict ordering, float formatting, and set
ordering are all pinned here rather than left to whatever `repr` does today.
"""

from __future__ import annotations

import hashlib
from typing import Any

DIGEST_BYTES = 16
_EMPTY = "blake2b:" + hashlib.blake2b(b"", digest_size=DIGEST_BYTES).hexdigest()


def digest(value: Any) -> str:
    """A stable content digest, prefixed with the algorithm."""
    hasher = hashlib.blake2b(digest_size=DIGEST_BYTES)
    _feed(hasher, value)
    return "blake2b:" + hasher.hexdigest()


def digest_all(values: object) -> str:
    """One digest over an ordered sequence of values."""
    hasher = hashlib.blake2b(digest_size=DIGEST_BYTES)
    for item in values:  # type: ignore[attr-defined]
        hasher.update(digest(item).encode())
        hasher.update(b"\x00")
    return "blake2b:" + hasher.hexdigest()


def empty_digest() -> str:
    return _EMPTY


def _feed(hasher: Any, value: Any) -> None:
    """Write a type-tagged canonical encoding of ``value`` into ``hasher``.

    Type tags matter: without them ``"1"`` and ``1`` would collide, and a cache hit on
    the wrong type is worse than a miss.
    """
    match value:
        case None:
            hasher.update(b"n")
        case bool():
            hasher.update(b"b1" if value else b"b0")
        case int():
            hasher.update(b"i" + str(value).encode())
        case float():
            # repr round-trips exactly and is stable across platforms; str is not.
            hasher.update(b"f" + repr(value).encode())
        case str():
            encoded = value.encode("utf-8")
            hasher.update(b"s" + str(len(encoded)).encode() + b":" + encoded)
        case bytes() | bytearray():
            hasher.update(b"y" + str(len(value)).encode() + b":" + bytes(value))
        case list() | tuple():
            hasher.update(b"l" + str(len(value)).encode() + b"[")
            for item in value:
                _feed(hasher, item)
                hasher.update(b",")
            hasher.update(b"]")
        case set() | frozenset():
            # Sets have no order, so hash the members and sort the hashes.
            parts = sorted(digest(item) for item in value)
            hasher.update(b"e" + str(len(parts)).encode() + b"[")
            for part in parts:
                hasher.update(part.encode() + b",")
            hasher.update(b"]")
        case dict():
            hasher.update(b"d" + str(len(value)).encode() + b"{")
            for key in sorted(value, key=_sort_key):
                _feed(hasher, key)
                hasher.update(b"=")
                _feed(hasher, value[key])
                hasher.update(b",")
            hasher.update(b"}")
        case _:
            hasher.update(_fallback(value))


def _fallback(value: Any) -> bytes:
    """Digest an object we do not have a canonical form for.

    Prefer whatever the object offers about its own content — a Table exposes
    `content_digest` — before falling back to its type and repr.
    """
    own = getattr(value, "content_digest", None)
    if callable(own):
        try:
            return b"o" + str(own()).encode()
        except Exception:  # noqa: BLE001 - a broken digest must not fail the run
            pass
    return b"r" + type(value).__name__.encode() + b":" + repr(value).encode("utf-8", "replace")


def _sort_key(key: Any) -> tuple[str, str]:
    """Order dict keys deterministically even when they are of mixed types."""
    return (type(key).__name__, repr(key))
