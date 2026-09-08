"""Generic resource staging and publication, deliberately provider-agnostic."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from sclpl.ext.resources import ResourceNotFound, ResourceRef, resource_provider
from sclpl.run.ports import Bindings
from sclpl.state.db import default_root


@dataclass(slots=True)
class RemoteOutput:
    port: str
    destination: ResourceRef
    staged: Path
    expected_revision: str | None


@dataclass(slots=True)
class PreparedResources:
    root: Path
    outputs: list[RemoteOutput] = field(default_factory=list)

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def prepare(bindings: Bindings, *, run_id: str, root: Path | None = None) -> PreparedResources:
    """Materialize remote inputs and allocate local staging for remote outputs."""
    staging = root or default_root() / "tmp" / run_id
    staging.mkdir(parents=True, exist_ok=True)
    prepared = PreparedResources(staging)
    for binding in bindings.inputs.values():
        for index, ref in enumerate(binding.resources):
            provider = resource_provider(ref.uri)
            suffix = Path(ref.uri).suffix
            target = staging / "inputs" / binding.name / f"{index}{suffix}"
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                with target.open("wb") as handle:
                    info = provider.download(ref.uri, handle)
            except ResourceNotFound:
                if binding.required:
                    raise
                continue
            ref.local_path, ref.revision = target, info.revision
            binding.paths.append(target)
    for binding in bindings.outputs.values():
        for index, ref in enumerate(binding.resources):
            provider = resource_provider(ref.uri)
            try:
                before = provider.stat(ref.uri)
                ref.revision = before.revision
            except ResourceNotFound:
                ref.revision = None
            suffix = Path(ref.uri).suffix
            target = staging / "outputs" / binding.name / f"{index}{suffix}"
            target.parent.mkdir(parents=True, exist_ok=True)
            ref.local_path = target
            binding.paths.append(target)
            prepared.outputs.append(RemoteOutput(binding.name, ref, target, ref.revision))
    return prepared


def publish(prepared: PreparedResources, *, overwrite: bool) -> None:
    """Publish successful staged outputs with safe create/replace conditions."""
    for output in sorted(prepared.outputs, key=lambda item: item.port):
        provider = resource_provider(output.destination.uri)
        if not output.staged.is_file():
            continue
        with output.staged.open("rb") as source:
            info = provider.upload(
                source,
                output.destination.uri,
                overwrite=overwrite,
                expected_revision=output.expected_revision,
            )
        output.destination.revision = info.revision
