/**
 * HTTP gateway implementation.
 *
 * Implements StudioGateway by calling the FastAPI backend via fetch.
 * This is the ONLY module that knows about API endpoints and wire format.
 */

import type {
  StudioGateway,
  HealthGateway,
  ProjectsGateway,
  CollectionsGateway,
  RequestsGateway,
  EnvironmentsGateway,
  HistoryGateway,
  WorkflowsGateway,
  FunctionsGateway,
  PluginsGateway,
  MonitorsGateway,
  RunsGateway,
  BatchesGateway,
  TransfersGateway,
  SettingsGateway,
  EventsGateway,
  GatewayOptions,
} from '../types'
import type {
  HealthResponse,
  PaginatedResponse,
  Project,
  ProjectCreate,
  ProjectUpdate,
  Operation,
  OperationStatus,
  Collection,
  CollectionCreate,
  CollectionUpdate,
  RequestDef,
  RequestCreate,
  RequestUpdate,
  RunResult,
  Environment,
  EnvironmentCreate,
  EnvironmentUpdate,
  HistoryEntry,
  WorkflowDef,
  WorkflowCreate,
  WorkflowUpdate,
  FunctionDef,
  FunctionCreate,
  FunctionUpdate,
  FunctionListItem,
  FunctionDetail,
  AstValidationResult,
  FixtureResult,
  TrustAck,
  FileTreeEntry,
  PluginInfo,
  PluginDetail,
  PluginDiagnostics,
  Monitor,
  MonitorCreate,
  MonitorUpdate,
  MonitorEvent,
  ExportJob,
  ExportCreate,
  ExportPreset,
  AppSettings,
  SseEventType,
} from '@/types/api'
import { apiFetch, apiUpload } from './client'
import { connectSse } from './sse'

// ── Health ──────────────────────────────────────────────────────────────

class HttpHealthGateway implements HealthGateway {
  constructor(private readonly base: string) {}

  check(opts?: GatewayOptions): Promise<HealthResponse> {
    return apiFetch<HealthResponse>(this.base, '/health', { signal: opts?.signal })
  }
}

// ── Projects ────────────────────────────────────────────────────────────

class HttpProjectsGateway implements ProjectsGateway {
  constructor(private readonly base: string) {}

  async list(opts?: GatewayOptions): Promise<Project[]> {
    const res = await apiFetch<PaginatedResponse<Project>>(this.base, '/api/v1/projects', {
      signal: opts?.signal,
    })
    return res.items
  }

  get(id: string, opts?: GatewayOptions): Promise<Project> {
    return apiFetch<Project>(this.base, `/api/v1/projects/${id}`, { signal: opts?.signal })
  }

  create(input: ProjectCreate, opts?: GatewayOptions): Promise<Project> {
    return apiFetch<Project>(this.base, '/api/v1/projects', {
      method: 'POST',
      body: input,
      signal: opts?.signal,
    })
  }

  update(id: string, input: ProjectUpdate, opts?: GatewayOptions): Promise<Project> {
    return apiFetch<Project>(this.base, `/api/v1/projects/${id}`, {
      method: 'PATCH',
      body: input,
      signal: opts?.signal,
    })
  }

  async delete(id: string, opts?: GatewayOptions): Promise<void> {
    await apiFetch<void>(this.base, `/api/v1/projects/${id}`, {
      method: 'DELETE',
      signal: opts?.signal,
    })
  }
}

// ── Collections ─────────────────────────────────────────────────────────

class HttpCollectionsGateway implements CollectionsGateway {
  constructor(private readonly base: string) {}

  async list(projectId: string, opts?: GatewayOptions): Promise<Collection[]> {
    const res = await apiFetch<PaginatedResponse<Collection>>(
      this.base,
      `/api/v1/projects/${projectId}/collections`,
      { signal: opts?.signal },
    )
    return res.items
  }

  get(projectId: string, id: string, opts?: GatewayOptions): Promise<Collection> {
    return apiFetch<Collection>(
      this.base,
      `/api/v1/projects/${projectId}/collections/${id}`,
      { signal: opts?.signal },
    )
  }

