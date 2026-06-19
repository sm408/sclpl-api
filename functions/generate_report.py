"""
@name: Generate Report
@type: transformer
@version: 1

Generates a final report summarizing all processed data from the
advanced logic workflow. Aggregates results from foreach loops,
repeat batches, and conditional steps.
"""

import json


def run(ctx):
    processed_users_raw = ctx.workflow_variables.get("processed_users", "[]")
    try:
        processed_users = json.loads(processed_users_raw)
    except (json.JSONDecodeError, TypeError):
        processed_users = []

    failure_raw = ctx.workflow_variables.get("failure_handled")
    failure_info = None
    if failure_raw:
        try:
            failure_info = json.loads(failure_raw)
        except (json.JSONDecodeError, TypeError):
            failure_info = failure_raw

    batch_results = ctx.step_outputs.get("batch_fetch_items", [])
    if isinstance(batch_results, list):
        batch_count = len(batch_results)
    else:
        batch_count = 1 if batch_results else 0

    report = {
        "total_users_processed": len(processed_users),
        "users": processed_users,
        "batch_items_fetched": batch_count,
        "failure_info": failure_info,
    }

    ctx.workflow_variables["final_report"] = json.dumps(report, indent=2)
    return ctx
