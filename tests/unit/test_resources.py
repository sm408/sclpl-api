from __future__ import annotations

import io
import json
from collections.abc import Generator
from pathlib import Path
from typing import BinaryIO

import pytest
from _pytest.monkeypatch import MonkeyPatch

from sclpl import bootstrap
from sclpl.catalog.resolve import resolve
from sclpl.cli.resource_cmd import doctor
from sclpl.errors import CacheMiss, UnknownTarget, ValidationError
from sclpl.ext.resources import (
    ResourceCapabilities,
    ResourceConflict,
    ResourceInfo,
    ResourceUnsupportedOperation,
    clear_resource_providers,
    copy_resource,
    register_resource_provider,
    resource_provider,
    resource_providers,
    resource_ref,
)
from sclpl.render.plain import PlainSink
from sclpl.render.reporter import Reporter
from sclpl.run.ir import Port, WorkflowDoc
from sclpl.run.ports import bind
from sclpl.run.resources import prepare, publish, publish_generation
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
        return [ResourceInfo(uri=key) for key in sorted(self.objects) if key.startswith(uri)]

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


def test_registered_resource_providers_are_stably_ordered() -> None:
    first = Memory()
    second = Memory()
    second.scheme = "archive"
    register_resource_provider("memory", first)
    register_resource_provider("archive", second)
    assert [provider.scheme for provider in resource_providers()] == ["archive", "memory"]


def test_copy_resource_streams_between_registered_providers() -> None:
    source = Memory({"memory://source/orders.csv": b"id,total\n1,42\n"})
    destination = Memory()
    destination.scheme = "archive"
    register_resource_provider("memory", source)
    register_resource_provider("archive", destination)

    copied = copy_resource("memory://source/orders.csv", "archive://warehouse/orders.csv")

    assert copied.uri == "archive://warehouse/orders.csv"
    assert destination.objects["archive://warehouse/orders.csv"] == b"id,total\n1,42\n"


def test_resource_doctor_reports_readable_provider_without_writing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    register_resource_provider("memory", Memory({"memory://jobs/object.csv": b"id\n"}))
    doctor("memory://jobs/object.csv")
    rendered = capsys.readouterr().out
    assert "authentication: usable" in rendered
    assert "write: supported" in rendered


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
    assert located.origin_revision is None


def test_remote_bundle_runs_offline_from_the_resource_cache(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    provider = Memory({"memory://jobs/orders/workflow.sclpll": b"@workflow orders\n"})
    register_resource_provider("memory", provider)

    resolve("memory://jobs/orders/")
    provider.objects.clear()
    located = resolve("memory://jobs/orders/", resource_cache_require_hit=True)

    assert located.doc.name == "orders"


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


def test_remote_input_glob_lists_matches_in_stable_order() -> None:
    register_resource_provider(
        "memory",
        Memory(
            {
                "memory://jobs/orders/inputs/events-2.json": b"[]",
                "memory://jobs/orders/inputs/events-1.json": b"[]",
                "memory://jobs/orders/inputs/ignore.csv": b"x\n",
            }
        ),
    )
    doc = WorkflowDoc(name="orders", inputs=[Port(name="events", format="json")])
    bindings = bind(
        doc,
        named_in={"events": "memory://jobs/orders/inputs/events-*.json"},
    )

    assert [ref.uri for ref in bindings.inputs["events"].resources] == [
        "memory://jobs/orders/inputs/events-1.json",
        "memory://jobs/orders/inputs/events-2.json",
    ]


def test_remote_input_glob_requires_at_least_one_match() -> None:
    register_resource_provider("memory", Memory())
    doc = WorkflowDoc(name="orders", inputs=[Port(name="events", format="json")])

    with pytest.raises(ValidationError, match="matched no resources"):
        bind(doc, named_in={"events": "memory://jobs/orders/inputs/events-*.json"})


def test_remote_input_glob_requires_provider_listing_support() -> None:
    class NoListMemory(Memory):
        def capabilities(self) -> ResourceCapabilities:
            return ResourceCapabilities()

    register_resource_provider("memory", NoListMemory())
    doc = WorkflowDoc(name="orders", inputs=[Port(name="events", format="json")])

    with pytest.raises(ResourceUnsupportedOperation, match="cannot list"):
        bind(doc, named_in={"events": "memory://jobs/orders/inputs/events-*.json"})


def test_remote_output_glob_is_refused() -> None:
    register_resource_provider("memory", Memory())
    doc = WorkflowDoc(name="orders", outputs=[Port(name="report", format="csv")])

    with pytest.raises(ValidationError, match="output pattern"):
        bind(doc, named_out={"report": "memory://jobs/orders/outputs/*.csv"})


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


def test_remote_generation_publication_advances_latest_only_after_all_outputs(
    tmp_path: Path,
) -> None:
    provider = Memory()
    register_resource_provider("memory", provider)
    doc = WorkflowDoc(
        name="orders",
        outputs=[Port(name="report", format="csv"), Port(name="summary", format="json")],
    )
    bindings = bind(doc, resource_base="memory://jobs/orders/")
    prepared = prepare(bindings, run_id="generation", root=tmp_path / "stage")
    bindings.outputs["report"].path.write_bytes(b"report")  # type: ignore[union-attr]
    bindings.outputs["summary"].path.write_bytes(b"summary")  # type: ignore[union-attr]

    publish_generation(prepared, run_id="run-123")

    root = "memory://jobs/orders/outputs"
    assert provider.objects[f"{root}/generations/run-123/report.csv"] == b"report"
    assert provider.objects[f"{root}/generations/run-123/summary.json"] == b"summary"
    assert json.loads(provider.objects[f"{root}/latest.json"]) == {
        "generation": "run-123",
        "outputs": {
            "report": "generations/run-123/report.csv",
            "summary": "generations/run-123/summary.json",
        },
    }


def test_offline_refuses_remote_output_publication(tmp_path: Path) -> None:
    register_resource_provider("memory", Memory())
    doc = WorkflowDoc(name="orders", outputs=[Port(name="report", format="csv")])
    bindings = bind(doc, resource_base="memory://jobs/orders/")
    with pytest.raises(CacheMiss, match="cannot publish"):
        prepare(bindings, run_id="offline-output", root=tmp_path / "stage", cache_require_hit=True)


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
