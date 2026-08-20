/**
 * PluginsView — manage plugins and extensions.
 *
 * Shows a list of plugins with scaffold, enable/disable, reload,
 * manifest editing, diagnostics, and export.
 */

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { getGateway } from '@/gateway'
import { useProjectStore } from '@/stores/project'
import type { PluginDetail, PluginDiagnostics, FileTreeEntry } from '@/types/api'
import {
  Puzzle, Plus, Trash2, Power, PowerOff, RefreshCw, Download, Settings,
  Loader2, ChevronRight, ChevronDown, Folder, FolderOpen, FileCode,
  CheckCircle, AlertTriangle, Shield, Eye, EyeOff,
} from 'lucide-vue-next'

const router = useRouter()
const projectStore = useProjectStore()
const queryClient = useQueryClient()
const gateway = getGateway()

const projectId = computed(() => projectStore.activeProjectId)

// ── State ──────────────────────────────────────────────────────────────

const selectedPlugin = ref<string | null>(null)
const showCreateDialog = ref(false)
const newName = ref('')
const newDesc = ref('')
const expandedSections = ref<Set<string>>(new Set(['info', 'diagnostics']))
const showVariables = ref(false)

// ── Fetch plugins list ─────────────────────────────────────────────────

const { data: plugins, isLoading } = useQuery({
  queryKey: ['plugins', projectId],
  queryFn: () => gateway.plugins.list(projectId.value!),
  enabled: computed(() => !!projectId.value),
})

// ── Fetch selected plugin detail ───────────────────────────────────────

const { data: pluginDetail, isLoading: isLoadingDetail } = useQuery({
  queryKey: ['plugin-detail', projectId, selectedPlugin],
  queryFn: () => gateway.plugins.get(projectId.value!, selectedPlugin.value!),
  enabled: computed(() => !!projectId.value && !!selectedPlugin.value),
})

// ── Fetch diagnostics ──────────────────────────────────────────────────

const { data: diagnostics } = useQuery({
  queryKey: ['plugin-diagnostics', projectId, selectedPlugin],
  queryFn: () => gateway.plugins.getDiagnostics(projectId.value!, selectedPlugin.value!),
  enabled: computed(() => !!projectId.value && !!selectedPlugin.value),
})

// ── Scaffold ───────────────────────────────────────────────────────────

const scaffoldMutation = useMutation({
  mutationFn: () =>
    gateway.plugins.scaffold(projectId.value!, newName.value, newDesc.value),
  onSuccess: (plugin) => {
    queryClient.invalidateQueries({ queryKey: ['plugins'] })
    showCreateDialog.value = false
    newName.value = ''
    newDesc.value = ''
    selectedPlugin.value = plugin.name
  },
})

function handleScaffold(): void {
  if (!newName.value.trim()) return
  scaffoldMutation.mutate()
}

// ── Enable/Disable ─────────────────────────────────────────────────────

const enableMutation = useMutation({
  mutationFn: () => gateway.plugins.enable(projectId.value!, selectedPlugin.value!),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['plugins'] })
    queryClient.invalidateQueries({ queryKey: ['plugin-detail'] })
  },
})

const disableMutation = useMutation({
  mutationFn: () => gateway.plugins.disable(projectId.value!, selectedPlugin.value!),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['plugins'] })
    queryClient.invalidateQueries({ queryKey: ['plugin-detail'] })
  },
})

// ── Reload ─────────────────────────────────────────────────────────────

const reloadMutation = useMutation({
  mutationFn: () => gateway.plugins.reload(projectId.value!),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['plugins'] })
    queryClient.invalidateQueries({ queryKey: ['plugin-detail'] })
  },
})

// ── Export ──────────────────────────────────────────────────────────────

