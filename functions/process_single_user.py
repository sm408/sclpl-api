"""
@name: Process Single User
@type: transformer
@version: 1

Processes a single user object. Used by @foreach and @when directives.
Extracts key fields from nested JSON using dot notation references.

Input: current_user variable (set by @foreach loop) or step_outputs
Output: Processed user summary
"""

import json


def run(ctx):
    user_raw = ctx.workflow_variables.get("current_user")

    if user_raw:
        if isinstance(user_raw, str):
            try:
                user = json.loads(user_raw)
            except (json.JSONDecodeError, TypeError):
                user = {"raw": user_raw}
        elif isinstance(user_raw, dict):
            user = user_raw
        else:
            user = {"raw": str(user_raw)}
    else:
        detail = ctx.step_outputs.get("fetch_user_detail", {})
        body = detail.get("body", "{}")
        if isinstance(body, str):
            try:
                user = json.loads(body)
            except (json.JSONDecodeError, TypeError):
                user = {}
        else:
            user = body if isinstance(body, dict) else {}

    summary = {
        "user_id": user.get("id"),
        "name": user.get("name"),
        "email": user.get("email"),
        "city": user.get("address", {}).get("city"),
        "company": user.get("company", {}).get("name"),
    }

    existing = ctx.workflow_variables.get("processed_users")
    if existing:
        try:
            processed = json.loads(existing)
        except (json.JSONDecodeError, TypeError):
            processed = []
    else:
        processed = []

    processed.append(summary)
    ctx.workflow_variables["processed_users"] = json.dumps(processed, indent=2)
    return ctx
