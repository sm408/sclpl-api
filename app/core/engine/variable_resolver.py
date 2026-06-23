from __future__ import annotations

import re
from typing import Any

from app.core.contracts.variable_resolver import VariableResolver
from app.core.models.context import ExecutionContext, ResolvedVariable

_VARIABLE_PATTERN = re.compile(r"\{\{([\w.]+)\}\}")


class DefaultVariableResolver(VariableResolver):
    def resolve(self, text: str, ctx: ExecutionContext) -> str:
        def _replace(match: re.Match[str]) -> str:
            key = match.group(1)
            return self._resolve_key(key, ctx)

        return _VARIABLE_PATTERN.sub(_replace, text)

    def _resolve_key(self, key: str, ctx: ExecutionContext) -> str:
        if "." not in key:
            return ctx.variables.get(key, ctx.step_outputs.get(key, "{{" + key + "}}"))

        parts = key.split(".")
        root = parts[0]
        raw = ctx.variables.get(root)
        if raw is None:
            raw = ctx.step_outputs.get(root)
        if raw is None:
            return "{{" + key + "}}"

        value: Any = raw
        if isinstance(value, str):
            import json as _json
            try:
                value = _json.loads(value)
            except (ValueError, TypeError):
                return "{{" + key + "}}"

        for part in parts[1:]:
            if isinstance(value, dict):
                if part not in value:
                    return "{{" + key + "}}"
                value = value[part]
            elif isinstance(value, list):
                try:
                    idx = int(part)
                except (ValueError, TypeError):
                    return "{{" + key + "}}"
                if idx < 0 or idx >= len(value):
                    return "{{" + key + "}}"
                value = value[idx]
            else:
                return "{{" + key + "}}"

        return str(value) if value is not None else "{{" + key + "}}"

    def resolve_all(self, ctx: ExecutionContext) -> list[ResolvedVariable]:
        resolved: list[ResolvedVariable] = []
        seen: set[str] = set()

        for key, value in ctx.variables.items():
            if key not in seen:
                seen.add(key)
                source = self._determine_source(key, ctx)
                resolved.append(ResolvedVariable(key=key, value=value, source=source))

        return resolved

    def extract_variable_keys(self, text: str) -> list[str]:
        return _VARIABLE_PATTERN.findall(text)

    def _determine_source(self, key: str, ctx: ExecutionContext) -> str:
        if key in ctx.batch_row:
            return "batch_row"
        if ctx.environment and any(v.key == key for v in ctx.environment.variables):
            return "environment"
        if key in ctx.workflow_variables:
            return "workflow"
        return "global"

    def build_variable_map(self, ctx: ExecutionContext) -> dict[str, str]:
        merged: dict[str, Any] = {}

        if ctx.environment:
            for var in ctx.environment.variables:
                if var.enabled:
                    merged[var.key] = var.value

        merged.update(ctx.workflow_variables)
        merged.update(ctx.batch_row)

        return {k: str(v) for k, v in merged.items()}
