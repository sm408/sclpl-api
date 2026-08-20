/**
 * RequestEditorView — full-featured HTTP request editor.
 *
 * Features: method selector, URL bar with variable highlighting,
 * tabbed editor (Params, Headers, Body, Auth), send/cancel,
 * response viewer, save/discard.
 */

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { getGateway } from '@/gateway'
import { useProjectStore } from '@/stores/project'
import { useTabsStore } from '@/stores/tabs'
import KeyValueEditor from '@/components/common/KeyValueEditor.vue'
import ResponseViewer from '@/components/common/ResponseViewer.vue'
import type { ResponseData } from '@/components/common/ResponseViewer.vue'
import type { KeyValueEntry } from '@/components/common/KeyValueEditor.vue'
import type { RequestDef, HttpMethod, RequestParam } from '@/types/api'
import {
  Send, Save, X, ChevronDown, Loader2, AlertCircle,
  FileText, List, Code, Shield,
} from 'lucide-vue-next'

const route = useRoute()
const projectStore = useProjectStore()
const tabsStore = useTabsStore()
const queryClient = useQueryClient()
const gateway = getGateway()

const requestId = computed(() => route.params.requestId as string)
const isNew = computed(() => requestId.value === 'new')

// ── Form state ─────────────────────────────────────────────────────────

const formName = ref('')
const formMethod = ref<HttpMethod>('GET')
const formUrl = ref('')
const formHeaders = ref<KeyValueEntry[]>([])
const formParams = ref<KeyValueEntry[]>([])
const formBody = ref('')
const formBodyType = ref<string>('none')
const formAuthType = ref<string>('none')
const formCollectionId = ref<string | undefined>(undefined)

// Track the original loaded state for dirty detection
const originalState = ref<string>('')

const isDirty = computed(() => {
  const current = JSON.stringify({
    name: formName.value,
    method: formMethod.value,
    url: formUrl.value,
    headers: formHeaders.value,
    params: formParams.value,
    body: formBody.value,
    bodyType: formBodyType.value,
  })
  return current !== originalState.value
})

// Update tab dirty state
watch(isDirty, (dirty) => {
  const tabId = `request-${requestId.value}`
  if (tabsStore.tabs.some((t) => t.id === tabId)) {
    tabsStore.markDirty(tabId, dirty)
  }
})

// ── Load request ───────────────────────────────────────────────────────

const { data: request, isLoading } = useQuery({
  queryKey: ['request', requestId],
  queryFn: () => gateway.requests.get(projectStore.activeProjectId!, requestId.value),
  enabled: computed(() => !isNew.value && !!projectStore.activeProjectId),
})

watch(request, (req) => {
  if (!req) return
  formName.value = req.name
  formMethod.value = req.method
  formUrl.value = req.url
  formHeaders.value = (req.headers || []).map((h: any) => ({
    key: h.key || '',
    value: h.value || '',
    enabled: h.enabled !== false,
  }))
  formParams.value = (req.params || []).map((p: any) => ({
    key: p.key || '',
    value: p.value || '',
    enabled: p.enabled !== false,
  }))
  formBody.value = req.body?.content || req.body || ''
  formBodyType.value = req.body?.contentType || 'none'
  formCollectionId.value = req.collectionId

  // Snapshot for dirty detection
  snapshotOriginal()
}, { immediate: true })

function snapshotOriginal(): void {
  originalState.value = JSON.stringify({
    name: formName.value,
    method: formMethod.value,
    url: formUrl.value,
    headers: formHeaders.value,
    params: formParams.value,
    body: formBody.value,
    bodyType: formBodyType.value,
  })
}

// ── Methods ────────────────────────────────────────────────────────────

const httpMethods: HttpMethod[] = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
const methodColors: Record<string, string> = {
  GET: 'var(--method-get)',
  POST: 'var(--method-post)',
  PUT: 'var(--method-put)',
  PATCH: 'var(--method-patch)',
  DELETE: 'var(--method-delete)',
  HEAD: 'var(--method-head)',
  OPTIONS: 'var(--method-options)',
}

// ── Variable highlighting ──────────────────────────────────────────────

const variablePattern = /\{\{([\w.]+)\}\}/g

function highlightVariables(text: string): string {
  return text.replace(
    variablePattern,
    '<span class="var-highlight">{{$1}}</span>',
  )
}

// ── Tabs ───────────────────────────────────────────────────────────────

type EditorTab = 'params' | 'headers' | 'body' | 'auth'

const activeEditorTab = ref<EditorTab>('params')

