/**
 * ResponseViewer — displays an HTTP response with tabbed views.
 *
 * Tabs: Body, Headers, Request, Timeline.
 * Supports JSON syntax highlighting via pre/code.
 */

<script setup lang="ts">
import { ref, computed } from 'vue'
import { FileText, List, Clock, ArrowUpRight } from 'lucide-vue-next'

export interface ResponseData {
  statusCode: number
  headers: Record<string, string>
  body: string
  durationMs: number
  error?: string | null
}

const props = defineProps<{
  response: ResponseData | null
  loading?: boolean
}>()

type Tab = 'body' | 'headers' | 'timeline'

const activeTab = ref<Tab>('body')

const statusClass = computed(() => {
  if (!props.response) return ''
  const code = props.response.statusCode
  if (code >= 200 && code < 300) return 'status-success'
  if (code >= 300 && code < 400) return 'status-redirect'
  if (code >= 400 && code < 500) return 'status-client-error'
  if (code >= 500) return 'status-server-error'
  return 'status-error'
})

const statusText = computed(() => {
  if (!props.response) return ''
  const code = props.response.statusCode
  const map: Record<number, string> = {
    200: 'OK', 201: 'Created', 204: 'No Content',
    301: 'Moved', 302: 'Found', 304: 'Not Modified',
    400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden',
    404: 'Not Found', 409: 'Conflict', 422: 'Unprocessable',
    429: 'Too Many Requests', 500: 'Server Error', 502: 'Bad Gateway',
    503: 'Unavailable',
  }
  return map[code] || ''
})

const formattedBody = computed(() => {
  if (!props.response?.body) return ''
  try {
    const parsed = JSON.parse(props.response.body)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return props.response.body
  }
})

const headerEntries = computed(() => {
  if (!props.response?.headers) return []
  return Object.entries(props.response.headers).sort(([a], [b]) => a.localeCompare(b))
})

const tabs: { id: Tab; label: string; icon: typeof FileText }[] = [
  { id: 'body', label: 'Body', icon: FileText },
  { id: 'headers', label: 'Headers', icon: List },
  { id: 'timeline', label: 'Timeline', icon: Clock },
]
</script>

<template>
  <div class="response-viewer">
    <!-- Status bar -->
    <div class="response-status-bar">
      <template v-if="loading">
        <span class="status-loading">Sending...</span>
      </template>
      <template v-else-if="response">
        <span class="status-badge" :class="statusClass">
          {{ response.statusCode }} {{ statusText }}
        </span>
        <span class="status-meta">
          <Clock :size="12" />
          {{ response.durationMs }}ms
        </span>
        <span class="status-meta">
          {{ (response.body?.length || 0).toLocaleString() }} bytes
        </span>
      </template>
      <template v-else>
        <span class="status-empty">No response yet</span>
      </template>
    </div>

    <!-- Error banner -->
    <div v-if="response?.error" class="response-error">
      {{ response.error }}
    </div>

    <!-- Tabs -->
    <div class="response-tabs" role="tablist">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="response-tab"
        :class="{ active: activeTab === tab.id }"
        role="tab"
        :aria-selected="activeTab === tab.id"
        @click="activeTab = tab.id"
      >
        <component :is="tab.icon" :size="14" />
        <span>{{ tab.label }}</span>
      </button>
    </div>

    <!-- Tab content -->
    <div class="response-content">
      <!-- Body -->
      <div v-if="activeTab === 'body'" class="response-body" role="tabpanel">
        <pre v-if="formattedBody" class="body-pre"><code>{{ formattedBody }}</code></pre>
        <div v-else class="body-empty">Empty response body</div>
      </div>

      <!-- Headers -->
      <div v-if="activeTab === 'headers'" class="response-headers" role="tabpanel">
        <div v-if="headerEntries.length === 0" class="body-empty">No headers</div>
        <div
          v-for="[key, value] in headerEntries"
          :key="key"
          class="header-row"
        >
          <span class="header-key">{{ key }}</span>
          <span class="header-value">{{ value }}</span>
        </div>
      </div>

      <!-- Timeline -->
      <div v-if="activeTab === 'timeline'" class="response-timeline" role="tabpanel">
        <div class="timeline-item">
          <ArrowUpRight :size="14" class="timeline-icon" />
          <span>Request sent</span>
        </div>
        <div v-if="response" class="timeline-item">
          <Clock :size="14" class="timeline-icon" />
          <span>Response received in {{ response.durationMs }}ms</span>
        </div>
        <div v-if="response?.error" class="timeline-item error">
          <span>Error: {{ response.error }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.response-viewer {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-md);
  overflow: hidden;
  min-height: 200px;
}

