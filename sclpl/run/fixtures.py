"""Versioned, content-addressed HTTP fixtures for recording and offline replay."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sclpl.errors import ValidationError

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class Fixture:
    method: str
    url: str
    occurrence: int
    status: int
    headers: dict[str, str]
    body: bytes


def fingerprint(method: str, url: str, *, occurrence: int = 0) -> str:
    """Identity preserves the request spelling and repeated-call occurrence."""
    payload = f"{method.upper()}\x00{url}\x00{occurrence}".encode()
    return hashlib.sha256(payload).hexdigest()


class Store:
    """Fixture metadata plus detached, verified response-body blobs."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.blobs = root / "blobs"
        self.blobs.mkdir(parents=True, exist_ok=True)

    def record(self, fixture: Fixture) -> Path:
        digest = hashlib.sha256(fixture.body).hexdigest()
        blob = self.blobs / digest
        if not blob.exists():
            temporary = blob.with_suffix(".partial")
            temporary.write_bytes(fixture.body)
            temporary.replace(blob)
        payload = {
            "schema": SCHEMA_VERSION,
            "method": fixture.method.upper(),
            "url": fixture.url,
            "occurrence": fixture.occurrence,
            "status": fixture.status,
            "headers": _safe_headers(fixture.headers),
            "body_digest": digest,
        }
        path = (
            self.root
            / f"{fingerprint(fixture.method, fixture.url, occurrence=fixture.occurrence)}.json"
        )
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def replay(self, method: str, url: str, *, occurrence: int = 0) -> Fixture:
        path = self.root / f"{fingerprint(method, url, occurrence=occurrence)}.json"
        if not path.is_file():
            raise ValidationError(
                "fixture mismatch", remedies=["record this request", "check request occurrence"]
            )
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA_VERSION:
            raise ValidationError(f"unsupported fixture schema at {path}")
        digest = payload.get("body_digest")
        if not isinstance(digest, str):
            raise ValidationError(f"fixture body digest missing at {path}")
        body = (self.blobs / digest).read_bytes()
        if hashlib.sha256(body).hexdigest() != digest:
            raise ValidationError(f"fixture body digest mismatch at {path}")
        return Fixture(
            method=str(payload["method"]),
            url=str(payload["url"]),
            occurrence=int(payload["occurrence"]),
            status=int(payload["status"]),
            headers=dict(payload["headers"]),
            body=body,
        )


def _safe_headers(headers: dict[str, str]) -> dict[str, str]:
    forbidden = {"authorization", "cookie", "proxy-authorization"}
    return {name: value for name, value in headers.items() if name.lower() not in forbidden}
