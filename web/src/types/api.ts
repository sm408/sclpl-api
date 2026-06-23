/**
 * TypeScript types matching the SCLPLAPI backend DTOs.
 *
 * These mirror the Pydantic camelCase wire format. When the backend
 * evolves, regenerate from OpenAPI and this file should be updated.
 */

// ── Enums ───────────────────────────────────────────────────────────────

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'HEAD' | 'OPTIONS'

export type OperationType =
  | 'workflow_run'
  | 'batch_run'
  | 'monitor_start'
  | 'monitor_stop'
  | 'export'
  | 'import'

export type OperationStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelling'
  | 'cancelled'

export type StepType = 'request' | 'function' | 'transformer' | 'export' | 'delay'

export type PluginStatus = 'discovered' | 'loaded' | 'active' | 'error'

export type MonitorStatus = 'stopped' | 'running' | 'paused' | 'error'

export type NotificationMode = 'always' | 'change' | 'condition_met'

export type ExportFormat = 'json' | 'csv' | 'excel'

export type RunStatus = 'success' | 'error' | 'timeout' | 'cancelled'

export type VariableScope = 'global' | 'environment'

// ── Error protocol ──────────────────────────────────────────────────────

export interface FieldError {
  field: string
  message: string
}

export interface ErrorBody {
  code: string
  message: string
  fieldErrors: FieldError[]
  correlationId: string
}

export interface ErrorResponse {
  error: ErrorBody
}

// ── Pagination ──────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[]
  nextCursor: string | null
  total: number
}

// ── Health ──────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string
  version: string
  schemaVersion: number
}

// ── Project ─────────────────────────────────────────────────────────────

export interface Project {
  id: string
  name: string
  description: string
  rootPath: string
  isDefault: boolean
  createdAt: string | null
  updatedAt: string | null
}

export interface ProjectCreate {
  name: string
  description?: string
}

export interface ProjectUpdate {
  name?: string
  description?: string
}

// ── Operation ───────────────────────────────────────────────────────────

export interface Operation {
  id: string
  projectId: string
  type: OperationType
  status: OperationStatus
  progress: number
  createdAt: string
  startedAt: string | null
  finishedAt: string | null
  result: Record<string, unknown> | null
  error: string | null
}

// ── Collection ──────────────────────────────────────────────────────────

export interface CollectionItem {
  id: string
  name: string
  type: 'request' | 'folder'
  requestId?: string
  children?: CollectionItem[]
}

export interface Collection {
  id: string
  projectId: string
  name: string
  description: string
  items: CollectionItem[]
}

export interface CollectionCreate {
  name: string
  description?: string
}

export interface CollectionUpdate {
  name?: string
  description?: string
}

// ── Request ─────────────────────────────────────────────────────────────

export interface RequestParam {
  key: string
  value: string
  enabled: boolean
}

export interface RequestBody {
  contentType?: string
  content?: string
}

export interface RequestDef {
  id: string
  projectId: string
  collectionId?: string
  name: string
  method: HttpMethod
  url: string
  headers: Record<string, string>
  params: RequestParam[]
  body?: RequestBody
}

export interface RequestCreate {
  name: string
  method: HttpMethod
  url: string
  collectionId?: string
  headers?: Record<string, string>
  params?: RequestParam[]
  body?: RequestBody
}

export interface RequestUpdate {
  name?: string
  method?: HttpMethod
  url?: string
  collectionId?: string
  headers?: Record<string, string>
  params?: RequestParam[]
  body?: RequestBody
}

export interface RunResult {
  statusCode: number
  headers: Record<string, string>
  body: unknown
  duration: number
}

// ── Environment ─────────────────────────────────────────────────────────

export interface Variable {
  key: string
  value: string
  scope: VariableScope
}

export interface Environment {
  id: string
  projectId: string
  name: string
  variables: Variable[]
}

export interface EnvironmentCreate {
  name: string
  variables?: Variable[]
}

export interface EnvironmentUpdate {
  name?: string
  variables?: Variable[]
}

// ── Workflow ────────────────────────────────────────────────────────────

export interface RetryConfig {
  maxRetries: number
  delayMs: number
  backoffMultiplier?: number
}

export interface WorkflowStep {
  id: string
  name: string
  type: StepType
  config: Record<string, unknown>
  dependsOn: string[]
  retry?: RetryConfig
}

export interface WorkflowDef {
  id: string
  projectId: string
  name: string
  description: string
  steps: WorkflowStep[]
}

export interface WorkflowCreate {
  name: string
  description?: string
  steps?: WorkflowStep[]
}

export interface WorkflowUpdate {
  name?: string
  description?: string
  steps?: WorkflowStep[]
}

// ── Function ────────────────────────────────────────────────────────────

export interface FunctionDef {
  id: string
  projectId: string
  name: string
  description: string
  source: string
}

