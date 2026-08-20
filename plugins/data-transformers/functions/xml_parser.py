"""
@name: xml_parser
@type: transformer
@version: 1
@description: Parse XML responses and convert to Python dicts

Config via workflow_variables: xml_source (step output key or inline XML),
xml_root_tag (optional root tag filter).
"""

import json
import re


def _parse_xml_element(xml_str: str) -> dict:
    result = {}
    tag_pattern = re.compile(r"<(\w+)([^>]*)>(.*?)</\1>|<(\w+)([^>]*)/>", re.DOTALL)

    for match in tag_pattern.finditer(xml_str):
        tag = match.group(1) or match.group(4)
        content = match.group(3) or ""

        if not tag:
            continue

        inner_tags = tag_pattern.findall(content)
        if inner_tags:
            result[tag] = _parse_xml_element(content)
        else:
            text = content.strip()
            if not text:
                attrs = match.group(2) or match.group(5) or ""
                attr_dict = {}
                for attr_match in re.finditer(r'(\w+)="([^"]*)"', attrs):
                    attr_dict[attr_match.group(1)] = attr_match.group(2)
                if attr_dict:
                    result[tag] = attr_dict
            else:
                result[tag] = text

    return result


def run(ctx):
    source_key = ctx.workflow_variables.get("xml_source", "")
    root_tag = ctx.workflow_variables.get("xml_root_tag", "")

    xml_str = ctx.workflow_variables.get(source_key, "") if source_key else ""
    if not xml_str:
        xml_str = ctx.step_outputs.get(source_key, "") if source_key else ""

    if not xml_str:
        return {"success": False, "error": "No XML data found"}

    if isinstance(xml_str, dict):
        xml_str = json.dumps(xml_str)

    xml_str = str(xml_str).strip()

    try:
        parsed = _parse_xml_element(xml_str)
    except Exception as exc:
        return {"success": False, "error": f"XML parsing failed: {exc}"}

    if root_tag and root_tag in parsed:
        parsed = parsed[root_tag]

    return {
        "success": True,
        "parsed": parsed,
        "root_tag": root_tag or "root",
    }
