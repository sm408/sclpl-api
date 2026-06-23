/**
 * Mock gateway implementation.
 *
 * Returns deterministic fixtures for every resource family.
 * Used for development, testing, and Storybook-style isolation.
 *
 * Components do not know which mode is active — they interact
 * exclusively through the StudioGateway interface.
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
import { StudioError } from '../error'
import type {
  HealthResponse,
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
import * as fixtures from './fixtures'

// ── Helpers ─────────────────────────────────────────────────────────────

/** Simulate network latency (50-150ms). */
function delay(ms = 80): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** Check if the signal is already aborted. */
function checkAbort(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new StudioError({ message: 'Request was cancelled', code: 'ABORTED', status: 0 })
  }
}

/** Generate a deterministic short ID. */
let _idCounter = 100
function nextId(prefix: string): string {
  return `${prefix}-mock-${String(++_idCounter).padStart(3, '0')}`
}

// ── Health ──────────────────────────────────────────────────────────────

class MockHealthGateway implements HealthGateway {
  async check(opts?: GatewayOptions): Promise<HealthResponse> {
    checkAbort(opts?.signal)
    await delay()
    return { ...fixtures.FIXTURE_HEALTH }
  }
}

// ── Projects ────────────────────────────────────────────────────────────

class MockProjectsGateway implements ProjectsGateway {
  private projects = new Map(
    fixtures.FIXTURE_PROJECTS.map((p) => [p.id, { ...p }]),
  )

  async list(opts?: GatewayOptions): Promise<Project[]> {
    checkAbort(opts?.signal)
    await delay()
    return Array.from(this.projects.values())
  }

  async get(id: string, opts?: GatewayOptions): Promise<Project> {
    checkAbort(opts?.signal)
    await delay()
    const project = this.projects.get(id)
    if (!project) {
      throw new StudioError({
        message: `Project '${id}' not found.`,
        code: 'NOT_FOUND',
        status: 404,
      })
    }
    return { ...project }
  }

  async create(input: ProjectCreate, opts?: GatewayOptions): Promise<Project> {
    checkAbort(opts?.signal)
    await delay()
    const now = new Date().toISOString()
    const project: Project = {
      id: nextId('proj'),
      name: input.name,
      description: input.description ?? '',
      rootPath: '',
      isDefault: false,
      createdAt: now,
      updatedAt: now,
    }
    this.projects.set(project.id, project)
    return { ...project }
  }

  async update(id: string, input: ProjectUpdate, opts?: GatewayOptions): Promise<Project> {
    checkAbort(opts?.signal)
    await delay()
    const project = this.projects.get(id)
    if (!project) {
      throw new StudioError({
        message: `Project '${id}' not found.`,
        code: 'NOT_FOUND',
        status: 404,
      })
    }
    if (project.isDefault) {
      throw new StudioError({
        message: 'The Default project cannot be modified.',
        code: 'CONFLICT',
        status: 409,
      })
    }
    if (input.name !== undefined) project.name = input.name
    if (input.description !== undefined) project.description = input.description
    project.updatedAt = new Date().toISOString()
    return { ...project }
  }

  async delete(id: string, opts?: GatewayOptions): Promise<void> {
    checkAbort(opts?.signal)
    await delay()
    const project = this.projects.get(id)
    if (!project) {
      throw new StudioError({
        message: `Project '${id}' not found.`,
        code: 'NOT_FOUND',
        status: 404,
      })
    }
    if (project.isDefault) {
      throw new StudioError({
        message: 'The Default project cannot be deleted.',
        code: 'CONFLICT',
        status: 409,
      })
    }
    this.projects.delete(id)
  }
}

// ── Collections ─────────────────────────────────────────────────────────

class MockCollectionsGateway implements CollectionsGateway {
  private collections = new Map([[fixtures.FIXTURE_COLLECTION.id, { ...fixtures.FIXTURE_COLLECTION }]])

  async list(projectId: string, opts?: GatewayOptions): Promise<Collection[]> {
    checkAbort(opts?.signal)
    await delay()
    return Array.from(this.collections.values()).filter((c) => c.projectId === projectId)
  }