  create(
    projectId: string,
    input: CollectionCreate,
    opts?: GatewayOptions,
  ): Promise<Collection> {
    return apiFetch<Collection>(
      this.base,
      `/api/v1/projects/${projectId}/collections`,
      { method: 'POST', body: input, signal: opts?.signal },
    )
  }

  update(
    projectId: string,
    id: string,
    input: CollectionUpdate,
    opts?: GatewayOptions,
  ): Promise<Collection> {
    return apiFetch<Collection>(
      this.base,
      `/api/v1/projects/${projectId}/collections/${id}`,
      { method: 'PATCH', body: input, signal: opts?.signal },
    )
  }

  async delete(projectId: string, id: string, opts?: GatewayOptions): Promise<void> {
    await apiFetch<void>(
      this.base,
      `/api/v1/projects/${projectId}/collections/${id}`,
      { method: 'DELETE', signal: opts?.signal },
    )
  }

  duplicate(projectId: string, id: string, opts?: GatewayOptions): Promise<Collection> {
    return apiFetch<Collection>(
      this.base,
      `/api/v1/projects/${projectId}/collections/${id}/duplicate`,
      { method: 'POST', signal: opts?.signal },
    )
  }
}

// ── Requests ────────────────────────────────────────────────────────────

class HttpRequestsGateway implements RequestsGateway {
  constructor(private readonly base: string) {}

  async list(
    projectId: string,
    collectionId?: string,
    opts?: GatewayOptions,
  ): Promise<RequestDef[]> {
    const res = await apiFetch<PaginatedResponse<RequestDef>>(
      this.base,
      `/api/v1/projects/${projectId}/requests`,
      {
        signal: opts?.signal,
        query: collectionId ? { collection_id: collectionId } : undefined,
      },
    )
    return res.items
  }

  get(projectId: string, id: string, opts?: GatewayOptions): Promise<RequestDef> {
    return apiFetch<RequestDef>(
      this.base,
      `/api/v1/projects/${projectId}/requests/${id}`,
      { signal: opts?.signal },
    )
  }

  create(projectId: string, input: RequestCreate, opts?: GatewayOptions): Promise<RequestDef> {
    return apiFetch<RequestDef>(
      this.base,
      `/api/v1/projects/${projectId}/requests`,
      { method: 'POST', body: input, signal: opts?.signal },
    )
  }

  update(
    projectId: string,
    id: string,
    input: RequestUpdate,
    opts?: GatewayOptions,
  ): Promise<RequestDef> {
    return apiFetch<RequestDef>(
      this.base,
      `/api/v1/projects/${projectId}/requests/${id}`,
      { method: 'PATCH', body: input, signal: opts?.signal },
    )
  }

  async delete(projectId: string, id: string, opts?: GatewayOptions): Promise<void> {
    await apiFetch<void>(
      this.base,
      `/api/v1/projects/${projectId}/requests/${id}`,
      { method: 'DELETE', signal: opts?.signal },
    )
  }

  move(
    projectId: string,
    id: string,
    targetCollectionId?: string,
    opts?: GatewayOptions,
  ): Promise<RequestDef> {
    return apiFetch<RequestDef>(
      this.base,
      `/api/v1/projects/${projectId}/requests/${id}/move`,
      { method: 'POST', signal: opts?.signal, query: targetCollectionId ? { target_collection_id: targetCollectionId } : undefined },
    )
  }

  execute(
    projectId: string,
    id: string,
    context?: Record<string, unknown>,
    opts?: GatewayOptions,
  ): Promise<RunResult> {
    return apiFetch<RunResult>(
      this.base,
      `/api/v1/projects/${projectId}/requests/${id}/execute`,
      { method: 'POST', body: context ?? {}, signal: opts?.signal },
    )
  }
}

// ── Environments ────────────────────────────────────────────────────────

class HttpEnvironmentsGateway implements EnvironmentsGateway {
  constructor(private readonly base: string) {}

  async list(projectId: string, opts?: GatewayOptions): Promise<Environment[]> {
    const res = await apiFetch<PaginatedResponse<Environment>>(
      this.base,
      `/api/v1/projects/${projectId}/environments`,
      { signal: opts?.signal },
    )
    return res.items
  }

