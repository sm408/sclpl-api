/**
 * FunctionsView — manage Python transformation functions.
 *
 * Shows a file tree of functions with a code editor panel, AST
 * validation, fixture execution, and trust acknowledgement.
 */

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { getGateway } from '@/gateway'
import { useProjectStore } from '@/stores/project'
import type { FunctionListItem, FunctionDetail, AstDiagnostic, FixtureResult, FileTreeEntry } from '@/types/api'
import {
  FileCode, Plus, Trash2, Play, Shield, ShieldOff, CheckCircle, AlertTriangle,
  Loader2, ChevronRight, ChevronDown, Folder, FolderOpen, RefreshCw,
} from 'lucide-vue-next'

const router = useRouter()
const projectStore = useProjectStore()
const queryClient = useQueryClient()
const gateway = getGateway()

const projectId = computed(() => projectStore.activeProjectId)

// ── State ──────────────────────────────────────────────────────────────

const selectedPath = ref<string | null>(null)
const sourceCode = ref('')
const isDirty = ref(false)
const showCreateDialog = ref(false)
const newName = ref('')
const newSource = ref('')
const fixtureInput = ref('{}')
const fixtureResult = ref<FixtureResult | null>(null)
const expandedDirs = ref<Set<string>>(new Set())

// ── Fetch functions list ───────────────────────────────────────────────

const { data: functions, isLoading } = useQuery({
  queryKey: ['functions', projectId],
  queryFn: () => gateway.functions.list(projectId.value!),
  enabled: computed(() => !!projectId.value),
})

// ── Fetch file tree ────────────────────────────────────────────────────

const { data: fileTree } = useQuery({
  queryKey: ['function-tree', projectId],
  queryFn: () => gateway.functions.tree(projectId.value!),
  enabled: computed(() => !!projectId.value),
})

// ── Fetch selected function detail ─────────────────────────────────────

const { data: selectedFunction, isLoading: isLoadingDetail } = useQuery({
  queryKey: ['function-detail', projectId, selectedPath],
  queryFn: () => gateway.functions.get(projectId.value!, selectedPath.value!),
  enabled: computed(() => !!projectId.value && !!selectedPath.value),
})

watch(selectedFunction, (fn) => {
  if (fn && !isDirty.value) {
    sourceCode.value = fn.content
  }
})

// ── Create ─────────────────────────────────────────────────────────────

const createMutation = useMutation({
  mutationFn: () =>
    gateway.functions.create(projectId.value!, {
      name: newName.value,
      source: newSource.value || '"""\n@name: ' + newName.value + '\n@description: \n"""\n\ndef run(ctx):\n    return {}',
    }),
  onSuccess: (fn) => {
    queryClient.invalidateQueries({ queryKey: ['functions'] })
    queryClient.invalidateQueries({ queryKey: ['function-tree'] })
    showCreateDialog.value = false
    newName.value = ''
    newSource.value = ''
    selectedPath.value = fn.path
  },
})

function handleCreate(): void {
  if (!newName.value.trim()) return
  createMutation.mutate()
}

// ── Save ───────────────────────────────────────────────────────────────

const saveMutation = useMutation({
  mutationFn: () =>
    gateway.functions.update(projectId.value!, selectedPath.value!, {
      source: sourceCode.value,
      expectedHash: selectedFunction.value?.hash,
    }),
  onSuccess: (fn) => {
    queryClient.invalidateQueries({ queryKey: ['functions'] })
    queryClient.invalidateQueries({ queryKey: ['function-detail'] })
    isDirty.value = false
  },
})

function handleSave(): void {
  if (!selectedPath.value) return
  saveMutation.mutate()
}

// ── Delete ─────────────────────────────────────────────────────────────

const deleteMutation = useMutation({
  mutationFn: (path: string) => gateway.functions.delete(projectId.value!, path),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['functions'] })
    queryClient.invalidateQueries({ queryKey: ['function-tree'] })
    selectedPath.value = null
    sourceCode.value = ''
  },
})

