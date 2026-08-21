"""
@name: Filter Active Jobs
@type: transformer
@version: 1

Filters job applications to only include active ones.
"""

import json


def run(ctx):
    merged_raw = ctx.workflow_variables.get("merged_jobs", "[]")

    try:
        merged = json.loads(merged_raw) if isinstance(merged_raw, str) else merged_raw
    except json.JSONDecodeError:
        merged = []

    active_statuses = {"applied", "interviewing", "offer", "pending", "reviewing"}
    active = [j for j in merged if j.get("status", "").lower() in active_statuses]

    ctx.workflow_variables["active_jobs"] = json.dumps(active)
    return ctx
