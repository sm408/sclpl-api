"""
@name: Enrich User Data
@type: transformer
@version: 1

Enriches raw user data with computed fields.
"""

import json


def run(ctx):
    raw = ctx.step_outputs.get("fetch_users", {})
    body = raw.get("body", "") if isinstance(raw.get("body"), str) else json.dumps(raw.get("body", ""))

    try:
        data = json.loads(body) if isinstance(body, str) else body
    except json.JSONDecodeError:
        data = {}

    users = data if isinstance(data, list) else data.get("users", data.get("data", []))

    enriched = []
    for user in (users if isinstance(users, list) else []):
        enriched.append({
            **user,
            "display_name": user.get("name", user.get("username", "Unknown")),
            "has_email": bool(user.get("email")),
            "source": "users",
        })

    ctx.workflow_variables["enriched_users"] = json.dumps(enriched)
    return ctx