// ── Validate ───────────────────────────────────────────────────────────

const validateMutation = useMutation({
  mutationFn: () => gateway.functions.validate(projectId.value!, sourceCode.value),
})

function handleValidate(): void {
  validateMutation.mutate()
}

// ── Run fixture ────────────────────────────────────────────────────────

const runMutation = useMutation({
  mutationFn: () => {
    let input = {}
    try { input = JSON.parse(fixtureInput.value) } catch {}
    return gateway.functions.runFixture(
      projectId.value!,
      selectedPath.value!,
      input,
      selectedFunction.value?.trusted,
    )
  },
  onSuccess: (result) => {
    fixtureResult.value = result
    if (!result.success && result.error?.includes('TRUST_REQUIRED')) {
      // Show trust dialog
    }
  },
})

function handleRun(): void {
  if (!selectedPath.value) return
  runMutation.mutate()
}

// ── Trust ──────────────────────────────────────────────────────────────

const trustMutation = useMutation({
  mutationFn: () =>
    gateway.functions.acknowledgeTrust(
      projectId.value!,
      selectedPath.value!,
      selectedFunction.value?.hash ?? '',
    ),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['function-detail'] })
  },
})

const revokeTrustMutation = useMutation({
  mutationFn: () =>
    gateway.functions.revokeTrust(projectId.value!, selectedPath.value!),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['function-detail'] })
  },
})

// ── Tree helpers ───────────────────────────────────────────────────────

function toggleDir(path: string): void {
  if (expandedDirs.value.has(path)) {
    expandedDirs.value.delete(path)
  } else {
    expandedDirs.value.add(path)
  }
}

function selectFile(path: string): void {
  selectedPath.value = path
  isDirty.value = false
  fixtureResult.value = null
}

function onSourceChange(e: Event): void {
  sourceCode.value = (e.target as HTMLTextAreaElement).value
  isDirty.value = true
}

// ── Diagnostics helpers ────────────────────────────────────────────────

function severityIcon(severity: string): string {
  switch (severity) {
    case 'error': return 'text-red-500'
    case 'warning': return 'text-yellow-500'
    default: return 'text-blue-500'
  }
}
</script>

