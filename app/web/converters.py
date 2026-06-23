"""Shared response conversion helpers for the web API.

Eliminates duplication of ``_to_response`` / ``_history_to_response``
functions that were previously copy-pasted across multiple route modules.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.models.workflow_document import (
    DiffEntry,
    GraphLayout,
    ParseResult,
    PreflightResult,
    PreviewResult,
    RevisionConflict,
    WorkflowDocument,
    WorkflowVersion,
)
from app.web.dto import (
    CollectionResponse,
    DiffEntryDto,
    GraphLayoutDto,
    HistoryResponse,
    ParamDto,
    ParseResultDto,
    PreflightResultDto,
    PreviewResultDto,
    RequestResponse,
    RevisionConflictDto,
    SourceDiagnosticDto,
    WorkflowResponse,
    WorkflowVersionResponse,
)


def _parse_json_field(value: str | list | dict | None, default: list | dict | None = None):
    """Parse a JSON string field, returning the parsed value or a default."""
    if value is None:
        return default if default is not None else ([] if isinstance(default, list) else {})
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default if default is not None else []
    return default if default is not None else []


def collection_to_response(col: dict) -> dict:
    """Convert a raw collection dict to a camelCase response dict."""
    return CollectionResponse(
        id=col["id"],
        project_id=col.get("project_id", ""),
        name=col["name"],
        description=col.get("description", ""),
        revision=col.get("revision", 1),
        created_at=col.get("created_at"),
        updated_at=col.get("updated_at"),
    ).model_dump(by_alias=True)


def request_to_response(req: dict) -> dict:
    """Convert a raw request dict from DB to a camelCase response dict."""
    headers = _parse_json_field(req.get("headers", "[]"), [])
    query_params = _parse_json_field(req.get("query_params", "[]"), [])
    auth_config = _parse_json_field(req.get("auth_config", "{}"), {})

    return RequestResponse(
        id=req["id"],
        project_id=req.get("project_id", ""),
        collection_id=req.get("collection_id"),
        name=req["name"],
        method=req.get("method", "GET"),
        url=req.get("url", ""),
        headers=[ParamDto(**h) for h in headers] if isinstance(headers, list) else [],
        query_params=[ParamDto(**p) for p in query_params] if isinstance(query_params, list) else [],
        body=req.get("body"),
        body_type=req.get("body_type"),
        auth_type=req.get("auth_type"),
        auth_config=auth_config if isinstance(auth_config, dict) else {},
        revision=req.get("revision", 1),
        created_at=req.get("created_at"),
        updated_at=req.get("updated_at"),
    ).model_dump(by_alias=True)


def history_to_response(row: dict) -> dict:
    """Convert a raw history dict from DB to a camelCase response dict."""
    response_headers = _parse_json_field(row.get("response_headers", "{}"), {})
    variables_used = _parse_json_field(row.get("variables_used", "{}"), {})

    return HistoryResponse(
        id=row["id"],
        project_id=row.get("project_id", ""),
        request_id=row.get("request_id"),
        request_name=row.get("request_name", ""),
        method=row.get("method", ""),
        url=row.get("url", ""),
        status=row.get("status", ""),
        status_code=row.get("status_code"),
        response_body=row.get("response_body"),
        response_headers=response_headers if isinstance(response_headers, dict) else {},
        duration_ms=row.get("duration_ms", 0),
        error_message=row.get("error_message"),
        environment_id=row.get("environment_id"),
        variables_used=variables_used if isinstance(variables_used, dict) else {},
        created_at=row.get("created_at"),
    ).model_dump(by_alias=True)


# ── Workflow converters ────────────────────────────────────────────────


def _to_diff_dto(entry: DiffEntry) -> dict:
    return DiffEntryDto(
        path=entry.path,
        action=entry.action.value if hasattr(entry.action, "value") else entry.action,
        old_value=entry.old_value,
        new_value=entry.new_value,
    ).model_dump(by_alias=True)


def workflow_to_response(doc: WorkflowDocument) -> dict:
    """Convert a WorkflowDocument to a camelCase response dict."""
    layout_dto = GraphLayoutDto(
        nodes=doc.layout.nodes,
        viewport=doc.layout.viewport,
    )
    return WorkflowResponse(
        id=doc.id,
        project_id=doc.project_id,
        name=doc.name,
        description=doc.description,
        definition=doc.definition,
        layout=layout_dto,
        sclpll_source=doc.sclpll_source,
        revision=doc.revision,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    ).model_dump(by_alias=True)


def version_to_response(ver: WorkflowVersion) -> dict:
    """Convert a WorkflowVersion to a camelCase response dict."""
    return WorkflowVersionResponse(
        id=ver.id,
        workflow_id=ver.workflow_id,
        version=ver.version,
        definition=ver.definition,
        sclpll_source=ver.sclpll_source,
        description=ver.description,
        author=ver.author,
        metadata=ver.metadata,
        created_at=ver.created_at,
    ).model_dump(by_alias=True)


def parse_result_to_response(result: ParseResult) -> dict:
    """Convert a ParseResult to a camelCase response dict."""
    diagnostics = [
        SourceDiagnosticDto(
            line=d.line,
            column=d.column,
            severity=d.severity,
            message=d.message,
        ).model_dump(by_alias=True)
        for d in result.diagnostics
    ]
    return ParseResultDto(
        success=result.success,
        definition=result.definition,
        diagnostics=diagnostics,
        source_hash=result.source_hash,
    ).model_dump(by_alias=True)


def preview_to_response(result: PreviewResult) -> dict:
    """Convert a PreviewResult to a camelCase response dict."""
    return PreviewResultDto(
        definition=result.definition,
        sclpll_source=result.sclpll_source,
        diff=[_to_diff_dto(d) for d in result.diff],
        warnings=result.warnings,
        losses=result.losses,
    ).model_dump(by_alias=True)


def preflight_to_response(result: PreflightResult) -> dict:
    """Convert a PreflightResult to a camelCase response dict."""
    issues = [
        {"severity": i.severity, "message": i.message, "path": i.path}
        for i in result.issues
    ]
    return PreflightResultDto(
        valid=result.valid,
        issues=issues,
    ).model_dump(by_alias=True)


def conflict_to_response(conflict: RevisionConflict) -> dict:
    """Convert a RevisionConflict to a camelCase response dict."""
    return RevisionConflictDto(
        current_revision=conflict.current_revision,
        attempted_revision=conflict.attempted_revision,
        current_definition=conflict.current_definition,
        server_diff=[_to_diff_dto(d) for d in conflict.server_diff],
    ).model_dump(by_alias=True)
