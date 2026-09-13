"""H4: a client for a versioned static package index -- local directory or HTTPS.

This is a client and a documented hosting layout, not a new registry server: the
index is one JSON file an existing team CI/storage tool can publish (H5), and this
module only ever reads it. Credentials never enter the index or the on-disk cache;
a private HTTPS registry authenticates via a bearer token read from the environment.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from sclpl.errors import CacheMiss, ValidationError

INDEX_NAME = "index.json"
SCHEMA_VERSION = 1
#: Read by the registry client only -- never logged, never written to the index
#: or the local cache, and never accepted from a workflow or project manifest.
TOKEN_ENV = "SCLPL_REGISTRY_TOKEN"


@dataclass(frozen=True, slots=True)
class IndexEntry:
    name: str
    version: str
    digest: str
    url: str


@dataclass(frozen=True, slots=True)
class FetchResult:
    path: Path
    name: str
    version: str
    digest: str


def load_index(base: str) -> dict[tuple[str, str], IndexEntry]:
    """Read a registry's index from a local directory path or an `https://` base."""
    raw = _read_index(base)
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA_VERSION:
        raise ValidationError(f"unsupported registry index schema at {base}")
    packages = raw.get("packages")
    if not isinstance(packages, dict):
        raise ValidationError(f"registry index at {base} is missing 'packages'")

    entries: dict[tuple[str, str], IndexEntry] = {}
    for name, versions in packages.items():
        if not isinstance(name, str) or not isinstance(versions, dict):
            raise ValidationError(f"malformed registry index entry {name!r} at {base}")
        for version, info in versions.items():
            if not isinstance(version, str) or not isinstance(info, dict):
                raise ValidationError(f"malformed registry index entry {name!r} at {base}")
            digest, url = info.get("digest"), info.get("url")
            if not isinstance(digest, str) or not isinstance(url, str):
                raise ValidationError(
                    f"registry index entry {name}=={version} needs digest and url", where=base
                )
            entries[(name, version)] = IndexEntry(name, version, digest, url)
    return entries


def fetch(
    base: str,
    name: str,
    version: str,
    *,
    cache: Path,
    offline: bool = False,
) -> FetchResult:
    """Resolve one `name`/`version` against a registry index and return a local file.

    The downloaded (or cached) artifact's own bytes are hashed and compared against
    the index's declared digest before this returns -- a registry serving a
    different, still internally well-formed package than it advertised is refused,
    not silently trusted. Offline mode never contacts the registry at all.
    """
    cache.mkdir(parents=True, exist_ok=True)
    if offline:
        cached = _cached_path(cache, name, version)
        if cached is None:
            raise CacheMiss(
                f"{name} {version} is not cached and --offline forbids fetching it",
                remedies=["run once without --offline to fetch and cache it"],
            )
        return FetchResult(cached, name, version, hashlib.sha256(cached.read_bytes()).hexdigest())

    entries = load_index(base)
    entry = entries.get((name, version))
    if entry is None:
        raise ValidationError(f"{name} {version} is not in the registry index at {base}")

    destination = cache / f"{name}-{version}-{entry.digest[:16]}.sclplpkg"
    if not destination.is_file():
        _download(base, entry, destination)

    actual = hashlib.sha256(destination.read_bytes()).hexdigest()
    if actual != entry.digest:
        destination.unlink(missing_ok=True)
        raise ValidationError(
            f"{name} {version} does not match the registry's declared digest "
            "(the artifact was altered, or the download was corrupted)",
            where=base,
        )
    return FetchResult(destination, name, version, entry.digest)


def _cached_path(cache: Path, name: str, version: str) -> Path | None:
    matches = sorted(cache.glob(f"{name}-{version}-*.sclplpkg"))
    return matches[-1] if matches else None


def _download(base: str, entry: IndexEntry, destination: Path) -> None:
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    if _is_url(base):
        _download_https(urljoin(base if base.endswith("/") else base + "/", entry.url), temporary)
    else:
        source = Path(base) / entry.url
        if not source.is_file():
            raise ValidationError(f"registry artifact {entry.url!r} not found under {base}")
        shutil.copyfile(source, temporary)
    temporary.replace(destination)


def _download_https(url: str, destination: Path) -> None:
    headers = {}
    token = os.environ.get(TOKEN_ENV)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with httpx.stream("GET", url, headers=headers, follow_redirects=True) as response:
            response.raise_for_status()
            with destination.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
    except httpx.HTTPError as error:
        raise ValidationError(f"could not fetch {url}: {error}") from error


def _read_index(base: str) -> object:
    if _is_url(base):
        url = urljoin(base if base.endswith("/") else base + "/", INDEX_NAME)
        headers = {}
        token = os.environ.get(TOKEN_ENV)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = httpx.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise ValidationError(f"could not fetch registry index at {url}: {error}") from error
        return response.json()

    path = Path(base) / INDEX_NAME
    if not path.is_file():
        raise ValidationError(f"no {INDEX_NAME} found under {base}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValidationError(f"invalid {INDEX_NAME}: {error}", where=str(path)) from error


def _is_url(base: str) -> bool:
    return urlsplit(base).scheme in ("http", "https")
