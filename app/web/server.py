from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.engine.parallel_workflow import ParallelWorkflowEngine
from app.core.engine.sclpll_compiler import SCLPLLCompiler, SCLPLLParseError
from app.core.models.context import ExecutionContext
from app.core.models.request import HttpMethod, RequestDef, RequestParam
from app.core.models.workflow import (
    RetryConfig,
    RetryStrategy,
    StepType,
    WorkflowDef,
    WorkflowStep,
)
from app.ui.app import App
from app.web.models import (
    CollectionCreateRequest,
    CollectionResponse,
    EnvironmentResponse,
    FunctionInfo,
    HealthResponse,
    HistoryEntryResponse,
    PluginInfoResponse,
    SCLPLLCompileRequest,
    SCLPLLCompileResponse,
    SCLPLLValidateRequest,
    SCLPLLValidateResponse,
    SendRequestRequest,
    SendRequestResponse,
    StepResultResponse,
    WorkflowDetail,
    WorkflowInfo,
    WorkflowRunRequest,
    WorkflowRunResponse,
)

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
EXAMPLES_DIR = Path("examples")
FUNCTIONS_DIR = Path("functions")
PLUGINS_DIR = Path("plugins")


def create_app(db_path: str | None = None) -> FastAPI:
    application = App(db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await application.start()
        yield
        await application.stop()

    app = FastAPI(
        title="SCLPLAPI",
        description="Local-first, Python-first API workflow studio",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Health ────────────────────────────────────────────────────────

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse()

    # ── Workflows ─────────────────────────────────────────────────────

    @app.get("/api/workflows", response_model=list[WorkflowInfo])
    async def list_workflows() -> list[WorkflowInfo]:
        workflows: list[WorkflowInfo] = []
        if EXAMPLES_DIR.exists():
            for wf_dir in sorted(EXAMPLES_DIR.iterdir()):
                wf_file = wf_dir / "workflow.json"
                if wf_file.exists():
                    try:
                        data = json.loads(wf_file.read_text(encoding="utf-8"))
                        workflows.append(WorkflowInfo(
                            id=data.get("id", wf_dir.name),
                            name=data.get("name", wf_dir.name),
                            description=data.get("description", ""),
                            step_count=len(data.get("steps", [])),
                            path=str(wf_file),
                        ))
                    except Exception as exc:
                        logger.warning("Failed to load workflow %s: %s", wf_file, exc)
        return workflows

    @app.get("/api/workflows/{workflow_id}", response_model=WorkflowDetail)
    async def get_workflow(workflow_id: str) -> WorkflowDetail:
        wf_file = _find_workflow_file(workflow_id)
        if not wf_file:
            raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
        data = json.loads(wf_file.read_text(encoding="utf-8"))
        return WorkflowDetail(
            id=data.get("id", workflow_id),
            name=data.get("name", workflow_id),
            description=data.get("description", ""),
            steps=data.get("steps", []),
            variables=data.get("variables", {}),
            path=str(wf_file),
        )

    @app.post("/api/workflows/run", response_model=WorkflowRunResponse)
    async def run_workflow(req: WorkflowRunRequest) -> WorkflowRunResponse:
        wf_file = _find_workflow_file(req.workflow_id)
        if not wf_file:
            raise HTTPException(status_code=404, detail=f"Workflow '{req.workflow_id}' not found")

        data = json.loads(wf_file.read_text(encoding="utf-8"))

        steps = []
        for s in data.get("steps", []):
            steps.append(WorkflowStep(
                id=s["id"],
                name=s.get("name", s["id"]),
                step_type=StepType(s["type"]),
                request_id=s.get("request_id"),
                function_name=s.get("function_name"),
                config=s.get("config", {}),
                depends_on=s.get("depends_on", []),
                condition=s.get("condition"),
                output_variable=s.get("output_variable"),
                semaphore=s.get("semaphore"),
                foreach_collection=s.get("foreach_collection"),
                foreach_variable=s.get("foreach_variable"),
                repeat_count=s.get("repeat_count"),
                retry=RetryConfig(
                    max_retries=s.get("retry", {}).get("max_retries", 0),
                    delay_ms=s.get("retry", {}).get("delay_ms", 1000),
                    strategy=RetryStrategy(s.get("retry", {}).get("strategy", "fixed")),
                ),
            ))

        workflow_def = WorkflowDef(
            id=data.get("id", req.workflow_id),
            name=data.get("name", req.workflow_id),
            description=data.get("description", ""),
            steps=steps,
            variables={**data.get("variables", {}), **req.variables},
        )

        requests_map: dict[str, RequestDef] = {}
        for s in steps:
            if s.request_id:
                req_data = await application.requests.get(s.request_id)
                if req_data:
                    headers = [
                        RequestParam(key=h["key"], value=h["value"])
                        for h in json.loads(req_data.get("headers", "[]"))
                    ]
                    requests_map[s.request_id] = RequestDef(
                        id=req_data["id"],
                        name=req_data["name"],
                        method=HttpMethod(req_data["method"]),
                        url=req_data["url"],
                        headers=headers,
                        body=req_data.get("body"),
                        auth_type=req_data.get("auth_type"),
                        auth_config=json.loads(req_data.get("auth_config", "{}")),
                    )

        ctx = ExecutionContext()
        if req.env_name:
            envs = await application.environments.list_all()
            env = next((e for e in envs if e["name"] == req.env_name), None)
            if env:
                ctx.environment = None
                for v in env.get("variables", []):
                    ctx.variables[v["key"]] = v["value"]
        else:
            active_env = await application.environments.get_active()
            if active_env:
                for v in active_env.get("variables", []):
                    ctx.variables[v["key"]] = v["value"]

        engine = ParallelWorkflowEngine(
            request_executor=application.request_executor,
            event_bus=application.event_bus,
        )

        result = await engine.execute(workflow_def, ctx, requests_map)

        return WorkflowRunResponse(
            workflow_id=result.workflow_id,
            workflow_name=result.workflow_name,
            success=result.success,
            step_results=[
                StepResultResponse(
                    step_id=sr.step_id,
                    step_name=sr.step_name,
                    success=sr.success,
                    output=sr.output,
                    error=sr.error,
                    duration_ms=sr.duration_ms,
                )
                for sr in result.step_results
            ],
            total_duration_ms=result.total_duration_ms,
            parallel_groups=result.parallel_groups,
            error=result.error,
        )

    # ── Functions ─────────────────────────────────────────────────────

    @app.get("/api/functions", response_model=list[FunctionInfo])
    async def list_functions() -> list[FunctionInfo]:
        from app.core.engine.function_runner import FilesystemFunctionRunner

        runner = FilesystemFunctionRunner(FUNCTIONS_DIR)
        funcs = runner.discover()

        result: list[FunctionInfo] = []
        for f in funcs:
            result.append(FunctionInfo(
                name=f.get("name", "?"),
                type=f.get("type", ""),
                version=f.get("version", ""),
                description=f.get("description", ""),
                path=f.get("path", ""),
                source=f.get("_source", "local"),
            ))
        return result

    @app.get("/api/functions/{fn_name}/source")
    async def get_function_source(fn_name: str):
        from app.core.engine.function_runner import FilesystemFunctionRunner

        runner = FilesystemFunctionRunner(FUNCTIONS_DIR)
        funcs = runner.discover()
        func = next((f for f in funcs if f.get("name") == fn_name), None)
        if not func:
            raise HTTPException(status_code=404, detail=f"Function '{fn_name}' not found")

        path = Path(func.get("path", ""))
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Function file not found: {path}")

        source = path.read_text(encoding="utf-8")
        return {"name": fn_name, "source": source, "path": str(path)}

    # ── History ───────────────────────────────────────────────────────

    @app.get("/api/history", response_model=list[HistoryEntryResponse])
    async def list_history(limit: int = 50) -> list[HistoryEntryResponse]:
        entries = await application.history.list_recent(limit)
        return [
            HistoryEntryResponse(
                id=e["id"],
                request_id=e.get("request_id"),
                request_name=e.get("request_name"),
                method=e.get("method"),
                url=e.get("url"),
                status=e.get("status"),
                status_code=e.get("status_code"),
                duration_ms=e.get("duration_ms", 0),
                error_message=e.get("error_message"),
                created_at=e.get("created_at"),
            )
            for e in entries
        ]

    # ── Collections ───────────────────────────────────────────────────

    @app.get("/api/collections", response_model=list[CollectionResponse])
    async def list_collections() -> list[CollectionResponse]:
        cols = await application.collections.list_all()
        result = []
        for c in cols:
            reqs = await application.requests.list_all(collection_id=c["id"])
            result.append(CollectionResponse(
                id=c["id"],
                name=c["name"],
                description=c.get("description", ""),
                created_at=c.get("created_at"),
                requests=reqs,
            ))
        return result

    @app.post("/api/collections", response_model=CollectionResponse, status_code=201)
    async def create_collection(req: CollectionCreateRequest) -> CollectionResponse:
        col = await application.collections.create(req.name, req.description)
        return CollectionResponse(
            id=col["id"],
            name=col["name"],
            description=col.get("description", ""),
            created_at=col.get("created_at"),
            requests=[],
        )

    @app.delete("/api/collections/{col_id}")
    async def delete_collection(col_id: str):
        await application.collections.delete(col_id)
        return {"deleted": True}

    @app.post("/api/collections/{col_id}/requests")
    async def add_request_to_collection(col_id: str, req: SendRequestRequest):
        req_data = await application.requests.create({
            "collection_id": col_id,
            "name": f"{req.method} {req.url}",
            "method": req.method,
            "url": req.url,
            "headers": [{"key": k, "value": v} for k, v in req.headers.items()],
            "body": req.body,
        })
        return req_data

    @app.get("/api/collections/{col_id}/requests")
    async def list_collection_requests(col_id: str):
        reqs = await application.requests.list_all(collection_id=col_id)
        return reqs

    # ── Environments ──────────────────────────────────────────────────

    @app.get("/api/environments", response_model=list[EnvironmentResponse])
    async def list_environments() -> list[EnvironmentResponse]:
        envs = await application.environments.list_all()
        return [
            EnvironmentResponse(
                id=e["id"],
                name=e["name"],
                is_active=bool(e.get("is_active")),
                variables=e.get("variables", []),
            )
            for e in envs
        ]

    # ── Send Request ──────────────────────────────────────────────────

    @app.post("/api/requests/send", response_model=SendRequestResponse)
    async def send_request(req: SendRequestRequest) -> SendRequestResponse:
        headers = [
            RequestParam(key=k, value=v, enabled=True)
            for k, v in req.headers.items()
        ]

        request = RequestDef(
            id="web-api",
            name=f"{req.method} {req.url}",
            method=HttpMethod(req.method.upper()),
            url=req.url,
            headers=headers,
            body=req.body,
            body_type=req.body_type,
            auth_type=req.auth_type,
            auth_config=req.auth_config,
        )

        ctx = ExecutionContext()

        active_env = await application.environments.get_active()
        if active_env:
            for v in active_env.get("variables", []):
                ctx.variables[v["key"]] = v["value"]

        result, entry = await application.request_executor.execute_with_history(request, ctx)
        await application.history.save(entry)

        return SendRequestResponse(
            status_code=result.status_code,
            headers=result.headers,
            body=result.body,
            duration_ms=result.duration_ms,
            error=result.error,
        )

    # ── Plugins ───────────────────────────────────────────────────────

    @app.get("/api/plugins", response_model=list[PluginInfoResponse])
    async def list_plugins() -> list[PluginInfoResponse]:
        if not application.plugin_registry:
            return []

        plugins = application.plugin_registry.list_plugins()
        return [
            PluginInfoResponse(
                name=info.manifest.name,
                version=info.manifest.version,
                status=info.status.value,
                description=info.manifest.description,
                function_count=len(info.manifest.functions),
                workflow_count=len(info.manifest.workflows),
            )
            for info in plugins
        ]

    # ── SCLPLL ────────────────────────────────────────────────────────

    @app.post("/api/sclpll/compile", response_model=SCLPLLCompileResponse)
    async def compile_sclpll(req: SCLPLLCompileRequest) -> SCLPLLCompileResponse:
        compiler = SCLPLLCompiler()
        try:
            workflow = compiler.parse(req.source)
            compiled_json = compiler.compile_to_json(req.source)
            return SCLPLLCompileResponse(workflow=workflow, compiled_json=compiled_json)
        except SCLPLLParseError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/sclpll/validate", response_model=SCLPLLValidateResponse)
    async def validate_sclpll(req: SCLPLLValidateRequest) -> SCLPLLValidateResponse:
        compiler = SCLPLLCompiler()
        try:
            compiler.parse(req.source)
            return SCLPLLValidateResponse(valid=True)
        except SCLPLLParseError as exc:
            return SCLPLLValidateResponse(
                valid=False,
                error=str(exc),
                line_number=exc.line_number,
            )

    # ── Static files & catch-all ──────────────────────────────────────

    if STATIC_DIR.exists():
        # Mount CSS and JS at root so relative paths in HTML work
        css_dir = STATIC_DIR / "css"
        js_dir = STATIC_DIR / "js"

        if css_dir.exists():
            app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")
        if js_dir.exists():
            app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")

        @app.get("/")
        async def serve_index():
            index = STATIC_DIR / "index.html"
            if index.exists():
                return FileResponse(index)
            return JSONResponse(
                {"message": "SCLPLAPI Web UI — static/index.html not found"},
                status_code=200,
            )

    else:
        @app.get("/")
        async def root():
            return JSONResponse({"message": "SCLPLAPI Web UI — static directory not found"})

    # ── Helpers ───────────────────────────────────────────────────────

    def _find_workflow_file(workflow_id: str) -> Path | None:
        if not EXAMPLES_DIR.exists():
            return None
        for wf_dir in EXAMPLES_DIR.iterdir():
            wf_file = wf_dir / "workflow.json"
            if wf_file.exists():
                data = json.loads(wf_file.read_text(encoding="utf-8"))
                if data.get("id") == workflow_id or wf_dir.name == workflow_id:
                    return wf_file
        return None

    return app
