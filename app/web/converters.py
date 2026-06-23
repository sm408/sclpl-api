"""Shared response conversion helpers for the web API.

Eliminates duplication of ``_to_response`` / ``_history_to_response``
functions that were previously copy-pasted across multiple route modules.
"""

from __future__ import annotations

import json

from app.web.dto import (
    CollectionResponse,
    HistoryResponse,
    ParamDto,
    RequestResponse,
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
