"""
@name: Generate Job Summary
@type: transformer
@version: 1

Generates a summary report of job applications.
"""

import json
from datetime import datetime, timezone


def run(ctx):
    active_raw = ctx.workflow_variables.get("active_jobs", "[]")

    try:
        active = json.loads(active_raw) if isinstance(active_raw, str) else active_raw
    except json.JSONDecodeError:
        active = []

    status_counts = {}
    for job in active:
        status = job.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_active": len(active),
        "by_status": status_counts,
        "applications": active[:10],
    }

    ctx.workflow_variables["job_summary"] = json.dumps(summary, indent=2)
    return ctx
