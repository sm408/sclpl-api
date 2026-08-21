"""
@name: json_validator
@type: validator
@version: 1
@description: Validate JSON data against a schema definition

Config via workflow_variables: validate_source (step output key),
validate_schema (JSON schema as string), validate_strict (true/false).
"""

import json


def _validate_type(value, expected_type):
    type_map = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }
    expected = type_map.get(expected_type)
    if expected is None:
        return True
    return isinstance(value, expected)


def _validate_schema(data, schema, path=""):
    errors = []

    if "type" in schema:
        if not _validate_type(data, schema["type"]):
            errors.append(f"{path or '/'}: expected type '{schema['type']}', got '{type(data).__name__}'")
            return errors

    if schema.get("type") == "object" and isinstance(data, dict):
        required = schema.get("required", [])
        for field in required:
            if field not in data:
                errors.append(f"{path}/{field}: required field missing")

        properties = schema.get("properties", {})
        for key, prop_schema in properties.items():
            if key in data:
                errors.extend(_validate_schema(data[key], prop_schema, f"{path}/{key}"))

    if schema.get("type") == "array" and isinstance(data, list):
        items_schema = schema.get("items")
        if items_schema:
            min_items = schema.get("minItems")
            max_items = schema.get("maxItems")
            if min_items is not None and len(data) < min_items:
                errors.append(f"{path}: array has {len(data)} items, minimum is {min_items}")
            if max_items is not None and len(data) > max_items:
                errors.append(f"{path}: array has {len(data)} items, maximum is {max_items}")
            for i, item in enumerate(data):
                errors.extend(_validate_schema(item, items_schema, f"{path}[{i}]"))

    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: value '{data}' not in enum {schema['enum']}")

    if "minimum" in schema and isinstance(data, (int, float)):
        if data < schema["minimum"]:
            errors.append(f"{path}: value {data} is below minimum {schema['minimum']}")

    if "maximum" in schema and isinstance(data, (int, float)):
        if data > schema["maximum"]:
            errors.append(f"{path}: value {data} is above maximum {schema['maximum']}")

    if "minLength" in schema and isinstance(data, str):
        if len(data) < schema["minLength"]:
            errors.append(f"{path}: string length {len(data)} is below minimum {schema['minLength']}")

    if "maxLength" in schema and isinstance(data, str):
        if len(data) > schema["maxLength"]:
            errors.append(f"{path}: string length {len(data)} is above maximum {schema['maxLength']}")

    if "pattern" in schema and isinstance(data, str):
        import re
        if not re.search(schema["pattern"], data):
            errors.append(f"{path}: string does not match pattern '{schema['pattern']}'")

    return errors


def run(ctx):
    source_key = ctx.workflow_variables.get("validate_source", "")
    schema_raw = ctx.workflow_variables.get("validate_schema", "{}")

    data = ctx.workflow_variables.get(source_key) if source_key else None
    if data is None:
        data = ctx.step_outputs.get(source_key) if source_key else None

    if data is None:
        return {"success": False, "error": "No data to validate"}

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return {"success": False, "error": "Source data is not valid JSON"}

    try:
        schema = json.loads(schema_raw)
    except (json.JSONDecodeError, TypeError):
        return {"success": False, "error": "Schema is not valid JSON"}

    errors = _validate_schema(data, schema)

    return {
        "success": len(errors) == 0,
        "valid": len(errors) == 0,
        "errors": errors,
        "error_count": len(errors),
    }
