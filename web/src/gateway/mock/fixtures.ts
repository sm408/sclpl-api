/**
 * Deterministic mock fixtures for every resource family.
 *
 * These fixtures are used by both the mock gateway and tests.
 * They cover all resource types and all operation states.
 */

import type {
  Project,
  Operation,
  Collection,
  CollectionItem,
  RequestDef,
  Environment,
  WorkflowDef,
  FunctionDef,
  PluginInfo,
  Monitor,
  MonitorEvent,
  ExportJob,
  ExportPreset,
  HistoryEntry,
  HealthResponse,
  AppSettings,
} from '@/types/api'

// ── IDs ─────────────────────────────────────────────────────────────────

export const IDS = {
  project: 'proj-default-001',
  projectAlt: 'proj-workspace-002',
  collection: 'col-api-tests-001',
  request: 'req-get-users-001',
  requestPost: 'req-post-user-002',
  environment: 'env-dev-001',
  workflow: 'wf-smoke-test-001',
  function: 'fn-parse-json-001',
  plugin: 'plug-jsonpath-001',
  monitor: 'mon-health-check-001',
  exportJob: 'exp-users-csv-001',
  historyEntry: 'hist-run-001',
  // Operations in every state
  opQueued: 'op-queued-001',
  opRunning: 'op-running-002',
  opSucceeded: 'op-succeeded-003',
  opFailed: 'op-failed-004',
  opCancelling: 'op-cancelling-005',
  opCancelled: 'op-cancelled-006',
} as const

// ── Health ──────────────────────────────────────────────────────────────

export const FIXTURE_HEALTH: HealthResponse = {
  status: 'ok',
  version: '0.1.0',
  schemaVersion: 4,
}

// ── Projects ────────────────────────────────────────────────────────────

export const FIXTURE_PROJECT_DEFAULT: Project = {
  id: IDS.project,
  name: 'Default',
  description: 'Default project',
  rootPath: '/data/projects/default',
  isDefault: true,
  createdAt: '2025-01-01T00:00:00Z',
  updatedAt: '2025-01-01T00:00:00Z',
}

export const FIXTURE_PROJECT_WORKSPACE: Project = {
  id: IDS.projectAlt,
  name: 'My Workspace',
  description: 'A test workspace',
  rootPath: '/data/projects/workspace',
  isDefault: false,
  createdAt: '2025-06-01T10:00:00Z',
  updatedAt: '2025-06-15T14:30:00Z',
}

export const FIXTURE_PROJECTS: Project[] = [
  FIXTURE_PROJECT_DEFAULT,
  FIXTURE_PROJECT_WORKSPACE,
]

// ── Collections ─────────────────────────────────────────────────────────

export const FIXTURE_COLLECTION_ITEMS: CollectionItem[] = [
  { id: 'item-001', name: 'Get Users', type: 'request', requestId: IDS.request },
  { id: 'item-002', name: 'Create User', type: 'request', requestId: IDS.requestPost },
  {
    id: 'item-003',
    name: 'Auth',
    type: 'folder',
    children: [
      { id: 'item-004', name: 'Login', type: 'request' },
      { id: 'item-005', name: 'Logout', type: 'request' },
    ],
  },
]

export const FIXTURE_COLLECTION: Collection = {
  id: IDS.collection,
  projectId: IDS.project,
  name: 'API Tests',
  description: 'Collection of API test requests',
  items: FIXTURE_COLLECTION_ITEMS,
}

export const FIXTURE_COLLECTIONS: Collection[] = [FIXTURE_COLLECTION]

// ── Requests ────────────────────────────────────────────────────────────

export const FIXTURE_REQUEST_GET: RequestDef = {
  id: IDS.request,
  projectId: IDS.project,
  collectionId: IDS.collection,
  name: 'Get Users',
  method: 'GET',
  url: 'https://jsonplaceholder.typicode.com/users',
  headers: { Accept: 'application/json' },
  params: [{ key: 'limit', value: '10', enabled: true }],
}

