"""
@name: Handle Success
@type: transformer
@version: 1

Demonstrates @when conditional execution.
Handles the success case when a resource is created.
"""

import json


def run(ctx):
    create_raw = ctx.step_outputs.get("create_post", {})
    status_code = create_raw.get("status_code", 0)

    ctx.workflow_variables["success_status"] = str(status_code)
    ctx.workflow_variables["success_message"] = "Resource created successfully"

    # Extract created resource details if available
    body = create_raw.get("body", "{}")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            body = {}

    if body:
        ctx.workflow_variables["created_resource_id"] = str(body.get("id", "unknown"))
        ctx.workflow_variables["created_resource_title"] = body.get("title", "")

    return ctx
