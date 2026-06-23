/**
 * Tabs store — manages the editor tab bar.
 *
 * Each tab represents an open resource (request, workflow, etc.) with
 * a stable route. Dirty (unsaved) state is tracked per-tab. Tabs are
 * persisted to localStorage for session restoration.
 */

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { RouteLocationRaw } from 'vue-router'

export interface Tab {
  /** Unique tab identifier (usually resource type + id). */
  id: string
  /** Display label shown in the tab bar. */
  label: string
  /** Resource type for icon selection. */
  kind: 'request' | 'workflow' | 'monitor' | 'function' | 'environment' | 'settings' | 'home'
  /** Route this tab navigates to. */
  route: RouteLocationRaw
  /** Whether this tab has unsaved changes. */
  dirty: boolean
  /** Associated project ID (for filtering on project switch). */
  projectId: string
  /** Whether this tab is pinned (cannot be closed by close-all). */
  pinned: boolean
}

const STORAGE_KEY = 'sclplapi:tabs'

function readPersistedTabs(): Tab[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (t): t is Tab =>
        typeof t === 'object' &&
        t !== null &&
        'id' in t &&
        'label' in t &&
        'route' in t,
    )
  } catch {
    return []
  }
}

export const useTabsStore = defineStore('tabs', () => {
  // ── State ──────────────────────────────────────────────────────────────

  const tabs = ref<Tab[]>(readPersistedTabs())
  const activeTabId = ref<string | null>(tabs.value[0]?.id ?? null)

  // ── Derived ────────────────────────────────────────────────────────────

  const activeTab = computed<Tab | undefined>(() =>
    tabs.value.find((t) => t.id === activeTabId.value),
  )

  const dirtyTabs = computed<Tab[]>(() => tabs.value.filter((t) => t.dirty))

  const hasDirtyTabs = computed<boolean>(() => dirtyTabs.value.length > 0)

  const tabsForProject = (projectId: string): Tab[] =>
    tabs.value.filter((t) => t.projectId === projectId)

  // ── Actions ────────────────────────────────────────────────────────────

  function openTab(tab: Tab): void {
    const existing = tabs.value.find((t) => t.id === tab.id)
    if (existing) {
      // Already open — just activate it
      activeTabId.value = tab.id
      return
    }
    tabs.value.push(tab)
    activeTabId.value = tab.id
  }

  function closeTab(id: string): void {
    const idx = tabs.value.findIndex((t) => t.id === id)
    if (idx === -1) return

    tabs.value.splice(idx, 1)

    // If we closed the active tab, activate the nearest neighbor
    if (activeTabId.value === id) {
      if (tabs.value.length === 0) {
        activeTabId.value = null
      } else {
        const newIdx = Math.min(idx, tabs.value.length - 1)
        activeTabId.value = tabs.value[newIdx]!.id
      }
    }
  }

  function closeAllTabs(projectId?: string): void {
    const toClose = projectId
      ? tabs.value.filter((t) => t.projectId === projectId && !t.pinned)
      : tabs.value.filter((t) => !t.pinned)

    for (const tab of toClose) {
      closeTab(tab.id)
    }
  }

  function closeOtherTabs(keepId: string): void {
    tabs.value = tabs.value.filter((t) => t.id === keepId || t.pinned)
    if (!tabs.value.some((t) => t.id === activeTabId.value)) {
      activeTabId.value = tabs.value[0]?.id ?? null
    }
  }

  function activateTab(id: string): void {
    if (tabs.value.some((t) => t.id === id)) {
      activeTabId.value = id
    }
  }

  function markDirty(id: string, dirty = true): void {
    const tab = tabs.value.find((t) => t.id === id)
    if (tab) tab.dirty = dirty
  }

  function markClean(id: string): void {
    markDirty(id, false)
  }

  function updateLabel(id: string, label: string): void {
    const tab = tabs.value.find((t) => t.id === id)
    if (tab) tab.label = label
  }

  // ── Persistence ────────────────────────────────────────────────────────

  function persist(): void {
    try {
      // Don't persist dirty state — tabs are clean on restore
      const serializable = tabs.value.map((t) => ({ ...t, dirty: false }))
      localStorage.setItem(STORAGE_KEY, JSON.stringify(serializable))
    } catch {
      // localStorage may be unavailable
    }
  }

  // Auto-persist on change
  watch(tabs, persist, { deep: true })

  // ── Dirty-tab review ───────────────────────────────────────────────────

  /** Returns dirty tabs for a given project, used before project switch. */
  function getDirtyTabsForProject(projectId: string): Tab[] {
    return tabs.value.filter((t) => t.projectId === projectId && t.dirty)
  }

  /** Discard all dirty state for a project (used after user confirms abandon). */
  function discardDirtyForProject(projectId: string): void {
    for (const tab of tabs.value) {
      if (tab.projectId === projectId) {
        tab.dirty = false
      }
    }
  }

  return {
    // State
    tabs,
    activeTabId,
    // Derived
    activeTab,
    dirtyTabs,
    hasDirtyTabs,
    // Actions
    openTab,
    closeTab,
    closeAllTabs,
    closeOtherTabs,
    activateTab,
    markDirty,
    markClean,
    updateLabel,
    getDirtyTabsForProject,
    discardDirtyForProject,
    tabsForProject,
    persist,
  }
})