  get(projectId: string, id: string, opts?: GatewayOptions): Promise<Environment> {
    return apiFetch<Environment>(
      this.base,
      `/api/v1/projects/${projectId}/environments/${id}`,
      { signal: opts?.signal },
    )
  }

  async getActive(projectId: string, opts?: GatewayOptions): Promise<Environment | null> {
    try {
      return await apiFetch<Environment>(
        this.base,
        `/api/v1/projects/${projectId}/environments/active`,
        { signal: opts?.signal },
      )
    } catch {
      return null
    }
  }

  create(
    projectId: string,
    input: EnvironmentCreate,
    opts?: GatewayOptions,
  ): Promise<Environment> {
    return apiFetch<Environment>(
      this.base,
      `/api/v1/projects/${projectId}/environments`,
      { method: 'POST', body: input, signal: opts?.signal },
    )
  }

  update(
    projectId: string,
    id: string,
    input: EnvironmentUpdate,
    opts?: GatewayOptions,
  ): Promise<Environment> {
    return apiFetch<Environment>(
      this.base,
      `/api/v1/projects/${projectId}/environments/${id}`,
      { method: 'PATCH', body: input, signal: opts?.signal },
    )
  }

  async delete(projectId: string, id: string, opts?: GatewayOptions): Promise<void> {
    await apiFetch<void>(
      this.base,
      `/api/v1/projects/${projectId}/environments/${id}`,
      { method: 'DELETE', signal: opts?.signal },
    )
  }

  activate(projectId: string, id: string, opts?: GatewayOptions): Promise<Environment> {
    return apiFetch<Environment>(
      this.base,
      `/api/v1/projects/${projectId}/environments/${id}/activate`,
      { method: 'POST', signal: opts?.signal },
    )
  }
}

// ── History ─────────────────────────────────────────────────────────────

class HttpHistoryGateway implements HistoryGateway {
  constructor(private readonly base: string) {}

  async list(
    projectId: string,
    opts?: GatewayOptions & { cursor?: string; limit?: number; requestId?: string },
  ): Promise<PaginatedResponse<HistoryEntry>> {
    const query: Record<string, unknown> = {}
    if (opts?.cursor) query.cursor = opts.cursor
    if (opts?.limit) query.limit = opts.limit
    if (opts?.requestId) query.request_id = opts.requestId
    return apiFetch<PaginatedResponse<HistoryEntry>>(
      this.base,
      `/api/v1/projects/${projectId}/history`,
      { signal: opts?.signal, query },
    )
  }

  get(projectId: string, id: string, opts?: GatewayOptions): Promise<HistoryEntry> {
    return apiFetch<HistoryEntry>(
      this.base,
      `/api/v1/projects/${projectId}/history/${id}`,
      { signal: opts?.signal },
    )
  }

  async clear(projectId: string, opts?: GatewayOptions): Promise<{ deleted: number }> {
    return apiFetch<{ deleted: number }>(
      this.base,
      `/api/v1/projects/${projectId}/history`,
      { method: 'DELETE', signal: opts?.signal },
    )
  }
}

// ── Workflows ───────────────────────────────────────────────────────────

class HttpWorkflowsGateway implements WorkflowsGateway {
  constructor(private readonly base: string) {}

  async list(projectId: string, opts?: GatewayOptions): Promise<WorkflowDef[]> {
    const res = await apiFetch<PaginatedResponse<WorkflowDef>>(
      this.base,
      `/api/v1/projects/${projectId}/workflows`,
      { signal: opts?.signal },
    )
    return res.items
  }

  get(projectId: string, id: string, opts?: GatewayOptions): Promise<WorkflowDef> {
    return apiFetch<WorkflowDef>(
      this.base,
      `/api/v1/projects/${projectId}/workflows/${id}`,
      { signal: opts?.signal },
    )
  }

  create(projectId: string, input: WorkflowCreate, opts?: GatewayOptions): Promise<WorkflowDef> {
    return apiFetch<WorkflowDef>(
      this.base,
      `/api/v1/projects/${projectId}/workflows`,
      { method: 'POST', body: input, signal: opts?.signal },
    )
  }

