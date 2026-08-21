# API, Data, And Security Architecture

## 1. Server Composition

Create `app/web/server.py` with `create_app(db_path)` as the supported factory already referenced by the CLI. The FastAPI lifespan creates the existing application service container, runs migrations, starts monitor infrastructure, initializes an operation registry, and closes all resources on shutdown.

Routers live under `app/web/api/` by resource. Route handlers validate transport DTOs, call project-aware services, translate domain errors, and return DTOs. They do not contain SQL, filesystem traversal, workflow execution logic, or UI formatting. Existing services gain missing operations rather than being bypassed.

The production server serves `/api/v1/*`, `/health`, hashed static assets, and SPA fallback. `/docs` and `/openapi.json` remain loopback-accessible. The fallback never intercepts `/api`, asset, or documentation paths.

## 2. Common Protocol

Successful single-resource responses return the resource directly. Lists return:

```json
{
  "items": [],
  "nextCursor": null,
  "total": 0
}
```

Errors always return:

```json
{
  "error": {
    "code": "REVISION_CONFLICT",
    "message": "Workflow changed after this editor was opened.",
    "fieldErrors": null,
    "correlationId": "uuid"
  }
}
```

Status mapping: `400` malformed request, `404` missing or wrong-project resource, `409` revision/name/state conflict, `413` configured upload limit, `422` semantic validation, `429` operation limit, `500` redacted unexpected error, `503` service unavailable. A wrong-project lookup returns `404` to avoid cross-project disclosure.

All JSON uses camelCase, UTC ISO-8601 timestamps, string UUIDs, and uppercase machine enums only where existing domain contracts require them. Booleans use `is/has/can`. PATCH-like update DTOs distinguish omitted fields from explicit nulls.

## 3. Resource Families

```text
GET/POST              /api/v1/projects
GET/PATCH/DELETE      /api/v1/projects/{projectId}
GET/POST              /api/v1/projects/{projectId}/collections
GET/PATCH/DELETE      /api/v1/projects/{projectId}/collections/{id}
GET/POST              /api/v1/projects/{projectId}/requests
GET/PATCH/DELETE      /api/v1/projects/{projectId}/requests/{id}
POST                  /api/v1/projects/{projectId}/requests:execute
GET/POST              /api/v1/projects/{projectId}/environments
GET/PATCH/DELETE      /api/v1/projects/{projectId}/environments/{id}
POST                  /api/v1/projects/{projectId}/environments/{id}:activate
GET/POST              /api/v1/projects/{projectId}/workflows
GET/PATCH/DELETE      /api/v1/projects/{projectId}/workflows/{id}
POST                  /api/v1/projects/{projectId}/workflows/{id}:execute
POST                  /api/v1/projects/{projectId}/workflows/{id}:parse-sclpll
GET/POST/PUT/DELETE   /api/v1/projects/{projectId}/functions
GET/POST              /api/v1/projects/{projectId}/plugins
GET/PATCH/DELETE      /api/v1/projects/{projectId}/plugins/{id}
POST                  /api/v1/projects/{projectId}/plugins:reload
GET/POST              /api/v1/projects/{projectId}/monitors
GET/PATCH/DELETE      /api/v1/projects/{projectId}/monitors/{id}
POST                  /api/v1/projects/{projectId}/monitors/{id}:start|stop
GET                   /api/v1/projects/{projectId}/runs
GET                   /api/v1/projects/{projectId}/runs/{id}
POST                  /api/v1/projects/{projectId}/batches
POST                  /api/v1/projects/{projectId}/imports:preview|apply
POST                  /api/v1/projects/{projectId}/exports
GET/DELETE            /api/v1/operations/{operationId}
GET                   /api/v1/events?projectId={projectId}
GET/PATCH             /api/v1/settings
```

Colon commands are used only for state transitions or execution that are not resource CRUD. Delete is idempotent where a repeated request can be safely treated as complete. All list routes use cursor pagination and bounded `pageSize` from 1 to 200.

## 4. Operations And SSE

Long-running commands return `202` with:

```json
{
  "id": "uuid",
  "projectId": "uuid",
  "type": "WORKFLOW_RUN",
  "status": "QUEUED",
  "progress": {"completed": 0, "total": 5, "message": "Queued"},
  "startedAt": null,
  "finishedAt": null,
  "result": null,
  "error": null
}
```

Statuses are `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLING`, and `CANCELLED`. Cancellation is `DELETE /operations/{id}` and returns the current operation. Terminal operations cannot be cancelled and return unchanged.

