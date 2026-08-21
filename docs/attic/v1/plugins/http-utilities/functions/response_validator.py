"""
@name: response_validator
@type: http
@version: 1
@description: Validate HTTP response against expected schemas and status codes

Config via workflow_variables: expected_status, expected_content_type,
required_fields (comma-separated JSON path list).
"""

import json


def _get_nested(data: dict, path: str):
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def run(ctx):
    response = ctx.metadata.get("response")
    if not response:
        return {"success": False, "valid": False, "errors": ["No response in context"]}

    errors = []
    status_code = getattr(response, "status_code", 0)
    expected_status = ctx.workflow_variables.get("expected_status")

    if expected_status:
        expected_codes = {int(s.strip()) for s in expected_status.split(",")}
        if status_code not in expected_codes:
            errors.append(f"Expected status {expected_status}, got {status_code}")

    content_type = ""
    headers = getattr(response, "headers", {})
    if isinstance(headers, dict):
        content_type = headers.get("content-type", headers.get("Content-Type", ""))
    expected_ct = ctx.workflow_variables.get("expected_content_type")
    if expected_ct and expected_ct.lower() not in content_type.lower():
        errors.append(f"Expected content-type '{expected_ct}', got '{content_type}'")

    required_fields = ctx.workflow_variables.get("required_fields", "")
    if required_fields:
        body = getattr(response, "body", None)
        if body:
            try:
                data = json.loads(body) if isinstance(body, str) else body
            except (json.JSONDecodeError, TypeError):
                errors.append("Response body is not valid JSON")
                data = None

            if isinstance(data, dict):
                for field_path in required_fields.split(","):
                    field_path = field_path.strip()
                    if field_path and _get_nested(data, field_path) is None:
                        errors.append(f"Missing required field: {field_path}")

    return {
        "success": len(errors) == 0,
        "valid": len(errors) == 0,
        "status_code": status_code,
        "errors": errors,
    }