  update(
    projectId: string,
    id: string,
    input: WorkflowUpdate,
    opts?: GatewayOptions,
  ): Promise<WorkflowDef> {
    return apiFetch<WorkflowDef>(
      this.base,
      `/api/v1/projects/${projectId}/workflows/${id}`,
      { method: 'PATCH', body: input, signal: opts?.signal },
    )
  }

  async delete(projectId: string, id: string, opts?: GatewayOptions): Promise<void> {
    await apiFetch<void>(
      this.base,
      `/api/v1/projects/${projectId}/workflows/${id}`,
      { method: 'DELETE', signal: opts?.signal },
    )
  }

  run(projectId: string, id: string, opts?: GatewayOptions): Promise<Operation> {
    return apiFetch<Operation>(
      this.base,
      `/api/v1/projects/${projectId}/workflows/${id}/run`,
      { method: 'POST', signal: opts?.signal },
    )
  }
}

// ── Functions ───────────────────────────────────────────────────────────

class HttpFunctionsGateway implements FunctionsGateway {
  constructor(private readonly base: string) {}

  async list(projectId: string, opts?: GatewayOptions): Promise<FunctionListItem[]> {
    const res = await apiFetch<PaginatedResponse<FunctionListItem>>(
      this.base,
      `/api/v1/projects/${projectId}/functions`,
      { signal: opts?.signal },
    )
    return res.items
  }

  get(projectId: string, path: string, opts?: GatewayOptions): Promise<FunctionDetail> {
    return apiFetch<FunctionDetail>(
      this.base,
      `/api/v1/projects/${projectId}/functions/${encodeURIComponent(path)}`,
      { signal: opts?.signal },
    )
  }

  create(projectId: string, input: FunctionCreate, opts?: GatewayOptions): Promise<FunctionDetail> {
    return apiFetch<FunctionDetail>(
      this.base,
      `/api/v1/projects/${projectId}/functions`,
      { method: 'POST', body: input, signal: opts?.signal },
    )
  }

  update(
    projectId: string,
    path: string,
    input: { source?: string; expectedHash?: string },
    opts?: GatewayOptions,
  ): Promise<FunctionDetail> {
    return apiFetch<FunctionDetail>(
      this.base,
      `/api/v1/projects/${projectId}/functions/${encodeURIComponent(path)}`,
      { method: 'PATCH', body: input, signal: opts?.signal },
    )
  }

  async delete(projectId: string, path: string, opts?: GatewayOptions): Promise<void> {
    await apiFetch<void>(
      this.base,
      `/api/v1/projects/${projectId}/functions/${encodeURIComponent(path)}`,
      { method: 'DELETE', signal: opts?.signal },
    )
  }

  async tree(projectId: string, opts?: GatewayOptions): Promise<FileTreeEntry[]> {
    const res = await apiFetch<{ tree: FileTreeEntry[] }>(
      this.base,
      `/api/v1/projects/${projectId}/functions/tree`,
      { signal: opts?.signal },
    )
    return res.tree
  }

  validate(projectId: string, source: string, opts?: GatewayOptions): Promise<AstValidationResult> {
    return apiFetch<AstValidationResult>(
      this.base,
      `/api/v1/projects/${projectId}/functions/validate`,
      { method: 'POST', body: { source }, signal: opts?.signal },
    )
  }

  runFixture(
    projectId: string,
    path: string,
    input?: Record<string, unknown>,
    trusted?: boolean,
    opts?: GatewayOptions,
  ): Promise<FixtureResult> {
    return apiFetch<FixtureResult>(
      this.base,
      `/api/v1/projects/${projectId}/functions/${encodeURIComponent(path)}/run`,
      { method: 'POST', body: { fixtureInput: input ?? {}, trusted: trusted ?? false }, signal: opts?.signal },
    )
  }

  acknowledgeTrust(
    projectId: string,
    path: string,
    contentHash: string,
    opts?: GatewayOptions,
  ): Promise<TrustAck> {
    return apiFetch<TrustAck>(
      this.base,
      `/api/v1/projects/${projectId}/functions/${encodeURIComponent(path)}/trust`,
      { method: 'POST', body: { path, contentHash }, signal: opts?.signal },
    )
  }

