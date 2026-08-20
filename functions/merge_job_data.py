"""
@name: Merge Job Data
@type: transformer
@version: 1

Merges job application data with status information.
"""

import json


def run(ctx):
    apps_raw = ctx.step_outputs.get("fetch_applications", {})
    statuses_raw = ctx.step_outputs.get("check_statuses", {})

    apps_body = apps_raw.get("body", "") if isinstance(apps_raw.get("body"), str) else json.dumps(apps_raw.get("body", ""))
    statuses_body = statuses_raw.get("body", "") if isinstance(statuses_raw.get("body"), str) else json.dumps(statuses_raw.get("body", ""))

    try:
        apps = json.loads(apps_body) if isinstance(apps_body, str) else apps_body
    except json.JSONDecodeError:
        apps = []

    try:
        statuses = json.loads(statuses_body) if isinstance(statuses_body, str) else statuses_body
    except json.JSONDecodeError:
        statuses = []

    status_map = {}
    if isinstance(statuses, list):
        for s in statuses:
            status_map[s.get("id", "")] = s.get("status", "unknown")
    elif isinstance(statuses, dict):
        status_map = statuses

    merged = []
    if isinstance(apps, list):
        for app in apps:
            app_id = app.get("id", "")
            app["status"] = status_map.get(app_id, "unknown")
            merged.append(app)

    ctx.workflow_variables["merged_jobs"] = json.dumps(merged)
    return ctx
