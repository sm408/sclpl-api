# Frontend Architecture

## 1. Runtime Model

The frontend is a separately buildable Vue application under `web/`. It can run in two modes:

- **HTTP mode:** `HttpStudioGateway` calls the FastAPI server at the current origin and subscribes to SSE.
- **Mock mode:** `MockStudioGateway` uses deterministic fixtures and an in-memory event scheduler. It supports the same success, validation, delay, conflict, disconnection, and execution states as HTTP mode.

Feature code receives a `StudioGateway` through application injection and cannot import an HTTP client directly. This rule is enforced by ESLint import boundaries. Components do not know which mode is active.

Production build output is emitted to `app/web/static/` and included in the Python wheel. Source maps are generated for release diagnostics but excluded from the served distribution unless explicitly enabled. FastAPI serves immutable hashed assets and an uncached `index.html`.

## 2. Source Structure

```text
web/
  src/
    app/                 startup, providers, routes, shell, error boundary
    design-system/       tokens, primitives, domain-neutral composites
    gateway/             interface, HTTP adapter, mock adapter, generated types
    commands/            command registry, keyboard dispatch, palette ranking
    workbench/           tabs, drafts, panels, editors, close/conflict handling
    features/
      projects/
      requests/
      workflows/
      functions/
      monitors/
      runs/
      extensions/
      environments/
      batch/
      transfer/
      settings/
    shared/              formatting and domain components used by 2+ features
    test/                render harness, gateway fixtures, accessibility helpers
  e2e/
  package.json
  pnpm-lock.yaml
  vite.config.ts
```

A feature owns its routes, explorer contribution, queries, mutations, editors, view models, and tests. `shared/` is not a holding area: code moves there only after two real feature consumers exist. Features may import the gateway and shared packages but not each other. Cross-feature navigation uses typed route helpers; cross-feature actions use commands or gateway contracts.

## 3. Public Frontend Interfaces

```ts
export interface StudioGateway {
  projects: ProjectGateway;
  collections: CollectionGateway;
  requests: RequestGateway;
  environments: EnvironmentGateway;
  workflows: WorkflowGateway;
  functions: FunctionGateway;
  plugins: PluginGateway;
  monitors: MonitorGateway;
  runs: RunGateway;
  batches: BatchGateway;
  transfers: TransferGateway;
  settings: SettingsGateway;
  events: EventGateway;
}

export interface PageRequest {
  cursor?: string;
  pageSize: number;
  search?: string;
  sort?: string;
}

export interface Page<T> {
  items: T[];
  nextCursor: string | null;
  total: number;
}

export interface Revisioned {
  revision: number;
  updatedAt: string;
}

export interface EventSubscription {
  close(): void;
  state: Readonly<Ref<'connecting' | 'open' | 'closed'>>;
}
```

Each resource gateway defines explicit `list`, `get`, `create`, `update`, and supported command methods. It never exposes generic URL or raw request methods. Generated DTOs describe transport shapes; feature view models convert dates, enum labels, tree structure, and Monaco models at the feature boundary.

## 4. Routing And Application Lifecycle

Startup sequence:

1. Render a minimal local shell and error boundary.
2. Resolve gateway mode from build-time configuration; query parameters cannot switch production into mock mode.
3. Fetch server capabilities and compatible API version.
4. Load projects and resolve route project, last project, or Default project.
5. Start one project-filtered SSE subscription.
6. Restore shell preferences and tabs whose resources still exist.
7. Mount route feature and lazy chunks.

An incompatible API version shows a blocking upgrade message. A temporary startup failure retains Retry and Copy diagnostics. Router guards never discard dirty drafts: they allow navigation but keep the tab registered, except project switches which present a dirty-resource review.

## 5. State Ownership

### TanStack Query

Owns resource lists/details, server capabilities, settings, execution records, and monitor status. Query keys begin with project ID: `['project', projectId, 'workflows', filters]`. Successful mutations update or invalidate the narrowest keys. Events update known cached records and invalidate on sequence gaps.

Defaults:

- Resource lists remain fresh for 15 seconds.
- Static capabilities remain fresh for the session.
- Refetch on window focus is disabled for active editors and enabled for operational summaries.
- Mutation retry is disabled unless the operation is explicitly idempotent.
- Query retry uses at most two attempts and never retries 4xx responses.

### Pinia

Owns rail state, panel dimensions, theme, density, open tabs, active tab, command contexts, notification queue, and a registry of draft handles. It does not contain full server resource copies.

### Drafts

Each editor creates a typed draft from a server snapshot:

```ts
interface ResourceDraft<T> {
  key: string;
  baseRevision: number | string;
  base: Readonly<T>;
  value: T;
  isDirty: ComputedRef<boolean>;
  validation: ComputedRef<ValidationIssue[]>;
  save(): Promise<void>;
  revert(): void;
  dispose(): void;
}
```

Drafts persist in memory across navigation. Small non-secret drafts may be session-stored after a crash, but request auth fields, environment values, function source, response bodies, and any marked secret are excluded. Saving is explicit. Autosave is limited to shell layout and preferences.

## 6. Events And Operations

One `EventSource` is opened per active project with `Last-Event-ID` reconnection. The event coordinator:

- Verifies monotonically increasing sequence numbers.
- Deduplicates by event ID.
- Routes operation events to open activity views.
- Updates monitor/run summaries in the query cache.
- Invalidates affected queries after a sequence gap or reconnect.
- Shows Disconnected only after three seconds to avoid flicker during sleep/wake.

An operation continues if its tab closes. The global running indicator opens a list of active operations. Cancel sends a REST command and changes UI to Cancelling until the server confirms a terminal state.

## 7. Editors And Heavy Dependencies

Monaco, Vue Flow, ECharts, and diff support are dynamic imports owned by wrappers. The shell must not import them transitively. Monaco workers are local Vite workers with an explicit CSP-compatible setup. Each open source document has one model URI; views share that model and reference counts prevent leaks.

Workflow canvas state is converted from canonical definition and layout by pure functions. Canvas components emit commands such as `addStep`, `connectDependency`, and `moveSteps`; they never patch gateway DTOs directly. Undo/redo stores bounded domain commands, not full Vue reactive snapshots.

Large tables use server pagination first and virtualization for loaded rows. Response rendering detects content type and size before formatting. JSON above the configured threshold opens in raw/streamed mode with an opt-in Format action.

## 8. Error Handling And Observability

All gateway errors normalize into:

```ts
interface StudioError {
  code: string;
  message: string;
  status?: number;
  fieldErrors?: Record<string, string[]>;
  correlationId?: string;
  isRetryable: boolean;
}
```

Expected validation/conflict errors remain in their feature. Unexpected render errors are captured by route-level boundaries so the shell and drafts survive. Client diagnostics contain route template, application/API version, error code, and stack in development; they redact query values, request bodies, headers, source, environment data, and response content.

## 9. Build And Verification

- `pnpm dev` starts mock mode by default; `pnpm dev:http` proxies `/api` to local FastAPI.
- `pnpm typecheck` checks handwritten and generated types.
- `pnpm lint` enforces Vue, accessibility, import-boundary, and no-direct-fetch rules.
- `pnpm test` runs Vitest with deterministic time and MSW where the HTTP adapter itself is under test.
- `pnpm test:e2e` runs Playwright against a temporary database and project root.
- `pnpm build` reports chunk sizes and fails when budgets are exceeded without an approved exception.
- CI generates OpenAPI, regenerates TypeScript types in a temporary directory, and fails on diff.

