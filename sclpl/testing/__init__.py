"""Versioned project-test manifest discovery and validation."""

from sclpl.testing.execute import Outcome, run
from sclpl.testing.manifest import Manifest, discover, load
from sclpl.testing.resources import (
    ResourceProviderFixture,
    assert_resource_error,
    assert_resource_provider_contract,
)
from sclpl.testing.select import select

__all__ = [
    "Manifest",
    "Outcome",
    "ResourceProviderFixture",
    "assert_resource_error",
    "assert_resource_provider_contract",
    "discover",
    "load",
    "run",
    "select",
]