export const FIXTURE_REQUEST_POST: RequestDef = {
  id: IDS.requestPost,
  projectId: IDS.project,
  collectionId: IDS.collection,
  name: 'Create User',
  method: 'POST',
  url: 'https://jsonplaceholder.typicode.com/users',
  headers: { 'Content-Type': 'application/json' },
  params: [],
  body: {
    contentType: 'application/json',
    content: '{"name": "John Doe", "email": "john@example.com"}',
  },
}

export const FIXTURE_REQUESTS: RequestDef[] = [FIXTURE_REQUEST_GET, FIXTURE_REQUEST_POST]

// ── Environments ────────────────────────────────────────────────────────

export const FIXTURE_ENVIRONMENT: Environment = {
  id: IDS.environment,
  projectId: IDS.project,
  name: 'Development',
  variables: [
    { key: 'base_url', value: 'https://api.dev.example.com', scope: 'environment' },
    { key: 'api_key', value: 'dev-key-123', scope: 'environment' },
    { key: 'timeout', value: '5000', scope: 'global' },
  ],
}

export const FIXTURE_ENVIRONMENTS: Environment[] = [FIXTURE_ENVIRONMENT]

// ── Workflows ───────────────────────────────────────────────────────────

export const FIXTURE_WORKFLOW: WorkflowDef = {
  id: IDS.workflow,
  projectId: IDS.project,
  name: 'Smoke Test',
  description: 'Run basic health checks',
  steps: [
    {
      id: 'step-001',
      name: 'Health Check',
      type: 'request',
      config: { requestId: IDS.request },
      dependsOn: [],
    },
    {
      id: 'step-002',
      name: 'Parse Response',
      type: 'function',
      config: { functionId: IDS.function },
      dependsOn: ['step-001'],
    },
    {
      id: 'step-003',
      name: 'Export Results',
      type: 'export',
      config: { format: 'json' },
      dependsOn: ['step-002'],
    },
  ],
}

export const FIXTURE_WORKFLOWS: WorkflowDef[] = [FIXTURE_WORKFLOW]

// ── Functions ───────────────────────────────────────────────────────────

export const FIXTURE_FUNCTION: FunctionDef = {
  id: IDS.function,
  projectId: IDS.project,
  name: 'parse_json',
  description: 'Parse JSON response body',
  source: 'def parse_json(response):\n    return response.json()',
}

export const FIXTURE_FUNCTIONS: FunctionDef[] = [FIXTURE_FUNCTION]

// ── Plugins ─────────────────────────────────────────────────────────────

export const FIXTURE_PLUGIN: PluginInfo = {
  id: IDS.plugin,
  name: 'jsonpath',
  version: '1.0.0',
  status: 'active',
  description: 'JSONPath query support',
}

export const FIXTURE_PLUGINS: PluginInfo[] = [FIXTURE_PLUGIN]

// ── Monitors ────────────────────────────────────────────────────────────

export const FIXTURE_MONITOR: Monitor = {
  id: IDS.monitor,
  projectId: IDS.project,
  name: 'Health Check',
  url: 'https://api.example.com/health',
  method: 'GET',
  interval: 60,
  status: 'running',
  notificationMode: 'change',
}

export const FIXTURE_MONITORS: Monitor[] = [FIXTURE_MONITOR]

export const FIXTURE_MONITOR_EVENTS: MonitorEvent[] = [
  {
    id: 'mev-001',
    monitorId: IDS.monitor,
    timestamp: '2025-06-20T10:00:00Z',
    statusCode: 200,
    duration: 150,
    changed: false,
  },
  {
    id: 'mev-002',
    monitorId: IDS.monitor,
    timestamp: '2025-06-20T10:01:00Z',
    statusCode: 503,
    duration: 5000,
    changed: true,
  },
]

// ── Operations (every state) ────────────────────────────────────────────

export const FIXTURE_OP_QUEUED: Operation = {
  id: IDS.opQueued,
  projectId: IDS.project,
  type: 'workflow_run',
  status: 'queued',
  progress: 0,
  createdAt: '2025-06-20T10:00:00Z',
  startedAt: null,
  finishedAt: null,
  result: null,
  error: null,
}

export const FIXTURE_OP_RUNNING: Operation = {
  id: IDS.opRunning,
  projectId: IDS.project,
  type: 'workflow_run',
  status: 'running',
  progress: 0.45,
  createdAt: '2025-06-20T10:00:00Z',
  startedAt: '2025-06-20T10:00:01Z',
  finishedAt: null,
  result: null,
  error: null,
}

