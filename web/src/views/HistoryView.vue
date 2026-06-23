/**
 * HistoryView — request execution history.
 *
 * Shows a list of past request executions with status, duration,
 * and the ability to rerun or view details.
 */

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { getGateway } from '@/gateway'
import { useProjectStore } from '@/stores/project'
import { useTabsStore } from '@/stores/tabs'
import type { HistoryEntry } from '@/types/api'
import {
  Clock, RotateCcw, Trash2, ChevronRight, Loader2, CheckCircle,
  XCircle, AlertTriangle, Timer,
} from 'lucide-vue-next'

const router = useRouter()
const projectStore = useProjectStore()
const tabsStore = useTabsStore()
const queryClient = useQueryClient()
const gateway = getGateway()

const projectId = computed(() => projectStore.activeProjectId)

// ── Fetch history ──────────────────────────────────────────────────────

const cursor = ref<string | null>(null)

const { data: historyData, isLoading } = useQuery({
  queryKey: ['history', projectId, cursor],
  queryFn: async () => {
    // The gateway doesn't have a direct history method yet.
    // For now we use the runs gateway which lists operations.
    // TODO: Add history gateway method
    return { items: [] as HistoryEntry[], nextCursor: null as string | null, total: 0 }
  },
  enabled: computed(() => !!projectId.value),
})

const entries = computed(() => historyData.value?.items ?? [])
const nextCursor = computed(() => historyData.value?.nextCursor)
const total = computed(() => historyData.value?.total ?? 0)

// ── Clear history ──────────────────────────────────────────────────────

const clearMutation = useMutation({
  mutationFn: async () => {
    // TODO: Add clear history gateway method
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['history'] })
  },
})

// ── Rerun ──────────────────────────────────────────────────────────────

function rerun(entry: HistoryEntry): void {
  if (!entry.requestId) return
  const tabId = `request-${entry.requestId}`
  tabsStore.openTab({
    id: tabId,
    label: entry.requestName || entry.url,
    kind: 'request',
    route: `/requests/${entry.requestId}`,
    dirty: false,
    projectId: projectId.value || '',
    pinned: false,
  })
  router.push(`/requests/${entry.requestId}`)
}

// ── Status helpers ─────────────────────────────────────────────────────

function statusIcon(status: string): typeof CheckCircle {
  if (status === 'success') return CheckCircle
  if (status === 'error') return XCircle
  if (status === 'timeout') return Timer
  return AlertTriangle
}

function statusClass(status: string): string {
  if (status === 'success') return 'status-success'
  if (status === 'error') return 'status-error'
  if (status === 'timeout') return 'status-timeout'
  return 'status-other'
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatTime(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString()
  } catch {
    return ts
  }
}

function formatDate(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleDateString()
  } catch {
    return ts
  }
}

// ── Detail panel ───────────────────────────────────────────────────────

const expandedId = ref<string | null>(null)

function toggleExpand(id: string): void {
  expandedId.value = expandedId.value === id ? null : id
}

// ── Pagination ─────────────────────────────────────────────────────────

function loadMore(): void {
  if (nextCursor.value) {
    cursor.value = nextCursor.value
  }
}
</script>

<template>
  <div class="history-view">
    <div class="view-header">
      <h1>History</h1>
      <div class="header-meta">
        <span class="entry-count">{{ total }} entries</span>
        <button
          class="btn-clear"
          :disabled="entries.length === 0 || clearMutation.isPending.value"
          @click="clearMutation.mutate()"
        >
          <Trash2 :size="14" />
          <span>Clear</span>
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="view-loading">
      <Loader2 :size="20" class="spin" />
      <span>Loading history...</span>
    </div>

    <!-- Empty -->
    <div v-else-if="entries.length === 0" class="view-empty">
      <Clock :size="32" />
      <p>No history yet</p>
      <p class="empty-hint">Execute a request to see it appear here.</p>
    </div>

    <!-- History list -->
    <div v-else class="history-list">
      <div
        v-for="entry in entries"
        :key="entry.id"
        class="history-entry"
        :class="{ expanded: expandedId === entry.id }"
      >
        <div class="entry-row" @click="toggleExpand(entry.id)">
          <div class="entry-status" :class="statusClass(entry.runStatus)">
            <component :is="statusIcon(entry.runStatus)" :size="14" />
          </div>

          <div class="entry-method" :class="`method-${entry.method?.toLowerCase()}`">
            {{ entry.method }}
          </div>

          <div class="entry-info">
            <span class="entry-name">{{ entry.requestName || entry.url }}</span>
            <span class="entry-url">{{ entry.url }}</span>
          </div>

          <div class="entry-meta">
            <span v-if="entry.status" class="entry-code">{{ entry.status }}</span>
            <span class="entry-duration">{{ formatDuration(entry.duration) }}</span>
            <span class="entry-time">{{ formatTime(entry.timestamp) }}</span>
          </div>

          <ChevronRight :size="14" class="expand-icon" :class="{ rotated: expandedId === entry.id }" />
        </div>

        <!-- Expanded detail -->
        <div v-if="expandedId === entry.id" class="entry-detail">
          <div class="detail-row">
            <span class="detail-label">Date</span>
            <span class="detail-value">{{ formatDate(entry.timestamp) }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Status</span>
            <span class="detail-value">{{ entry.runStatus }} ({{ entry.status }})</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Duration</span>
            <span class="detail-value">{{ formatDuration(entry.duration) }}</span>
          </div>
          <div class="detail-actions">
            <button class="btn-rerun" @click.stop="rerun(entry)">
              <RotateCcw :size="14" />
              <span>Rerun</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Load more -->
      <div v-if="nextCursor" class="load-more">
        <button class="btn-load-more" @click="loadMore">
          Load more
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.history-view {
  display: flex;
  flex-direction: column;
  gap: var(--density-space-4);
}

.view-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

h1 {
  font-size: var(--density-font-xl);
  font-weight: 600;
}

.header-meta {
  display: flex;
  align-items: center;
  gap: var(--density-space-3);
}

.entry-count {
  font-size: var(--density-font-sm);
  color: var(--text-tertiary);
}

.btn-clear {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  padding: var(--density-space-1) var(--density-space-3);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-sm);
  background: transparent;
  color: var(--text-tertiary);
  font-size: var(--density-font-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-clear:hover:not(:disabled) {
  color: var(--semantic-error);
  border-color: var(--semantic-error);
}

.btn-clear:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Loading / Empty */
.view-loading,
.view-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--density-space-2);
  padding: var(--density-space-8);
  color: var(--text-tertiary);
}

