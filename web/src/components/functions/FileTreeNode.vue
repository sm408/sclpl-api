/**
 * FileTreeNode — recursive tree node for the function file tree.
 *
 * Renders a single tree entry (file or directory). If the entry is a
 * directory and is expanded, recursively renders children.
 */

<script setup lang="ts">
import { computed } from 'vue'
import {
  ChevronRight, ChevronDown, Folder, FolderOpen, FileCode,
} from 'lucide-vue-next'
import type { FileTreeEntry } from '@/types/api'

const props = defineProps<{
  entry: FileTreeEntry
  depth: number
  expandedDirs: Set<string>
  selectedPath: string | null
}>()

const emit = defineEmits<{
  toggleDir: [path: string]
  selectFile: [path: string]
}>()

const isDir = computed(() => props.entry.type === 'dir')
const isExpanded = computed(() => props.expandedDirs.has(props.entry.path))

const indentStyle = computed(() => ({
  paddingLeft: `${props.depth * 16 + 8}px`,
}))

function handleClick(): void {
  if (isDir.value) {
    emit('toggleDir', props.entry.path)
  } else {
    emit('selectFile', props.entry.path)
  }
}
</script>

<template>
  <div class="file-tree-node">
    <div
      class="tree-item"
      :class="{ selected: selectedPath === entry.path }"
      :style="indentStyle"
      @click="handleClick"
    >
      <template v-if="isDir">
        <ChevronDown v-if="isExpanded" :size="14" />
        <ChevronRight v-else :size="14" />
        <FolderOpen v-if="isExpanded" :size="14" />
        <Folder v-else :size="14" />
      </template>
      <template v-else>
        <span class="indent"></span>
        <FileCode :size="14" />
      </template>
      <span class="tree-name">{{ entry.name }}</span>
    </div>

    <div v-if="isDir && isExpanded && entry.children" class="tree-children">
      <FileTreeNode
        v-for="child in entry.children"
        :key="child.path"
        :entry="child"
        :depth="depth + 1"
        :expanded-dirs="expandedDirs"
        :selected-path="selectedPath"
        @toggle-dir="emit('toggleDir', $event)"
        @select-file="emit('selectFile', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
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
</style>
