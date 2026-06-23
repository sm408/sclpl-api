/**
 * Gateway interfaces for the SCLPLAPI web studio.
 *
 * StudioGateway is the single point of access for all backend resources.
 * Feature code receives it through injection and never imports the HTTP
 * client or mock adapter directly.
 *
 * Each sub-gateway mirrors a resource family on the backend. Methods
 * return plain data; errors are thrown as StudioError.
 */

import type {
  // Health
  HealthResponse,
  // Pagination
  PaginatedResponse,
  // Project
  Project,
  ProjectCreate,
  ProjectUpdate,
  // Operation
  Operation,
  // Collection
  Collection,
  CollectionCreate,
  CollectionUpdate,
  // Request
  RequestDef,
  RequestCreate,
  RequestUpdate,
  RunResult,
  // Environment
  Environment,
  EnvironmentCreate,
  EnvironmentUpdate,
  // Workflow
  WorkflowDef,
  WorkflowCreate,
  WorkflowUpdate,
  // Function
  FunctionDef,
  FunctionCreate,
  FunctionUpdate,
  // Plugin
  PluginInfo,
  // Monitor
  Monitor,
  MonitorCreate,
  MonitorUpdate,
  MonitorEvent,
  // Export
  ExportJob,
  ExportCreate,
  ExportPreset,
  // History
  HistoryEntry,
  // Settings
  AppSettings,
  // Operations filter
  OperationStatus,
  // SSE
  SseEventType,
} from '@/types/api'

// ── Abort signal type ──────────────────────────────────────────────────

/** Options accepted by every gateway method. */
export interface GatewayOptions {
  /** AbortSignal for cancellation / timeout. */
  signal?: AbortSignal
}

// ── Sub-gateway interfaces ──────────────────────────────────────────────

export interface HealthGateway {
  check(opts?: GatewayOptions): Promise<HealthResponse>
}

export interface ProjectsGateway {
  list(opts?: GatewayOptions): Promise<Project[]>
  get(id: string, opts?: GatewayOptions): Promise<Project>
  create(input: ProjectCreate, opts?: GatewayOptions): Promise<Project>
  update(id: string, input: ProjectUpdate, opts?: GatewayOptions): Promise<Project>
  delete(id: string, opts?: GatewayOptions): Promise<void>
}

export interface CollectionsGateway {
  list(projectId: string, opts?: GatewayOptions): Promise<Collection[]>
  get(projectId: string, id: string, opts?: GatewayOptions): Promise<Collection>
  create(projectId: string, input: CollectionCreate, opts?: GatewayOptions): Promise<Collection>
  update(
    projectId: string,
    id: string,
    input: CollectionUpdate,
    opts?: GatewayOptions,
  ): Promise<Collection>
  delete(projectId: string, id: string, opts?: GatewayOptions): Promise<void>
}

export interface RequestsGateway {
  list(
    projectId: string,
    collectionId?: string,
    opts?: GatewayOptions,
  ): Promise<RequestDef[]>
  get(projectId: string, id: string, opts?: GatewayOptions): Promise<RequestDef>
  create(projectId: string, input: RequestCreate, opts?: GatewayOptions): Promise<RequestDef>
  update(
    projectId: string,
    id: string,
    input: RequestUpdate,
    opts?: GatewayOptions,
  ): Promise<RequestDef>
  delete(projectId: string, id: string, opts?: GatewayOptions): Promise<void>
  execute(
    projectId: string,
    id: string,
    context?: Record<string, unknown>,
    opts?: GatewayOptions,
  ): Promise<RunResult>
}

export interface EnvironmentsGateway {
  list(projectId: string, opts?: GatewayOptions): Promise<Environment[]>
  get(projectId: string, id: string, opts?: GatewayOptions): Promise<Environment>
  create(
    projectId: string,
    input: EnvironmentCreate,
    opts?: GatewayOptions,
  ): Promise<Environment>
  update(
    projectId: string,
    id: string,
    input: EnvironmentUpdate,
    opts?: GatewayOptions,
  ): Promise<Environment>
  delete(projectId: string, id: string, opts?: GatewayOptions): Promise<void>
}

