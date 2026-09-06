"""E8: a project's `[outputs]` table -- immediate or validated publication.

`publish = "immediate"` (the default, absent entirely) is the behavior this project
has always had: a `-> port` writer's value lands at its bound destination the moment
that step runs. `publish = "validated"` opts a project into staged publication
(`run/publication.py`, SPEC 3.5): every declared output writes to a scratch file
first, and none of them replace their real destination unless the whole run finishes
without a single failure. Absent entirely, a project (or a standalone workflow with
no project at all) behaves exactly as before -- this is additive, not a new default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sclpl.errors import ValidationError
from sclpl.project.context import ProjectContext

PublishMode = Literal["immediate", "validated"]


@dataclass(frozen=True, slots=True)
class OutputSettings:
    publish: PublishMode = "immediate"


DEFAULT = OutputSettings()


def parse(project: ProjectContext) -> OutputSettings:
    raw = project.manifest.get("outputs", {})
    if not isinstance(raw, dict):
        raise ValidationError("outputs must be a table", where=str(project.manifest_path))
    if not raw:
        return DEFAULT

    unknown_keys = set(raw) - {"publish"}
    if unknown_keys:
        raise ValidationError(
            f"unknown outputs key {sorted(unknown_keys)[0]!r}", where=str(project.manifest_path)
        )

    publish = raw.get("publish", "immediate")
    if publish not in ("immediate", "validated"):
        raise ValidationError(
            f"outputs.publish must be 'immediate' or 'validated', not {publish!r}",
            where=str(project.manifest_path),
        )
    return OutputSettings(publish=publish)
