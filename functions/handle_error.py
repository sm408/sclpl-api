"""
@name: Handle Error
@type: transformer
@version: 1

Demonstrates @when conditional execution.
Handles the error case when resource creation fails.
"""

import json


def run(ctx):
    create_raw = ctx.step_outputs.get("create_post", {})
    status_code = create_raw.get("status_code", 0)
    error = create_raw.get("error", "")

    ctx.workflow_variables["error_status"] = str(status_code)
    ctx.workflow_variables["error_message"] = error or f"Request failed with status {status_code}"

    return ctx
