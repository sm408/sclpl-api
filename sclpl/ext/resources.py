"""Provider-neutral remote resource contract exposed to plugins.

The runner deliberately depends only on these types.  Storage SDKs and their
authentication models stay in provider packages.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Protocol
from urllib.parse import urlsplit

from sclpl.errors import SclplError


class ResourceError(SclplError):
    """A provider could not complete a resource operation."""


class ResourceNotFound(ResourceError):
    """The requested logical resource does not exist."""


class ResourceAuthenticationError(ResourceError):
    """The provider could not obtain usable credentials."""


class ResourcePermissionDenied(ResourceError):
    """The identity lacks permission for the requested resource operation."""


class ResourceConflict(ResourceError):
    """A revision-aware write discovered a concurrent change."""


class ResourceUnavailable(ResourceError):
    """The provider is temporarily unavailable."""


class ResourceUnsupportedOperation(ResourceError):
    """The provider does not implement this optional operation."""


class ResourceInvalidURI(ResourceError):
    """A URI is invalid for its claimed resource scheme."""


@dataclass(slots=True)
class ResourceRef:
    """Logical identity plus the local execution path, when one is allocated."""

    uri: str
    scheme: str
    local_path: Path | None = None
    revision: str | None = None


@dataclass(frozen=True, slots=True)
class ResourceInfo:
    uri: str
    size: int | None = None
    modified: datetime | None = None
    revision: str | None = None
    content_type: str | None = None


@dataclass(frozen=True, slots=True)
class ResourceCapabilities:
    read: bool = True
    write: bool = False
    list: bool = False
    revisions: bool = False
    conditional_write: bool = False


class ResourceProvider(Protocol):
    """Stable provider boundary; implementations must not import runner internals."""

    scheme: str

    def capabilities(self) -> ResourceCapabilities: ...
    def normalize(self, uri: str) -> str: ...
    def resolve(self, base_uri: str, reference: str) -> str: ...
    def stat(self, uri: str) -> ResourceInfo: ...
    def exists(self, uri: str) -> bool: ...
    def list(self, uri: str) -> Iterable[ResourceInfo]: ...
    def download(self, uri: str, target: BinaryIO) -> ResourceInfo: ...
    def upload(
        self,
        source: BinaryIO,
        uri: str,
        *,
        overwrite: bool = False,
        expected_revision: str | None = None,
    ) -> ResourceInfo: ...
    def display_uri(self, uri: str) -> str: ...


_PROVIDERS: dict[str, ResourceProvider] = {}


def resource_scheme(uri: str) -> str | None:
    """Return a URI scheme only for provider-style ``scheme://`` references."""
    parsed = urlsplit(uri)
    return parsed.scheme.lower() if parsed.scheme and parsed.netloc else None


def register_resource_provider(scheme: str, provider: ResourceProvider) -> None:
    normalized = scheme.lower()
    if not normalized or normalized != resource_scheme(f"{normalized}://provider"):
        raise ResourceInvalidURI(f"invalid resource scheme {scheme!r}")
    existing = _PROVIDERS.get(normalized)
    if existing is not None and existing is not provider:
        raise ResourceConflict(f"resource scheme {normalized!r} is already registered")
    if provider.scheme.lower() != normalized:
        raise ResourceInvalidURI(
            f"provider scheme {provider.scheme!r} does not match registration {scheme!r}"
        )
    _PROVIDERS[normalized] = provider


def resource_provider(uri_or_scheme: str) -> ResourceProvider:
    scheme = resource_scheme(uri_or_scheme) or uri_or_scheme.lower()
    provider = _PROVIDERS.get(scheme)
    if provider is None:
        raise ResourceUnsupportedOperation(f"no resource provider registered for scheme {scheme!r}")
    return provider


def resource_ref(uri: str) -> ResourceRef:
    provider = resource_provider(uri)
    normalized = provider.normalize(uri)
    return ResourceRef(uri=normalized, scheme=provider.scheme.lower())


def display_resource_uri(uri: str) -> str:
    """Render a provider-owned URI without credentials or opaque query secrets."""
    provider = resource_provider(uri)
    return provider.display_uri(provider.normalize(uri))


def clear_resource_providers() -> None:
    """Test-only reset; not re-exported by the public plugin API."""
    _PROVIDERS.clear()
