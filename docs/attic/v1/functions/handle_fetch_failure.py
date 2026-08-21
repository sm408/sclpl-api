"""
@name: Handle Fetch Failure
@type: transformer
@version: 1

Handles the case when a fetch step fails (non-200 status).
Used as a fallback in @when conditional flows.
"""

import json


def run(ctx):
    detail = ctx.step_outputs.get("fetch_user_detail", {})
    status = detail.get("status_code", "unknown")

    ctx.workflow_variables["failure_handled"] = json.dumps({
        "status": "fallback_triggered",
        "original_status_code": status,
        "message": f"Fetch failed with status {status}, using fallback logic",
    }, indent=2)
    return ctx