const editorTabs: { id: EditorTab; label: string; icon: typeof FileText }[] = [
  { id: 'params', label: 'Params', icon: List },
  { id: 'headers', label: 'Headers', icon: List },
  { id: 'body', label: 'Body', icon: Code },
  { id: 'auth', label: 'Auth', icon: Shield },
]

// ── Execute ────────────────────────────────────────────────────────────

const response = ref<ResponseData | null>(null)
const isExecuting = ref(false)
const abortController = ref<AbortController | null>(null)

async function handleSend(): Promise<void> {
  if (!projectStore.activeProjectId) return

  // If new and unsaved, save first
  if (isNew.value && !requestId.value.startsWith('new-')) {
    await handleSave()
  }

  isExecuting.value = true
  response.value = null
  abortController.value = new AbortController()

  try {
    const result = await gateway.requests.execute(
      projectStore.activeProjectId,
      requestId.value,
      {},
      { signal: abortController.value.signal },
    )
    response.value = {
      statusCode: result.statusCode,
      headers: result.headers || {},
      body: typeof result.body === 'string' ? result.body : JSON.stringify(result.body),
      durationMs: result.duration,
      error: result.error,
    }
  } catch (err: any) {
    if (err?.code === 'ABORTED') {
      response.value = {
        statusCode: 0,
        headers: {},
        body: '',
        durationMs: 0,
        error: 'Request cancelled',
      }
    } else {
      response.value = {
        statusCode: 0,
        headers: {},
        body: '',
        durationMs: 0,
        error: err?.message || 'Request failed',
      }
    }
  } finally {
    isExecuting.value = false
    abortController.value = null
  }
}

function handleCancel(): void {
  abortController.value?.abort()
}

// ── Save ───────────────────────────────────────────────────────────────

const saveMutation = useMutation({
  mutationFn: async () => {
    if (!projectStore.activeProjectId) throw new Error('No active project')

    const data = {
      name: formName.value || 'Untitled Request',
      method: formMethod.value,
      url: formUrl.value,
      headers: formHeaders.value,
      queryParams: formParams.value,
      body: formBody.value || undefined,
      bodyType: formBodyType.value !== 'none' ? formBodyType.value : undefined,
      collectionId: formCollectionId.value,
    }

    if (isNew.value || requestId.value.startsWith('new-')) {
      return gateway.requests.create(projectStore.activeProjectId, data)
    } else {
      return gateway.requests.update(projectStore.activeProjectId, requestId.value, data)
    }
  },
  onSuccess: (saved) => {
    queryClient.invalidateQueries({ queryKey: ['requests'] })
    snapshotOriginal()
    tabsStore.markClean(`request-${requestId.value}`)

    // If this was a new request, update the URL
    if (isNew.value && saved?.id) {
      tabsStore.updateLabel(`request-${requestId.value}`, saved.name)
    }
  },
})

async function handleSave(): Promise<void> {
  await saveMutation.mutateAsync()
}

// ── Keyboard shortcut ──────────────────────────────────────────────────

function handleKeydown(e: KeyboardEvent): void {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    e.preventDefault()
    handleSave()
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    handleSend()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
  abortController.value?.abort()
})

// ── Body types ─────────────────────────────────────────────────────────

const bodyTypes = [
  { value: 'none', label: 'None' },
  { value: 'json', label: 'JSON' },
  { value: 'form-data', label: 'Form Data' },
  { value: 'x-www-form-urlencoded', label: 'URL Encoded' },
  { value: 'raw', label: 'Raw' },
]
</script>