  async revokeTrust(projectId: string, path: string, opts?: GatewayOptions): Promise<void> {
    await apiFetch<void>(
      this.base,
      `/api/v1/projects/${projectId}/functions/${encodeURIComponent(path)}/trust`,
      { method: 'DELETE', signal: opts?.signal },
    )
  }
}

// ── Plugins ─────────────────────────────────────────────────────────────

class HttpPluginsGateway implements PluginsGateway {
  constructor(private readonly base: string) {}

  async list(projectId: string, opts?: GatewayOptions): Promise<PluginDetail[]> {
    const res = await apiFetch<PaginatedResponse<PluginDetail>>(
      this.base,
      `/api/v1/projects/${projectId}/plugins`,
      { signal: opts?.signal },
    )
    return res.items
  }

  get(projectId: string, name: string, opts?: GatewayOptions): Promise<PluginDetail> {
    return apiFetch<PluginDetail>(
      this.base,
      `/api/v1/projects/${projectId}/plugins/${encodeURIComponent(name)}`,
      { signal: opts?.signal },
    )
  }

  scaffold(
    projectId: string,
    name: string,
    description?: string,
    opts?: GatewayOptions,
  ): Promise<PluginDetail> {
    return apiFetch<PluginDetail>(
      this.base,
      `/api/v1/projects/${projectId}/plugins`,
      { method: 'POST', body: { name, description: description ?? '' }, signal: opts?.signal },
    )
  }

  enable(projectId: string, name: string, opts?: GatewayOptions): Promise<PluginDetail> {
    return apiFetch<PluginDetail>(
      this.base,
      `/api/v1/projects/${projectId}/plugins/${encodeURIComponent(name)}/enable`,
      { method: 'POST', signal: opts?.signal },
    )
  }

  disable(projectId: string, name: string, opts?: GatewayOptions): Promise<PluginDetail> {
    return apiFetch<PluginDetail>(
      this.base,
      `/api/v1/projects/${projectId}/plugins/${encodeURIComponent(name)}/disable`,
      { method: 'POST', signal: opts?.signal },
    )
  }

  async reload(projectId: string, opts?: GatewayOptions): Promise<PluginDetail[]> {
    const res = await apiFetch<PaginatedResponse<PluginDetail>>(
      this.base,
      `/api/v1/projects/${projectId}/plugins/reload`,
      { method: 'POST', signal: opts?.signal },
    )
    return res.items
  }

  getManifest(projectId: string, name: string, opts?: GatewayOptions): Promise<Record<string, unknown>> {
    return apiFetch<Record<string, unknown>>(
      this.base,
      `/api/v1/projects/${projectId}/plugins/${encodeURIComponent(name)}/manifest`,
      { signal: opts?.signal },
    )
  }

  updateManifest(
    projectId: string,
    name: string,
    data: Record<string, unknown>,
    opts?: GatewayOptions,
  ): Promise<PluginDetail> {
    return apiFetch<PluginDetail>(
      this.base,
      `/api/v1/projects/${projectId}/plugins/${encodeURIComponent(name)}/manifest`,
      { method: 'PATCH', body: { data }, signal: opts?.signal },
    )
  }

  async getTree(projectId: string, name: string, opts?: GatewayOptions): Promise<FileTreeEntry[]> {
    const res = await apiFetch<{ tree: FileTreeEntry[] }>(
      this.base,
      `/api/v1/projects/${projectId}/plugins/${encodeURIComponent(name)}/tree`,
      { signal: opts?.signal },
    )
    return res.tree
  }

  readFile(
    projectId: string,
    name: string,
    path: string,
    opts?: GatewayOptions,
  ): Promise<{ content: string; hash: string; size: number }> {
    return apiFetch<{ content: string; hash: string; size: number }>(
      this.base,
      `/api/v1/projects/${projectId}/plugins/${encodeURIComponent(name)}/files/${encodeURIComponent(path)}`,
      { signal: opts?.signal },
    )
  }

