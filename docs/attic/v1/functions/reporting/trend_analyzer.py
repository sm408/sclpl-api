"""
@name: trend_analyzer
@type: report
@version: 1
@description: Analyze trends in time-series or sequential data: direction, slope, anomalies

Config via workflow_variables: trend_source (step output key),
trend_value_field, trend_time_field, trend_threshold (for anomaly detection).
"""

import json


def _get_nested(data, path):
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def run(ctx):
    source_key = ctx.workflow_variables.get("trend_source", "")
    value_field = ctx.workflow_variables.get("trend_value_field", "")
    time_field = ctx.workflow_variables.get("trend_time_field", "")
    threshold = float(ctx.workflow_variables.get("trend_threshold", "2.0"))

    data = ctx.workflow_variables.get(source_key) if source_key else None
    if data is None:
        data = ctx.step_outputs.get(source_key, []) if source_key else []

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            data = []

    if not isinstance(data, list) or len(data) < 2:
        return {"success": False, "error": "Need at least 2 data points for trend analysis"}

    values = []
    for item in data:
        if isinstance(item, dict) and value_field:
            val = _get_nested(item, value_field)
        else:
            val = item
        try:
            values.append(float(val))
        except (TypeError, ValueError):
            values.append(0)

    n = len(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    std_dev = variance ** 0.5

    if n >= 2:
        x_mean = (n - 1) / 2
        numerator = sum((i - x_mean) * (v - mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator else 0
    else:
        slope = 0

    if slope > 0.01:
        direction = "upward"
    elif slope < -0.01:
        direction = "downward"
    else:
        direction = "flat"

    anomalies = []
    if std_dev > 0:
        for i, v in enumerate(values):
            z_score = abs(v - mean) / std_dev
            if z_score > threshold:
                anomalies.append({"index": i, "value": v, "z_score": round(z_score, 2)})

    changes = [values[i] - values[i - 1] for i in range(1, n)]
    pct_changes = []
    for i in range(1, n):
        if values[i - 1] != 0:
            pct_changes.append(round(((values[i] - values[i - 1]) / abs(values[i - 1])) * 100, 2))

    result = {
        "direction": direction,
        "slope": round(slope, 4),
        "mean": round(mean, 4),
        "std_dev": round(std_dev, 4),
        "min": min(values),
        "max": max(values),
        "data_points": n,
        "anomalies": anomalies,
        "anomaly_count": len(anomalies),
        "avg_change": round(sum(changes) / len(changes), 4) if changes else 0,
        "avg_pct_change": round(sum(pct_changes) / len(pct_changes), 2) if pct_changes else 0,
    }

    ctx.workflow_variables["trend"] = json.dumps(result)

    return {
        "success": True,
        "trend": result,
    }
