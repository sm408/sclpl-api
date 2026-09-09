"""Provider-agnostic assertions for resource-plugin authors.

These checks deliberately use a caller-provided, already-created fixture.  They
never create, overwrite, or delete remote resources, so the same suite can run
against Azurite, S3 emulators, or a real least-privilege test account.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sclpl.ext.resources import ResourceError, ResourceInfo, ResourceProvider, resource_scheme


@dataclass(frozen=True, slots=True)
class ResourceProviderFixture:
    """One existing resource and optional expectations for a contract check."""

    uri: str
    relative_reference: str | None = None
    resolved_uri: str | None = None
    missing_uri: str | None = None


def assert_resource_provider_contract(
    provider: ResourceProvider,
    fixture: ResourceProviderFixture,
) -> ResourceInfo:
    """Assert the read-only, provider-independent portion of the contract.

    Returns the fixture's ``ResourceInfo`` so a provider-specific suite can add
    assertions for ETags, metadata, version IDs, and SDK behavior.
    """
    normalized = provider.normalize(fixture.uri)
    assert resource_scheme(normalized) == provider.scheme.lower(), (
        "normalize() must return a URI with the provider's scheme"
    )
    assert provider.normalize(normalized) == normalized, "normalize() must be idempotent"
    assert provider.display_uri(normalized), "display_uri() must provide a non-empty diagnostic URI"

    if fixture.relative_reference is not None:
        assert fixture.resolved_uri is not None, "relative_reference requires resolved_uri"
        assert provider.resolve(normalized, fixture.relative_reference) == provider.normalize(
            fixture.resolved_uri
        ), "resolve() returned an unexpected logical URI"

    capabilities = provider.capabilities()
    assert capabilities.read, "the conformance fixture requires a readable provider"
    info = provider.stat(normalized)
    assert info.uri == normalized, "stat() must preserve the normalized logical URI"
    assert provider.exists(normalized), "exists() must report the stat() fixture"

    if fixture.missing_uri is not None:
        assert not provider.exists(provider.normalize(fixture.missing_uri)), (
            "exists() must return False for the supplied missing fixture"
        )
    if capabilities.list:
        listed = list(provider.list(normalized))
        assert all(item.uri == provider.normalize(item.uri) for item in listed), (
            "list() must return normalized logical URIs"
        )
    return info


def assert_resource_error(operation: Callable[[], object], expected: type[ResourceError]) -> None:
    """Assert that a provider translates a failed SDK operation to a core error."""
    try:
        operation()
    except expected:
        return
    except ResourceError as error:
        raise AssertionError(f"expected {expected.__name__}, got {type(error).__name__}") from error
    except Exception as error:
        raise AssertionError("provider leaked a non-resource exception") from error
    raise AssertionError(f"expected {expected.__name__}, but the operation succeeded")