<template>
  <div class="functions-view">
    <!-- Header -->
    <header class="functions-header">
      <div class="header-left">
        <FileCode :size="20" />
        <h1>Functions</h1>
        <span class="count" v-if="functions">{{ functions.length }}</span>
      </div>
      <div class="header-actions">
        <button class="btn btn-ghost" @click="queryClient.invalidateQueries({ queryKey: ['function-tree'] })">
          <RefreshCw :size="16" />
        </button>
        <button class="btn btn-primary" @click="showCreateDialog = true">
          <Plus :size="16" />
          New Function
        </button>
      </div>
    </header>

    <div class="functions-content">
      <!-- File tree sidebar -->
      <aside class="functions-sidebar">
        <div class="tree-container">
          <div v-if="isLoading" class="loading">
            <Loader2 :size="20" class="spin" />
            Loading...
          </div>
          <template v-else-if="fileTree">
            <div v-for="entry in fileTree" :key="entry.path">
              <div
                class="tree-item"
                :class="{ selected: selectedPath === entry.path }"
                @click="entry.type === 'dir' ? toggleDir(entry.path) : selectFile(entry.path)"
              >
                <template v-if="entry.type === 'dir'">
                  <ChevronDown v-if="expandedDirs.has(entry.path)" :size="14" />
                  <ChevronRight v-else :size="14" />
                  <FolderOpen v-if="expandedDirs.has(entry.path)" :size="14" />
                  <Folder v-else :size="14" />
                </template>
                <template v-else>
                  <span class="indent"></span>
                  <FileCode :size="14" />
                </template>
                <span class="tree-name">{{ entry.name }}</span>
              </div>
              <div v-if="entry.type === 'dir' && expandedDirs.has(entry.path) && entry.children" class="tree-children">
                <div
                  v-for="child in entry.children"
                  :key="child.path"
                  class="tree-item"
                  :class="{ selected: selectedPath === child.path }"
                  @click="selectFile(child.path)"
                >
                  <span class="indent"></span>
                  <FileCode :size="14" />
                  <span class="tree-name">{{ child.name }}</span>
                </div>
              </div>
            </div>
          </template>
          <div v-else class="empty-tree">
            <FileCode :size="32" />
            <p>No functions yet</p>
            <button class="btn btn-sm btn-primary" @click="showCreateDialog = true">
              <Plus :size="14" />
              Create first function
            </button>
          </div>
        </div>
      </aside>

      <!-- Editor panel -->
      <main class="functions-editor">
        <template v-if="selectedPath && selectedFunction">
          <!-- Editor toolbar -->
          <div class="editor-toolbar">
            <div class="toolbar-left">
              <span class="file-path">{{ selectedPath }}</span>
              <span v-if="selectedFunction.trusted" class="badge badge-success">
                <Shield :size="12" /> Trusted
              </span>
              <span v-else class="badge badge-warning">
                <ShieldOff :size="12" /> Untrusted
              </span>
              <span v-if="isDirty" class="badge badge-info">Modified</span>
            </div>
            <div class="toolbar-actions">
              <button class="btn btn-ghost btn-sm" @click="handleValidate" :disabled="validateMutation.isPending.value">
                <CheckCircle :size="14" />
                Validate
              </button>
              <button class="btn btn-ghost btn-sm" @click="handleSave" :disabled="saveMutation.isPending.value || !isDirty">
                <Loader2 v-if="saveMutation.isPending.value" :size="14" class="spin" />
                Save
              </button>
              <button class="btn btn-ghost btn-sm" @click="handleRun" :disabled="runMutation.isPending.value">
                <Play :size="14" />
                Run
              </button>
              <button
                v-if="!selectedFunction.trusted"
                class="btn btn-ghost btn-sm"
                @click="trustMutation.mutate()"
              >
                <Shield :size="14" />
                Trust
              </button>
              <button
                v-else
                class="btn btn-ghost btn-sm"
                @click="revokeTrustMutation.mutate()"
              >
                <ShieldOff :size="14" />
                Revoke
              </button>
              <button class="btn btn-ghost btn-sm btn-danger" @click="deleteMutation.mutate(selectedPath)">
                <Trash2 :size="14" />
              </button>
            </div>
          </div>

          <!-- Code editor -->
          <div class="editor-body">
            <textarea
              class="code-editor"
              :value="sourceCode"
              @input="onSourceChange"
              spellcheck="false"
              placeholder="# Write your Python function here..."
            />
          </div>

          <!-- Diagnostics -->
          <div v-if="validateMutation.data.value || selectedFunction.diagnostics.length > 0" class="diagnostics-panel">
            <div class="panel-header">
              <AlertTriangle :size="14" />
              <span>Diagnostics</span>
            </div>
            <div class="diagnostics-list">
              <div
                v-for="(diag, i) in (validateMutation.data.value?.diagnostics ?? selectedFunction.diagnostics)"
                :key="i"
                class="diagnostic-item"
                :class="severityIcon(diag.severity)"
              >
                <span class="diag-severity">{{ diag.severity }}</span>
                <span class="diag-location">Line {{ diag.line }}, Col {{ diag.column }}</span>
                <span class="diag-message">{{ diag.message }}</span>
              </div>
              <div v-if="(validateMutation.data.value?.diagnostics ?? selectedFunction.diagnostics).length === 0" class="diagnostic-ok">
                <CheckCircle :size="14" class="text-green-500" />
                No issues found
              </div>
            </div>
          </div>

          <!-- Fixture input/output -->
          <div class="fixture-panel">
            <div class="panel-header">
              <Play :size="14" />
              <span>Test Fixture</span>
            </div>
            <div class="fixture-content">
              <div class="fixture-input">
                <label>Input (JSON):</label>
                <textarea
                  v-model="fixtureInput"
                  class="fixture-textarea"
                  placeholder='{"key": "value"}'
                />
              </div>
              <div v-if="fixtureResult" class="fixture-output">
                <div class="output-header" :class="fixtureResult.success ? 'text-green-500' : 'text-red-500'">
                  {{ fixtureResult.success ? 'Success' : 'Error' }}
                  <span v-if="fixtureResult.durationMs">({{ fixtureResult.durationMs }}ms)</span>
                </div>
                <pre v-if="fixtureResult.output" class="output-body">{{ JSON.stringify(fixtureResult.output, null, 2) }}</pre>
                <pre v-if="fixtureResult.error" class="output-error">{{ fixtureResult.error }}</pre>
                <pre v-if="fixtureResult.stdout" class="output-stdout">{{ fixtureResult.stdout }}</pre>
                <pre v-if="fixtureResult.stderr" class="output-stderr">{{ fixtureResult.stderr }}</pre>
              </div>
            </div>
          </div>
        </template>

        <!-- Empty state -->
        <div v-else class="editor-empty">
          <FileCode :size="48" />
          <h2>Select a function</h2>
          <p>Choose a function from the tree to edit it, or create a new one.</p>
        </div>
      </main>
    </div>

    <!-- Create dialog -->
    <Teleport to="body">
      <div v-if="showCreateDialog" class="dialog-overlay" @click.self="showCreateDialog = false">
        <div class="dialog">
          <h2>Create Function</h2>
          <div class="dialog-field">
            <label>Name</label>
            <input v-model="newName" placeholder="my_function" autofocus />
          </div>
          <div class="dialog-field">
            <label>Source (optional)</label>
            <textarea v-model="newSource" class="code-editor" placeholder="Leave empty for template" />
          </div>
          <div class="dialog-actions">
            <button class="btn btn-ghost" @click="showCreateDialog = false">Cancel</button>
            <button class="btn btn-primary" @click="handleCreate" :disabled="!newName.trim() || createMutation.isPending.value">
              <Loader2 v-if="createMutation.isPending.value" :size="14" class="spin" />
              Create
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.functions-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.functions-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--density-space-3) var(--density-space-4);
  border-bottom: 1px solid var(--border-subtle);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
}

