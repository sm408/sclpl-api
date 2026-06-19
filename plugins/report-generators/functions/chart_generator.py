# -*- coding: utf-8 -*-
"""
@name: chart_generator
@type: report
@version: 1
@description: Generate text-based charts (bar, sparkline) from numerical data

Config via workflow_variables: chart_source (step output key),
chart_type (bar/sparkline), chart_label_field, chart_value_field,
chart_width (default 40), chart_title.
"""


def _bar_chart(labels: list[str], values: list[float], width: int, title: str) -> str:
    if not values:
        return f"{title}\n  No data."

    max_val = max(values) or 1
    max_label_len = max(len(str(l)) for l in labels) if labels else 0

    lines = [f"  {title}", ""]
    for label, value in zip(labels, values):
        bar_len = int((value / max_val) * width)
        bar = "█" * bar_len
        lines.append(f"  {str(label):<{max_label_len}} | {bar} {value}")

    return "\n".join(lines)


def _sparkline(values: list[float]) -> str:
    if not values:
        return ""

    blocks = " ▁▂▃▄▅▆▇█"
    min_val = min(values)
    max_val = max(values)
    spread = max_val - min_val or 1

    return "".join(blocks[min(8, int((v - min_val) / spread * 8))] for v in values)


def run(ctx):
    source_key = ctx.workflow_variables.get("chart_source", "")
    chart_type = ctx.workflow_variables.get("chart_type", "bar")
    label_field = ctx.workflow_variables.get("chart_label_field", "")
    value_field = ctx.workflow_variables.get("chart_value_field", "")
    width = int(ctx.workflow_variables.get("chart_width", "40"))
    title = ctx.workflow_variables.get("chart_title", "Chart")

    data = ctx.workflow_variables.get(source_key) if source_key else None
    if data is None:
        data = ctx.step_outputs.get(source_key, []) if source_key else []

    if isinstance(data, str):
        import json
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return {"success": False, "error": "Source data is not valid JSON"}

    if not isinstance(data, list):
        data = [data]

    labels = []
    values = []

    for item in data:
        if isinstance(item, dict):
            label = str(item.get(label_field, len(labels)))
            try:
                value = float(item.get(value_field, 0))
            except (TypeError, ValueError):
                value = 0
        else:
            label = str(len(labels))
            try:
                value = float(item)
            except (TypeError, ValueError):
                value = 0
        labels.append(label)
        values.append(value)

    if chart_type == "sparkline":
        chart = _sparkline(values)
        result = f"{title}: {chart}"
    else:
        chart = _bar_chart(labels, values, width, title)
        result = chart

    ctx.workflow_variables["chart_output"] = result

    return {
        "success": True,
        "chart": result,
        "data_points": len(values),
    }
