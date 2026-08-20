/**
 * LogsView — application log viewer with filtering, pause, copy, and export.
 *
 * Fetches logs from the backend with periodic polling.
 * Supports level filtering, text search, pause/resume, copy to clipboard,
 * clear view, and redacted CSV export.
 */

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getGateway } from '@/gateway'
import type { LogEntry } from '@/types/api'
import {
  Search,
  Pause,
  Play,
  Trash2,
  Download,
  Copy,
  Check,
  Filter,
} from 'lucide-vue-next'

const gateway = getGateway()

// ── State ──────────────────────────────────────────────────────────────

const logs = ref<LogEntry[]>([])
const total = ref(0)
const paused = ref(false)
const loading = ref(true)
const levelFilter = ref('all')
const searchQuery = ref('')
const autoScroll = ref(true)
const copied = ref(false)
const logContainerRef = ref<HTMLElement | null>(null)

let pollTimer: ReturnType<typeof setInterval> | null = null

const levels = [
  { value: 'all', label: 'All' },
  { value: 'debug', label: 'Debug' },
  { value: 'info', label: 'Info' },
  { value: 'warning', label: 'Warning' },
  { value: 'error', label: 'Error' },
  { value: 'critical', label: 'Critical' },
]

// ── Derived ────────────────────────────────────────────────────────────

const levelColors: Record<string, string> = {
  debug: 'var(--text-tertiary)',
  info: 'var(--color-info, #3b82f6)',
  warning: 'var(--color-warning, #f59e0b)',
  error: 'var(--color-error, #ef4444)',
  critical: 'var(--color-error, #dc2626)',
}

// ── Actions ────────────────────────────────────────────────────────────

async function fetchLogs(): Promise<void> {
  try {
    const res = await gateway.logs.list({
      level: levelFilter.value !== 'all' ? levelFilter.value : undefined,
      search: searchQuery.value || undefined,
      limit: 500,
    })
    logs.value = res.items
    total.value = res.total
    paused.value = res.paused
  } catch {
    // Fetch failed — keep existing logs
  } finally {
    loading.value = false
    if (autoScroll.value) scrollToBottom()
  }
}

function startPolling(): void {
  fetchLogs()
  pollTimer = setInterval(fetchLogs, 2000)
}

function stopPolling(): void {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function togglePause(): Promise<void> {
  try {
    if (paused.value) {
      await gateway.logs.resume()
      paused.value = false
    } else {
      await gateway.logs.pause()
      paused.value = true
    }
  } catch {
    // Toggle failed
  }
}

async function clearLogs(): Promise<void> {
  try {
    await gateway.logs.clear()
    logs.value = []
    total.value = 0
  } catch {
    // Clear failed
  }
}

function copyLogs(): void {
  const text = logs.value
    .map((l) => `[${l.timestamp}] ${l.level.toUpperCase()} ${l.source}: ${l.message}`)
    .join('\n')
  navigator.clipboard.writeText(text).then(() => {
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  })
}

function exportLogs(): void {
  const url = gateway.logs.exportUrl(
    levelFilter.value !== 'all' ? levelFilter.value : undefined,
    undefined,
    searchQuery.value || undefined,
    true,
  )
  const a = document.createElement('a')
  a.href = url
  a.download = 'sclplapi-logs.csv'
  a.click()
}

function scrollToBottom(): void {
  requestAnimationFrame(() => {
    if (logContainerRef.value) {
      logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
    }
  })
}

function handleScroll(): void {
  if (!logContainerRef.value) return
  const { scrollTop, scrollHeight, clientHeight } = logContainerRef.value
  autoScroll.value = scrollHeight - scrollTop - clientHeight < 50
}

// ── Lifecycle ──────────────────────────────────────────────────────────

onMounted(startPolling)
onUnmounted(stopPolling)
</script>

<template>
  <div class="logs-view">
    <!-- Toolbar -->
    <div class="logs-toolbar">
      <div class="toolbar-left">
        <div class="level-filter" role="radiogroup" aria-label="Log level filter">
          <button
            v-for="level in levels"
            :key="level.value"
            class="level-btn"
            :class="{ active: levelFilter === level.value }"
            role="radio"
            :aria-checked="levelFilter === level.value"
            @click="levelFilter = level.value; fetchLogs()"
          >
            {{ level.label }}
          </button>
        </div>

        <div class="search-wrap">
          <Search :size="14" class="search-icon" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Filter logs..."
            class="search-input"
            @keydown.enter="fetchLogs"
          />
        </div>
      </div>

      <div class="toolbar-right">
        <span class="log-count">{{ total }} entries</span>

        <button
          class="toolbar-btn"
          :class="{ active: paused }"
          :title="paused ? 'Resume' : 'Pause'"
          @click="togglePause"
        >
          <Pause v-if="!paused" :size="14" />
          <Play v-else :size="14" />
          <span>{{ paused ? 'Resume' : 'Pause' }}</span>
        </button>

        <button class="toolbar-btn" title="Copy to clipboard" @click="copyLogs">
          <Check v-if="copied" :size="14" />
          <Copy v-else :size="14" />
          <span>{{ copied ? 'Copied' : 'Copy' }}</span>
        </button>

        <button class="toolbar-btn" title="Export as CSV (redacted)" @click="exportLogs">
          <Download :size="14" />
          <span>Export</span>
        </button>

        <button class="toolbar-btn danger" title="Clear view" @click="clearLogs">
          <Trash2 :size="14" />
          <span>Clear</span>
        </button>
      </div>
    </div>

    <!-- Paused indicator -->
    <div v-if="paused" class="paused-banner" role="status">
      <Pause :size="14" />
      <span>Log collection paused. New entries are being dropped.</span>
    </div>

    <!-- Log entries -->
    <div
      ref="logContainerRef"
      class="log-container"
      @scroll="handleScroll"
    >
      <div v-if="loading" class="log-empty">Loading logs...</div>
      <div v-else-if="logs.length === 0" class="log-empty">No log entries</div>
      <template v-else>
        <div
          v-for="(entry, idx) in logs"
          :key="idx"
          class="log-entry"
        >
          <span class="log-timestamp">{{ entry.timestamp }}</span>
          <span
            class="log-level"
            :style="{ color: levelColors[entry.level] || 'var(--text-primary)' }"
          >
            {{ entry.level.toUpperCase().padEnd(8) }}
          </span>
          <span class="log-source">{{ entry.source }}</span>
          <span class="log-message">{{ entry.message }}</span>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.logs-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 0;
  overflow: hidden;
}

