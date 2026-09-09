"""Generic resource staging and publication, deliberately provider-agnostic."""

from __future__ import annotations

import io
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sclpl.errors import CacheMiss
from sclpl.ext.resources import (
    ResourceConflict,
    ResourceNotFound,
    ResourceRef,
    display_resource_uri,
    resource_provider,
)
from sclpl.run.ports import Bindings
from sclpl.state.db import default_root, file_digest
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
    run_id: str
    journal_root: Path
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
    prepared = PreparedResources(
        staging,
        run_id,
        (root or default_root()) / "resource-publications",
    )
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
    journal = _write_pending(prepared, overwrite)
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
        _mark_published(journal, output.port, info.revision)
    journal.unlink(missing_ok=True)


@dataclass(frozen=True, slots=True)
class RemoteRecoveryReport:
    found: bool
    completed: tuple[str, ...] = ()
    already_published: tuple[str, ...] = ()


def recover(run_id: str, *, root: Path | None = None) -> RemoteRecoveryReport:
    """Retry a fixed-output publication only when its staged evidence is intact."""
    path = (root or default_root()) / "resource-publications" / f"{run_id}.pending.json"
    if not path.is_file():
        return RemoteRecoveryReport(found=False)
    payload = json.loads(path.read_text(encoding="utf-8"))
    completed: list[str] = []
    already: list[str] = []
    for port, item in sorted(payload["outputs"].items()):
        provider = resource_provider(item["uri"])
        published = item.get("published")
        if published:
            revision = item.get("published_revision")
            if not isinstance(revision, str):
                raise ResourceConflict(
                    f"remote recovery {run_id}: published output {port!r} lacks revision"
                )
            if provider.stat(item["uri"]).revision != revision:
                raise ResourceConflict(
                    f"remote recovery {run_id}: published destination {port!r} changed"
                )
            already.append(port)
            continue
        staged = Path(item["staged"])
        if not staged.is_file() or file_digest(staged) != item["digest"]:
            raise ResourceConflict(
                f"remote recovery {run_id}: staged output {port!r} is unavailable"
            )
        with staged.open("rb") as source:
            info = provider.upload(
                source,
                item["uri"],
                overwrite=bool(payload["overwrite"]),
                expected_revision=item.get("expected_revision"),
            )
        _mark_published(path, port, info.revision)
        completed.append(port)
    path.unlink(missing_ok=True)
    return RemoteRecoveryReport(True, tuple(completed), tuple(already))


def _pending_path(prepared: PreparedResources) -> Path:
    return prepared.journal_root / f"{prepared.run_id}.pending.json"


def _write_pending(prepared: PreparedResources, overwrite: bool) -> Path:
    path = _pending_path(prepared)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "overwrite": overwrite,
        "outputs": {
            output.port: {
                "uri": display_resource_uri(output.destination.uri),
                "staged": str(output.staged),
                "digest": file_digest(output.staged),
                "expected_revision": output.expected_revision,
            }
            for output in prepared.outputs
            if output.staged.is_file()
        },
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
    return path


def _mark_published(path: Path, port: str, revision: str | None) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["outputs"][port]["published"] = True
    payload["outputs"][port]["published_revision"] = revision
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def publish_generation(prepared: PreparedResources, *, run_id: str) -> None:
    """Publish remote outputs as immutable objects, then advance each latest manifest.

    A failed generation can leave unreachable objects behind, but never a manifest
    pointing at a partial set. Readers that follow ``latest.json`` therefore see only
    completed generations.
    """
    groups: dict[str, list[RemoteOutput]] = {}
    for output in prepared.outputs:
        groups.setdefault(_parent_uri(output.destination.uri), []).append(output)
    for parent, outputs in sorted(groups.items()):
        entries: dict[str, str] = {}
        provider = resource_provider(outputs[0].destination.uri)
        for output in sorted(outputs, key=lambda item: item.port):
            target, relative = _generation_uri(output.destination.uri, run_id)
            with output.staged.open("rb") as source:
                info = provider.upload(source, target, overwrite=False)
            output.destination.revision = info.revision
            entries[output.port] = relative
        manifest_uri = f"{parent}/latest.json"
        try:
            expected = provider.stat(manifest_uri).revision
        except ResourceNotFound:
            expected = None
        payload = json.dumps({"generation": run_id, "outputs": entries}, sort_keys=True).encode()
        provider.upload(
            io.BytesIO(payload), manifest_uri, overwrite=True, expected_revision=expected
        )


def _parent_uri(uri: str) -> str:
    parsed = urlsplit(uri)
    parent, _, _ = parsed.path.rpartition("/")
    return urlunsplit((parsed.scheme, parsed.netloc, parent, parsed.query, ""))


def _generation_uri(uri: str, run_id: str) -> tuple[str, str]:
    parsed = urlsplit(uri)
    parent, _, name = parsed.path.rpartition("/")
    relative = f"generations/{run_id}/{name}"
    return urlunsplit(
        (parsed.scheme, parsed.netloc, f"{parent}/{relative}", parsed.query, "")
    ), relative
