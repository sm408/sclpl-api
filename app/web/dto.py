"""Data Transfer Objects for the web API.

All DTOs use camelCase aliases so the JSON wire format is camelCase
while Python code uses snake_case.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(string: str) -> str:
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class CamelModel(BaseModel):
    """Base model that serialises to/from camelCase."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )


# ── Error protocol ──────────────────────────────────────────────────────


class FieldError(CamelModel):
    field: str
    message: str


class ErrorBody(CamelModel):
    code: str
    message: str
    field_errors: list[FieldError] = Field(default_factory=list)
    correlation_id: str = ""


class ErrorResponse(CamelModel):
    error: ErrorBody


# ── Pagination ──────────────────────────────────────────────────────────


class PaginatedResponse(CamelModel):
    """Standard envelope for list endpoints."""

    items: list[Any]
    next_cursor: str | None = None
    total: int = 0


# ── Health ──────────────────────────────────────────────────────────────


class HealthResponse(CamelModel):
    status: str
    version: str
    schema_version: int


# ── Project DTOs ────────────────────────────────────────────────────────


class ProjectCreate(CamelModel):
    name: str
    description: str = ""


class ProjectUpdate(CamelModel):
    name: str | None = None
    description: str | None = None


class ProjectResponse(CamelModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: str
    name: str
    description: str = ""
    root_path: str = ""
    is_default: bool = False
    created_at: str | None = None
    updated_at: str | None = None


# ── Collection DTOs ────────────────────────────────────────────────────


class CollectionCreate(CamelModel):
    name: str
    description: str = ""


class CollectionUpdate(CamelModel):
    name: str | None = None
    description: str | None = None
    revision: int | None = None


class CollectionResponse(CamelModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: str
    project_id: str
    name: str
    description: str = ""
    revision: int = 1
    created_at: str | None = None
    updated_at: str | None = None


# ── Request DTOs ───────────────────────────────────────────────────────


class ParamDto(CamelModel):
    """Ordered key/value pair with enabled flag."""

    key: str
    value: str
    enabled: bool = True


class RequestCreate(CamelModel):
    name: str
    method: str = "GET"
    url: str = ""
    collection_id: str | None = None
    headers: list[ParamDto] = Field(default_factory=list)
    query_params: list[ParamDto] = Field(default_factory=list)
    body: str | None = None
    body_type: str | None = None
    auth_type: str | None = None
    auth_config: dict[str, Any] = Field(default_factory=dict)


class RequestUpdate(CamelModel):
    name: str | None = None
    method: str | None = None
    url: str | None = None
    collection_id: str | None = None
    headers: list[ParamDto] | None = None
    query_params: list[ParamDto] | None = None
    body: str | None = None
    body_type: str | None = None
    auth_type: str | None = None
    auth_config: dict[str, Any] | None = None
    revision: int | None = None


class RequestResponse(CamelModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: str
    project_id: str
    collection_id: str | None = None
    name: str
    method: str
    url: str
    headers: list[ParamDto] = Field(default_factory=list)
    query_params: list[ParamDto] = Field(default_factory=list)
    body: str | None = None
    body_type: str | None = None
    auth_type: str | None = None
    auth_config: dict[str, Any] = Field(default_factory=dict)
    revision: int = 1
    created_at: str | None = None
    updated_at: str | None = None


# ── Environment DTOs ───────────────────────────────────────────────────


class VariableDto(CamelModel):
    key: str
    value: str
    scope: str = "environment"
    is_secret: bool = False
    enabled: bool = True


class EnvironmentCreate(CamelModel):
    name: str
    variables: list[VariableDto] = Field(default_factory=list)


class EnvironmentUpdate(CamelModel):
    name: str | None = None


class EnvironmentResponse(CamelModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: str
    project_id: str
    name: str
    is_active: bool = False
    variables: list[VariableDto] = Field(default_factory=list)
    revision: int = 1
    created_at: str | None = None
    updated_at: str | None = None


class VariableCreate(CamelModel):
    key: str
    value: str
    is_secret: bool = False


# ── History DTOs ───────────────────────────────────────────────────────


class HistoryResponse(CamelModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: str
    project_id: str
    request_id: str | None = None
    request_name: str
    method: str
    url: str
    status: str
    status_code: int | None = None
    response_body: str | None = None
    response_headers: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int = 0
    error_message: str | None = None
    environment_id: str | None = None
    variables_used: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


# ── Execute DTOs ───────────────────────────────────────────────────────


class ExecuteRequest(CamelModel):
    variables: dict[str, str] = Field(default_factory=dict)


class RunResultResponse(CamelModel):
    status_code: int
    headers: dict[str, str] = Field(default_factory=dict)
    body: str = ""
    duration_ms: int = 0
    error: str | None = None


# ── Workflow DTOs ─────────────────────────────────────────────────────


class GraphLayoutDto(CamelModel):
    """Visual layout metadata for workflow graph nodes."""
    nodes: dict[str, dict[str, float]] = Field(default_factory=dict)
    viewport: dict[str, float] = Field(default_factory=dict)


class WorkflowCreate(CamelModel):
    name: str
    description: str = ""
    definition: dict[str, Any] | None = None
    layout: GraphLayoutDto | None = None
    sclpll_source: str = ""


class WorkflowUpdate(CamelModel):
    name: str | None = None
    description: str | None = None
    definition: dict[str, Any] | None = None
    layout: GraphLayoutDto | None = None
    sclpll_source: str | None = None
    revision: int | None = None


class WorkflowResponse(CamelModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: str
    project_id: str
    name: str
    description: str = ""
    definition: dict[str, Any] = Field(default_factory=dict)
    layout: GraphLayoutDto = Field(default_factory=GraphLayoutDto)
    sclpll_source: str = ""
    revision: int = 1
    created_at: str | None = None
    updated_at: str | None = None


class WorkflowVersionResponse(CamelModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: str
    workflow_id: str
    version: int
    definition: dict[str, Any] = Field(default_factory=dict)
    sclpll_source: str = ""
    description: str = ""
    author: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class DiffEntryDto(CamelModel):
    path: str
    action: str
    old_value: Any = None
    new_value: Any = None


class SourceDiagnosticDto(CamelModel):
    line: int
    column: int
    severity: str
    message: str


class ParseResultDto(CamelModel):
    success: bool
    definition: dict[str, Any] | None = None
    diagnostics: list[SourceDiagnosticDto] = Field(default_factory=list)
    source_hash: str = ""


class PreviewResultDto(CamelModel):
    definition: dict[str, Any]
    sclpll_source: str
    diff: list[DiffEntryDto] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    losses: list[str] = Field(default_factory=list)


class PreflightResultDto(CamelModel):
    valid: bool
    issues: list[dict[str, Any]] = Field(default_factory=list)


class RevisionConflictDto(CamelModel):
    current_revision: int
    attempted_revision: int
    current_definition: dict[str, Any]
    server_diff: list[DiffEntryDto] = Field(default_factory=list)


class SclpllApplyRequest(CamelModel):
    source: str
    revision: int | None = None


class VersionCreateRequest(CamelModel):
    description: str = ""
    author: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class VersionRestoreRequest(CamelModel):
    version: int


class VersionCompareRequest(CamelModel):
    version_a: int
    version_b: int


class GenerateSclpllResponse(CamelModel):
    sclpll_source: str


# ── Function DTOs ──────────────────────────────────────────────────────


class FunctionCreate(CamelModel):
    name: str
    source: str
    description: str = ""


class FunctionUpdate(CamelModel):
    name: str | None = None
    source: str | None = None
    description: str | None = None
    expected_hash: str | None = None


class FunctionResponse(CamelModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    path: str
    name: str
    description: str = ""
    type: str = "utility"
    category: str = "uncategorized"
    content: str = ""
    hash: str = ""
    size: int = 0
    valid: bool = True
    diagnostics: list[dict] = Field(default_factory=list)
    trusted: bool = False


class FunctionListItem(CamelModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    path: str
    name: str
    description: str = ""
    type: str = "utility"
    category: str = "uncategorized"
    hash: str = ""
    size: int = 0


class FileTreeEntry(CamelModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    path: str
    name: str
    type: str
    size: int | None = None
    children: list[dict] = Field(default_factory=list)


class AstValidationResult(CamelModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    valid: bool
    diagnostics: list[dict] = Field(default_factory=list)


class FixtureResult(CamelModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: int = 0
    stdout: str = ""
    stderr: str = ""


class TrustAckRequest(CamelModel):
    path: str
    content_hash: str


class TrustAckResponse(CamelModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    path: str
    hash: str
    trusted: bool


class FixtureRunRequest(CamelModel):
    fixture_input: dict[str, Any] = Field(default_factory=dict)
    trusted: bool = False


# ── Plugin DTOs ─────────────────────────────────────────────────────────


class PluginResponse(CamelModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    id: str
    name: str
    version: str
    description: str = ""
    author: str = ""
    category: str = ""
    status: str = "discovered"
    function_count: int = 0
    workflow_count: int = 0
    variable_names: list[str] = Field(default_factory=list)
    error: str | None = None
    dependencies: list[str] = Field(default_factory=list)


class PluginScaffoldRequest(CamelModel):
    name: str
    description: str = ""


class PluginManifestUpdate(CamelModel):
    data: dict[str, Any] = Field(default_factory=dict)


class PluginDiagnostics(CamelModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    name: str
    status: str
    function_count: int = 0
    workflow_count: int = 0
    variable_names: list[str] = Field(default_factory=list)
    error: str | None = None
    dependencies: list[str] = Field(default_factory=list)


class PluginFileWrite(CamelModel):
    content: str
    expected_hash: str | None = None
