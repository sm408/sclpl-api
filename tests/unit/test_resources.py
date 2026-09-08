from __future__ import annotations

from io import BytesIO

import pytest

from sclpl.catalog.resolve import resolve
from sclpl.ext.resources import (
    ResourceCapabilities,
    ResourceConflict,
    ResourceInfo,
    ResourceUnsupportedOperation,
    clear_resource_providers,
    register_resource_provider,
    resource_provider,
    resource_ref,
)


class Memory:
    scheme = "memory"

    def __init__(self, objects: dict[str, bytes] | None = None) -> None:
        self.objects = objects or {}

    def capabilities(self) -> ResourceCapabilities:
        return ResourceCapabilities(write=True, list=True, revisions=True, conditional_write=True)

    def normalize(self, uri: str) -> str:
        return uri.rstrip("/")

    def resolve(self, base_uri: str, reference: str) -> str:
        return f"{base_uri.rstrip('/')}/{reference}"

    def stat(self, uri: str) -> ResourceInfo:
        return ResourceInfo(uri=uri)

    def exists(self, uri: str) -> bool:
        return uri in self.objects

    def list(self, uri: str) -> list[ResourceInfo]:
        return []

    def download(self, uri: str, target: BytesIO) -> ResourceInfo:
        target.write(self.objects[uri])
        return ResourceInfo(uri=uri)

    def upload(self, source: BytesIO, uri: str, *, overwrite: bool = False, expected_revision: str | None = None) -> ResourceInfo:
        return ResourceInfo(uri=uri)

    def display_uri(self, uri: str) -> str:
        return uri


@pytest.fixture(autouse=True)
def providers() -> None:
    clear_resource_providers()
    yield
    clear_resource_providers()


def test_registration_is_scheme_keyed_and_normalizes_references() -> None:
    register_resource_provider("memory", Memory())
    assert resource_provider("memory://jobs/orders").scheme == "memory"
    assert resource_ref("memory://jobs/orders/").uri == "memory://jobs/orders"


def test_duplicate_scheme_is_refused_deterministically() -> None:
    register_resource_provider("memory", Memory())
    with pytest.raises(ResourceConflict, match="already registered"):
        register_resource_provider("memory", Memory())


def test_unknown_scheme_has_generic_error() -> None:
    with pytest.raises(ResourceUnsupportedOperation, match="no resource provider"):
        resource_provider("unknown://bucket/item")


def test_remote_bundle_loads_and_preserves_its_logical_origin(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    register_resource_provider(
        "memory", Memory({"memory://jobs/orders/workflow.sclpll": b"@workflow orders\n"})
    )
    located = resolve("memory://jobs/orders/")
    assert located.doc.name == "orders"
    assert located.origin_uri == "memory://jobs/orders/workflow.sclpll"