.empty-hint {
  font-size: var(--density-font-sm);
  color: var(--text-disabled);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* History list */
.history-list {
  display: flex;
  flex-direction: column;
  gap: var(--density-space-1);
}

.history-entry {
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-md);
  overflow: hidden;
  transition: border-color var(--transition-fast);
}

.history-entry.expanded {
  border-color: var(--accent-primary);
}

.entry-row {
  display: flex;
  align-items: center;
  gap: var(--density-space-3);
  padding: var(--density-space-2) var(--density-space-3);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.entry-row:hover {
  background: var(--surface-raised);
}

.entry-status {
  flex-shrink: 0;
}

.entry-status.status-success { color: var(--semantic-success); }
.entry-status.status-error { color: var(--semantic-error); }
.entry-status.status-timeout { color: var(--semantic-warning); }
.entry-status.status-other { color: var(--text-tertiary); }

.entry-method {
  font-family: var(--font-mono);
  font-size: var(--density-font-xs);
  font-weight: 600;
  padding: var(--density-space-1) var(--density-space-2);
  border-radius: var(--density-radius-sm);
  flex-shrink: 0;
}

.method-get { color: var(--method-get); background: rgba(34, 197, 94, 0.1); }
.method-post { color: var(--method-post); background: rgba(234, 179, 8, 0.1); }
.method-put { color: var(--method-put); background: rgba(59, 130, 246, 0.1); }
.method-patch { color: var(--method-patch); background: rgba(168, 85, 247, 0.1); }
.method-delete { color: var(--method-delete); background: rgba(239, 68, 68, 0.1); }

.entry-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.entry-name {
  font-size: var(--density-font-sm);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.entry-url {
  font-size: var(--density-font-xs);
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.entry-meta {
  display: flex;
  align-items: center;
  gap: var(--density-space-3);
  flex-shrink: 0;
}

.entry-code {
  font-family: var(--font-mono);
  font-size: var(--density-font-xs);
  color: var(--text-secondary);
}

.entry-duration {
  font-size: var(--density-font-xs);
  color: var(--text-tertiary);
}

.entry-time {
  font-size: var(--density-font-xs);
  color: var(--text-disabled);
}

.expand-icon {
  flex-shrink: 0;
  color: var(--text-tertiary);
  transition: transform var(--transition-fast);
}

.expand-icon.rotated {
  transform: rotate(90deg);
}

/* Detail */
.entry-detail {
  padding: var(--density-space-3);
  border-top: 1px solid var(--surface-border-subtle);
  background: var(--surface-base);
  display: flex;
  flex-direction: column;
  gap: var(--density-space-2);
}

.detail-row {
  display: flex;
  gap: var(--density-space-3);
  font-size: var(--density-font-sm);
}

.detail-label {
  color: var(--text-tertiary);
  min-width: 80px;
}

.detail-value {
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.detail-actions {
  margin-top: var(--density-space-2);
}

.btn-rerun {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  padding: var(--density-space-1) var(--density-space-3);
  border: 1px solid var(--accent-primary);
  border-radius: var(--density-radius-sm);
  background: transparent;
  color: var(--accent-primary);
  font-size: var(--density-font-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-rerun:hover {
  background: var(--accent-primary);
  color: white;
}

/* Load more */
.load-more {
  display: flex;
  justify-content: center;
  padding: var(--density-space-3);
}

.btn-load-more {
  padding: var(--density-space-2) var(--density-space-4);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--density-font-sm);
  cursor: pointer;
  transition: border-color var(--transition-fast);
}

.btn-load-more:hover {
  border-color: var(--accent-primary);
  color: var(--accent-primary);
}
</style>
