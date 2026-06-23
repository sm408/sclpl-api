"""Canonical workflow document model with definition/layout separation.

The definition JSON is the canonical source of truth.  Graph layout
(node positions, viewport) is stored separately so that visual edits
never mutate the workflow's logical structure.

WorkflowDocument bundles definition + layout + SCLPLL source into a
single transfer object used by the API and services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DiffAction(StrEnum):
    """Kind of change in a structural diff entry."""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


@dataclass
class DiffEntry:
    """A single change between two workflow definitions."""
    path: str
    action: DiffAction
    old_value: Any = None
    new_value: Any = None


@dataclass
class SourceDiagnostic:
    """A single diagnostic produced by parsing SCLPLL source."""
    line: int
    column: int
    severity: str  # "error" | "warning" | "info"
    message: str


@dataclass
class ParseResult:
    """Result of parsing SCLPLL source into a workflow definition."""
    success: bool
    definition: dict[str, Any] | None = None
    diagnostics: list[SourceDiagnostic] = field(default_factory=list)
    source_hash: str = ""

    @property
    def errors(self) -> list[SourceDiagnostic]:
        return [d for d in self.diagnostics if d.severity == "error"]

    @property
    def warnings(self) -> list[SourceDiagnostic]:
        return [d for d in self.diagnostics if d.severity == "warning"]


@dataclass
class PreviewResult:
    """Preview of what would change when applying SCLPLL source."""
    definition: dict[str, Any]
    sclpll_source: str
    diff: list[DiffEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    losses: list[str] = field(default_factory=list)


@dataclass
class ValidationIssue:
    """A single preflight validation issue."""
    severity: str  # "error" | "warning"
    message: str
    path: str = ""


@dataclass
class PreflightResult:
    """Result of preflight validation on a workflow definition."""
    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]


@dataclass
class GraphLayout:
    """Visual layout metadata for workflow graph nodes.

    Stored separately from the canonical definition so that
    drag-and-drop positioning never mutates workflow logic.
    """
    nodes: dict[str, dict[str, float]] = field(default_factory=dict)
    # Each entry maps step_id -> {"x": float, "y": float, ...}
    viewport: dict[str, float] = field(default_factory=dict)
    # {"x": float, "y": float, "zoom": float}


@dataclass
class WorkflowVersion:
    """An immutable snapshot of a workflow at a point in time."""
    id: str
    workflow_id: str
    version: int
    definition: dict[str, Any]
    sclpll_source: str = ""
    description: str = ""
    author: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None


@dataclass
class RevisionConflict:
    """Payload returned when an update hits a stale revision."""
    current_revision: int
    attempted_revision: int
    current_definition: dict[str, Any]
    server_diff: list[DiffEntry] = field(default_factory=list)


@dataclass
class ExecutionSnapshot:
    """A point-in-time snapshot of a workflow execution."""
    workflow_id: str
    workflow_name: str
    definition: dict[str, Any]
    step_events: list[StepEvent] = field(default_factory=list)
    started_at: str | None = None
    completed_at: str | None = None
    success: bool | None = None
    total_duration_ms: int = 0


@dataclass
class StepEvent:
    """Typed event emitted during workflow step execution."""
    step_id: str
    step_name: str
    event_type: str  # "started" | "completed" | "failed" | "skipped"
    timestamp: str | None = None
    duration_ms: int = 0
    output: Any = None
    error: str | None = None


@dataclass
class WorkflowDocument:
    """The canonical workflow document combining definition + layout + source.

    The definition dict is the single source of truth.  SCLPLL source is
    a derived or user-supplied textual representation.  Graph layout is
    purely visual metadata.
    """
    id: str
    project_id: str
    name: str
    description: str = ""
    definition: dict[str, Any] = field(default_factory=dict)
    layout: GraphLayout = field(default_factory=GraphLayout)
    sclpll_source: str = ""
    revision: int = 1
    created_at: str | None = None
    updated_at: str | None = None

    def to_db_row(self) -> dict[str, Any]:
        """Serialize to database column values."""
        import json
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": json.dumps(self.definition.get("steps", [])),
            "variables": json.dumps(self.definition.get("variables", {})),
            "layout": json.dumps({
                "nodes": self.layout.nodes,
                "viewport": self.layout.viewport,
            }),
            "sclpll_source": self.sclpll_source,
            "project_id": self.project_id,
            "revision": self.revision,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> WorkflowDocument:
        """Deserialize from a database row."""
        import json
        steps = row.get("steps", "[]")
        variables = row.get("variables", "{}")
        layout_raw = row.get("layout", "{}")

        if isinstance(steps, str):
            steps = json.loads(steps)
        if isinstance(variables, str):
            variables = json.loads(variables)
        if isinstance(layout_raw, str):
            layout_raw = json.loads(layout_raw)

        layout = GraphLayout(
            nodes=layout_raw.get("nodes", {}),
            viewport=layout_raw.get("viewport", {}),
        )

        return cls(
            id=row["id"],
            project_id=row.get("project_id", ""),
            name=row["name"],
            description=row.get("description", ""),
            definition={"id": row["id"], "name": row["name"],
                        "description": row.get("description", ""),
                        "steps": steps, "variables": variables},
            layout=layout,
            sclpll_source=row.get("sclpll_source", ""),
            revision=row.get("revision", 1),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )


def compute_definition_diff(
    old: dict[str, Any],
    new: dict[str, Any],
    prefix: str = "",
) -> list[DiffEntry]:
    """Compute a structural diff between two workflow definitions.

    Returns a list of DiffEntry describing what changed.
    """
    diffs: list[DiffEntry] = []
    all_keys = set(list(old.keys()) + list(new.keys()))

    for key in sorted(all_keys):
        path = f"{prefix}.{key}" if prefix else key
        old_val = old.get(key)
        new_val = new.get(key)

        if key not in old:
            diffs.append(DiffEntry(path=path, action=DiffAction.ADDED, new_value=new_val))
        elif key not in new:
            diffs.append(DiffEntry(path=path, action=DiffAction.REMOVED, old_value=old_val))
        elif old_val != new_val:
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                diffs.extend(compute_definition_diff(old_val, new_val, path))
            elif isinstance(old_val, list) and isinstance(new_val, list):
                # For lists (like steps), do index-based comparison
                max_len = max(len(old_val), len(new_val))
                for i in range(max_len):
                    item_path = f"{path}[{i}]"
                    if i >= len(old_val):
                        diffs.append(DiffEntry(path=item_path, action=DiffAction.ADDED, new_value=new_val[i]))
                    elif i >= len(new_val):
                        diffs.append(DiffEntry(path=item_path, action=DiffAction.REMOVED, old_value=old_val[i]))
                    elif old_val[i] != new_val[i]:
                        if isinstance(old_val[i], dict) and isinstance(new_val[i], dict):
                            diffs.extend(compute_definition_diff(old_val[i], new_val[i], item_path))
                        else:
                            diffs.append(DiffEntry(
                                path=item_path, action=DiffAction.MODIFIED,
                                old_value=old_val[i], new_value=new_val[i],
                            ))
            else:
                diffs.append(DiffEntry(
                    path=path, action=DiffAction.MODIFIED,
                    old_value=old_val, new_value=new_val,
                ))

    return diffs
