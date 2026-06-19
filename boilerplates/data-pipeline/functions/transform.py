"""
@name: Transform Data
@type: transformer
@version: 1

Template for the transform stage of a data pipeline.
Normalizes raw API response data into a consistent structure.
"""

import json


def run(ctx):
    primary_step = None
    secondary_step = None
    for sid in ctx.step_outputs:
        if "users" in sid:
            primary_step = sid
        elif "posts" in sid:
            primary_step = primary_step or sid
            secondary_step = sid
        elif "comments" in sid:
            secondary_step = sid

    if not primary_step:
        for sid in ctx.step_outputs:
            primary_step = sid
            break

    raw = ctx.step_outputs.get(primary_step, {})
    body = raw.get("body", "[]")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            body = []

    if not isinstance(body, list):
        body = [body]

    secondary_data = []
    if secondary_step:
        sec_raw = ctx.step_outputs.get(secondary_step, {})
        sec_body = sec_raw.get("body", "[]")
        if isinstance(sec_body, str):
            try:
                sec_body = json.loads(sec_body)
            except (json.JSONDecodeError, TypeError):
                sec_body = []
        secondary_data = sec_body if isinstance(sec_body, list) else [sec_body]

    result = {
        "source_step": primary_step,
        "record_count": len(body),
        "records": body[:10],
        "secondary_count": len(secondary_data),
        "transformed": True,
    }

    var_name = f"transformed_{primary_step.replace('fetch_', '')}"
    ctx.workflow_variables[var_name] = json.dumps(result, indent=2)
    return ctx
