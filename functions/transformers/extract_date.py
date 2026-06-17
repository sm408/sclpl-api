"""
@name: Extract Date
@type: transformer
@version: 1
"""

import json


def run(ctx):
    raw = ctx.step_outputs.get("get_weather_today")
    if not raw:
        return ctx

    body = raw.get("body", "{}") if isinstance(raw, dict) else "{}"
    try:
        data = json.loads(body)
        weather_list = data.get("weather", [])
        if weather_list:
            today = weather_list[0].get("date", "")
            ctx.workflow_variables["today"] = today
            ctx.workflow_variables["city"] = "NewYork"
    except (json.JSONDecodeError, TypeError):
        pass

    return ctx
