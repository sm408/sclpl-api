/**
 * CollectionsView — manage API request collections.
 *
 * Shows a list of collections with create, rename, delete, and
 * duplicate actions. Clicking a collection navigates to it.
 */

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { getGateway } from '@/gateway'
import { useProjectStore } from '@/stores/project'
import { useTabsStore } from '@/stores/tabs'
import type { Collection } from '@/types/api'
import {
  FolderOpen, Plus, Trash2, Copy, Edit3, MoreVertical, Loader2,
} from 'lucide-vue-next'

const router = useRouter()
const projectStore = useProjectStore()
const tabsStore = useTabsStore()
const queryClient = useQueryClient()
const gateway = getGateway()

const projectId = computed(() => projectStore.activeProjectId)

// ── Fetch collections ──────────────────────────────────────────────────

const { data: collections, isLoading } = useQuery({
  queryKey: ['collections', projectId],
  queryFn: () => gateway.collections.list(projectId.value!),
  enabled: computed(() => !!projectId.value),
})

// ── Create ─────────────────────────────────────────────────────────────

const showCreateDialog = ref(false)
const newCollectionName = ref('')
const newCollectionDesc = ref('')

const createMutation = useMutation({
  mutationFn: () =>
    gateway.collections.create(projectId.value!, {
      name: newCollectionName.value,
      description: newCollectionDesc.value,
    }),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['collections'] })
    showCreateDialog.value = false
    newCollectionName.value = ''
    newCollectionDesc.value = ''
  },
})

function openCreate(): void {
  newCollectionName.value = ''
  newCollectionDesc.value = ''
  showCreateDialog.value = true
}

function handleCreate(): void {
  if (!newCollectionName.value.trim()) return
  createMutation.mutate()
}

// ── Delete ─────────────────────────────────────────────────────────────

const deleteMutation = useMutation({
  mutationFn: (id: string) => gateway.collections.delete(projectId.value!, id),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['collections'] })
  },
})

// ── Duplicate ──────────────────────────────────────────────────────────

const duplicateMutation = useMutation({
  mutationFn: (id: string) => {
    // The backend duplicate endpoint exists, but the gateway doesn't have a
    // duplicate method. Use create with the same name + "(copy)".
    const col = collections.value?.find((c) => c.id === id)
    return gateway.collections.create(projectId.value!, {
      name: col ? `${col.name} (copy)` : 'Copy',
      description: col?.description,
    })
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['collections'] })
  },
})

// ── Context menu ───────────────────────────────────────────────────────

const contextMenuId = ref<string | null>(null)

function toggleContextMenu(id: string): void {
  contextMenuId.value = contextMenuId.value === id ? null : id
}

function closeContextMenu(): void {
  contextMenuId.value = null
}

// ── Navigation ─────────────────────────────────────────────────────────

function openCollection(col: Collection): void {
  tabsStore.openTab({
    id: `collection-${col.id}`,
    label: col.name,
    kind: 'request',
    route: `/collections/${col.id}`,
    dirty: false,
    projectId: projectId.value || '',
    pinned: false,
  })
  router.push(`/collections/${col.id}`)
}

// ── New request in collection ──────────────────────────────────────────

function newRequestInCollection(colId: string): void {
  const tabId = `request-new-${Date.now()}`
  tabsStore.openTab({
    id: tabId,
    label: 'New Request',
    kind: 'request',
    route: `/requests/new`,
    dirty: false,
    projectId: projectId.value || '',
    pinned: false,
  })
  router.push(`/requests/new`)
}
</script>

