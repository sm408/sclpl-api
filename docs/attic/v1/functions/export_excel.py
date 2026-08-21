"""
@name: Export Excel Report
@type: exporter
@version: 1

Exports workflow report data to an Excel (.xlsx) file.
Falls back to CSV if openpyxl is not installed.

Reads JSON data from ctx.workflow_variables["report_data"] and writes
the output file path back to ctx.workflow_variables["export_file_path"].
"""

import csv
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def run(ctx):
    output_dir = Path(ctx.workflow_variables.get("export_output_dir", "output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = ctx.workflow_variables.get("export_filename", "report")

    raw = ctx.workflow_variables.get("report_data", "{}")
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            data = {}
    else:
        data = raw

    rows = _extract_rows(data)

    try:
        import openpyxl

        path = _write_xlsx(output_dir, filename, rows, openpyxl)
    except ImportError:
        logger.info("openpyxl not installed, falling back to CSV export")
        path = _write_csv(output_dir, filename, rows)

    ctx.workflow_variables["export_file_path"] = str(path)
    ctx.metadata["export_result"] = {"path": str(path), "rows": len(rows)}
    return ctx


def _extract_rows(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "rows" in data and isinstance(data["rows"], list):
            return data["rows"]
        if "data" in data and isinstance(data["data"], list):
            return data["data"]
        if "items" in data and isinstance(data["items"], list):
            return data["items"]
        return [data]
    return []


def _write_xlsx(output_dir, filename, rows, openpyxl):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Report"

    if not rows:
        ws.append(["(no data)"])
        path = output_dir / f"{filename}.xlsx"
        wb.save(path)
        return path

    if isinstance(rows[0], dict):
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h, "") for h in headers])
    else:
        ws.append(["value"])
        for row in rows:
            ws.append([row])

    path = output_dir / f"{filename}.xlsx"
    wb.save(path)
    logger.info("Wrote Excel report: %s (%d rows)", path, len(rows))
    return path


def _write_csv(output_dir, filename, rows):
    path = output_dir / f"{filename}.csv"

    if not rows:
        with open(path, "w", newline="") as f:
            f.write("(no data)\n")
        return path

    if isinstance(rows[0], dict):
        headers = list(rows[0].keys())
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
    else:
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["value"])
            for row in rows:
                writer.writerow([row])

    logger.info("Wrote CSV report: %s (%d rows)", path, len(rows))
    return path