SSE uses named events and JSON data:

```json
{
  "id": "uuid",
  "projectId": "uuid",
  "operationId": "uuid-or-null",
  "event": "workflow.step.completed",
  "sequence": 42,
  "occurredAt": "2026-06-23T12:00:00Z",
  "data": {}
}
```

The server emits heartbeat comments every 15 seconds, retains a bounded per-project replay buffer, honors `Last-Event-ID` when available, and emits `stream.reset` if replay is impossible. Event data is serialized from explicit schemas, never arbitrary object dictionaries.

## 5. Project Schema And Migration

Add `projects(id, name, description, root_path, is_default, revision, created_at, updated_at)`. Add `project_id` and `revision` to top-level project resources: collections, requests, environments, workflows, history, monitors, plugins, export presets, and monitor events where direct filtering is required. Child rows retain parent foreign keys and may duplicate `project_id` only when required for efficient isolation with a composite integrity check.

Migration procedure:

1. Acquire the existing database migration lock.
2. Create a timestamped database backup adjacent to the database.
3. Create one Default project whose root is the existing application working root.
4. Add nullable project columns and backfill every row in one transaction.
5. Rebuild SQLite tables that require non-null foreign keys and indexes.
6. Validate orphan counts, active environment uniqueness per project, and row counts.
7. Commit schema version only after validation.
8. On failure, roll back and report the backup path; do not start the normal UI.

The Default project cannot be deleted and its root files are not moved. New projects use `data/projects/<uuid>/` with `functions/`, `plugins/`, `workflows/`, and `exports/` subdirectories. Project names need not be filesystem-safe because IDs determine directories.

## 6. Revision And Conflict Rules

Mutable database resources have an integer revision beginning at 1. Update requests include `revision`; SQL updates use `WHERE id=? AND project_id=? AND revision=?` and increment atomically. Zero affected rows trigger a fresh existence/revision check and return `404` or `409`.

Function and manifest files use a SHA-256 content revision. Writes require `expectedSha256`; creation requires null. Rename is a distinct operation with source hash and target path. Imports use a preview token bound to the analyzed files, project, conflict policy, and expiration so Apply cannot execute a different unreviewed payload.

## 7. Filesystem Security

- Decode and normalize relative POSIX paths once at the boundary.
- Reject absolute paths, drive prefixes, empty segments, `.`/`..`, NULs, reserved Windows names, and unsupported extensions.
- Resolve both parent and target and verify containment within the project-owned category root.
- Reject symlinks or junctions that escape the root.
- Permit `.py` only in functions and approved plugin Python directories; permit declared workflow/manifest formats in their roots.
- Write through a same-directory temporary file, flush, and atomically replace.
- Apply size limits before parsing: configurable defaults of 2MB source, 10MB request/response preview, 25MB CSV, and 100MB import archive.
- Never accept a browser-provided server output directory. Exports produce downloadable operation artifacts in the project export root.

Python functions and plugins execute with local process authority. The UI and docs state this clearly before first execution of newly imported code. The server does not claim sandboxing.

## 8. Secrets And Local Security

Secret variable DTOs return key, scope, enabled, `isSecret`, and `hasValue`, never the value. Updating a secret accepts `newValue` only over same-origin requests; omitting it preserves the current value and explicit `clearValue: true` removes it. Logs, validation errors, events, history snapshots, diagnostics, and normal exports pass through redaction.

Production security defaults:

- Bind `127.0.0.1` or `::1`; reject non-loopback hosts in v1.
- No production CORS headers; dev CORS allows only the configured Vite origin.
- Validate `Host` against the bound host and port.
- Use CSP `default-src 'self'`, with explicit worker/style allowances required by the bundled editor and no remote sources.
- Set `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and frame denial.
- Validate Origin on mutating requests as defense in depth.
- Do not store credentials or session tokens because v1 has no authentication model.

## 9. Contract Verification

- Pydantic DTO tests assert aliases, omitted/null behavior, bounds, and secret exclusion.
- Router tests use a temporary database and project root for success, validation, not-found, conflict, and traversal cases.
- Service tests prove every query and mutation is project-scoped.
- Migration tests start from each supported schema version and compare row counts/content.
- SSE tests cover ordering, replay, heartbeat, reset, disconnect, cancellation, and redaction.
- OpenAPI snapshots are generated deterministically and feed frontend type generation.

