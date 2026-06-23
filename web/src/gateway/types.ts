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
  // History
  HistoryEntry,
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
  FunctionListItem,
  FunctionDetail,
  AstValidationResult,
  FixtureResult,
  TrustAck,
  FileTreeEntry,
  // Plugin
  PluginInfo,
  PluginDetail,
  PluginDiagnostics,
  // Monitor
  Monitor,
  MonitorCreate,
  MonitorUpdate,
  MonitorEvent,
  // Export
  ExportJob,
  ExportCreate,
  ExportPreset,
  // Settings
  AppSettings,
  AppSettingsUpdate,
  // Logs
  LogEntry,
  LogListResponse,
  // Licenses
  LicenseEntry,
  LicenseListResponse,
  // Commands
  CommandEntry,
  CommandListResponse,
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
  duplicate(projectId: string, id: string, opts?: GatewayOptions): Promise<Collection>
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
  move(
    projectId: string,
    id: string,
    targetCollectionId?: string,
    opts?: GatewayOptions,
  ): Promise<RequestDef>
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
  getActive(projectId: string, opts?: GatewayOptions): Promise<Environment | null>
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
  activate(projectId: string, id: string, opts?: GatewayOptions): Promise<Environment>
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
  list(projectId: string, opts?: GatewayOptions): Promise<FunctionListItem[]>
  get(projectId: string, path: string, opts?: GatewayOptions): Promise<FunctionDetail>
  create(projectId: string, input: FunctionCreate, opts?: GatewayOptions): Promise<FunctionDetail>
  update(
    projectId: string,
    path: string,
    input: { source?: string; expectedHash?: string },
    opts?: GatewayOptions,
  ): Promise<FunctionDetail>
  delete(projectId: string, path: string, opts?: GatewayOptions): Promise<void>
  tree(projectId: string, opts?: GatewayOptions): Promise<FileTreeEntry[]>
  validate(projectId: string, source: string, opts?: GatewayOptions): Promise<AstValidationResult>
  runFixture(
    projectId: string,
    path: string,
    input?: Record<string, unknown>,
    trusted?: boolean,
    opts?: GatewayOptions,
  ): Promise<FixtureResult>
  acknowledgeTrust(
    projectId: string,
    path: string,
    contentHash: string,
    opts?: GatewayOptions,
  ): Promise<TrustAck>
  revokeTrust(projectId: string, path: string, opts?: GatewayOptions): Promise<void>
}

export interface PluginsGateway {
  list(projectId: string, opts?: GatewayOptions): Promise<PluginDetail[]>
  get(projectId: string, name: string, opts?: GatewayOptions): Promise<PluginDetail>
  scaffold(
    projectId: string,
    name: string,
    description?: string,
    opts?: GatewayOptions,
  ): Promise<PluginDetail>
  enable(projectId: string, name: string, opts?: GatewayOptions): Promise<PluginDetail>
  disable(projectId: string, name: string, opts?: GatewayOptions): Promise<PluginDetail>
  reload(projectId: string, opts?: GatewayOptions): Promise<PluginDetail[]>
  getManifest(projectId: string, name: string, opts?: GatewayOptions): Promise<Record<string, unknown>>
  updateManifest(
    projectId: string,
    name: string,
    data: Record<string, unknown>,
    opts?: GatewayOptions,
  ): Promise<PluginDetail>
  getTree(projectId: string, name: string, opts?: GatewayOptions): Promise<FileTreeEntry[]>
  readFile(projectId: string, name: string, path: string, opts?: GatewayOptions): Promise<{ content: string; hash: string; size: number }>
  writeFile(
    projectId: string,
    name: string,
    path: string,
    content: string,
    expectedHash?: string,
    opts?: GatewayOptions,
  ): Promise<{ path: string; hash: string; size: number }>
  getDiagnostics(projectId: string, name: string, opts?: GatewayOptions): Promise<PluginDiagnostics>
  export(projectId: string, name: string, opts?: GatewayOptions): Promise<Blob>
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
  update(input: AppSettingsUpdate, opts?: GatewayOptions): Promise<AppSettings>
}

export interface LogsGateway {
  list(opts?: GatewayOptions & { level?: string; source?: string; search?: string; limit?: number }): Promise<LogListResponse>
  pause(opts?: GatewayOptions): Promise<{ paused: boolean }>
  resume(opts?: GatewayOptions): Promise<{ paused: boolean }>
  clear(opts?: GatewayOptions): Promise<{ cleared: number }>
  exportUrl(level?: string, source?: string, search?: string, redact?: boolean): string
}

export interface LicensesGateway {
  list(opts?: GatewayOptions): Promise<LicenseListResponse>
}

export interface CommandsGateway {
  list(opts?: GatewayOptions): Promise<CommandListResponse>
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

export interface HistoryGateway {
  list(
    projectId: string,
    opts?: GatewayOptions & { cursor?: string; limit?: number; requestId?: string },
  ): Promise<PaginatedResponse<HistoryEntry>>
  get(projectId: string, id: string, opts?: GatewayOptions): Promise<HistoryEntry>
  clear(projectId: string, opts?: GatewayOptions): Promise<{ deleted: number }>
}

// ── Top-level gateway ───────────────────────────────────────────────────

export interface StudioGateway {
  readonly health: HealthGateway
  readonly projects: ProjectsGateway
  readonly collections: CollectionsGateway
  readonly requests: RequestsGateway
  readonly environments: EnvironmentsGateway
  readonly history: HistoryGateway
  readonly workflows: WorkflowsGateway
  readonly functions: FunctionsGateway
  readonly plugins: PluginsGateway
  readonly monitors: MonitorsGateway
  readonly runs: RunsGateway
  readonly batches: BatchesGateway
  readonly transfers: TransfersGateway
  readonly settings: SettingsGateway
  readonly logs: LogsGateway
  readonly licenses: LicensesGateway
  readonly commands: CommandsGateway
  readonly events: EventsGateway
}
