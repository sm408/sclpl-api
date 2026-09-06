"""E6: project policy -- host allowlists, output roots, overwrite, capabilities.

Read once from the project manifest's `[policy]` table and enforced at exactly the
points where a side effect would otherwise happen: before the first HTTP request of a
run, and again before every redirect hop, since a redirect can point anywhere a
declared allowlist was meant to keep the run away from; before any output is written,
by comparing the fully resolved (symlinks and `..` followed) destination against the
declared roots; and before an existing file is silently replaced.

A project with no `[policy]` table enforces nothing beyond what already existed --
this is opt-in, matching every other project-manifest feature, not a new default that
would fail existing projects the moment they upgrade. Once a project *does* declare a
`[policy]` table, `overwrite` defaults to denied within it: opting in to policy at all
means the author is thinking about safety, and silently clobbering an existing file is
exactly the kind of thing that should require saying so.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

from sclpl.errors import PolicyDenied, ValidationError
from sclpl.project.context import ProjectContext

#: Everything a plugin may declare (`sclpl.ext.plugins.CAPABILITIES`), duplicated as a
#: plain tuple here to avoid `project/` depending on `ext/` just to validate a name --
#: the set a project may deny is not allowed to silently drift from the set a plugin
#: may declare, so `sclpl.ext.plugins` re-checks its own list against this one.
KNOWN_CAPABILITIES = frozenset({"network", "fs:read", "fs:write", "secrets:read", "subprocess"})


@dataclass(frozen=True, slots=True)
class Policy:
    """Resolved, enforceable policy for one run. Immutable: read once, applied everywhere."""

    #: `None` means unrestricted. An empty set is deliberately not used for "no
    #: restriction" -- it would be indistinguishable from a project that meant to
    #: allow nothing, which is a plausible (if unusual) thing to declare on purpose.
    allowed_hosts: frozenset[str] | None = None
    #: Every declared output must resolve under one of these. Empty means unrestricted.
    output_roots: tuple[Path, ...] = ()
    overwrite: bool = True
    deny_capabilities: frozenset[str] = frozenset()

    @property
    def restricts_hosts(self) -> bool:
        return self.allowed_hosts is not None

    @property
    def restricts_outputs(self) -> bool:
        return bool(self.output_roots)

    def host_allowed(self, host: str) -> bool:
        if self.allowed_hosts is None:
            return True
        lowered = host.lower()
        return any(fnmatch.fnmatchcase(lowered, pattern.lower()) for pattern in self.allowed_hosts)

    def check_host(self, host: str) -> None:
        """Raise unless ``host`` is allowed. Called before every request, every hop."""
        if self.host_allowed(host):
            return
        allowed = ", ".join(sorted(self.allowed_hosts or ())) or "(none)"
        raise PolicyDenied(
            f"host {host!r} is not in the project's allowed hosts",
            remedies=[
                f"declared: {allowed}",
                "add it to [policy] hosts in the project manifest if this is expected",
            ],
        )

    def check_output(self, path: Path) -> None:
        """Raise unless ``path`` resolves under a declared output root.

        Resolved rather than compared lexically: a symlink or junction in the path, or
        a `..` that walks back out, both change where the bytes actually land, and a
        check against the literal path string would miss either.
        """
        if not self.output_roots:
            return
        resolved = path.resolve()
        if any(resolved.is_relative_to(root) for root in self.output_roots):
            return
        declared = ", ".join(str(root) for root in self.output_roots)
        raise PolicyDenied(
            f"output {path} resolves to {resolved}, outside the project's declared output roots",
            remedies=[f"declared output roots: {declared}"],
        )


DEFAULT = Policy()


def parse(project: ProjectContext) -> Policy:
    """Read `[policy]` from the project manifest. Absent entirely, this is `DEFAULT`."""
    raw = project.manifest.get("policy", {})
    if not isinstance(raw, dict):
        raise ValidationError("policy must be a table", where=str(project.manifest_path))
    if not raw:
        return DEFAULT

    allowed_hosts = _optional_string_list(raw, "hosts", project.manifest_path)
    output_root_values = _optional_string_list(raw, "output_roots", project.manifest_path)
    overwrite = raw.get("overwrite", False)
    if not isinstance(overwrite, bool):
        raise ValidationError(
            "policy.overwrite must be a boolean", where=str(project.manifest_path)
        )
    deny_values = _optional_string_list(raw, "deny_capabilities", project.manifest_path) or []
    unknown = set(deny_values) - KNOWN_CAPABILITIES
    if unknown:
        raise ValidationError(
            f"policy.deny_capabilities names unknown capability {sorted(unknown)[0]!r}",
            where=str(project.manifest_path),
            remedies=[f"known capabilities: {', '.join(sorted(KNOWN_CAPABILITIES))}"],
        )

    unknown_keys = set(raw) - {"hosts", "output_roots", "overwrite", "deny_capabilities"}
    if unknown_keys:
        raise ValidationError(
            f"unknown policy key {sorted(unknown_keys)[0]!r}", where=str(project.manifest_path)
        )

    return Policy(
        allowed_hosts=frozenset(allowed_hosts) if allowed_hosts is not None else None,
        output_roots=tuple(project.resolve_path(item) for item in (output_root_values or ())),
        overwrite=overwrite,
        deny_capabilities=frozenset(deny_values),
    )


def _optional_string_list(raw: dict[str, object], key: str, where: Path) -> list[str] | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValidationError(f"policy.{key} must be an array of strings", where=str(where))
    return value
