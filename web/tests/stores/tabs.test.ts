/**
 * Tabs store tests.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useTabsStore } from '@/stores/tabs'
import type { Tab } from '@/stores/tabs'

function makeTab(overrides: Partial<Tab> = {}): Tab {
  return {
    id: 'test-tab-1',
    label: 'Test Tab',
    kind: 'request',
    route: { name: 'home' },
    dirty: false,
    projectId: 'proj-1',
    pinned: false,
    ...overrides,
  }
}

describe('TabsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('starts with no tabs', () => {
    const store = useTabsStore()
    expect(store.tabs).toEqual([])
    expect(store.activeTabId).toBeNull()
  })

  it('opens a tab and activates it', () => {
    const store = useTabsStore()
    const tab = makeTab()
    store.openTab(tab)
    expect(store.tabs).toHaveLength(1)
    expect(store.tabs[0]!.id).toBe('test-tab-1')
    expect(store.activeTabId).toBe('test-tab-1')
  })

  it('does not duplicate tabs when opening the same id', () => {
    const store = useTabsStore()
    store.openTab(makeTab())
    store.openTab(makeTab())
    expect(store.tabs).toHaveLength(1)
    expect(store.activeTabId).toBe('test-tab-1')
  })

  it('closes a tab', () => {
    const store = useTabsStore()
    store.openTab(makeTab({ id: 'tab-1' }))
    store.openTab(makeTab({ id: 'tab-2' }))
    store.closeTab('tab-1')
    expect(store.tabs).toHaveLength(1)
    expect(store.tabs[0]!.id).toBe('tab-2')
  })

  it('activates the next tab when closing the active tab', () => {
    const store = useTabsStore()
    store.openTab(makeTab({ id: 'tab-1' }))
    store.openTab(makeTab({ id: 'tab-2' }))
    store.openTab(makeTab({ id: 'tab-3' }))
    store.activateTab('tab-2')
    store.closeTab('tab-2')
    // Should activate tab-3 (the one after the closed tab)
    expect(store.activeTabId).toBe('tab-3')
  })

  it('activates the previous tab when closing the last tab', () => {
    const store = useTabsStore()
    store.openTab(makeTab({ id: 'tab-1' }))
    store.openTab(makeTab({ id: 'tab-2' }))
    store.closeTab('tab-2')
    expect(store.activeTabId).toBe('tab-1')
  })

  it('sets activeTabId to null when closing the last tab', () => {
    const store = useTabsStore()
    store.openTab(makeTab())
    store.closeTab('test-tab-1')
    expect(store.tabs).toHaveLength(0)
    expect(store.activeTabId).toBeNull()
  })

  it('closes all non-pinned tabs', () => {
    const store = useTabsStore()
    store.openTab(makeTab({ id: 'tab-1', pinned: false }))
    store.openTab(makeTab({ id: 'tab-2', pinned: true }))
    store.openTab(makeTab({ id: 'tab-3', pinned: false }))
    store.closeAllTabs()
    expect(store.tabs).toHaveLength(1)
    expect(store.tabs[0]!.id).toBe('tab-2')
  })

  it('closes other tabs', () => {
    const store = useTabsStore()
    store.openTab(makeTab({ id: 'tab-1' }))
    store.openTab(makeTab({ id: 'tab-2' }))
    store.openTab(makeTab({ id: 'tab-3' }))
    store.closeOtherTabs('tab-2')
    expect(store.tabs).toHaveLength(1)
    expect(store.tabs[0]!.id).toBe('tab-2')
  })

  it('marks a tab as dirty', () => {
    const store = useTabsStore()
    store.openTab(makeTab())
    store.markDirty('test-tab-1')
    expect(store.tabs[0]!.dirty).toBe(true)
  })

  it('marks a tab as clean', () => {
    const store = useTabsStore()
    store.openTab(makeTab())
    store.markDirty('test-tab-1')
    store.markClean('test-tab-1')
    expect(store.tabs[0]!.dirty).toBe(false)
  })

  it('computes dirtyTabs', () => {
    const store = useTabsStore()
    store.openTab(makeTab({ id: 'tab-1', dirty: false }))
    store.openTab(makeTab({ id: 'tab-2', dirty: true }))
    store.openTab(makeTab({ id: 'tab-3', dirty: true }))
    expect(store.dirtyTabs).toHaveLength(2)
    expect(store.hasDirtyTabs).toBe(true)
  })

  it('updates tab label', () => {
    const store = useTabsStore()
    store.openTab(makeTab())
    store.updateLabel('test-tab-1', 'Updated Label')
    expect(store.tabs[0]!.label).toBe('Updated Label')
  })

  it('returns dirty tabs for a project', () => {
    const store = useTabsStore()
    store.openTab(makeTab({ id: 'tab-1', projectId: 'proj-1', dirty: true }))
    store.openTab(makeTab({ id: 'tab-2', projectId: 'proj-2', dirty: true }))
    store.openTab(makeTab({ id: 'tab-3', projectId: 'proj-1', dirty: false }))
    const dirty = store.getDirtyTabsForProject('proj-1')
    expect(dirty).toHaveLength(1)
    expect(dirty[0]!.id).toBe('tab-1')
  })

  it('discards dirty state for a project', () => {
    const store = useTabsStore()
    store.openTab(makeTab({ id: 'tab-1', projectId: 'proj-1', dirty: true }))
    store.openTab(makeTab({ id: 'tab-2', projectId: 'proj-1', dirty: true }))
    store.discardDirtyForProject('proj-1')
    expect(store.tabs[0]!.dirty).toBe(false)
    expect(store.tabs[1]!.dirty).toBe(false)
  })

  it('returns tabs for a specific project', () => {
    const store = useTabsStore()
    store.openTab(makeTab({ id: 'tab-1', projectId: 'proj-1' }))
    store.openTab(makeTab({ id: 'tab-2', projectId: 'proj-2' }))
    store.openTab(makeTab({ id: 'tab-3', projectId: 'proj-1' }))
    const tabs = store.tabsForProject('proj-1')
    expect(tabs).toHaveLength(2)
  })

  it('returns active tab', () => {
    const store = useTabsStore()
    store.openTab(makeTab({ id: 'tab-1' }))
    store.openTab(makeTab({ id: 'tab-2' }))
    expect(store.activeTab?.id).toBe('tab-2')
  })

  it('returns undefined for active tab when no tabs', () => {
    const store = useTabsStore()
    expect(store.activeTab).toBeUndefined()
  })
})
