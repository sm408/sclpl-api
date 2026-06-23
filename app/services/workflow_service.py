"""Workflow repository with document model, versioning, and SCLPLL integration.

Provides CRUD operations for workflow documents, version
save/compare/restore, revision conflict detection, and
SCLPLL parse/preview/apply workflows.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.engine.sclpll_compiler import SCLPLLCompiler
from app.core.models.project import DEFAULT_PROJECT_ID
from app.core.models.workflow_document import (
    DiffEntry,
    GraphLayout,
    ParseResult,
    PreflightResult,
    PreviewResult,
    RevisionConflict,
    SourceDiagnostic,
    ValidationIssue,
    WorkflowDocument,
    WorkflowVersion,
    compute_definition_diff,
)
from app.storage.db import Database


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _hash_source(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


class WorkflowRepository:
    """Repository for workflow documents with versioning and SCLPLL support."""

    def __init__(self, db: Database, compiler: SCLPLLCompiler | None = None) -> None:
        self._db = db
        self._compiler = compiler or SCLPLLCompiler()

    # ── CRUD ──────────────────────────────────────────────────────────────

    async def create(
        self,
        name: str,
        project_id: str | None = None,
        description: str = "",
        definition: dict[str, Any] | None = None,
        layout: GraphLayout | None = None,
        sclpll_source: str = "",
    ) -> WorkflowDocument:
        """Create a new workflow document."""
        now = _now_iso()
        wf_id = str(uuid.uuid4())
        pid = project_id or DEFAULT_PROJECT_ID
        definition = definition or {"id": wf_id, "name": name, "description": description, "steps": [], "variables": {}}
        layout = layout or GraphLayout()

        # Ensure definition id matches
        definition["id"] = wf_id
        definition["name"] = name
        definition["description"] = description

        await self._db.execute(
            """INSERT INTO workflows
            (id, name, description, steps, variables, layout, sclpll_source, project_id, revision, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                wf_id,
                name,
                description,
                json.dumps(definition.get("steps", [])),
                json.dumps(definition.get("variables", {})),
                json.dumps({"nodes": layout.nodes, "viewport": layout.viewport}),
                sclpll_source,
                pid,
                1,
                now,
                now,
            ),
        )
        await self._db.commit()
        return WorkflowDocument(
            id=wf_id,
            project_id=pid,
            name=name,
            description=description,
            definition=definition,
            layout=layout,
            sclpll_source=sclpll_source,
            revision=1,
            created_at=now,
            updated_at=now,
        )

    async def list_all(self, project_id: str | None = None) -> list[WorkflowDocument]:
        """List all workflow documents, optionally filtered by project."""
        if project_id:
            rows = await self._db.fetch_all(
                "SELECT * FROM workflows WHERE project_id = ? ORDER BY name",
                (project_id,),
            )
        else:
            rows = await self._db.fetch_all("SELECT * FROM workflows ORDER BY name")
        return [WorkflowDocument.from_db_row(r) for r in rows]

    async def get(self, workflow_id: str) -> WorkflowDocument | None:
        """Get a single workflow document by ID."""
        row = await self._db.fetch_one(
            "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
        )
        if not row:
            return None
        return WorkflowDocument.from_db_row(row)

    async def update(
        self,
        workflow_id: str,
        data: dict[str, Any],
        revision: int | None = None,
    ) -> WorkflowDocument | RevisionConflict | None:
        """Update a workflow document.

        Returns:
            WorkflowDocument on success,
            RevisionConflict if revision mismatch,
            None if not found.
        """
        existing_row = await self._db.fetch_one(
            "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
        )
        if not existing_row:
            return None

        existing = WorkflowDocument.from_db_row(existing_row)

        # Revision conflict check
        if revision is not None and existing.revision != revision:
            server_diff = compute_definition_diff(
                existing.definition,
                data.get("definition", existing.definition),
            )
            return RevisionConflict(
                current_revision=existing.revision,
                attempted_revision=revision,
                current_definition=existing.definition,
                server_diff=server_diff,
            )

        now = _now_iso()
        fields: list[str] = []
        values: list[Any] = []

        if "name" in data and data["name"] is not None:
            fields.append("name = ?")
            values.append(data["name"])
        if "description" in data and data["description"] is not None:
            fields.append("description = ?")
            values.append(data["description"])
        if "definition" in data and data["definition"] is not None:
            defn = data["definition"]
            fields.append("steps = ?")
            values.append(json.dumps(defn.get("steps", [])))
            fields.append("variables = ?")
            values.append(json.dumps(defn.get("variables", {})))
        if "layout" in data and data["layout"] is not None:
            layout = data["layout"]
            if isinstance(layout, GraphLayout):
                layout = {"nodes": layout.nodes, "viewport": layout.viewport}
            fields.append("layout = ?")
            values.append(json.dumps(layout))
        if "sclpll_source" in data:
            fields.append("sclpll_source = ?")
            values.append(data["sclpll_source"])

        new_rev = (existing.revision or 1) + 1
        fields.append("revision = ?")
        values.append(new_rev)
        fields.append("updated_at = ?")
        values.append(now)
        values.append(workflow_id)

        sql = f"UPDATE workflows SET {', '.join(fields)} WHERE id = ?"
        await self._db.execute(sql, tuple(values))
        await self._db.commit()
        return await self.get(workflow_id)

    async def delete(self, workflow_id: str) -> bool:
        """Delete a workflow and its versions."""
        cursor = await self._db.execute(
            "DELETE FROM workflows WHERE id = ?", (workflow_id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def duplicate(self, workflow_id: str, new_name: str | None = None) -> WorkflowDocument | None:
        """Duplicate a workflow document."""
        source = await self.get(workflow_id)
        if not source:
            return None
        name = new_name or f"{source.name} (copy)"
        return await self.create(
            name=name,
            project_id=source.project_id,
            description=source.description,
            definition=source.definition,
            layout=source.layout,
            sclpll_source=source.sclpll_source,
        )

    # ── Versions ──────────────────────────────────────────────────────────

    async def save_version(
        self,
        workflow_id: str,
        description: str = "",
        author: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> WorkflowVersion | None:
        """Save an immutable version snapshot of the current workflow state."""
        doc = await self.get(workflow_id)
        if not doc:
            return None

        # Determine next version number
        row = await self._db.fetch_one(
            "SELECT MAX(version) as max_ver FROM workflow_versions WHERE workflow_id = ?",
            (workflow_id,),
        )
        next_ver = (row["max_ver"] or 0) + 1 if row else 1

        ver_id = str(uuid.uuid4())
        now = _now_iso()

        # Store description in metadata since the table has no description column
        merged_metadata = dict(metadata or {})
        if description:
            merged_metadata["_description"] = description

        await self._db.execute(
            """INSERT INTO workflow_versions
            (id, workflow_id, version, sclpll_source, json_source, metadata, author, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ver_id,
                workflow_id,
                next_ver,
                doc.sclpll_source,
                json.dumps(doc.definition),
                json.dumps(merged_metadata),
                author,
                now,
            ),
        )
        await self._db.commit()

        return WorkflowVersion(
            id=ver_id,
            workflow_id=workflow_id,
            version=next_ver,
            definition=doc.definition,
            sclpll_source=doc.sclpll_source,
            description=description,
            author=author,
            metadata=merged_metadata,
            created_at=now,
        )

    async def list_versions(self, workflow_id: str) -> list[WorkflowVersion]:
        """List all versions of a workflow, newest first."""
        rows = await self._db.fetch_all(
            "SELECT * FROM workflow_versions WHERE workflow_id = ? ORDER BY version DESC",
            (workflow_id,),
        )
        versions = []
        for r in rows:
            json_src = r.get("json_source", "{}")
            if isinstance(json_src, str):
                json_src = json.loads(json_src)
            meta_raw = r.get("metadata", "{}")
            if isinstance(meta_raw, str):
                meta_raw = json.loads(meta_raw)
            # Description is stored in metadata since the table has no description column
            desc = meta_raw.pop("_description", "") if isinstance(meta_raw, dict) else ""
            versions.append(WorkflowVersion(
                id=r["id"],
                workflow_id=r["workflow_id"],
                version=r["version"],
                definition=json_src,
                sclpll_source=r.get("sclpll_source", ""),
                description=desc,
                author=r.get("author", ""),
                metadata=meta_raw,
                created_at=r.get("created_at"),
            ))
        return versions

    async def get_version(self, workflow_id: str, version: int) -> WorkflowVersion | None:
        """Get a specific version of a workflow."""
        row = await self._db.fetch_one(
            "SELECT * FROM workflow_versions WHERE workflow_id = ? AND version = ?",
            (workflow_id, version),
        )
        if not row:
            return None
        json_src = row.get("json_source", "{}")
        if isinstance(json_src, str):
            json_src = json.loads(json_src)
        meta_raw = row.get("metadata", "{}")
        if isinstance(meta_raw, str):
            meta_raw = json.loads(meta_raw)
        desc = meta_raw.pop("_description", "") if isinstance(meta_raw, dict) else ""
        return WorkflowVersion(
            id=row["id"],
            workflow_id=row["workflow_id"],
            version=row["version"],
            definition=json_src,
            sclpll_source=row.get("sclpll_source", ""),
            description=desc,
            author=row.get("author", ""),
            metadata=meta_raw,
            created_at=row.get("created_at"),
        )

    async def restore_version(self, workflow_id: str, version: int) -> WorkflowDocument | None:
        """Restore a workflow to a previous version.

        Saves a version of the current state first, then overwrites
        the workflow definition with the specified version's data.
        """
        ver = await self.get_version(workflow_id, version)
        if not ver:
            return None

        # Save current state as a new version before restoring
        await self.save_version(workflow_id, description="Auto-save before restore")

        doc = await self.get(workflow_id)
        if not doc:
            return None

        now = _now_iso()
        new_rev = (doc.revision or 1) + 1

        await self._db.execute(
            """UPDATE workflows
            SET name=?, description=?, steps=?, variables=?, sclpll_source=?, revision=?, updated_at=?
            WHERE id=?""",
            (
                ver.definition.get("name", doc.name),
                ver.definition.get("description", doc.description),
                json.dumps(ver.definition.get("steps", [])),
                json.dumps(ver.definition.get("variables", {})),
                ver.sclpll_source,
                new_rev,
                now,
                workflow_id,
            ),
        )
        await self._db.commit()
        return await self.get(workflow_id)

    async def compare_versions(
        self, workflow_id: str, version_a: int, version_b: int
    ) -> list[DiffEntry] | None:
        """Compare two versions and return the structural diff."""
        ver_a = await self.get_version(workflow_id, version_a)
        ver_b = await self.get_version(workflow_id, version_b)
        if not ver_a or not ver_b:
            return None
        return compute_definition_diff(ver_a.definition, ver_b.definition)

    # ── SCLPLL Integration ────────────────────────────────────────────────

    def parse_sclpll(self, source: str) -> ParseResult:
        """Parse SCLPLL source and return a structured result with diagnostics."""
        diagnostics: list[SourceDiagnostic] = []
        try:
            definition = self._compiler.parse(source)
            source_hash = _hash_source(source)
            return ParseResult(
                success=True,
                definition=definition,
                diagnostics=diagnostics,
                source_hash=source_hash,
            )
        except Exception as exc:
            # Extract line info from SCLPLLParseError
            line = 0
            raw_line = ""
            if hasattr(exc, "line_number"):
                line = exc.line_number
            if hasattr(exc, "line"):
                raw_line = exc.line
            diagnostics.append(SourceDiagnostic(
                line=line,
                column=0,
                severity="error",
                message=str(exc),
            ))
            return ParseResult(
                success=False,
                definition=None,
                diagnostics=diagnostics,
                source_hash=_hash_source(source),
            )

    def preview_sclpll(
        self,
        source: str,
        current_definition: dict[str, Any] | None = None,
    ) -> PreviewResult:
        """Preview what would change when applying SCLPLL source.

        Does NOT write to the database.
        """
        parse_result = self.parse_sclpll(source)
        if not parse_result.success or not parse_result.definition:
            raise ValueError(
                f"SCLPLL parse failed: {parse_result.errors[0].message if parse_result.errors else 'unknown error'}"
            )

        definition = parse_result.definition
        warnings: list[str] = []
        losses: list[str] = []
        diff: list[DiffEntry] = []

        if current_definition:
            diff = compute_definition_diff(current_definition, definition)

            # Detect fields that exist in current but not in SCLPLL
            # (non-representable fields like retry config, semaphore, etc.)
            current_steps = {s["id"]: s for s in current_definition.get("steps", [])}
            new_steps = {s["id"]: s for s in definition.get("steps", [])}

            for step_id, step in current_steps.items():
                if step_id in new_steps:
                    new_step = new_steps[step_id]
                    # Check for fields that SCLPLL doesn't preserve
                    for field in ("retry", "request_id"):
                        if field in step and field not in new_step:
                            losses.append(
                                f"Step '{step_id}': field '{field}' is not representable in SCLPLL and will be lost"
                            )
                else:
                    losses.append(f"Step '{step_id}': removed (not in SCLPLL source)")

        sclpll_out = self._compiler.decompile_dict_to_sclpll(definition)

        return PreviewResult(
            definition=definition,
            sclpll_source=sclpll_out,
            diff=diff,
            warnings=warnings,
            losses=losses,
        )

    async def apply_sclpll(
        self,
        workflow_id: str,
        source: str,
        revision: int | None = None,
    ) -> WorkflowDocument | RevisionConflict | None:
        """Parse SCLPLL source and apply it to the workflow.

        This is an explicit parse -> preview -> apply pipeline.
        """
        doc = await self.get(workflow_id)
        if not doc:
            return None

        parse_result = self.parse_sclpll(source)
        if not parse_result.success or not parse_result.definition:
            raise ValueError(
                f"SCLPLL parse failed: {parse_result.errors[0].message if parse_result.errors else 'unknown error'}"
            )

        definition = parse_result.definition
        # Preserve the workflow id
        definition["id"] = workflow_id

        sclpll_out = self._compiler.decompile_dict_to_sclpll(definition)

        result = await self.update(
            workflow_id,
            {
                "definition": definition,
                "sclpll_source": sclpll_out,
                "name": definition.get("name", doc.name),
                "description": definition.get("description", doc.description),
            },
            revision=revision,
        )
        return result

    def generate_sclpll(self, definition: dict[str, Any]) -> str:
        """Generate deterministic SCLPLL from a workflow definition."""
        return self._compiler.decompile_dict_to_sclpll(definition)

    # ── Preflight Validation ──────────────────────────────────────────────

    def validate_preflight(self, definition: dict[str, Any]) -> PreflightResult:
        """Validate a workflow definition before execution.

        Checks for missing step IDs, broken dependency references,
        circular dependencies, and missing workflow ID.
        """
        issues: list[ValidationIssue] = []
        steps = definition.get("steps", [])
        step_ids = {s.get("id") for s in steps}

        # Missing step IDs
        for i, step in enumerate(steps):
            if not step.get("id"):
                issues.append(ValidationIssue(
                    severity="error",
                    message=f"Step at index {i} is missing an 'id' field",
                    path=f"steps[{i}].id",
                ))

        # Broken dependency references
        for step in steps:
            sid = step.get("id", "")
            for dep in step.get("depends_on", []):
                if dep not in step_ids:
                    issues.append(ValidationIssue(
                        severity="error",
                        message=f"Step '{sid}' depends on unknown step '{dep}'",
                        path=f"steps.{sid}.depends_on",
                    ))

        # Circular dependencies
        visited: set[str] = set()
        in_stack: set[str] = set()
        step_map = {s.get("id", ""): s for s in steps}

        def _detect_cycle(sid: str) -> bool:
            if sid in in_stack:
                return True
            if sid in visited:
                return False
            visited.add(sid)
            in_stack.add(sid)
            for dep in step_map.get(sid, {}).get("depends_on", []):
                if _detect_cycle(dep):
                    return True
            in_stack.discard(sid)
            return False

        for sid in step_ids:
            if sid and sid not in visited:
                if _detect_cycle(sid):
                    issues.append(ValidationIssue(
                        severity="error",
                        message=f"Circular dependency detected involving step '{sid}'",
                        path=f"steps.{sid}",
                    ))

        # Check for missing workflow ID
        if not definition.get("id"):
            issues.append(ValidationIssue(
                severity="warning",
                message="Workflow definition is missing an 'id' field",
                path="id",
            ))

        return PreflightResult(
            valid=not any(i.severity == "error" for i in issues),
            issues=issues,
        )
