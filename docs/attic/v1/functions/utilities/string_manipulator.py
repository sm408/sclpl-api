"""
@name: string_manipulator
@type: utility
@version: 1
@description: String operations: case conversion, trimming, replacement, extraction, and padding

Config via workflow_variables: string_operation (upper/lower/title/trim/replace/extract/pad/truncate/split),
string_input, string_pattern, string_replacement, string_length, string_pad_char.
"""

import re


def run(ctx):
    operation = ctx.workflow_variables.get("string_operation", "trim")
    text = ctx.workflow_variables.get("string_input", "")

    if not text:
        return {"success": False, "error": "No string_input provided"}

    if operation == "upper":
        result = text.upper()
    elif operation == "lower":
        result = text.lower()
    elif operation == "title":
        result = text.title()
    elif operation == "trim":
        result = text.strip()
    elif operation == "replace":
        pattern = ctx.workflow_variables.get("string_pattern", "")
        replacement = ctx.workflow_variables.get("string_replacement", "")
        result = text.replace(pattern, replacement)
    elif operation == "extract":
        pattern = ctx.workflow_variables.get("string_pattern", "")
        if not pattern:
            return {"success": False, "error": "No string_pattern provided for extract"}
        matches = re.findall(pattern, text)
        result = matches
    elif operation == "pad":
        length = int(ctx.workflow_variables.get("string_length", "10"))
        pad_char = ctx.workflow_variables.get("string_pad_char", " ")
        side = ctx.workflow_variables.get("string_pad_side", "right")
        if side == "left":
            result = text.rjust(length, pad_char)
        elif side == "center":
            result = text.center(length, pad_char)
        else:
            result = text.ljust(length, pad_char)
    elif operation == "truncate":
        length = int(ctx.workflow_variables.get("string_length", "100"))
        suffix = ctx.workflow_variables.get("string_suffix", "...")
        if len(text) > length:
            result = text[:length - len(suffix)] + suffix
        else:
            result = text
    elif operation == "split":
        separator = ctx.workflow_variables.get("string_separator", ",")
        result = [s.strip() for s in text.split(separator)]
    else:
        return {"success": False, "error": f"Unknown operation: {operation}"}

    ctx.workflow_variables["string_result"] = str(result) if not isinstance(result, list) else ",".join(result)

    return {
        "success": True,
        "result": result,
        "operation": operation,
    }
