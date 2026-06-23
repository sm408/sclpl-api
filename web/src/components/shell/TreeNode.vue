/**
 * TreeNode — recursive tree node for the workspace explorer.
 *
 * Renders a single tree item with expand/collapse, icon, and label.
 * Recursively renders children when expanded. Supports keyboard navigation.
 */

<script setup lang="ts">
import { computed } from 'vue'
import { ChevronRight, ChevronDown, FolderOpen, FileCode, GitBranch, Radio, Puzzle } from 'lucide-vue-next'
import type { Tab } from '@/stores/tabs'
import type { TreeNode as TreeNodeData } from './ExplorerHost.vue'

const props = defineProps<{
  node: TreeNodeData
  depth: number
  expandedIds: Set<string>
  focusedId: string | null
}>()

const emit = defineEmits<{
  toggleExpand: [id: string]
  openNode: [node: TreeNodeData]
  focus: [id: string]
}>()

const iconMap: Record<Tab['kind'], typeof FolderOpen> = {
  request: FileCode,
  workflow: GitBranch,
  monitor: Radio,
  function: Puzzle,
  environment: FolderOpen,
  settings: FolderOpen,
  home: FolderOpen,
}

const isExpanded = computed(() => props.expandedIds.has(props.node.id))

const paddingStyle = computed(() => ({
  paddingLeft: `calc(var(--density-space-2) + var(--density-explorer-indent) * ${props.depth})`,
}))

function handleClick(): void {
  emit('openNode', props.node)
}

function handleKeydown(e: KeyboardEvent): void {
  switch (e.key) {
    case 'Enter':
    case ' ':
      e.preventDefault()
      emit('openNode', props.node)
      break
    case 'ArrowRight':
      if (props.node.expandable && !isExpanded.value) {
        e.preventDefault()
        emit('toggleExpand', props.node.id)
      }
      break
    case 'ArrowLeft':
      if (props.node.expandable && isExpanded.value) {
        e.preventDefault()
        emit('toggleExpand', props.node.id)
      }
      break
  }
}

function handleFocus(): void {
  emit('focus', props.node.id)
}
</script>

<template>
  <div class="tree-node">
    <button
      class="node-row"
      :class="{
        expanded: isExpanded,
        focused: focusedId === node.id,
      }"
      role="treeitem"
      :aria-expanded="node.expandable ? isExpanded : undefined"
      :aria-selected="focusedId === node.id"
      :style="paddingStyle"
      @click="handleClick"
      @keydown="handleKeydown"
      @focus="handleFocus"
    >
      <ChevronDown
        v-if="node.expandable && isExpanded"
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

    <div
      v-if="node.children && isExpanded"
      class="node-children"
      role="group"
    >
      <TreeNode
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :depth="depth + 1"
        :expanded-ids="expandedIds"
        :focused-id="focusedId"
        @toggle-expand="emit('toggleExpand', $event)"
        @open-node="emit('openNode', $event)"
        @focus="emit('focus', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
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
</style>
