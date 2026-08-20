/**
 * ExplorerHost — resizable tree panel for workspace resources.
 *
 * Shows a tree of collections, workflows, monitors, etc. for the
 * active project. Supports keyboard navigation and resize handle.
 */

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useProjectStore } from '@/stores/project'
import { useTabsStore } from '@/stores/tabs'
import type { Tab } from '@/stores/tabs'
import TreeNode from './TreeNode.vue'
import { FolderOpen, Loader2 } from 'lucide-vue-next'

export interface TreeNode {
  id: string
  label: string
  kind: Tab['kind']
  icon?: typeof FolderOpen
  children?: TreeNode[]
  expandable?: boolean
  route?: string
}

const props = defineProps<{
  loading?: boolean
  nodes?: TreeNode[]
}>()

const emit = defineEmits<{
  resize: [width: number]
}>()

const projectStore = useProjectStore()
const tabsStore = useTabsStore()

const expandedIds = ref<Set<string>>(new Set())
const focusedId = ref<string | null>(null)
const panelWidth = ref(240)
const isResizing = ref(false)

function toggleExpand(id: string): void {
  if (expandedIds.value.has(id)) {
    expandedIds.value.delete(id)
  } else {
    expandedIds.value.add(id)
  }
}

function openNode(node: TreeNode): void {
  if (node.expandable) {
    toggleExpand(node.id)
    return
  }

  if (node.route) {
    tabsStore.openTab({
      id: `${node.kind}-${node.id}`,
      label: node.label,
      kind: node.kind,
      route: node.route,
      dirty: false,
      projectId: projectStore.activeProjectId ?? '',
      pinned: false,
    })
  }
}

// ── Resize handle ────────────────────────────────────────────────────

function startResize(e: MouseEvent): void {
  isResizing.value = true
  const startX = e.clientX
  const startWidth = panelWidth.value

  function onMouseMove(e: MouseEvent): void {
    const delta = e.clientX - startX
    const newWidth = Math.max(180, Math.min(480, startWidth + delta))
    panelWidth.value = newWidth
    emit('resize', newWidth)
  }

  function onMouseUp(): void {
    isResizing.value = false
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }

  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}
</script>

<template>
  <aside
    class="explorer"
    :style="{ width: `${panelWidth}px` }"
    role="tree"
    aria-label="Workspace explorer"
  >
    <div class="explorer-header">
      <span class="explorer-title">Explorer</span>
      <span class="explorer-project">{{ projectStore.activeProject?.name ?? '' }}</span>
    </div>

    <div class="explorer-content">
      <div v-if="loading" class="explorer-loading">
        <Loader2 :size="16" class="spin" />
        <span>Loading...</span>
      </div>

      <div v-else-if="!nodes || nodes.length === 0" class="explorer-empty">
        <span>No items</span>
      </div>

      <template v-else>
        <TreeNode
          v-for="node in nodes"
          :key="node.id"
          :node="node"
          :depth="0"
          :expanded-ids="expandedIds"
          :focused-id="focusedId"
          @toggle-expand="toggleExpand"
          @open-node="openNode"
          @focus="focusedId = $event"
        />
      </template>
    </div>

    <!-- Resize handle -->
    <div
      class="resize-handle"
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize explorer"
      tabindex="0"
      @mousedown="startResize"
    />
  </aside>
</template>

<style scoped>
.explorer {
  display: flex;
  flex-direction: column;
  background: var(--surface-base);
  border-right: 1px solid var(--surface-border);
  position: relative;
  min-width: 180px;
  max-width: 480px;
  overflow: hidden;
}

.explorer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--density-space-2) var(--density-space-3);
  border-bottom: 1px solid var(--surface-border-subtle);
  height: var(--density-topbar-height);
  min-height: var(--density-topbar-height);
}

.explorer-title {
  font-size: var(--density-font-sm);
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.explorer-project {
  font-size: var(--density-font-xs);
  color: var(--text-tertiary);
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.explorer-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: var(--density-space-1) 0;
}

.explorer-loading,
.explorer-empty {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
  padding: var(--density-space-3);
  color: var(--text-tertiary);
  font-size: var(--density-font-sm);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* ── Resize handle ────────────────────────────────────────────────── */

.resize-handle {
  position: absolute;
  top: 0;
  right: -2px;
  width: 4px;
  height: 100%;
  cursor: col-resize;
  z-index: 10;
  transition: background var(--transition-fast);
}

.resize-handle:hover,
.resize-handle:active {
  background: var(--accent-primary);
}
</style>
