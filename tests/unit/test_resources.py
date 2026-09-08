from __future__ import annotations

import io
from collections.abc import Generator
from pathlib import Path
from typing import BinaryIO

import pytest
from _pytest.monkeypatch import MonkeyPatch

from sclpl import bootstrap
from sclpl.catalog.resolve import resolve
from sclpl.errors import UnknownTarget
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
from sclpl.render.plain import PlainSink
from sclpl.render.reporter import Reporter
from sclpl.run.ir import Port, WorkflowDoc
from sclpl.run.ports import bind
from sclpl.run.resources import prepare, publish
from sclpl.run.runner import Options, run_workflow
from sclpl.run.sclpll import parse


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

    def download(self, uri: str, target: BinaryIO) -> ResourceInfo:
        if uri not in self.objects:
            from sclpl.ext.resources import ResourceNotFound

            raise ResourceNotFound(f"missing {uri}")
        target.write(self.objects[uri])
        return ResourceInfo(uri=uri)

    def upload(
        self,
        source: BinaryIO,
        uri: str,
        *,
        overwrite: bool = False,
        expected_revision: str | None = None,
    ) -> ResourceInfo:
        if uri in self.objects and not overwrite:
            raise ResourceConflict("already exists")
        self.objects[uri] = source.read()
        return ResourceInfo(uri=uri)

    def display_uri(self, uri: str) -> str:
        return uri


@pytest.fixture(autouse=True)
def providers() -> Generator[None, None, None]:
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


def test_remote_bundle_loads_and_preserves_its_logical_origin(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    register_resource_provider(
        "memory", Memory({"memory://jobs/orders/workflow.sclpll": b"@workflow orders\n"})
    )
    located = resolve("memory://jobs/orders/")
    assert located.doc.name == "orders"
    assert located.origin_uri == "memory://jobs/orders/workflow.sclpll"


def test_remote_bundle_refuses_ambiguous_workflow_surfaces(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    register_resource_provider(
        "memory",
        Memory(
            {
                "memory://jobs/orders/workflow.sclpll": b"@workflow orders\n",
                "memory://jobs/orders/workflow.json": b'{"name": "orders"}',
            }
        ),
    )
    with pytest.raises(UnknownTarget, match="ambiguous"):
        resolve("memory://jobs/orders/")


def test_remote_inputs_materialize_and_outputs_publish_through_provider(tmp_path: Path) -> None:
    provider = Memory({"memory://jobs/orders/inputs/customers.csv": b"id\n1\n"})
    register_resource_provider("memory", provider)
    doc = WorkflowDoc(
        name="orders",
        inputs=[Port(name="customers", format="csv")],
        outputs=[Port(name="report", format="csv")],
    )
    bindings = bind(doc, resource_base="memory://jobs/orders/")
    prepared = prepare(bindings, run_id="resource-test", root=tmp_path / "stage")
    input_path = bindings.inputs["customers"].path
    output_path = bindings.outputs["report"].path
    assert input_path is not None and output_path is not None
    assert input_path.read_bytes() == b"id\n1\n"
    output_path.write_bytes(b"id\n2\n")
    publish(prepared, overwrite=False)
    assert provider.objects["memory://jobs/orders/outputs/report.csv"] == b"id\n2\n"


def test_missing_optional_remote_input_remains_unbound(tmp_path: Path) -> None:
    register_resource_provider("memory", Memory())
    doc = WorkflowDoc(name="orders", inputs=[Port(name="notes", format="json", required=False)])
    bindings = bind(doc, resource_base="memory://jobs/orders/")
    prepare(bindings, run_id="optional-resource", root=tmp_path / "stage")
    assert bindings.inputs["notes"].paths == []


def test_remote_create_only_publication_refuses_a_racing_destination(tmp_path: Path) -> None:
    provider = Memory({"memory://jobs/orders/outputs/report.csv": b"old\n"})
    register_resource_provider("memory", provider)
    doc = WorkflowDoc(name="orders", outputs=[Port(name="report", format="csv")])
    bindings = bind(doc, resource_base="memory://jobs/orders/")
    prepared = prepare(bindings, run_id="conflict-resource", root=tmp_path / "stage")
    output_path = bindings.outputs["report"].path
    assert output_path is not None
    output_path.write_bytes(b"new\n")
    with pytest.raises(ResourceConflict):
        publish(prepared, overwrite=False)


@pytest.mark.asyncio
async def test_a_remote_output_runs_through_the_existing_writer_then_publishes(
    tmp_path: Path,
) -> None:
    bootstrap.load(plugins=False)
    provider = Memory()
    register_resource_provider("memory", provider)
    doc = parse(
        '@workflow orders\n\n@output report:csv\n\n@step rows\n  let [{"n": 1}]\n'
        "@step write -> report\n  save_csv @rows\n"
    )
    async with Reporter([PlainSink(io.StringIO(), verbosity=-2)]) as reporter:
        result = await run_workflow(
            doc,
            Options(
                resource_base="memory://jobs/orders/",
                record=False,
                no_cache=True,
                scratch_dir=tmp_path / "run",
            ),
            reporter,
        )
    assert result.ok
    assert (
        provider.objects["memory://jobs/orders/outputs/report.csv"].replace(b"\r\n", b"\n")
        == b"n\n1\n"
    )