/* Status bar */
.response-status-bar {
  display: flex;
  align-items: center;
  gap: var(--density-space-3);
  padding: var(--density-space-2) var(--density-space-3);
  background: var(--surface-base);
  border-bottom: 1px solid var(--surface-border-subtle);
  font-size: var(--density-font-sm);
}

.status-badge {
  font-weight: 600;
  font-family: var(--font-mono);
  font-size: var(--density-font-sm);
  padding: var(--density-space-1) var(--density-space-2);
  border-radius: var(--density-radius-sm);
}

.status-success { color: var(--semantic-success); background: rgba(34, 197, 94, 0.1); }
.status-redirect { color: var(--semantic-info); background: rgba(59, 130, 246, 0.1); }
.status-client-error { color: var(--semantic-warning); background: rgba(245, 158, 11, 0.1); }
.status-server-error { color: var(--semantic-error); background: rgba(239, 68, 68, 0.1); }
.status-error { color: var(--semantic-error); background: rgba(239, 68, 68, 0.1); }

.status-meta {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  color: var(--text-tertiary);
  font-size: var(--density-font-xs);
}

.status-loading {
  color: var(--accent-primary);
  font-style: italic;
}

.status-empty {
  color: var(--text-tertiary);
  font-style: italic;
}

/* Error banner */
.response-error {
  padding: var(--density-space-2) var(--density-space-3);
  background: rgba(239, 68, 68, 0.08);
  color: var(--semantic-error);
  font-size: var(--density-font-sm);
  border-bottom: 1px solid var(--surface-border-subtle);
}

/* Tabs */
.response-tabs {
  display: flex;
  gap: 0;
  background: var(--surface-base);
  border-bottom: 1px solid var(--surface-border-subtle);
}

.response-tab {
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

.response-tab:hover {
  color: var(--text-primary);
}

.response-tab.active {
  color: var(--accent-primary);
  border-bottom-color: var(--accent-primary);
}

/* Content */
.response-content {
  flex: 1;
  overflow: auto;
  min-height: 120px;
}

.response-body,
.response-headers,
.response-timeline {
  padding: var(--density-space-3);
}

.body-pre {
  margin: 0;
  font-family: var(--font-mono);
  font-size: var(--density-font-xs);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--text-primary);
}

.body-empty {
  color: var(--text-tertiary);
  font-style: italic;
  padding: var(--density-space-3);
  text-align: center;
}

/* Headers */
.header-row {
  display: flex;
  gap: var(--density-space-3);
  padding: var(--density-space-1) 0;
  border-bottom: 1px solid var(--surface-border-subtle);
  font-family: var(--font-mono);
  font-size: var(--density-font-xs);
}

.header-key {
  color: var(--accent-primary);
  min-width: 160px;
  flex-shrink: 0;
}

.header-value {
  color: var(--text-secondary);
  word-break: break-all;
}

/* Timeline */
.timeline-item {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
  padding: var(--density-space-2) 0;
  color: var(--text-secondary);
  font-size: var(--density-font-sm);
}

.timeline-item.error {
  color: var(--semantic-error);
}

.timeline-icon {
  color: var(--text-tertiary);
  flex-shrink: 0;
}
</style>
