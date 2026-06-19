"""
@name: Process Data
@type: transformer
@version: 1

Template function for processing step output data.
Replace this with your own transformation logic.
"""

import json


def run(ctx):
    raw = ctx.step_outputs.get("fetch_data", {})
    body = raw.get("body", "{}")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            body = {}

    result = {
        "source_step": "fetch_data",
        "status_code": raw.get("status_code", 0),
        "data": body,
        "processed": True,
    }

    ctx.workflow_variables["processed_data"] = json.dumps(result, indent=2)
    return ctx
