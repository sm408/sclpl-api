"""
@name: summary_generator
@type: report
@version: 1
@description: Generate text summaries from data with key metrics and highlights

Config via workflow_variables: summary_source (step output key),
summary_title, summary_max_items (default 10).
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
    source_key = ctx.workflow_variables.get("summary_source", "")
    title = ctx.workflow_variables.get("summary_title", "Data Summary")
    max_items = int(ctx.workflow_variables.get("summary_max_items", "10"))

    data = ctx.workflow_variables.get(source_key) if source_key else None
    if data is None:
        data = ctx.step_outputs.get(source_key, []) if source_key else []

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            data = []

    lines = [title, "=" * len(title), ""]

    if isinstance(data, list):
        lines.append(f"Total records: {len(data)}")

        if data and isinstance(data[0], dict):
            keys = list(data[0].keys())
            lines.append(f"Fields: {', '.join(keys)}")

            numeric_fields = []
            for key in keys:
                try:
                    values = [float(_get_nested(item, key) or 0) for item in data if isinstance(item, dict)]
                    if values:
                        numeric_fields.append(key)
                        lines.append(f"\n  {key}:")
                        lines.append(f"    min: {min(values)}")
                        lines.append(f"    max: {max(values)}")
                        lines.append(f"    avg: {sum(values) / len(values):.2f}")
                except (TypeError, ValueError):
                    pass

            lines.append(f"\nFirst {min(max_items, len(data))} records:")
            for i, item in enumerate(data[:max_items]):
                lines.append(f"  [{i + 1}] {json.dumps(item, default=str)[:120]}")
    elif isinstance(data, dict):
        lines.append(f"Keys: {', '.join(data.keys())}")
        for key, value in list(data.items())[:max_items]:
            lines.append(f"  {key}: {str(value)[:100]}")

    summary = "\n".join(lines)
    ctx.workflow_variables["summary"] = summary

    return {
        "success": True,
        "summary": summary,
        "record_count": len(data) if isinstance(data, list) else 1,
    }