.header-left h1 {
  font-size: var(--density-font-lg);
  font-weight: 600;
  margin: 0;
}

.count {
  background: var(--surface-secondary);
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  color: var(--text-secondary);
}

.header-actions {
  display: flex;
  gap: var(--density-space-2);
}

.functions-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.functions-sidebar {
  width: 260px;
  border-right: 1px solid var(--border-subtle);
  overflow-y: auto;
}

.tree-container {
  padding: var(--density-space-2);
}

.tree-item {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-primary);
}

.tree-item:hover {
  background: var(--surface-hover);
}

.tree-item.selected {
  background: var(--surface-active);
  color: var(--text-accent);
}

.tree-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.indent {
  width: 14px;
  flex-shrink: 0;
}

.tree-children {
  padding-left: 16px;
}

.functions-editor {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--density-space-2) var(--density-space-3);
  border-bottom: 1px solid var(--border-subtle);
  background: var(--surface-secondary);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
}

.file-path {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.toolbar-actions {
  display: flex;
  gap: var(--density-space-1);
}

.editor-body {
  flex: 1;
  overflow: hidden;
}

.code-editor {
  width: 100%;
  height: 100%;
  min-height: 200px;
  padding: var(--density-space-3);
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  background: var(--surface-primary);
  color: var(--text-primary);
  border: none;
  resize: none;
  outline: none;
  tab-size: 4;
}

.diagnostics-panel,
.fixture-panel {
  border-top: 1px solid var(--border-subtle);
  max-height: 200px;
  overflow-y: auto;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  padding: var(--density-space-2) var(--density-space-3);
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  background: var(--surface-secondary);
  border-bottom: 1px solid var(--border-subtle);
}

.diagnostics-list {
  padding: var(--density-space-2);
}

.diagnostic-item {
  display: flex;
  align-items: baseline;
  gap: var(--density-space-2);
  padding: 4px 0;
  font-size: 12px;
  font-family: monospace;
}

.diag-severity {
  font-weight: 600;
  text-transform: uppercase;
  min-width: 60px;
}

.diag-location {
  color: var(--text-secondary);
  min-width: 120px;
}

.diag-message {
  flex: 1;
}

.diagnostic-ok {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  font-size: 12px;
  color: var(--text-success);
}

.fixture-content {
  padding: var(--density-space-2);
  display: flex;
  gap: var(--density-space-3);
}

.fixture-input {
  flex: 1;
}

.fixture-input label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  margin-bottom: 4px;
  color: var(--text-secondary);
}

