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
  WorkflowDef,
  WorkflowCreate,
  WorkflowUpdate,
  FunctionDef,
  FunctionCreate,
  FunctionUpdate,
  PluginInfo,
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
import { apiFetch } from './client'
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

  async list(projectId: string, opts?: GatewayOptions): Promise<FunctionDef[]> {
    const res = await apiFetch<PaginatedResponse<FunctionDef>>(
      this.base,
      `/api/v1/projects/${projectId}/functions`,
      { signal: opts?.signal },
    )
    return res.items
  }

  get(projectId: string, id: string, opts?: GatewayOptions): Promise<FunctionDef> {
    return apiFetch<FunctionDef>(
      this.base,
      `/api/v1/projects/${projectId}/functions/${id}`,
      { signal: opts?.signal },
    )
  }

  create(projectId: string, input: FunctionCreate, opts?: GatewayOptions): Promise<FunctionDef> {
    return apiFetch<FunctionDef>(
      this.base,
      `/api/v1/projects/${projectId}/functions`,
      { method: 'POST', body: input, signal: opts?.signal },
    )
  }

  update(
    projectId: string,
    id: string,
    input: FunctionUpdate,
    opts?: GatewayOptions,
  ): Promise<FunctionDef> {
    return apiFetch<FunctionDef>(
      this.base,
      `/api/v1/projects/${projectId}/functions/${id}`,
      { method: 'PATCH', body: input, signal: opts?.signal },
    )
  }

  async delete(projectId: string, id: string, opts?: GatewayOptions): Promise<void> {
    await apiFetch<void>(
      this.base,
      `/api/v1/projects/${projectId}/functions/${id}`,
      { method: 'DELETE', signal: opts?.signal },
    )
  }
}

// ── Plugins ─────────────────────────────────────────────────────────────

class HttpPluginsGateway implements PluginsGateway {
  constructor(private readonly base: string) {}

  async list(projectId: string, opts?: GatewayOptions): Promise<PluginInfo[]> {
    const res = await apiFetch<PaginatedResponse<PluginInfo>>(
      this.base,
      `/api/v1/projects/${projectId}/plugins`,
      { signal: opts?.signal },
    )
    return res.items
  }

  get(projectId: string, id: string, opts?: GatewayOptions): Promise<PluginInfo> {
    return apiFetch<PluginInfo>(
      this.base,
      `/api/v1/projects/${projectId}/plugins/${id}`,
      { signal: opts?.signal },
    )
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

    const url = new URL(
      `/api/v1/projects/${projectId}/import`,
      this.base || window.location.origin,
    )

    const response = await fetch(url.toString(), {
      method: 'POST',
      body: formData,
      signal: opts?.signal,
    })

    if (!response.ok) {
      const { StudioError } = await import('../error')
      throw new StudioError({
        message: `Import failed: ${response.statusText}`,
        code: 'IMPORT_ERROR',
        status: response.status,
      })
    }

    return (await response.json()) as Operation
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