export interface FunctionCreate {
  name: string
  description?: string
  source: string
}

export interface FunctionUpdate {
  name?: string
  description?: string
  source?: string
}

export interface FunctionListItem {
  path: string
  name: string
  description: string
  type: string
  category: string
  hash: string
  size: number
}

export interface FunctionDetail {
  path: string
  name: string
  description: string
  type: string
  category: string
  content: string
  hash: string
  size: number
  valid: boolean
  diagnostics: AstDiagnostic[]
  trusted: boolean
}

export interface AstDiagnostic {
  line: number
  column: number
  severity: 'error' | 'warning' | 'info'
  message: string
}

export interface AstValidationResult {
  valid: boolean
  diagnostics: AstDiagnostic[]
}

export interface FixtureResult {
  success: boolean
  output: unknown
  error: string | null
  durationMs: number
  stdout: string
  stderr: string
}

export interface TrustAck {
  path: string
  hash: string
  trusted: boolean
}

export interface FileTreeEntry {
  path: string
  name: string
  type: 'file' | 'dir'
  size?: number
  children?: FileTreeEntry[]
}

// ── Plugin ──────────────────────────────────────────────────────────────

export interface PluginManifest {
  name: string
  version: string
  description: string
  author?: string
  entryPoint: string
}

export interface PluginInfo {
  id: string
  name: string
  version: string
  status: PluginStatus
  description: string
  manifest?: PluginManifest
}

export interface PluginDetail {
  id: string
  name: string
  version: string
  description: string
  author: string
  category: string
  status: PluginStatus
  functionCount: number
  workflowCount: number
  variableNames: string[]
  error: string | null
  dependencies: string[]
}

export interface PluginDiagnostics {
  name: string
  status: string
  functionCount: number
  workflowCount: number
  variableNames: string[]
  error: string | null
  dependencies: string[]
}

// ── Monitor ─────────────────────────────────────────────────────────────

export interface MonitorEvent {
  id: string
  monitorId: string
  timestamp: string
  statusCode: number
  duration: number
  changed: boolean
}

export interface Monitor {
  id: string
  projectId: string
  name: string
  url: string
  method: HttpMethod
  interval: number
  status: MonitorStatus
  notificationMode: NotificationMode
  headers?: Record<string, string>
  condition?: string
}

export interface MonitorCreate {
  name: string
  url: string
  method?: HttpMethod
  interval: number
  notificationMode?: NotificationMode
  headers?: Record<string, string>
  condition?: string
}

export interface MonitorUpdate {
  name?: string
  url?: string
  method?: HttpMethod
  interval?: number
  notificationMode?: NotificationMode
  headers?: Record<string, string>
  condition?: string
}

// ── Export ──────────────────────────────────────────────────────────────

export interface ExportFieldMapping {
  source: string
  target: string
}

export interface ExportPreset {
  id: string
  name: string
  format: ExportFormat
  fields: ExportFieldMapping[]
}

export interface ExportJob {
  id: string
  projectId: string
  format: ExportFormat
  status: string
  filePath?: string
}

export interface ExportCreate {
  format: ExportFormat
  sourceRequestId?: string
  fields?: ExportFieldMapping[]
}

// ── History ─────────────────────────────────────────────────────────────

export interface HistoryEntry {
  id: string
  projectId: string
  requestId: string | null
  requestName: string
  method: HttpMethod
  url: string
  status: RunStatus
  statusCode: number | null
  responseBody: string | null
  responseHeaders: Record<string, unknown>
  durationMs: number
  errorMessage: string | null
  environmentId: string | null
  variablesUsed: Record<string, unknown>
  createdAt: string | null
}

// ── Settings ────────────────────────────────────────────────────────────

export interface AppSettings {
  theme: 'light' | 'dark' | 'system'
  defaultTimeout: number
  followRedirects: boolean
  maxHistoryEntries: number
}

// ── SSE Events ──────────────────────────────────────────────────────────

export type SseEventType =
  | 'operation.started'
  | 'operation.progress'
  | 'operation.completed'
  | 'operation.failed'
  | 'operation.cancelled'
  | 'stream.reset'

export interface SseEvent<T = Record<string, unknown>> {
  id: string
  event: SseEventType
  data: T
}

export interface OperationStartedEvent {
  operationId: string
  projectId: string
  operationType: string
}

export interface OperationProgressEvent {
  operationId: string
  projectId: string
  progress: number
  message: string
}

export interface OperationCompletedEvent {
  operationId: string
  projectId: string
  result: Record<string, unknown>
}

export interface OperationFailedEvent {
  operationId: string
  projectId: string
  error: string
}

export interface OperationCancelledEvent {
  operationId: string
  projectId: string
}

export interface StreamResetEvent {
  reason: string
}