.fixture-textarea {
  width: 100%;
  min-height: 60px;
  padding: 8px;
  font-family: monospace;
  font-size: 12px;
  background: var(--surface-primary);
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  resize: vertical;
}

.fixture-output {
  flex: 1;
}

.output-header {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 4px;
}

.output-body,
.output-error,
.output-stdout,
.output-stderr {
  font-family: monospace;
  font-size: 12px;
  padding: 8px;
  border-radius: 4px;
  margin: 4px 0;
  max-height: 120px;
  overflow-y: auto;
  white-space: pre-wrap;
}

.output-body {
  background: var(--surface-secondary);
  color: var(--text-primary);
}

.output-error {
  background: var(--surface-error);
  color: var(--text-error);
}

.output-stdout {
  background: var(--surface-secondary);
  color: var(--text-secondary);
}

.output-stderr {
  background: var(--surface-warning);
  color: var(--text-warning);
}

.editor-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--density-space-3);
  color: var(--text-secondary);
}

.editor-empty h2 {
  font-size: var(--density-font-lg);
  font-weight: 600;
  margin: 0;
}

.editor-empty p {
  font-size: 14px;
  margin: 0;
}

.empty-tree {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--density-space-2);
  padding: var(--density-space-4);
  color: var(--text-secondary);
  text-align: center;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
}

.badge-success {
  background: var(--surface-success);
  color: var(--text-success);
}

.badge-warning {
  background: var(--surface-warning);
  color: var(--text-warning);
}

.badge-info {
  background: var(--surface-info);
  color: var(--text-info);
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--accent-primary);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-primary-hover);
}

.btn-ghost {
  background: transparent;
  color: var(--text-primary);
}

.btn-ghost:hover:not(:disabled) {
  background: var(--surface-hover);
}

.btn-sm {
  padding: 4px 8px;
  font-size: 12px;
}

.btn-danger {
  color: var(--text-error);
}

.btn-danger:hover:not(:disabled) {
  background: var(--surface-error);
}

.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog {
  background: var(--surface-primary);
  border-radius: 12px;
  padding: var(--density-space-4);
  width: 400px;
  max-width: 90vw;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.dialog h2 {
  font-size: var(--density-font-lg);
  font-weight: 600;
  margin: 0 0 var(--density-space-3);
}

.dialog-field {
  margin-bottom: var(--density-space-3);
}

.dialog-field label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 4px;
  color: var(--text-secondary);
}

.dialog-field input,
.dialog-field textarea {
  width: 100%;
  padding: 8px 12px;
  font-size: 14px;
  background: var(--surface-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  outline: none;
}

.dialog-field input:focus,
.dialog-field textarea:focus {
  border-color: var(--accent-primary);
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--density-space-2);
  margin-top: var(--density-space-4);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.loading {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
  padding: var(--density-space-3);
  color: var(--text-secondary);
}

.text-green-500 { color: var(--text-success); }
.text-red-500 { color: var(--text-error); }
.text-yellow-500 { color: var(--text-warning); }
.text-blue-500 { color: var(--text-info); }
</style>
