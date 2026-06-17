"""
@name: Extract 5AM Weather
@type: transformer
@version: 1
"""

import json


def run(ctx):
    raw = ctx.step_outputs.get("get_weather_hourly")
    if not raw:
        return ctx

    body = raw.get("body", "{}") if isinstance(raw, dict) else "{}"
    try:
        data = json.loads(body)
        weather_list = data.get("weather", [])
        if weather_list:
            day = weather_list[0]
            hourly = day.get("hourly", [])
            target = None
            for entry in hourly:
                t = int(entry.get("time", "0"))
                if t <= 500:
                    target = entry
                else:
                    if target is None:
                        target = entry
                    break

            if target:
                time_str = target.get("time", "0")
                hour = int(time_str) // 100
                ctx.workflow_variables["weatherAt5AM_tempC"] = target.get("tempC", "N/A")
                ctx.workflow_variables["weatherAt5AM_desc"] = target.get("weatherDesc", [{}])[0].get("value", "N/A")
                ctx.workflow_variables["weatherAt5AM_humidity"] = target.get("humidity", "N/A")
                ctx.workflow_variables["weatherAt5AM_windKmph"] = target.get("windspeedKmph", "N/A")
                ctx.workflow_variables["weatherAt5AM_actualTime"] = f"{hour:02d}:00"
    except (json.JSONDecodeError, TypeError):
        pass

    return ctx
