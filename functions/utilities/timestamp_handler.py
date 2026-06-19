"""
@name: timestamp_handler
@type: utility
@version: 1
@description: Handle timestamp operations: format, parse, convert, and calculate durations

Config via workflow_variables: timestamp_operation (now/format/parse/diff/add),
timestamp_input, timestamp_format (strftime pattern),
timestamp_target_tz, timestamp_add_unit, timestamp_add_value.
"""

import time
from datetime import datetime, timedelta, timezone


def run(ctx):
    operation = ctx.workflow_variables.get("timestamp_operation", "now")
    ts_input = ctx.workflow_variables.get("timestamp_input", "")
    fmt = ctx.workflow_variables.get("timestamp_format", "%Y-%m-%d %H:%M:%S")
    target_tz = ctx.workflow_variables.get("timestamp_target_tz", "")

    if operation == "now":
        now = datetime.now(timezone.utc)
        result = {
            "unix": int(now.timestamp()),
            "iso": now.isoformat(),
            "formatted": now.strftime(fmt),
        }
        ctx.workflow_variables["timestamp"] = str(int(now.timestamp()))
        ctx.workflow_variables["timestamp_iso"] = now.isoformat()
        return {"success": True, "timestamp": result}

    elif operation == "format":
        try:
            ts = float(ts_input)
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            try:
                dt = datetime.fromisoformat(ts_input)
            except (ValueError, TypeError):
                return {"success": False, "error": f"Cannot parse timestamp: {ts_input}"}

        formatted = dt.strftime(fmt)
        ctx.workflow_variables["formatted_timestamp"] = formatted
        return {"success": True, "formatted": formatted, "iso": dt.isoformat()}

    elif operation == "parse":
        try:
            dt = datetime.strptime(ts_input, fmt)
        except (ValueError, TypeError):
            try:
                dt = datetime.fromisoformat(ts_input)
            except (ValueError, TypeError):
                return {"success": False, "error": f"Cannot parse: '{ts_input}' with format '{fmt}'"}

        result = {
            "unix": int(dt.timestamp()),
            "iso": dt.isoformat(),
            "year": dt.year,
            "month": dt.month,
            "day": dt.day,
            "hour": dt.hour,
            "minute": dt.minute,
            "second": dt.second,
        }
        ctx.workflow_variables["parsed_timestamp"] = str(int(dt.timestamp()))
        return {"success": True, "parsed": result}

    elif operation == "diff":
        ts_a = ctx.workflow_variables.get("timestamp_a", ts_input)
        ts_b = ctx.workflow_variables.get("timestamp_b", str(int(time.time())))

        try:
            dt_a = datetime.fromtimestamp(float(ts_a), tz=timezone.utc)
            dt_b = datetime.fromtimestamp(float(ts_b), tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            return {"success": False, "error": "Cannot parse timestamps for diff"}

        diff = dt_b - dt_a
        result = {
            "seconds": int(diff.total_seconds()),
            "minutes": round(diff.total_seconds() / 60, 2),
            "hours": round(diff.total_seconds() / 3600, 2),
            "days": round(diff.total_seconds() / 86400, 2),
        }
        return {"success": True, "diff": result}

    elif operation == "add":
        try:
            base_dt = datetime.fromtimestamp(float(ts_input), tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            try:
                base_dt = datetime.fromisoformat(ts_input)
            except (ValueError, TypeError):
                return {"success": False, "error": f"Cannot parse base timestamp: {ts_input}"}

        unit = ctx.workflow_variables.get("timestamp_add_unit", "days")
        value = int(ctx.workflow_variables.get("timestamp_add_value", "1"))

        delta_kwargs = {unit: value}
        try:
            new_dt = base_dt + timedelta(**delta_kwargs)
        except TypeError:
            return {"success": False, "error": f"Invalid unit: {unit}"}

        ctx.workflow_variables["result_timestamp"] = str(int(new_dt.timestamp()))
        return {
            "success": True,
            "result": int(new_dt.timestamp()),
            "result_iso": new_dt.isoformat(),
        }

    return {"success": False, "error": f"Unknown operation: {operation}"}