<template>
  <div class="request-editor">
    <!-- Header: name + actions -->
    <div class="editor-header">
      <input
        v-model="formName"
        class="request-name"
        type="text"
        placeholder="Untitled Request"
      />
      <div class="header-actions">
        <button
          class="btn-save"
          :disabled="!isDirty || saveMutation.isPending.value"
          @click="handleSave"
        >
          <Save :size="14" />
          <span>Save</span>
        </button>
      </div>
    </div>

    <!-- URL bar -->
    <div class="url-bar">
      <div class="method-selector">
        <select v-model="formMethod" class="method-select" :style="{ color: methodColors[formMethod] }">
          <option v-for="m in httpMethods" :key="m" :value="m">{{ m }}</option>
        </select>
        <ChevronDown :size="12" class="method-chevron" />
      </div>

      <div class="url-input-wrap">
        <input
          v-model="formUrl"
          class="url-input"
          type="text"
          placeholder="Enter request URL (e.g., https://api.example.com/users)"
          spellcheck="false"
        />
      </div>

      <button
        class="btn-send"
        :class="{ executing: isExecuting }"
        :disabled="!formUrl || !projectStore.activeProjectId"
        @click="isExecuting ? handleCancel() : handleSend()"
      >
        <Loader2 v-if="isExecuting" :size="14" class="spin" />
        <Send v-else :size="14" />
        <span>{{ isExecuting ? 'Cancel' : 'Send' }}</span>
      </button>
    </div>

    <!-- Editor tabs -->
    <div class="editor-tabs" role="tablist">
      <button
        v-for="tab in editorTabs"
        :key="tab.id"
        class="editor-tab"
        :class="{ active: activeEditorTab === tab.id }"
        role="tab"
        :aria-selected="activeEditorTab === tab.id"
        @click="activeEditorTab = tab.id"
      >
        <component :is="tab.icon" :size="14" />
        <span>{{ tab.label }}</span>
        <span v-if="tab.id === 'params' && formParams.length" class="tab-count">{{ formParams.length }}</span>
        <span v-if="tab.id === 'headers' && formHeaders.length" class="tab-count">{{ formHeaders.length }}</span>
      </button>
    </div>

    <!-- Tab content -->
    <div class="editor-panel">
      <!-- Params -->
      <div v-if="activeEditorTab === 'params'" class="tab-content" role="tabpanel">
        <KeyValueEditor
          v-model="formParams"
          key-label="Parameter"
          value-label="Value"
          placeholder="Add query parameter..."
        />
      </div>

      <!-- Headers -->
      <div v-if="activeEditorTab === 'headers'" class="tab-content" role="tabpanel">
        <KeyValueEditor
          v-model="formHeaders"
          key-label="Header"
          value-label="Value"
          placeholder="Add header..."
        />
      </div>

      <!-- Body -->
      <div v-if="activeEditorTab === 'body'" class="tab-content" role="tabpanel">
        <div class="body-type-bar">
          <label class="body-type-label">Body type:</label>
          <div class="body-type-options">
            <button
              v-for="bt in bodyTypes"
              :key="bt.value"
              class="body-type-btn"
              :class="{ active: formBodyType === bt.value }"
              @click="formBodyType = bt.value"
            >
              {{ bt.label }}
            </button>
          </div>
        </div>
        <div v-if="formBodyType !== 'none'" class="body-editor">
          <textarea
            v-model="formBody"
            class="body-textarea"
            placeholder="Enter request body..."
            spellcheck="false"
          />
        </div>
        <div v-else class="body-none">
          This request does not have a body.
        </div>
      </div>

      <!-- Auth -->
      <div v-if="activeEditorTab === 'auth'" class="tab-content" role="tabpanel">
        <div class="auth-panel">
          <label class="auth-label">Auth Type</label>
          <select v-model="formAuthType" class="auth-select">
            <option value="none">No Auth</option>
            <option value="bearer">Bearer Token</option>
            <option value="basic">Basic Auth</option>
            <option value="api_key">API Key</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Response viewer -->
    <div class="response-section">
      <ResponseViewer
        :response="response"
        :loading="isExecuting"
      />
    </div>

    <!-- Status messages -->
    <div v-if="saveMutation.isError.value" class="error-banner">
      <AlertCircle :size="14" />
      <span>{{ saveMutation.error.value?.message || 'Save failed' }}</span>
    </div>
  </div>
</template>

<style scoped>
.request-editor {
  display: flex;
  flex-direction: column;
  gap: 0;
  height: 100%;
  min-height: 0;
}

/* Header */
.editor-header {
  display: flex;
  align-items: center;
  gap: var(--density-space-3);
  padding: var(--density-space-2) var(--density-space-3);
  border-bottom: 1px solid var(--surface-border-subtle);
}

.request-name {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: var(--density-font-lg);
  font-weight: 600;
  outline: none;
  padding: var(--density-space-1) 0;
}

.request-name::placeholder {
  color: var(--text-disabled);
}

.header-actions {
  display: flex;
  gap: var(--density-space-2);
}

.btn-save {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  padding: var(--density-space-1) var(--density-space-3);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-sm);
  background: var(--surface-raised);
  color: var(--text-secondary);
  font-size: var(--density-font-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-save:hover:not(:disabled) {
  border-color: var(--accent-primary);
  color: var(--accent-primary);
}

.btn-save:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* URL bar */
.url-bar {
  display: flex;
  align-items: center;
  gap: 0;
  padding: var(--density-space-2) var(--density-space-3);
  border-bottom: 1px solid var(--surface-border);
}

.method-selector {
  position: relative;
  display: flex;
  align-items: center;
}

.method-select {
  appearance: none;
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-sm) 0 0 var(--density-radius-sm);
  background: var(--surface-raised);
  font-family: var(--font-mono);
  font-size: var(--density-font-sm);
  font-weight: 600;
  padding: var(--density-space-2) var(--density-space-4) var(--density-space-2) var(--density-space-2);
  cursor: pointer;
  outline: none;
}

