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
import {
  ChevronRight,
  ChevronDown,
  FolderOpen,
  GitBranch,
  Radio,
  Puzzle,
  FileCode,
  Loader2,
} from 'lucide-vue-next'

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

const iconMap: Record<Tab['kind'], typeof FolderOpen> = {
  request: FileCode,
  workflow: GitBranch,
  monitor: Radio,
  function: Puzzle,
  environment: FolderOpen,
  settings: FolderOpen,
  home: FolderOpen,
}

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

function isExpanded(id: string): boolean {
  return expandedIds.value.has(id)
}

function handleNodeKeydown(e: KeyboardEvent, node: TreeNode): void {
  switch (e.key) {
    case 'Enter':
    case ' ':
      e.preventDefault()
      openNode(node)
      break
    case 'ArrowRight':
      if (node.expandable && !isExpanded(node.id)) {
        e.preventDefault()
        expandedIds.value.add(node.id)
      }
      break
    case 'ArrowLeft':
      if (node.expandable && isExpanded(node.id)) {
        e.preventDefault()
        expandedIds.value.delete(node.id)
      }
      break
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
        <div
          v-for="node in nodes"
          :key="node.id"
          class="tree-node"
        >
          <button
            class="node-row"
            :class="{
              expanded: isExpanded(node.id),
              focused: focusedId === node.id,
            }"
            role="treeitem"
            :aria-expanded="node.expandable ? isExpanded(node.id) : undefined"
            :aria-selected="focusedId === node.id"
            :style="{ paddingLeft: 'var(--density-space-2)' }"
            @click="openNode(node)"
            @keydown="handleNodeKeydown($event, node)"
            @focus="focusedId = node.id"
          >
            <ChevronDown
              v-if="node.expandable && isExpanded(node.id)"
              :size="14"
              class="expand-icon"
            />
            <ChevronRight
              v-else-if="node.expandable"
              :size="14"
              class="expand-icon"
            />
            <span v-else class="expand-icon-spacer" />

            <component
              :is="node.icon ?? iconMap[node.kind]"
              :size="14"
              class="node-icon"
            />
            <span class="node-label">{{ node.label }}</span>
          </button>

          <!-- Children -->
          <div
            v-if="node.children && isExpanded(node.id)"
            class="node-children"
            role="group"
          >
            <div
              v-for="child in node.children"
              :key="child.id"
              class="tree-node"
            >
              <button
                class="node-row child"
                role="treeitem"
                :style="{ paddingLeft: `calc(var(--density-space-2) + var(--density-explorer-indent))` }"
                @click="openNode(child)"
                @keydown="handleNodeKeydown($event, child)"
                @focus="focusedId = child.id"
              >
                <ChevronDown
                  v-if="child.expandable && isExpanded(child.id)"
                  :size="14"
                  class="expand-icon"
                />
                <ChevronRight
                  v-else-if="child.expandable"
                  :size="14"
                  class="expand-icon"
                />
                <span v-else class="expand-icon-spacer" />

                <component
                  :is="child.icon ?? iconMap[child.kind]"
                  :size="14"
                  class="node-icon"
                />
                <span class="node-label">{{ child.label }}</span>
              </button>

              <!-- Level 3 children -->
              <div
                v-if="child.children && isExpanded(child.id)"
                class="node-children"
                role="group"
              >
                <button
                  v-for="grandchild in child.children"
                  :key="grandchild.id"
                  class="node-row grandchild"
                  role="treeitem"
                  :style="{ paddingLeft: `calc(var(--density-space-2) + var(--density-explorer-indent) * 2)` }"
                  @click="openNode(grandchild)"
                  @keydown="handleNodeKeydown($event, grandchild)"
                  @focus="focusedId = grandchild.id"
                >
                  <span class="expand-icon-spacer" />
                  <component
                    :is="grandchild.icon ?? iconMap[grandchild.kind]"
                    :size="14"
                    class="node-icon"
                  />
                  <span class="node-label">{{ grandchild.label }}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
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

/* ── Tree nodes ───────────────────────────────────────────────────── */

.node-row {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  width: 100%;
  padding: var(--density-space-1) var(--density-space-2);
  border: none;
  border-radius: 0;
  background: transparent;
  color: var(--text-primary);
  font-size: var(--density-font-sm);
  cursor: pointer;
  text-align: left;
  transition: background var(--transition-fast);
}

.node-row:hover {
  background: var(--surface-raised);
}

.node-row:focus-visible {
  box-shadow: inset var(--focus-ring);
  outline: none;
}

.node-row.focused {
  background: var(--surface-raised);
}

.expand-icon {
  flex-shrink: 0;
  color: var(--text-tertiary);
}

.expand-icon-spacer {
  width: 14px;
  flex-shrink: 0;
}

.node-icon {
  flex-shrink: 0;
  color: var(--text-secondary);
}

.node-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.node-children {
  /* Indentation is handled via padding on child rows */
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
