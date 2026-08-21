"""
@name: math_operations
@type: utility
@version: 1
@description: Math operations: basic arithmetic, statistics, rounding, and random numbers

Config via workflow_variables: math_operation (add/sub/mul/div/avg/sum/min/max/round/random/abs/mod),
math_values (comma-separated numbers), math_a, math_b, math_precision, math_min, math_max.
"""

import json
import random


def run(ctx):
    operation = ctx.workflow_variables.get("math_operation", "sum")
    values_raw = ctx.workflow_variables.get("math_values", "")
    precision = int(ctx.workflow_variables.get("math_precision", "4"))

    values = []
    if values_raw:
        for v in values_raw.split(","):
            v = v.strip()
            try:
                values.append(float(v))
            except (ValueError, TypeError):
                pass

    a = ctx.workflow_variables.get("math_a")
    b = ctx.workflow_variables.get("math_b")

    if operation == "add":
        if a is not None and b is not None:
            result = float(a) + float(b)
        elif values:
            result = sum(values)
        else:
            return {"success": False, "error": "Provide math_a and math_b or math_values"}

    elif operation == "sub":
        if a is not None and b is not None:
            result = float(a) - float(b)
        else:
            return {"success": False, "error": "Provide math_a and math_b"}

    elif operation == "mul":
        if a is not None and b is not None:
            result = float(a) * float(b)
        elif values:
            result = 1
            for v in values:
                result *= v
        else:
            return {"success": False, "error": "Provide math_a and math_b or math_values"}

    elif operation == "div":
        if a is not None and b is not None:
            if float(b) == 0:
                return {"success": False, "error": "Division by zero"}
            result = float(a) / float(b)
        else:
            return {"success": False, "error": "Provide math_a and math_b"}

    elif operation == "mod":
        if a is not None and b is not None:
            if float(b) == 0:
                return {"success": False, "error": "Modulo by zero"}
            result = float(a) % float(b)
        else:
            return {"success": False, "error": "Provide math_a and math_b"}

    elif operation == "sum":
        result = sum(values) if values else 0

    elif operation == "avg":
        result = sum(values) / len(values) if values else 0

    elif operation == "min":
        result = min(values) if values else 0

    elif operation == "max":
        result = max(values) if values else 0

    elif operation == "abs":
        val = float(a) if a is not None else (values[0] if values else 0)
        result = abs(val)

    elif operation == "round":
        val = float(a) if a is not None else (values[0] if values else 0)
        result = round(val, precision)

    elif operation == "random":
        min_val = float(ctx.workflow_variables.get("math_min", "0"))
        max_val = float(ctx.workflow_variables.get("math_max", "100"))
        result = random.uniform(min_val, max_val)
        result = round(result, precision)

    elif operation == "pow":
        if a is not None and b is not None:
            result = float(a) ** float(b)
        else:
            return {"success": False, "error": "Provide math_a and math_b"}

    else:
        return {"success": False, "error": f"Unknown operation: {operation}"}

    if isinstance(result, float):
        result = round(result, precision)

    ctx.workflow_variables["math_result"] = str(result)

    return {
        "success": True,
        "result": result,
        "operation": operation,
    }
