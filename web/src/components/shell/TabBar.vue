/**
 * TabBar — editor tab strip with dirty indicators and close buttons.
 *
 * Supports keyboard navigation (arrow keys), context menu (close others,
 * close all), and dirty-draft indicators (dot icon).
 */

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useTabsStore } from '@/stores/tabs'
import type { Tab } from '@/stores/tabs'
import {
  X,
  Circle,
  Home,
  FolderOpen,
  GitBranch,
  Radio,
  History,
  Settings,
  Puzzle,
} from 'lucide-vue-next'

const router = useRouter()
const tabsStore = useTabsStore()

const tabListRef = ref<HTMLElement | null>(null)
const contextMenu = ref<{ x: number; y: number; tabId: string } | null>(null)

const iconMap: Record<Tab['kind'], typeof Home> = {
  request: FolderOpen,
  workflow: GitBranch,
  monitor: Radio,
  function: Puzzle,
  environment: Settings,
  settings: Settings,
  home: Home,
}

function activateTab(tab: Tab): void {
  tabsStore.activateTab(tab.id)
  router.push(tab.route)
}

function closeTab(e: MouseEvent, id: string): void {
  e.stopPropagation()
  tabsStore.closeTab(id)
}

function showContextMenu(e: MouseEvent, tabId: string): void {
  e.preventDefault()
  contextMenu.value = { x: e.clientX, y: e.clientY, tabId }
}

function closeContextMenu(): void {
  contextMenu.value = null
}

function closeOthers(): void {
  if (contextMenu.value) {
    tabsStore.closeOtherTabs(contextMenu.value.tabId)
    closeContextMenu()
  }
}

function closeAll(): void {
  tabsStore.closeAllTabs()
  closeContextMenu()
}

function closeToRight(): void {
  if (!contextMenu.value) return
  const idx = tabsStore.tabs.findIndex((t) => t.id === contextMenu.value!.tabId)
  if (idx === -1) return
  const toClose = tabsStore.tabs.slice(idx + 1).filter((t) => !t.pinned)
  for (const tab of toClose) {
    tabsStore.closeTab(tab.id)
  }
  closeContextMenu()
}

function handleTabKeydown(e: KeyboardEvent, tab: Tab): void {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    activateTab(tab)
  } else if (e.key === 'Delete' || e.key === 'Backspace') {
    e.preventDefault()
    tabsStore.closeTab(tab.id)
  }
}

// Navigate tabs with Ctrl+Tab / Ctrl+Shift+Tab
function handleGlobalKeydown(e: KeyboardEvent): void {
  if (e.ctrlKey && e.key === 'Tab') {
    e.preventDefault()
    const tabs = tabsStore.tabs
    if (tabs.length < 2) return
    const currentIdx = tabs.findIndex((t) => t.id === tabsStore.activeTabId)
    const nextIdx = e.shiftKey
      ? (currentIdx - 1 + tabs.length) % tabs.length
      : (currentIdx + 1) % tabs.length
    const nextTab = tabs[nextIdx]
    if (nextTab) activateTab(nextTab)
  }
}

// Close context menu on outside click
function handleDocumentClick(): void {
  closeContextMenu()
}

import { onMounted, onUnmounted } from 'vue'

onMounted(() => {
  document.addEventListener('keydown', handleGlobalKeydown)
  document.addEventListener('click', handleDocumentClick)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleGlobalKeydown)
  document.removeEventListener('click', handleDocumentClick)
})
</script>

<template>
  <div
    v-if="tabsStore.tabs.length > 0"
    ref="tabListRef"
    class="tab-bar"
    role="tablist"
    aria-label="Open editors"
  >
    <div class="tab-scroll">
      <button
        v-for="tab in tabsStore.tabs"
        :key="tab.id"
        class="tab"
        :class="{ active: tab.id === tabsStore.activeTabId, dirty: tab.dirty }"
        role="tab"
        :aria-selected="tab.id === tabsStore.activeTabId"
        :tabindex="tab.id === tabsStore.activeTabId ? 0 : -1"
        @click="activateTab(tab)"
        @keydown="handleTabKeydown($event, tab)"
        @contextmenu="showContextMenu($event, tab.id)"
      >
        <component :is="iconMap[tab.kind]" :size="12" class="tab-icon" />
        <span class="tab-label">{{ tab.label }}</span>
        <Circle v-if="tab.dirty" :size="8" class="dirty-indicator" aria-label="Unsaved changes" />
        <button
          class="tab-close"
          aria-label="Close tab"
          @click="closeTab($event, tab.id)"
        >
          <X :size="12" />
        </button>
      </button>
    </div>

    <!-- Context menu -->
    <div
      v-if="contextMenu"
      class="context-menu"
      :style="{ left: `${contextMenu.x}px`, top: `${contextMenu.y}px` }"
      role="menu"
    >
      <button role="menuitem" @click="closeOthers">Close Others</button>
      <button role="menuitem" @click="closeToRight">Close to the Right</button>
      <div class="context-separator" />
      <button role="menuitem" @click="closeAll">Close All</button>
    </div>
  </div>
</template>

<style scoped>
.tab-bar {
  display: flex;
  align-items: stretch;
  height: var(--density-tab-height);
  min-height: var(--density-tab-height);
  background: var(--surface-ground);
  border-bottom: 1px solid var(--surface-border);
  overflow-x: auto;
  overflow-y: hidden;
}

.tab-scroll {
  display: flex;
  align-items: stretch;
  min-width: 0;
}

.tab {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  padding: 0 var(--density-space-3);
  border: none;
  border-right: 1px solid var(--surface-border-subtle);
  background: var(--surface-ground);
  color: var(--text-tertiary);
  font-size: var(--density-font-sm);
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--transition-fast), color var(--transition-fast);
  min-width: 0;
}

.tab:hover {
  background: var(--surface-raised);
  color: var(--text-secondary);
}

.tab.active {
  background: var(--surface-base);
  color: var(--text-primary);
  border-bottom: 2px solid var(--accent-primary);
}

.tab:focus-visible {
  box-shadow: inset var(--focus-ring);
}

.tab-icon {
  flex-shrink: 0;
}

.tab-label {
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 140px;
}

.dirty-indicator {
  flex-shrink: 0;
  color: var(--accent-secondary);
}

.tab-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: none;
  border-radius: var(--density-radius-sm);
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  opacity: 0;
  transition: opacity var(--transition-fast), background var(--transition-fast);
  flex-shrink: 0;
}

.tab:hover .tab-close,
.tab.active .tab-close {
  opacity: 1;
}

.tab-close:hover {
  background: var(--surface-overlay);
  color: var(--color-error);
}

/* ── Context menu ─────────────────────────────────────────────────── */

.context-menu {
  position: fixed;
  min-width: 160px;
  background: var(--surface-overlay);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-md);
  box-shadow: var(--shadow-lg);
  padding: var(--density-space-1);
  z-index: 1000;
}

.context-menu button {
  display: block;
  width: 100%;
  padding: var(--density-space-2) var(--density-space-3);
  border: none;
  border-radius: var(--density-radius-sm);
  background: transparent;
  color: var(--text-primary);
  font-size: var(--density-font-sm);
  text-align: left;
  cursor: pointer;
}

.context-menu button:hover {
  background: var(--surface-raised);
}

.context-separator {
  height: 1px;
  background: var(--surface-border);
  margin: var(--density-space-1) 0;
}
</style>
