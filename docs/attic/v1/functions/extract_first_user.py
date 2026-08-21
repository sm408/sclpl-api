"""
@name: Extract First User
@type: transformer
@version: 1

Demonstrates dot notation for nested JSON access.
Extracts the first user from the users list using {{step.field.subfield}} syntax.
"""

import json


def run(ctx):
    users_raw = ctx.step_outputs.get("fetch_users", {})
    body = users_raw.get("body", "[]")

    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            body = []

    if body and isinstance(body, list) and len(body) > 0:
        first_user = body[0]
        ctx.workflow_variables["first_user_name"] = first_user.get("name", "Unknown")
        ctx.workflow_variables["first_user_email"] = first_user.get("email", "unknown@example.com")
        ctx.workflow_variables["first_user_city"] = first_user.get("address", {}).get("city", "Unknown")
        ctx.workflow_variables["first_user_company"] = first_user.get("company", {}).get("name", "Unknown")
    else:
        ctx.workflow_variables["first_user_name"] = "No users found"
        ctx.workflow_variables["first_user_email"] = ""
        ctx.workflow_variables["first_user_city"] = ""
        ctx.workflow_variables["first_user_company"] = ""

    return ctx