/* ── Toolbar ──────────────────────────────────────────────────────── */

.logs-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--density-space-3);
  padding: var(--density-space-2) var(--density-space-3);
  border-bottom: 1px solid var(--surface-border);
  background: var(--surface-base);
  flex-shrink: 0;
  flex-wrap: wrap;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
}

.level-filter {
  display: flex;
  gap: var(--density-space-1);
}

.level-btn {
  padding: var(--density-space-1) var(--density-space-2);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--density-font-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.level-btn:hover {
  border-color: var(--accent-primary);
}

.level-btn.active {
  background: var(--accent-primary-muted);
  border-color: var(--accent-primary);
  color: var(--accent-primary);
}

.search-wrap {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  padding: 0 var(--density-space-2);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-md);
  background: var(--surface-raised);
}

.search-icon {
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.search-input {
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: var(--density-font-sm);
  padding: var(--density-space-1) 0;
  outline: none;
  width: 160px;
}

.search-input::placeholder {
  color: var(--text-disabled);
}

.toolbar-btn {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  padding: var(--density-space-1) var(--density-space-2);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--density-font-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.toolbar-btn:hover {
  border-color: var(--accent-primary);
  color: var(--text-primary);
}

.toolbar-btn.active {
  background: var(--color-warning-bg, #fef3c7);
  border-color: var(--color-warning, #f59e0b);
  color: var(--color-warning-text, #92400e);
}

.toolbar-btn.danger:hover {
  border-color: var(--color-error);
  color: var(--color-error);
}

.log-count {
  font-size: var(--density-font-xs);
  color: var(--text-tertiary);
  font-family: var(--font-mono);
}

/* ── Paused banner ────────────────────────────────────────────────── */

.paused-banner {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
  padding: var(--density-space-1) var(--density-space-3);
  background: var(--color-warning-bg, #fef3c7);
  color: var(--color-warning-text, #92400e);
  font-size: var(--density-font-xs);
  flex-shrink: 0;
}

/* ── Log container ────────────────────────────────────────────────── */

.log-container {
  flex: 1;
  overflow-y: auto;
  font-family: var(--font-mono);
  font-size: var(--density-font-xs);
  line-height: 1.6;
  padding: var(--density-space-2);
}

.log-empty {
  color: var(--text-tertiary);
  font-family: var(--font-sans);
  font-size: var(--density-font-sm);
  padding: var(--density-space-4);
  text-align: center;
}

.log-entry {
  display: flex;
  gap: var(--density-space-2);
  padding: 1px 0;
  white-space: nowrap;
}

.log-entry:hover {
  background: var(--surface-raised);
}

.log-timestamp {
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.log-level {
  flex-shrink: 0;
  font-weight: 600;
}

.log-source {
  color: var(--text-secondary);
  flex-shrink: 0;
}

.log-source::before {
  content: '[';
  color: var(--text-tertiary);
}

.log-source::after {
  content: ']';
  color: var(--text-tertiary);
}

.log-message {
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
