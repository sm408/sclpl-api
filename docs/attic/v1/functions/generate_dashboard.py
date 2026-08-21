"""
@name: Generate Dashboard
@type: transformer
@version: 1

Combines current weather, forecast, and alerts into a unified dashboard view.
"""

import json
from datetime import datetime, timezone


def run(ctx):
    current_raw = ctx.step_outputs.get("fetch_current_weather", {})
    forecast_raw = ctx.step_outputs.get("fetch_forecast", {})
    alerts_raw = ctx.step_outputs.get("fetch_alerts", {})

    current_body = current_raw.get("body", "") if isinstance(current_raw.get("body"), str) else json.dumps(current_raw.get("body", ""))
    forecast_body = forecast_raw.get("body", "") if isinstance(forecast_raw.get("body"), str) else json.dumps(forecast_raw.get("body", ""))
    alerts_body = alerts_raw.get("body", "") if isinstance(alerts_raw.get("body"), str) else json.dumps(alerts_raw.get("body", ""))

    dashboard = {
        "dashboard_title": "Weather Dashboard",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_conditions": {
            "source": "wttr.in",
            "data": current_body[:500] if current_body else "No data available",
            "status": current_raw.get("status_code", 0),
        },
        "forecast": {
            "source": "wttr.in",
            "data": forecast_body[:500] if forecast_body else "No data available",
            "status": forecast_raw.get("status_code", 0),
        },
        "alerts": {
            "source": "wttr.in",
            "data": alerts_body[:500] if alerts_body else "No alerts",
            "status": alerts_raw.get("status_code", 0),
            "has_alerts": bool(alerts_body and "unknown" not in alerts_body.lower()),
        },
        "data_sources_ok": all(
            s.get("status_code", 0) == 200
            for s in [current_raw, forecast_raw, alerts_raw]
            if s
        ),
    }

    ctx.workflow_variables["dashboard"] = json.dumps(dashboard, indent=2)
    return ctx
