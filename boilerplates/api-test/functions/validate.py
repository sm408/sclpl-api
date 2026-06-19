"""
@name: Validate Response
@type: transformer
@version: 1

Validates an API response against expected criteria.
Checks status code, content type, and response body structure.
"""

import json


def run(ctx):
    step_id = ctx.workflow_variables.get("_validate_target", "")
    if not step_id:
        for sid in ["test_get_users", "test_get_posts", "fetch_data"]:
            if sid in ctx.step_outputs:
                step_id = sid
                break

    raw = ctx.step_outputs.get(step_id, {})
    status = raw.get("status_code", 0)
    body = raw.get("body", "{}")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            body = {}

    checks = {
        "status_ok": 200 <= status < 300,
        "has_body": bool(body),
        "is_json": isinstance(body, (dict, list)),
        "is_array": isinstance(body, list),
        "is_object": isinstance(body, dict),
    }

    result = {
        "step_tested": step_id,
        "status_code": status,
        "checks": checks,
        "passed": all(checks.values()),
        "body_preview": str(body)[:200] if body else "empty",
    }

    var_name = f"{step_id}_validation"
    ctx.workflow_variables[var_name] = json.dumps(result, indent=2)
    return ctx
