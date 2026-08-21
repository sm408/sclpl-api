"""
@name: Export Weather Data
@type: exporter
@version: 1
"""

import csv
import json
from pathlib import Path


def run(ctx):
    output_dir = Path("examples/weather_pipeline/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    record = {
        "date": ctx.workflow_variables.get("today", "unknown"),
        "city": ctx.workflow_variables.get("city", "unknown"),
        "weatherAt5AM_tempC": ctx.workflow_variables.get("weatherAt5AM_tempC", "N/A"),
        "weatherAt5AM_desc": ctx.workflow_variables.get("weatherAt5AM_desc", "N/A"),
        "weatherAt5AM_humidity": ctx.workflow_variables.get("weatherAt5AM_humidity", "N/A"),
        "weatherAt5AM_windKmph": ctx.workflow_variables.get("weatherAt5AM_windKmph", "N/A"),
        "nearest_reading": ctx.workflow_variables.get("weatherAt5AM_actualTime", "N/A"),
    }

    json_path = output_dir / "weather_at_5am.json"
    with open(json_path, "w") as f:
        json.dump(record, f, indent=2)

    csv_path = output_dir / "weather_at_5am.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=record.keys())
        writer.writeheader()
        writer.writerow(record)

    ctx.metadata["export_result"] = {
        "json": str(json_path),
        "csv": str(csv_path),
        "record": record,
    }

    return ctx