export const FIXTURE_OP_SUCCEEDED: Operation = {
  id: IDS.opSucceeded,
  projectId: IDS.project,
  type: 'workflow_run',
  status: 'succeeded',
  progress: 1,
  createdAt: '2025-06-20T10:00:00Z',
  startedAt: '2025-06-20T10:00:01Z',
  finishedAt: '2025-06-20T10:00:05Z',
  result: { output: 'All steps passed' },
  error: null,
}

export const FIXTURE_OP_FAILED: Operation = {
  id: IDS.opFailed,
  projectId: IDS.project,
  type: 'workflow_run',
  status: 'failed',
  progress: 0.3,
  createdAt: '2025-06-20T10:00:00Z',
  startedAt: '2025-06-20T10:00:01Z',
  finishedAt: '2025-06-20T10:00:03Z',
  result: null,
  error: 'Step "Health Check" failed: Connection refused',
}

export const FIXTURE_OP_CANCELLING: Operation = {
  id: IDS.opCancelling,
  projectId: IDS.project,
  type: 'batch_run',
  status: 'cancelling',
  progress: 0.6,
  createdAt: '2025-06-20T10:00:00Z',
  startedAt: '2025-06-20T10:00:01Z',
  finishedAt: null,
  result: null,
  error: null,
}

export const FIXTURE_OP_CANCELLED: Operation = {
  id: IDS.opCancelled,
  projectId: IDS.project,
  type: 'workflow_run',
  status: 'cancelled',
  progress: 0,
  createdAt: '2025-06-20T10:00:00Z',
  startedAt: null,
  finishedAt: '2025-06-20T10:00:02Z',
  result: null,
  error: null,
}

export const FIXTURE_OPERATIONS: Operation[] = [
  FIXTURE_OP_QUEUED,
  FIXTURE_OP_RUNNING,
  FIXTURE_OP_SUCCEEDED,
  FIXTURE_OP_FAILED,
  FIXTURE_OP_CANCELLING,
  FIXTURE_OP_CANCELLED,
]

// ── Exports ─────────────────────────────────────────────────────────────

export const FIXTURE_EXPORT_JOB: ExportJob = {
  id: IDS.exportJob,
  projectId: IDS.project,
  format: 'csv',
  status: 'completed',
  filePath: '/data/projects/default/exports/users.csv',
}

export const FIXTURE_EXPORT_PRESET: ExportPreset = {
  id: 'preset-001',
  name: 'Users CSV',
  format: 'csv',
  fields: [
    { source: 'name', target: 'Name' },
    { source: 'email', target: 'Email' },
  ],
}

export const FIXTURE_EXPORT_PRESETS: ExportPreset[] = [FIXTURE_EXPORT_PRESET]

// ── History ─────────────────────────────────────────────────────────────

export const FIXTURE_HISTORY_ENTRY: HistoryEntry = {
  id: IDS.historyEntry,
  projectId: IDS.project,
  requestId: IDS.request,
  requestName: 'Get Users',
  method: 'GET',
  url: 'https://jsonplaceholder.typicode.com/users',
  status: 'success',
  statusCode: 200,
  responseBody: '{"id": 1, "name": "Leanne Graham"}',
  responseHeaders: { 'content-type': 'application/json' },
  durationMs: 245,
  errorMessage: null,
  environmentId: null,
  variablesUsed: {},
  createdAt: '2025-06-20T10:00:00Z',
}

export const FIXTURE_HISTORY: HistoryEntry[] = [FIXTURE_HISTORY_ENTRY]

// ── Settings ────────────────────────────────────────────────────────────

export const FIXTURE_SETTINGS: AppSettings = {
  defaultTimeout: 30,
  followRedirects: true,
  maxHistoryEntries: 500,
  editor: {
    tabSize: 4,
    wordWrap: 'off',
    minimap: true,
    fontSize: 14,
  },
  history: {
    maxEntries: 500,
    autoClearDays: 0,
  },
  startup: {
    defaultProjectId: null,
    reopenLastTabs: true,
  },
  restartRequired: false,
}
