from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkflowRunRequest(BaseModel):
    workflow_id: str
    env_name: str | None = None
    variables: dict[str, str] = Field(default_factory=dict)


class StepResultResponse(BaseModel):
    step_id: str
    step_name: str
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: int = 0


class WorkflowRunResponse(BaseModel):
    workflow_id: str
    workflow_name: str
    success: bool
    step_results: list[StepResultResponse] = Field(default_factory=list)
    total_duration_ms: int = 0
    parallel_groups: list[list[str]] = Field(default_factory=list)
    error: str | None = None


class WorkflowInfo(BaseModel):
    id: str
    name: str
    description: str = ""
    step_count: int = 0
    path: str = ""


class WorkflowDetail(BaseModel):
    id: str
    name: str
    description: str = ""
    steps: list[dict[str, Any]] = Field(default_factory=list)
    variables: dict[str, str] = Field(default_factory=dict)
    path: str = ""


class SendRequestRequest(BaseModel):
    url: str
    method: str = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    body: str | None = None
    body_type: str | None = None
    auth_type: str | None = None
    auth_config: dict[str, Any] = Field(default_factory=dict)


class SendRequestResponse(BaseModel):
    status_code: int
    headers: dict[str, str] = Field(default_factory=dict)
    body: str = ""
    duration_ms: int = 0
    error: str | None = None


class FunctionInfo(BaseModel):
    name: str
    type: str = ""
    version: str = ""
    description: str = ""
    path: str = ""
    source: str = "local"


class HistoryEntryResponse(BaseModel):
    id: str
    request_id: str | None = None
    request_name: str | None = None
    method: str | None = None
    url: str | None = None
    status: str | None = None
    status_code: int | None = None
    duration_ms: int = 0
    error_message: str | None = None
    created_at: str | None = None


class CollectionCreateRequest(BaseModel):
    name: str
    description: str = ""


class CollectionResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    created_at: str | None = None
    requests: list[dict[str, Any]] = Field(default_factory=list)


class EnvironmentResponse(BaseModel):
    id: str
    name: str
    is_active: bool = False
    variables: list[dict[str, Any]] = Field(default_factory=list)


class PluginInfoResponse(BaseModel):
    name: str
    version: str
    status: str
    description: str = ""
    function_count: int = 0
    workflow_count: int = 0


class SCLPLLCompileRequest(BaseModel):
    source: str


class SCLPLLCompileResponse(BaseModel):
    workflow: dict[str, Any]
    compiled_json: str


class SCLPLLValidateRequest(BaseModel):
    source: str


class SCLPLLValidateResponse(BaseModel):
    valid: bool
    error: str | None = None
    line_number: int | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
