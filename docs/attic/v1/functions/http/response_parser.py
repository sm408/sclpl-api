"""
@name: response_parser
@type: utility
@version: 1
@description: Parse HTTP responses extracting status, headers, body fields, and timing

Config via workflow_variables: parse_extract_fields (comma-separated dot-paths),
parse_response_source (step output key).
"""

import json


def _get_nested(data, path):
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def run(ctx):
    extract_fields = ctx.workflow_variables.get("parse_extract_fields", "")
    source_key = ctx.workflow_variables.get("parse_response_source", "")

    response = ctx.metadata.get("response")
    if source_key:
        response = ctx.step_outputs.get(source_key)

    if not response:
        return {"success": False, "error": "No response to parse"}

    result = {
        "status_code": getattr(response, "status_code", 0),
        "duration_ms": getattr(response, "duration_ms", 0),
        "headers": getattr(response, "headers", {}),
        "error": getattr(response, "error", None),
    }

    body = getattr(response, "body", None)
    parsed_body = None
    if body:
        try:
            parsed_body = json.loads(body) if isinstance(body, str) else body
            result["body_type"] = "json"
        except (json.JSONDecodeError, TypeError):
            parsed_body = body
            result["body_type"] = "text"

    result["body"] = parsed_body

    if extract_fields and isinstance(parsed_body, dict):
        extracted = {}
        for field_path in extract_fields.split(","):
            field_path = field_path.strip()
            if field_path:
                extracted[field_path] = _get_nested(parsed_body, field_path)
        result["extracted"] = extracted

    ctx.workflow_variables["parsed_response"] = json.dumps(result, default=str)

    return {
        "success": True,
        "parsed": result,
    }