  async get(_projectId: string, id: string, opts?: GatewayOptions): Promise<Collection> {
    checkAbort(opts?.signal)
    await delay()
    const col = this.collections.get(id)
    if (!col) {
      throw new StudioError({ message: `Collection '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    }
    return { ...col }
  }

  async create(projectId: string, input: CollectionCreate, opts?: GatewayOptions): Promise<Collection> {
    checkAbort(opts?.signal)
    await delay()
    const col: Collection = {
      id: nextId('col'),
      projectId,
      name: input.name,
      description: input.description ?? '',
      items: [],
    }
    this.collections.set(col.id, col)
    return { ...col }
  }

  async update(_projectId: string, id: string, input: CollectionUpdate, opts?: GatewayOptions): Promise<Collection> {
    checkAbort(opts?.signal)
    await delay()
    const col = this.collections.get(id)
    if (!col) throw new StudioError({ message: `Collection '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    if (input.name !== undefined) col.name = input.name
    if (input.description !== undefined) col.description = input.description
    return { ...col }
  }

  async delete(_projectId: string, id: string, opts?: GatewayOptions): Promise<void> {
    checkAbort(opts?.signal)
    await delay()
    if (!this.collections.has(id)) {
      throw new StudioError({ message: `Collection '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    }
    this.collections.delete(id)
  }
}

// ── Requests ────────────────────────────────────────────────────────────

class MockRequestsGateway implements RequestsGateway {
  private requests = new Map(
    fixtures.FIXTURE_REQUESTS.map((r) => [r.id, { ...r }]),
  )

  async list(projectId: string, collectionId?: string, opts?: GatewayOptions): Promise<RequestDef[]> {
    checkAbort(opts?.signal)
    await delay()
    let items = Array.from(this.requests.values()).filter((r) => r.projectId === projectId)
    if (collectionId) items = items.filter((r) => r.collectionId === collectionId)
    return items
  }

  async get(_projectId: string, id: string, opts?: GatewayOptions): Promise<RequestDef> {
    checkAbort(opts?.signal)
    await delay()
    const req = this.requests.get(id)
    if (!req) throw new StudioError({ message: `Request '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    return { ...req }
  }

  async create(projectId: string, input: RequestCreate, opts?: GatewayOptions): Promise<RequestDef> {
    checkAbort(opts?.signal)
    await delay()
    const req: RequestDef = {
      id: nextId('req'),
      projectId,
      collectionId: input.collectionId,
      name: input.name,
      method: input.method,
      url: input.url,
      headers: input.headers ?? {},
      params: input.params ?? [],
      body: input.body,
    }
    this.requests.set(req.id, req)
    return { ...req }
  }

  async update(_projectId: string, id: string, input: RequestUpdate, opts?: GatewayOptions): Promise<RequestDef> {
    checkAbort(opts?.signal)
    await delay()
    const req = this.requests.get(id)
    if (!req) throw new StudioError({ message: `Request '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    Object.assign(req, input)
    return { ...req }
  }

  async delete(_projectId: string, id: string, opts?: GatewayOptions): Promise<void> {
    checkAbort(opts?.signal)
    await delay()
    if (!this.requests.has(id)) throw new StudioError({ message: `Request '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    this.requests.delete(id)
  }

  async execute(_projectId: string, _id: string, _context?: Record<string, unknown>, opts?: GatewayOptions): Promise<RunResult> {
    checkAbort(opts?.signal)
    await delay(200)
    return {
      statusCode: 200,
      headers: { 'content-type': 'application/json' },
      body: { message: 'Mock response' },
      duration: 200,
    }
  }
}

// ── Environments ────────────────────────────────────────────────────────

class MockEnvironmentsGateway implements EnvironmentsGateway {
  private envs = new Map([[fixtures.FIXTURE_ENVIRONMENT.id, { ...fixtures.FIXTURE_ENVIRONMENT }]])

  async list(projectId: string, opts?: GatewayOptions): Promise<Environment[]> {
    checkAbort(opts?.signal)
    await delay()
    return Array.from(this.envs.values()).filter((e) => e.projectId === projectId)
  }

  async get(_projectId: string, id: string, opts?: GatewayOptions): Promise<Environment> {
    checkAbort(opts?.signal)
    await delay()
    const env = this.envs.get(id)
    if (!env) throw new StudioError({ message: `Environment '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    return { ...env }
  }

  async create(projectId: string, input: EnvironmentCreate, opts?: GatewayOptions): Promise<Environment> {
    checkAbort(opts?.signal)
    await delay()
    const env: Environment = { id: nextId('env'), projectId, name: input.name, variables: input.variables ?? [] }
    this.envs.set(env.id, env)
    return { ...env }
  }

  async update(_projectId: string, id: string, input: EnvironmentUpdate, opts?: GatewayOptions): Promise<Environment> {
    checkAbort(opts?.signal)
    await delay()
    const env = this.envs.get(id)
    if (!env) throw new StudioError({ message: `Environment '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    if (input.name !== undefined) env.name = input.name
    if (input.variables !== undefined) env.variables = input.variables
    return { ...env }
  }

  async delete(_projectId: string, id: string, opts?: GatewayOptions): Promise<void> {
    checkAbort(opts?.signal)
    await delay()
    if (!this.envs.has(id)) throw new StudioError({ message: `Environment '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    this.envs.delete(id)
  }
}

// ── Workflows ───────────────────────────────────────────────────────────

class MockWorkflowsGateway implements WorkflowsGateway {
  private workflows = new Map([[fixtures.FIXTURE_WORKFLOW.id, { ...fixtures.FIXTURE_WORKFLOW }]])

  async list(projectId: string, opts?: GatewayOptions): Promise<WorkflowDef[]> {
    checkAbort(opts?.signal)
    await delay()
    return Array.from(this.workflows.values()).filter((w) => w.projectId === projectId)
  }

  async get(_projectId: string, id: string, opts?: GatewayOptions): Promise<WorkflowDef> {
    checkAbort(opts?.signal)
    await delay()
    const wf = this.workflows.get(id)
    if (!wf) throw new StudioError({ message: `Workflow '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    return { ...wf }
  }

  async create(projectId: string, input: WorkflowCreate, opts?: GatewayOptions): Promise<WorkflowDef> {
    checkAbort(opts?.signal)
    await delay()
    const wf: WorkflowDef = { id: nextId('wf'), projectId, name: input.name, description: input.description ?? '', steps: input.steps ?? [] }
    this.workflows.set(wf.id, wf)
    return { ...wf }
  }

  async update(_projectId: string, id: string, input: WorkflowUpdate, opts?: GatewayOptions): Promise<WorkflowDef> {
    checkAbort(opts?.signal)
    await delay()
    const wf = this.workflows.get(id)
    if (!wf) throw new StudioError({ message: `Workflow '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    if (input.name !== undefined) wf.name = input.name
    if (input.description !== undefined) wf.description = input.description
    if (input.steps !== undefined) wf.steps = input.steps
    return { ...wf }
  }

  async delete(_projectId: string, id: string, opts?: GatewayOptions): Promise<void> {
    checkAbort(opts?.signal)
    await delay()
    if (!this.workflows.has(id)) throw new StudioError({ message: `Workflow '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    this.workflows.delete(id)
  }

  async run(projectId: string, _id: string, opts?: GatewayOptions): Promise<Operation> {
    checkAbort(opts?.signal)
    await delay()
    return { ...fixtures.FIXTURE_OP_QUEUED, id: nextId('op'), projectId }
  }
}

// ── Functions ───────────────────────────────────────────────────────────

class MockFunctionsGateway implements FunctionsGateway {
  private functions = new Map([[fixtures.FIXTURE_FUNCTION.id, { ...fixtures.FIXTURE_FUNCTION }]])

  async list(projectId: string, opts?: GatewayOptions): Promise<FunctionDef[]> {
    checkAbort(opts?.signal)
    await delay()
    return Array.from(this.functions.values()).filter((f) => f.projectId === projectId)
  }

  async get(_projectId: string, id: string, opts?: GatewayOptions): Promise<FunctionDef> {
    checkAbort(opts?.signal)
    await delay()
    const fn = this.functions.get(id)
    if (!fn) throw new StudioError({ message: `Function '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    return { ...fn }
  }

  async create(projectId: string, input: FunctionCreate, opts?: GatewayOptions): Promise<FunctionDef> {
    checkAbort(opts?.signal)
    await delay()
    const fn: FunctionDef = { id: nextId('fn'), projectId, name: input.name, description: input.description ?? '', source: input.source }
    this.functions.set(fn.id, fn)
    return { ...fn }
  }

  async update(_projectId: string, id: string, input: FunctionUpdate, opts?: GatewayOptions): Promise<FunctionDef> {
    checkAbort(opts?.signal)
    await delay()
    const fn = this.functions.get(id)
    if (!fn) throw new StudioError({ message: `Function '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    if (input.name !== undefined) fn.name = input.name
    if (input.description !== undefined) fn.description = input.description
    if (input.source !== undefined) fn.source = input.source
    return { ...fn }
  }

  async delete(_projectId: string, id: string, opts?: GatewayOptions): Promise<void> {
    checkAbort(opts?.signal)
    await delay()
    if (!this.functions.has(id)) throw new StudioError({ message: `Function '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    this.functions.delete(id)
  }
}

// ── Plugins ─────────────────────────────────────────────────────────────

class MockPluginsGateway implements PluginsGateway {
  async list(_projectId: string, opts?: GatewayOptions): Promise<PluginInfo[]> {
    checkAbort(opts?.signal)
    await delay()
    return [...fixtures.FIXTURE_PLUGINS]
  }

  async get(_projectId: string, id: string, opts?: GatewayOptions): Promise<PluginInfo> {
    checkAbort(opts?.signal)
    await delay()
    const plugin = fixtures.FIXTURE_PLUGINS.find((p) => p.id === id)
    if (!plugin) throw new StudioError({ message: `Plugin '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    return { ...plugin }
  }
}

// ── Monitors ────────────────────────────────────────────────────────────

class MockMonitorsGateway implements MonitorsGateway {
  private monitors = new Map([[fixtures.FIXTURE_MONITOR.id, { ...fixtures.FIXTURE_MONITOR }]])

  async list(projectId: string, opts?: GatewayOptions): Promise<Monitor[]> {
    checkAbort(opts?.signal)
    await delay()
    return Array.from(this.monitors.values()).filter((m) => m.projectId === projectId)
  }

  async get(_projectId: string, id: string, opts?: GatewayOptions): Promise<Monitor> {
    checkAbort(opts?.signal)
    await delay()
    const mon = this.monitors.get(id)
    if (!mon) throw new StudioError({ message: `Monitor '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    return { ...mon }
  }

  async create(projectId: string, input: MonitorCreate, opts?: GatewayOptions): Promise<Monitor> {
    checkAbort(opts?.signal)
    await delay()
    const mon: Monitor = {
      id: nextId('mon'),
      projectId,
      name: input.name,
      url: input.url,
      method: input.method ?? 'GET',
      interval: input.interval,
      status: 'stopped',
      notificationMode: input.notificationMode ?? 'change',
      headers: input.headers,
      condition: input.condition,
    }
    this.monitors.set(mon.id, mon)
    return { ...mon }
  }

  async update(_projectId: string, id: string, input: MonitorUpdate, opts?: GatewayOptions): Promise<Monitor> {
    checkAbort(opts?.signal)
    await delay()
    const mon = this.monitors.get(id)
    if (!mon) throw new StudioError({ message: `Monitor '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    Object.assign(mon, input)
    return { ...mon }
  }

  async delete(_projectId: string, id: string, opts?: GatewayOptions): Promise<void> {
    checkAbort(opts?.signal)
    await delay()
    if (!this.monitors.has(id)) throw new StudioError({ message: `Monitor '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    this.monitors.delete(id)
  }

  async start(projectId: string, id: string, opts?: GatewayOptions): Promise<Operation> {
    checkAbort(opts?.signal)
    await delay()
    const mon = this.monitors.get(id)
    if (!mon) throw new StudioError({ message: `Monitor '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    mon.status = 'running'
    return { ...fixtures.FIXTURE_OP_QUEUED, id: nextId('op'), projectId, type: 'monitor_start' }
  }

  async stop(projectId: string, id: string, opts?: GatewayOptions): Promise<Operation> {
    checkAbort(opts?.signal)
    await delay()
    const mon = this.monitors.get(id)
    if (!mon) throw new StudioError({ message: `Monitor '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    mon.status = 'stopped'
    return { ...fixtures.FIXTURE_OP_QUEUED, id: nextId('op'), projectId, type: 'monitor_stop' }
  }

  async events(_projectId: string, id: string, opts?: GatewayOptions): Promise<MonitorEvent[]> {
    checkAbort(opts?.signal)
    await delay()
    return fixtures.FIXTURE_MONITOR_EVENTS.filter((e) => e.monitorId === id)
  }
}

// ── Runs (Operations) ───────────────────────────────────────────────────

class MockRunsGateway implements RunsGateway {
  async list(projectId: string, status?: OperationStatus, opts?: GatewayOptions): Promise<Operation[]> {
    checkAbort(opts?.signal)
    await delay()
    let ops = fixtures.FIXTURE_OPERATIONS.filter((op) => op.projectId === projectId)
    if (status) ops = ops.filter((op) => op.status === status)
    return ops.map((op) => ({ ...op }))
  }

  async get(projectId: string, id: string, opts?: GatewayOptions): Promise<Operation> {
    checkAbort(opts?.signal)
    await delay()
    const op = fixtures.FIXTURE_OPERATIONS.find((o) => o.id === id && o.projectId === projectId)
    if (!op) throw new StudioError({ message: `Operation '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    return { ...op }
  }

  async cancel(projectId: string, id: string, opts?: GatewayOptions): Promise<Operation> {
    checkAbort(opts?.signal)
    await delay()
    const op = fixtures.FIXTURE_OPERATIONS.find((o) => o.id === id && o.projectId === projectId)
    if (!op) throw new StudioError({ message: `Operation '${id}' not found.`, code: 'NOT_FOUND', status: 404 })
    if (op.status === 'succeeded' || op.status === 'failed' || op.status === 'cancelled') {
      throw new StudioError({ message: `Cannot cancel operation in ${op.status} status.`, code: 'CONFLICT', status: 409 })
    }
    return { ...op, status: op.status === 'queued' ? 'cancelled' : 'cancelling' }
  }
}

// ── Batches ─────────────────────────────────────────────────────────────

class MockBatchesGateway implements BatchesGateway {
  async run(projectId: string, _requestIds: string[], opts?: GatewayOptions): Promise<Operation> {
    checkAbort(opts?.signal)
    await delay()
    return { ...fixtures.FIXTURE_OP_QUEUED, id: nextId('op'), projectId, type: 'batch_run' }
  }
}

// ── Transfers ───────────────────────────────────────────────────────────

class MockTransfersGateway implements TransfersGateway {
  async export(projectId: string, input: ExportCreate, opts?: GatewayOptions): Promise<ExportJob> {
    checkAbort(opts?.signal)
    await delay()
    return { ...fixtures.FIXTURE_EXPORT_JOB, id: nextId('exp'), projectId, format: input.format }
  }

  async import(projectId: string, _file: File, opts?: GatewayOptions): Promise<Operation> {
    checkAbort(opts?.signal)
    await delay()
    return { ...fixtures.FIXTURE_OP_QUEUED, id: nextId('op'), projectId, type: 'import' }
  }

  async presets(_projectId: string, opts?: GatewayOptions): Promise<ExportPreset[]> {
    checkAbort(opts?.signal)
    await delay()
    return [...fixtures.FIXTURE_EXPORT_PRESETS]
  }
}

// ── Settings ────────────────────────────────────────────────────────────

class MockSettingsGateway implements SettingsGateway {
  private settings = { ...fixtures.FIXTURE_SETTINGS }

  async get(opts?: GatewayOptions): Promise<AppSettings> {
    checkAbort(opts?.signal)
    await delay()
    return { ...this.settings }
  }

  async update(input: Partial<AppSettings>, opts?: GatewayOptions): Promise<AppSettings> {
    checkAbort(opts?.signal)
    await delay()
    Object.assign(this.settings, input)
    return { ...this.settings }
  }
}

// ── Events ──────────────────────────────────────────────────────────────

class MockEventsGateway implements EventsGateway {
  subscribe(
    _projectId: string,
    _onEvent: (event: { event: SseEventType; data: Record<string, unknown> }) => void,
    _onError?: (error: Error) => void,
  ): () => void {
    // Mock mode: no real events, return unsubscribe no-op
    return () => {}
  }
}

// ── Factory ─────────────────────────────────────────────────────────────

export function createMockGateway(): StudioGateway {
  return {
    health: new MockHealthGateway(),
    projects: new MockProjectsGateway(),
    collections: new MockCollectionsGateway(),
    requests: new MockRequestsGateway(),
    environments: new MockEnvironmentsGateway(),
    workflows: new MockWorkflowsGateway(),
    functions: new MockFunctionsGateway(),
    plugins: new MockPluginsGateway(),
    monitors: new MockMonitorsGateway(),
    runs: new MockRunsGateway(),
    batches: new MockBatchesGateway(),
    transfers: new MockTransfersGateway(),
    settings: new MockSettingsGateway(),
    events: new MockEventsGateway(),
  }
}
