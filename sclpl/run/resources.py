"""Generic resource staging and publication, deliberately provider-agnostic."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from sclpl.errors import CacheMiss
from sclpl.ext.resources import ResourceNotFound, ResourceRef, resource_provider
from sclpl.run.ports import Bindings
from sclpl.state.db import default_root
from sclpl.state.resource_cache import ResourceCache


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


def prepare(
    bindings: Bindings,
    *,
    run_id: str,
    root: Path | None = None,
    cache_read: bool = True,
    cache_write: bool = True,
    cache_require_hit: bool = False,
) -> PreparedResources:
    """Materialize remote inputs and allocate local staging for remote outputs."""
    if cache_require_hit and any(binding.resources for binding in bindings.outputs.values()):
        raise CacheMiss(
            "--offline cannot publish a remote output",
            remedies=["remove --offline before publishing remote outputs"],
        )
    staging = root or default_root() / "tmp" / run_id
    staging.mkdir(parents=True, exist_ok=True)
    prepared = PreparedResources(staging)
    # An explicit staging root is an isolated test/embedding run, so keep its cache
    # alongside the staging files instead of reaching into the caller's real home.
    resource_cache = ResourceCache(root / "resource-cache" if root is not None else None)
    for binding in bindings.inputs.values():
        for index, ref in enumerate(binding.resources):
            provider = resource_provider(ref.uri)
            suffix = Path(ref.uri).suffix
            target = staging / "inputs" / binding.name / f"{index}{suffix}"
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                info = resource_cache.materialize(
                    provider,
                    ref.uri,
                    target,
                    read=cache_read,
                    write=cache_write,
                    require_hit=cache_require_hit,
                )
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