.method-chevron {
  position: absolute;
  right: 6px;
  pointer-events: none;
  color: var(--text-tertiary);
}

.url-input-wrap {
  flex: 1;
  position: relative;
}

.url-input {
  width: 100%;
  border: 1px solid var(--surface-border);
  border-left: none;
  border-right: none;
  background: var(--surface-base);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: var(--density-font-sm);
  padding: var(--density-space-2) var(--density-space-3);
  outline: none;
}

.url-input:focus {
  background: var(--surface-ground);
}

.url-input::placeholder {
  color: var(--text-disabled);
}

.btn-send {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  padding: var(--density-space-2) var(--density-space-4);
  border: none;
  border-radius: 0 var(--density-radius-sm) var(--density-radius-sm) 0;
  background: var(--accent-primary);
  color: white;
  font-size: var(--density-font-sm);
  font-weight: 600;
  cursor: pointer;
  transition: opacity var(--transition-fast);
  white-space: nowrap;
}

.btn-send:hover:not(:disabled) {
  opacity: 0.9;
}

.btn-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-send.executing {
  background: var(--semantic-error);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Editor tabs */
.editor-tabs {
  display: flex;
  gap: 0;
  background: var(--surface-base);
  border-bottom: 1px solid var(--surface-border-subtle);
}

.editor-tab {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  padding: var(--density-space-2) var(--density-space-3);
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--text-tertiary);
  font-size: var(--density-font-sm);
  cursor: pointer;
  transition: color var(--transition-fast), border-color var(--transition-fast);
}

.editor-tab:hover {
  color: var(--text-primary);
}

.editor-tab.active {
  color: var(--accent-primary);
  border-bottom-color: var(--accent-primary);
}

.tab-count {
  background: var(--surface-raised);
  color: var(--text-tertiary);
  font-size: var(--density-font-xs);
  padding: 0 var(--density-space-1);
  border-radius: var(--density-radius-full);
  min-width: 16px;
  text-align: center;
}

/* Tab content */
.editor-panel {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.tab-content {
  padding: var(--density-space-3);
}

/* Body */
.body-type-bar {
  display: flex;
  align-items: center;
  gap: var(--density-space-3);
  margin-bottom: var(--density-space-3);
}

.body-type-label {
  font-size: var(--density-font-sm);
  color: var(--text-secondary);
}

.body-type-options {
  display: flex;
  gap: var(--density-space-1);
}

.body-type-btn {
  padding: var(--density-space-1) var(--density-space-2);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-sm);
  background: transparent;
  color: var(--text-tertiary);
  font-size: var(--density-font-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.body-type-btn:hover {
  border-color: var(--accent-primary);
  color: var(--text-primary);
}

.body-type-btn.active {
  background: var(--accent-primary-muted);
  border-color: var(--accent-primary);
  color: var(--accent-primary);
}

.body-textarea {
  width: 100%;
  min-height: 200px;
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-sm);
  background: var(--surface-base);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: var(--density-font-sm);
  padding: var(--density-space-3);
  outline: none;
  resize: vertical;
}

.body-textarea:focus {
  border-color: var(--accent-primary);
}

.body-none {
  color: var(--text-tertiary);
  font-style: italic;
  padding: var(--density-space-4);
  text-align: center;
}

/* Auth */
.auth-panel {
  display: flex;
  flex-direction: column;
  gap: var(--density-space-2);
  max-width: 300px;
}

.auth-label {
  font-size: var(--density-font-sm);
  color: var(--text-secondary);
}

.auth-select {
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-sm);
  background: var(--surface-base);
  color: var(--text-primary);
  font-size: var(--density-font-sm);
  padding: var(--density-space-2);
  outline: none;
}

.auth-select:focus {
  border-color: var(--accent-primary);
}

/* Response section */
.response-section {
  flex-shrink: 0;
  max-height: 40vh;
  overflow: auto;
  border-top: 1px solid var(--surface-border);
}

/* Error banner */
.error-banner {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
  padding: var(--density-space-2) var(--density-space-3);
  background: rgba(239, 68, 68, 0.08);
  color: var(--semantic-error);
  font-size: var(--density-font-sm);
  border-top: 1px solid var(--surface-border-subtle);
}

/* Variable highlighting (applied via v-html) */
:deep(.var-highlight) {
  color: var(--accent-secondary);
  background: rgba(6, 182, 212, 0.1);
  border-radius: 2px;
  padding: 0 2px;
  font-weight: 500;
}
</style>