export interface WorkflowsGateway {
  list(projectId: string, opts?: GatewayOptions): Promise<WorkflowDef[]>
  get(projectId: string, id: string, opts?: GatewayOptions): Promise<WorkflowDef>
  create(projectId: string, input: WorkflowCreate, opts?: GatewayOptions): Promise<WorkflowDef>
  update(
    projectId: string,
    id: string,
    input: WorkflowUpdate,
    opts?: GatewayOptions,
  ): Promise<WorkflowDef>
  delete(projectId: string, id: string, opts?: GatewayOptions): Promise<void>
  run(projectId: string, id: string, opts?: GatewayOptions): Promise<Operation>
}

export interface FunctionsGateway {
  list(projectId: string, opts?: GatewayOptions): Promise<FunctionDef[]>
  get(projectId: string, id: string, opts?: GatewayOptions): Promise<FunctionDef>
  create(projectId: string, input: FunctionCreate, opts?: GatewayOptions): Promise<FunctionDef>
  update(
    projectId: string,
    id: string,
    input: FunctionUpdate,
    opts?: GatewayOptions,
  ): Promise<FunctionDef>
  delete(projectId: string, id: string, opts?: GatewayOptions): Promise<void>
}

export interface PluginsGateway {
  list(projectId: string, opts?: GatewayOptions): Promise<PluginInfo[]>
  get(projectId: string, id: string, opts?: GatewayOptions): Promise<PluginInfo>
}

export interface MonitorsGateway {
  list(projectId: string, opts?: GatewayOptions): Promise<Monitor[]>
  get(projectId: string, id: string, opts?: GatewayOptions): Promise<Monitor>
  create(projectId: string, input: MonitorCreate, opts?: GatewayOptions): Promise<Monitor>
  update(
    projectId: string,
    id: string,
    input: MonitorUpdate,
    opts?: GatewayOptions,
  ): Promise<Monitor>
  delete(projectId: string, id: string, opts?: GatewayOptions): Promise<void>
  start(projectId: string, id: string, opts?: GatewayOptions): Promise<Operation>
  stop(projectId: string, id: string, opts?: GatewayOptions): Promise<Operation>
  events(projectId: string, id: string, opts?: GatewayOptions): Promise<MonitorEvent[]>
}

export interface RunsGateway {
  list(
    projectId: string,
    status?: OperationStatus,
    opts?: GatewayOptions,
  ): Promise<Operation[]>
  get(projectId: string, id: string, opts?: GatewayOptions): Promise<Operation>
  cancel(projectId: string, id: string, opts?: GatewayOptions): Promise<Operation>
}

export interface BatchesGateway {
  run(
    projectId: string,
    requestIds: string[],
    opts?: GatewayOptions,
  ): Promise<Operation>
}

export interface TransfersGateway {
  export(projectId: string, input: ExportCreate, opts?: GatewayOptions): Promise<ExportJob>
  import(projectId: string, file: File, opts?: GatewayOptions): Promise<Operation>
  presets(projectId: string, opts?: GatewayOptions): Promise<ExportPreset[]>
}

export interface SettingsGateway {
  get(opts?: GatewayOptions): Promise<AppSettings>
  update(input: Partial<AppSettings>, opts?: GatewayOptions): Promise<AppSettings>
}

export interface EventsGateway {
  /**
   * Subscribe to SSE events for a project.
   * Returns an unsubscribe function.
   *
   * The callback receives parsed events. On connection loss the adapter
   * reconnects automatically and replays missed events when possible.
   */
  subscribe(
    projectId: string,
    onEvent: (event: { event: SseEventType; data: Record<string, unknown> }) => void,
    onError?: (error: Error) => void,
  ): () => void
}

// ── Top-level gateway ───────────────────────────────────────────────────

export interface StudioGateway {
  readonly health: HealthGateway
  readonly projects: ProjectsGateway
  readonly collections: CollectionsGateway
  readonly requests: RequestsGateway
  readonly environments: EnvironmentsGateway
  readonly workflows: WorkflowsGateway
  readonly functions: FunctionsGateway
  readonly plugins: PluginsGateway
  readonly monitors: MonitorsGateway
  readonly runs: RunsGateway
  readonly batches: BatchesGateway
  readonly transfers: TransfersGateway
  readonly settings: SettingsGateway
  readonly events: EventsGateway
}
