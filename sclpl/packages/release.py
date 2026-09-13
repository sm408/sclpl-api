"""H5: stage a registry index.json and its artifacts for an existing team CI or
storage tool to publish. This never talks to a registry or uploads anything --
publication is a separate, explicit step (deploying the staged output directory
with whatever tool a team already uses), never a side effect of building an
index, building a package (H1), or installing one (H2/H4).

Origin and authenticity: a staged index only proves every artifact's bytes match
its own declared digest (the same check H2's `validate` and H4's `fetch` apply).
It says nothing about who is allowed to publish, or whether an HTTPS endpoint
serving it later is the operator's real one -- trusted hosting (HTTPS, access
control on the storage backend) remains the publishing team's responsibility.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from sclpl.errors import ValidationError
from sclpl.packages import install as install_mod
from sclpl.packages.registry import INDEX_NAME
from sclpl.packages.registry import SCHEMA_VERSION as REGISTRY_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class ReleaseResult:
    index_path: Path
    entries: tuple[tuple[str, str], ...]


def build_index(archives: list[Path], *, out: Path) -> ReleaseResult:
    """Validate and stage a set of `.sclplpkg` archives plus one `index.json`.

    Refuses a name/version claimed by two archives with different digests --
    that origin ambiguity is a real refusal, never resolved by silently keeping
    whichever archive happened to be scanned last.
    """
    out.mkdir(parents=True, exist_ok=True)
    packages: dict[str, dict[str, dict[str, str]]] = {}
    seen: dict[tuple[str, str], tuple[str, Path]] = {}

    for archive in sorted(archives):
        # Full archive-safety validation (H2) refuses a malicious or corrupt
        # archive before it can ever enter a published index. Its PackageInfo
        # digest is H1's *content* digest, an abstraction over the bundled files
        # -- not what a client downloads. The registry's own digest, below, is
        # the archive *file*'s bytes, since that is what actually crosses the
        # wire and what `registry.fetch` verifies against.
        info = install_mod.validate(archive)
        file_digest = hashlib.sha256(archive.read_bytes()).hexdigest()

        key = (info.name, info.version)
        previous = seen.get(key)
        if previous is not None and previous[0] != file_digest:
            raise ValidationError(
                f"{info.name} {info.version} was built twice with different content "
                f"({previous[1].name} and {archive.name} do not match)",
                remedies=["give the differing build a new version, or remove the stale archive"],
            )
        seen[key] = (file_digest, archive)

        filename = f"{info.name}-{info.version}.sclplpkg"
        destination = out / filename
        if destination.resolve() != archive.resolve():
            shutil.copyfile(archive, destination)
        packages.setdefault(info.name, {})[info.version] = {"digest": file_digest, "url": filename}

    index = {"schema": REGISTRY_SCHEMA_VERSION, "packages": packages}
    index_path = out / INDEX_NAME
    temporary = index_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(index_path)

    return ReleaseResult(index_path, tuple(sorted(seen)))