const exportMutation = useMutation({
  mutationFn: async () => {
    const blob = await gateway.plugins.export(projectId.value!, selectedPlugin.value!)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${selectedPlugin.value}.zip`
    a.click()
    URL.revokeObjectURL(url)
  },
})

// ── Helpers ────────────────────────────────────────────────────────────

function selectPlugin(name: string): void {
  selectedPlugin.value = name
}

function toggleSection(section: string): void {
  if (expandedSections.value.has(section)) {
    expandedSections.value.delete(section)
  } else {
    expandedSections.value.add(section)
  }
}

function statusColor(status: string): string {
  switch (status) {
    case 'active': return 'text-green-500'
    case 'loaded': return 'text-blue-500'
    case 'error': return 'text-red-500'
    default: return 'text-gray-500'
  }
}

function statusIcon(status: string): string {
  switch (status) {
    case 'active': return 'badge-success'
    case 'loaded': return 'badge-info'
    case 'error': return 'badge-error'
    default: return 'badge-secondary'
  }
}
</script>

<template>
  <div class="plugins-view">
    <!-- Header -->
    <header class="plugins-header">
      <div class="header-left">
        <Puzzle :size="20" />
        <h1>Plugins</h1>
        <span class="count" v-if="plugins">{{ plugins.length }}</span>
      </div>
      <div class="header-actions">
        <button class="btn btn-ghost" @click="reloadMutation.mutate()" :disabled="reloadMutation.isPending.value">
          <Loader2 v-if="reloadMutation.isPending.value" :size="16" class="spin" />
          <RefreshCw v-else :size="16" />
          Reload
        </button>
        <button class="btn btn-primary" @click="showCreateDialog = true">
          <Plus :size="16" />
          Scaffold Plugin
        </button>
      </div>
    </header>

    <div class="plugins-content">
      <!-- Plugin list sidebar -->
      <aside class="plugins-sidebar">
        <div class="plugin-list">
          <div v-if="isLoading" class="loading">
            <Loader2 :size="20" class="spin" />
            Loading...
          </div>
          <template v-else-if="plugins">
            <div
              v-for="plugin in plugins"
              :key="plugin.name"
              class="plugin-item"
              :class="{ selected: selectedPlugin === plugin.name }"
              @click="selectPlugin(plugin.name)"
            >
              <div class="plugin-item-header">
                <Puzzle :size="14" :class="statusColor(plugin.status)" />
                <span class="plugin-name">{{ plugin.name }}</span>
                <span class="badge" :class="statusIcon(plugin.status)">{{ plugin.status }}</span>
              </div>
              <div class="plugin-item-meta">
                v{{ plugin.version }}
                <span v-if="plugin.functionCount > 0">{{ plugin.functionCount }} fn</span>
              </div>
            </div>
          </template>
          <div v-else class="empty-list">
            <Puzzle :size="32" />
            <p>No plugins yet</p>
            <button class="btn btn-sm btn-primary" @click="showCreateDialog = true">
              <Plus :size="14" />
              Scaffold first plugin
            </button>
          </div>
        </div>
      </aside>

      <!-- Detail panel -->
      <main class="plugins-detail">
        <template v-if="selectedPlugin && pluginDetail">
          <!-- Plugin toolbar -->
          <div class="detail-toolbar">
            <div class="toolbar-left">
              <Puzzle :size="18" :class="statusColor(pluginDetail.status)" />
              <h2>{{ pluginDetail.name }}</h2>
              <span class="badge" :class="statusIcon(pluginDetail.status)">{{ pluginDetail.status }}</span>
              <span class="version">v{{ pluginDetail.version }}</span>
            </div>
            <div class="toolbar-actions">
              <button
                v-if="pluginDetail.status !== 'active'"
                class="btn btn-ghost btn-sm"
                @click="enableMutation.mutate()"
                :disabled="enableMutation.isPending.value"
              >
                <Power :size="14" />
                Enable
              </button>
              <button
                v-else
                class="btn btn-ghost btn-sm"
                @click="disableMutation.mutate()"
                :disabled="disableMutation.isPending.value"
              >
                <PowerOff :size="14" />
                Disable
              </button>
              <button class="btn btn-ghost btn-sm" @click="exportMutation.mutate()" :disabled="exportMutation.isPending.value">
                <Download :size="14" />
                Export
              </button>
            </div>
          </div>

          <div class="detail-body">
            <!-- Info section -->
            <section class="detail-section">
              <div class="section-header" @click="toggleSection('info')">
                <ChevronDown v-if="expandedSections.has('info')" :size="14" />
                <ChevronRight v-else :size="14" />
                <span>Plugin Info</span>
              </div>
              <div v-if="expandedSections.has('info')" class="section-body">
                <div class="info-grid">
                  <div class="info-item">
                    <span class="info-label">Description</span>
                    <span class="info-value">{{ pluginDetail.description || 'No description' }}</span>
                  </div>
                  <div class="info-item">
                    <span class="info-label">Author</span>
                    <span class="info-value">{{ pluginDetail.author || 'Unknown' }}</span>
                  </div>
                  <div class="info-item">
                    <span class="info-label">Category</span>
                    <span class="info-value">{{ pluginDetail.category || 'Uncategorized' }}</span>
                  </div>
                  <div class="info-item">
                    <span class="info-label">Functions</span>
                    <span class="info-value">{{ pluginDetail.functionCount }}</span>
                  </div>
                  <div class="info-item">
                    <span class="info-label">Workflows</span>
                    <span class="info-value">{{ pluginDetail.workflowCount }}</span>
                  </div>
                  <div v-if="pluginDetail.dependencies.length > 0" class="info-item">
                    <span class="info-label">Dependencies</span>
                    <span class="info-value">{{ pluginDetail.dependencies.join(', ') }}</span>
                  </div>
                </div>
                <div v-if="pluginDetail.error" class="error-box">
                  <AlertTriangle :size="14" />
                  <span>{{ pluginDetail.error }}</span>
                </div>
              </div>
            </section>

            <!-- Diagnostics section (secrets excluded) -->
            <section class="detail-section">
              <div class="section-header" @click="toggleSection('diagnostics')">
                <ChevronDown v-if="expandedSections.has('diagnostics')" :size="14" />
                <ChevronRight v-else :size="14" />
                <span>Diagnostics</span>
                <span class="badge badge-secondary">Secrets excluded</span>
              </div>
              <div v-if="expandedSections.has('diagnostics') && diagnostics" class="section-body">
                <div class="diagnostics-grid">
                  <div class="diag-item">
                    <span class="diag-label">Status</span>
                    <span class="diag-value" :class="statusColor(diagnostics.status)">{{ diagnostics.status }}</span>
                  </div>
                  <div class="diag-item">
                    <span class="diag-label">Functions</span>
                    <span class="diag-value">{{ diagnostics.functionCount }}</span>
                  </div>
                  <div class="diag-item">
                    <span class="diag-label">Workflows</span>
                    <span class="diag-value">{{ diagnostics.workflowCount }}</span>
                  </div>
                  <div v-if="diagnostics.variableNames.length > 0" class="diag-item">
                    <span class="diag-label">Variables</span>
                    <span class="diag-value">
                      <span v-for="name in diagnostics.variableNames" :key="name" class="var-chip">
                        <Shield :size="10" />
                        {{ name }}
                      </span>
                    </span>
                  </div>
                  <div v-if="diagnostics.error" class="diag-item error">
                    <span class="diag-label">Error</span>
                    <span class="diag-value">{{ diagnostics.error }}</span>
                  </div>
                </div>
              </div>
            </section>
          </div>
        </template>

        <!-- Empty state -->
        <div v-else class="detail-empty">
          <Puzzle :size="48" />
          <h2>Select a plugin</h2>
          <p>Choose a plugin from the list to view its details and manage it.</p>
        </div>
      </main>
    </div>

    <!-- Create dialog -->
    <Teleport to="body">
      <div v-if="showCreateDialog" class="dialog-overlay" @click.self="showCreateDialog = false">
        <div class="dialog">
          <h2>Scaffold Plugin</h2>
          <div class="dialog-field">
            <label>Name</label>
            <input v-model="newName" placeholder="my_plugin" autofocus />
          </div>
          <div class="dialog-field">
            <label>Description</label>
            <input v-model="newDesc" placeholder="What does this plugin do?" />
          </div>
          <div class="dialog-actions">
            <button class="btn btn-ghost" @click="showCreateDialog = false">Cancel</button>
            <button class="btn btn-primary" @click="handleScaffold" :disabled="!newName.trim() || scaffoldMutation.isPending.value">
              <Loader2 v-if="scaffoldMutation.isPending.value" :size="14" class="spin" />
              Scaffold
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.plugins-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.plugins-header {
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

.plugins-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.plugins-sidebar {
  width: 280px;
  border-right: 1px solid var(--border-subtle);
  overflow-y: auto;
}

.plugin-list {
  padding: var(--density-space-2);
}

.plugin-item {
  padding: var(--density-space-2) var(--density-space-3);
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 2px;
}

.plugin-item:hover {
  background: var(--surface-hover);
}

.plugin-item.selected {
  background: var(--surface-active);
}

.plugin-item-header {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
}

.plugin-name {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.plugin-item-meta {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
  padding-left: 22px;
  display: flex;
  gap: var(--density-space-2);
}

.plugins-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--density-space-3) var(--density-space-4);
  border-bottom: 1px solid var(--border-subtle);
  background: var(--surface-secondary);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
}

.toolbar-left h2 {
  font-size: var(--density-font-lg);
  font-weight: 600;
  margin: 0;
}

.version {
  font-size: 12px;
  color: var(--text-secondary);
}

.toolbar-actions {
  display: flex;
  gap: var(--density-space-1);
}

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--density-space-3);
}

.detail-section {
  margin-bottom: var(--density-space-3);
}

.section-header {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  padding: var(--density-space-2);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  cursor: pointer;
  border-radius: 4px;
}

.section-header:hover {
  background: var(--surface-hover);
}

.section-body {
  padding: var(--density-space-2) var(--density-space-3);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--density-space-3);
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.info-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.info-value {
  font-size: 13px;
  color: var(--text-primary);
}

.error-box {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
  padding: var(--density-space-2);
  background: var(--surface-error);
  color: var(--text-error);
  border-radius: 6px;
  font-size: 13px;
  margin-top: var(--density-space-2);
}

.diagnostics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: var(--density-space-3);
}

.diag-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.diag-item.error {
  grid-column: 1 / -1;
}

.diag-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.diag-value {
  font-size: 13px;
  color: var(--text-primary);
}

.var-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: var(--surface-secondary);
  border-radius: 12px;
  font-size: 11px;
  margin-right: 4px;
  margin-bottom: 4px;
}

.detail-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--density-space-3);
  color: var(--text-secondary);
}

.detail-empty h2 {
  font-size: var(--density-font-lg);
  font-weight: 600;
  margin: 0;
}

.detail-empty p {
  font-size: 14px;
  margin: 0;
}

.empty-list {
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

.badge-info {
  background: var(--surface-info);
  color: var(--text-info);
}

.badge-error {
  background: var(--surface-error);
  color: var(--text-error);
}

.badge-secondary {
  background: var(--surface-secondary);
  color: var(--text-secondary);
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

.dialog-field input {
  width: 100%;
  padding: 8px 12px;
  font-size: 14px;
  background: var(--surface-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  outline: none;
}

.dialog-field input:focus {
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
.text-blue-500 { color: var(--text-info); }
.text-gray-500 { color: var(--text-secondary); }
</style>
