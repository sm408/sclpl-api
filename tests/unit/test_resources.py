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
from sclpl.run.ir import Port, WorkflowDoc
from sclpl.run.ports import bind
from sclpl.run.resources import prepare, publish


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
        if uri in self.objects and not overwrite:
            raise ResourceConflict("already exists")
        self.objects[uri] = source.read()
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


def test_remote_inputs_materialize_and_outputs_publish_through_provider(tmp_path) -> None:
    provider = Memory({"memory://jobs/orders/inputs/customers.csv": b"id\n1\n"})
    register_resource_provider("memory", provider)
    doc = WorkflowDoc(
        name="orders",
        inputs=[Port(name="customers", format="csv")],
        outputs=[Port(name="report", format="csv")],
    )
    bindings = bind(doc, resource_base="memory://jobs/orders/")
    prepared = prepare(bindings, run_id="resource-test", root=tmp_path / "stage")
    assert bindings.inputs["customers"].path.read_bytes() == b"id\n1\n"
    bindings.outputs["report"].path.write_bytes(b"id\n2\n")
    publish(prepared, overwrite=False)
    assert provider.objects["memory://jobs/orders/outputs/report.csv"] == b"id\n2\n"