  writeFile(
    projectId: string,
    name: string,
    path: string,
    content: string,
    expectedHash?: string,
    opts?: GatewayOptions,
  ): Promise<{ path: string; hash: string; size: number }> {
    return apiFetch<{ path: string; hash: string; size: number }>(
      this.base,
      `/api/v1/projects/${projectId}/plugins/${encodeURIComponent(name)}/files/${encodeURIComponent(path)}`,
      { method: 'PUT', body: { content, expectedHash }, signal: opts?.signal },
    )
  }

  getDiagnostics(projectId: string, name: string, opts?: GatewayOptions): Promise<PluginDiagnostics> {
    return apiFetch<PluginDiagnostics>(
      this.base,
      `/api/v1/projects/${projectId}/plugins/${encodeURIComponent(name)}/diagnostics`,
      { signal: opts?.signal },
    )
  }

  async export(projectId: string, name: string, opts?: GatewayOptions): Promise<Blob> {
    const url = new URL(
      `/api/v1/projects/${projectId}/plugins/${encodeURIComponent(name)}/export`,
      this.base || window.location.origin,
    )
    const response = await fetch(url.toString(), { signal: opts?.signal })
    if (!response.ok) {
      throw new Error(`Export failed: ${response.status}`)
    }
    return response.blob()
  }
}

// ── Monitors ────────────────────────────────────────────────────────────

class HttpMonitorsGateway implements MonitorsGateway {
  constructor(private readonly base: string) {}

  async list(projectId: string, opts?: GatewayOptions): Promise<Monitor[]> {
    const res = await apiFetch<PaginatedResponse<Monitor>>(
      this.base,
      `/api/v1/projects/${projectId}/monitors`,
      { signal: opts?.signal },
    )
    return res.items
  }

  get(projectId: string, id: string, opts?: GatewayOptions): Promise<Monitor> {
    return apiFetch<Monitor>(
      this.base,
      `/api/v1/projects/${projectId}/monitors/${id}`,
      { signal: opts?.signal },
    )
  }

  create(projectId: string, input: MonitorCreate, opts?: GatewayOptions): Promise<Monitor> {
    return apiFetch<Monitor>(
      this.base,
      `/api/v1/projects/${projectId}/monitors`,
      { method: 'POST', body: input, signal: opts?.signal },
    )
  }

  update(
    projectId: string,
    id: string,
    input: MonitorUpdate,
    opts?: GatewayOptions,
  ): Promise<Monitor> {
    return apiFetch<Monitor>(
      this.base,
      `/api/v1/projects/${projectId}/monitors/${id}`,
      { method: 'PATCH', body: input, signal: opts?.signal },
    )
  }

  async delete(projectId: string, id: string, opts?: GatewayOptions): Promise<void> {
    await apiFetch<void>(
      this.base,
      `/api/v1/projects/${projectId}/monitors/${id}`,
      { method: 'DELETE', signal: opts?.signal },
    )
  }

  start(projectId: string, id: string, opts?: GatewayOptions): Promise<Operation> {
    return apiFetch<Operation>(
      this.base,
      `/api/v1/projects/${projectId}/monitors/${id}/start`,
      { method: 'POST', signal: opts?.signal },
    )
  }

  stop(projectId: string, id: string, opts?: GatewayOptions): Promise<Operation> {
    return apiFetch<Operation>(
      this.base,
      `/api/v1/projects/${projectId}/monitors/${id}/stop`,
      { method: 'POST', signal: opts?.signal },
    )
  }

  async events(
    projectId: string,
    id: string,
    opts?: GatewayOptions,
  ): Promise<MonitorEvent[]> {
    const res = await apiFetch<PaginatedResponse<MonitorEvent>>(
      this.base,
      `/api/v1/projects/${projectId}/monitors/${id}/events`,
      { signal: opts?.signal },
    )
    return res.items
  }
}

// ── Runs (Operations) ───────────────────────────────────────────────────

class HttpRunsGateway implements RunsGateway {
  constructor(private readonly base: string) {}

  async list(
    projectId: string,
    status?: OperationStatus,
    opts?: GatewayOptions,
  ): Promise<Operation[]> {
    const res = await apiFetch<PaginatedResponse<Operation>>(
      this.base,
      '/api/v1/operations',
      {
        signal: opts?.signal,
        query: {
          project_id: projectId,
          status,
        },
      },
    )
    return res.items
  }

