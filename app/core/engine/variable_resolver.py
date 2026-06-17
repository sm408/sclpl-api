from __future__ import annotations

import re
from typing import Any

from app.core.contracts.variable_resolver import VariableResolver
from app.core.models.context import ExecutionContext, ResolvedVariable
from app.core.models.environment import VariableScope

_VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")


class DefaultVariableResolver(VariableResolver):
    def resolve(self, text: str, ctx: ExecutionContext) -> str:
        def _replace(match: re.Match[str]) -> str:
            key = match.group(1)
            return ctx.variables.get(key, match.group(0))

        return _VARIABLE_PATTERN.sub(_replace, text)

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