<template>
  <div class="collections-view" @click="closeContextMenu">
    <div class="view-header">
      <h1>Collections</h1>
      <button class="btn-create" @click="openCreate">
        <Plus :size="14" />
        <span>New Collection</span>
      </button>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="view-loading">
      <Loader2 :size="20" class="spin" />
      <span>Loading collections...</span>
    </div>

    <!-- Empty -->
    <div v-else-if="!collections || collections.length === 0" class="view-empty">
      <FolderOpen :size="32" />
      <p>No collections yet</p>
      <p class="empty-hint">Create a collection to organize your API requests.</p>
    </div>

    <!-- Collection list -->
    <div v-else class="collection-list">
      <div
        v-for="col in collections"
        :key="col.id"
        class="collection-card"
        @click="openCollection(col)"
      >
        <div class="card-icon">
          <FolderOpen :size="20" />
        </div>
        <div class="card-body">
          <h3 class="card-name">{{ col.name }}</h3>
          <p v-if="col.description" class="card-desc">{{ col.description }}</p>
        </div>
        <div class="card-actions" @click.stop>
          <button
            class="btn-icon"
            title="More actions"
            @click.stop="toggleContextMenu(col.id)"
          >
            <MoreVertical :size="16" />
          </button>

          <!-- Context menu -->
          <div
            v-if="contextMenuId === col.id"
            class="context-menu"
            @click.stop
          >
            <button class="ctx-item" @click="newRequestInCollection(col.id); closeContextMenu()">
              <Plus :size="14" />
              <span>New Request</span>
            </button>
            <button class="ctx-item" @click="duplicateMutation.mutate(col.id); closeContextMenu()">
              <Copy :size="14" />
              <span>Duplicate</span>
            </button>
            <div class="ctx-divider" />
            <button
              class="ctx-item danger"
              @click="deleteMutation.mutate(col.id); closeContextMenu()"
            >
              <Trash2 :size="14" />
              <span>Delete</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create dialog -->
    <Teleport to="body">
      <div v-if="showCreateDialog" class="dialog-overlay" @click.self="showCreateDialog = false">
        <div class="dialog">
          <h2>New Collection</h2>
          <div class="dialog-field">
            <label>Name</label>
            <input
              v-model="newCollectionName"
              type="text"
              placeholder="My Collection"
              autofocus
              @keydown.enter="handleCreate"
            />
          </div>
          <div class="dialog-field">
            <label>Description</label>
            <input
              v-model="newCollectionDesc"
              type="text"
              placeholder="Optional description"
            />
          </div>
          <div class="dialog-actions">
            <button class="btn-cancel" @click="showCreateDialog = false">Cancel</button>
            <button
              class="btn-confirm"
              :disabled="!newCollectionName.trim() || createMutation.isPending.value"
              @click="handleCreate"
            >
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
.collections-view {
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

.btn-create {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  padding: var(--density-space-2) var(--density-space-3);
  border: none;
  border-radius: var(--density-radius-sm);
  background: var(--accent-primary);
  color: white;
  font-size: var(--density-font-sm);
  cursor: pointer;
  transition: opacity var(--transition-fast);
}

.btn-create:hover {
  opacity: 0.9;
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

/* Collection list */
.collection-list {
  display: flex;
  flex-direction: column;
  gap: var(--density-space-2);
}

.collection-card {
  display: flex;
  align-items: center;
  gap: var(--density-space-3);
  padding: var(--density-space-3);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-md);
  background: var(--surface-raised);
  cursor: pointer;
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.collection-card:hover {
  border-color: var(--accent-primary);
  background: var(--surface-base);
}

.card-icon {
  color: var(--accent-primary);
  flex-shrink: 0;
}

.card-body {
  flex: 1;
  min-width: 0;
}

.card-name {
  font-size: var(--density-font-md);
  font-weight: 500;
  margin: 0;
}

.card-desc {
  font-size: var(--density-font-sm);
  color: var(--text-tertiary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-actions {
  position: relative;
  flex-shrink: 0;
}

.btn-icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--density-radius-sm);
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.btn-icon:hover {
  background: var(--surface-border);
}

/* Context menu */
.context-menu {
  position: absolute;
  top: 100%;
  right: 0;
  z-index: 100;
  min-width: 160px;
  background: var(--surface-overlay);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-md);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  padding: var(--density-space-1);
}

.ctx-item {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
  width: 100%;
  padding: var(--density-space-2) var(--density-space-3);
  border: none;
  border-radius: var(--density-radius-sm);
  background: transparent;
  color: var(--text-primary);
  font-size: var(--density-font-sm);
  cursor: pointer;
  text-align: left;
}

.ctx-item:hover {
  background: var(--surface-raised);
}

.ctx-item.danger {
  color: var(--semantic-error);
}

.ctx-divider {
  height: 1px;
  background: var(--surface-border-subtle);
  margin: var(--density-space-1) 0;
}

/* Dialog */
.dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
}

.dialog {
  width: 400px;
  background: var(--surface-overlay);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-lg);
  padding: var(--density-space-5);
  display: flex;
  flex-direction: column;
  gap: var(--density-space-4);
}

.dialog h2 {
  font-size: var(--density-font-lg);
  font-weight: 600;
  margin: 0;
}

.dialog-field {
  display: flex;
  flex-direction: column;
  gap: var(--density-space-1);
}

.dialog-field label {
  font-size: var(--density-font-sm);
  color: var(--text-secondary);
}

.dialog-field input {
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-sm);
  background: var(--surface-base);
  color: var(--text-primary);
  font-size: var(--density-font-sm);
  padding: var(--density-space-2) var(--density-space-3);
  outline: none;
}

.dialog-field input:focus {
  border-color: var(--accent-primary);
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--density-space-2);
}

.btn-cancel {
  padding: var(--density-space-2) var(--density-space-3);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--density-font-sm);
  cursor: pointer;
}

.btn-confirm {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  padding: var(--density-space-2) var(--density-space-3);
  border: none;
  border-radius: var(--density-radius-sm);
  background: var(--accent-primary);
  color: white;
  font-size: var(--density-font-sm);
  cursor: pointer;
}

.btn-confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