  get(projectId: string, id: string, opts?: GatewayOptions): Promise<Operation> {
    return apiFetch<Operation>(this.base, `/api/v1/operations/${id}`, {
      signal: opts?.signal,
      query: { project_id: projectId },
    })
  }

  cancel(projectId: string, id: string, opts?: GatewayOptions): Promise<Operation> {
    return apiFetch<Operation>(this.base, `/api/v1/operations/${id}`, {
      method: 'DELETE',
      signal: opts?.signal,
      query: { project_id: projectId },
    })
  }
}

// ── Batches ─────────────────────────────────────────────────────────────

class HttpBatchesGateway implements BatchesGateway {
  constructor(private readonly base: string) {}

  run(projectId: string, requestIds: string[], opts?: GatewayOptions): Promise<Operation> {
    return apiFetch<Operation>(
      this.base,
      `/api/v1/projects/${projectId}/batch/run`,
      { method: 'POST', body: { requestIds }, signal: opts?.signal },
    )
  }
}

// ── Transfers ───────────────────────────────────────────────────────────

class HttpTransfersGateway implements TransfersGateway {
  constructor(private readonly base: string) {}

  export(projectId: string, input: ExportCreate, opts?: GatewayOptions): Promise<ExportJob> {
    return apiFetch<ExportJob>(
      this.base,
      `/api/v1/projects/${projectId}/export`,
      { method: 'POST', body: input, signal: opts?.signal },
    )
  }

  async import(projectId: string, file: File, opts?: GatewayOptions): Promise<Operation> {
    const formData = new FormData()
    formData.append('file', file)
    return apiUpload<Operation>(
      this.base,
      `/api/v1/projects/${projectId}/import`,
      formData,
      { signal: opts?.signal },
    )
  }

  async presets(projectId: string, opts?: GatewayOptions): Promise<ExportPreset[]> {
    const res = await apiFetch<PaginatedResponse<ExportPreset>>(
      this.base,
      `/api/v1/projects/${projectId}/export/presets`,
      { signal: opts?.signal },
    )
    return res.items
  }
}

// ── Settings ────────────────────────────────────────────────────────────

class HttpSettingsGateway implements SettingsGateway {
  constructor(private readonly base: string) {}

  get(opts?: GatewayOptions): Promise<AppSettings> {
    return apiFetch<AppSettings>(this.base, '/api/v1/settings', { signal: opts?.signal })
  }

  update(input: Partial<AppSettings>, opts?: GatewayOptions): Promise<AppSettings> {
    return apiFetch<AppSettings>(this.base, '/api/v1/settings', {
      method: 'PATCH',
      body: input,
      signal: opts?.signal,
    })
  }
}

// ── Events (SSE) ────────────────────────────────────────────────────────

class HttpEventsGateway implements EventsGateway {
  constructor(private readonly base: string) {}

  subscribe(
    projectId: string,
    onEvent: (event: { event: SseEventType; data: Record<string, unknown> }) => void,
    onError?: (error: Error) => void,
  ): () => void {
    return connectSse(this.base, projectId, {
      onEvent: (e) => onEvent({ event: e.event as SseEventType, data: e.data }),
      onError,
    })
  }
}

// ── Factory ─────────────────────────────────────────────────────────────

export function createHttpGateway(baseUrl: string = ''): StudioGateway {
  const base = baseUrl.replace(/\/$/, '')

  return {
    health: new HttpHealthGateway(base),
    projects: new HttpProjectsGateway(base),
    collections: new HttpCollectionsGateway(base),
    requests: new HttpRequestsGateway(base),
    environments: new HttpEnvironmentsGateway(base),
    history: new HttpHistoryGateway(base),
    workflows: new HttpWorkflowsGateway(base),
    functions: new HttpFunctionsGateway(base),
    plugins: new HttpPluginsGateway(base),
    monitors: new HttpMonitorsGateway(base),
    runs: new HttpRunsGateway(base),
    batches: new HttpBatchesGateway(base),
    transfers: new HttpTransfersGateway(base),
    settings: new HttpSettingsGateway(base),
    events: new HttpEventsGateway(base),
  }
}
