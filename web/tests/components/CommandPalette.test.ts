/**
 * CommandPalette component tests.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import CommandPalette from '@/components/shell/CommandPalette.vue'
import { useCommandsStore } from '@/stores/commands'

describe('CommandPalette', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    // Clean up teleported elements
    document.body.innerHTML = ''
  })

  it('renders nothing when closed', () => {
    const wrapper = mount(CommandPalette)
    expect(document.querySelector('.palette-backdrop')).toBeNull()
    wrapper.unmount()
  })

  it('renders when open', async () => {
    const store = useCommandsStore()
    store.register({
      id: 'test.cmd',
      label: 'Test Command',
      execute: vi.fn(),
    })

    const wrapper = mount(CommandPalette)
    store.open()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(document.querySelector('.palette-backdrop')).not.toBeNull()
    expect(document.querySelector('.palette-input')).not.toBeNull()
    wrapper.unmount()
  })

  it('displays registered commands', async () => {
    const store = useCommandsStore()
    store.register({
      id: 'test.cmd1',
      label: 'First Command',
      execute: vi.fn(),
    })
    store.register({
      id: 'test.cmd2',
      label: 'Second Command',
      execute: vi.fn(),
    })

    const wrapper = mount(CommandPalette)
    store.open()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const items = document.querySelectorAll('.palette-item')
    expect(items.length).toBe(2)
    wrapper.unmount()
  })

  it('filters commands on input', async () => {
    const store = useCommandsStore()
    store.register({
      id: 'test.cmd1',
      label: 'Open Settings',
      execute: vi.fn(),
    })
    store.register({
      id: 'test.cmd2',
      label: 'Close All',
      execute: vi.fn(),
    })

    const wrapper = mount(CommandPalette)
    store.open()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    store.setQuery('settings')
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const items = document.querySelectorAll('.palette-item')
    expect(items.length).toBe(1)
    expect(items[0]!.textContent).toContain('Open Settings')
    wrapper.unmount()
  })

  it('shows empty state when no matches', async () => {
    const store = useCommandsStore()
    store.register({
      id: 'test.cmd',
      label: 'Test',
      execute: vi.fn(),
    })

    const wrapper = mount(CommandPalette)
    store.open()
    store.setQuery('nonexistent')
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(document.querySelector('.palette-empty')).not.toBeNull()
    wrapper.unmount()
  })

  it('shows keyboard shortcut', async () => {
    const store = useCommandsStore()
    store.register({
      id: 'test.cmd',
      label: 'Test',
      shortcut: 'Ctrl+K',
      execute: vi.fn(),
    })

    const wrapper = mount(CommandPalette)
    store.open()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const shortcut = document.querySelector('.palette-item-shortcut')
    expect(shortcut).not.toBeNull()
    expect(shortcut!.textContent).toBe('Ctrl+K')
    wrapper.unmount()
  })

  it('shows category', async () => {
    const store = useCommandsStore()
    store.register({
      id: 'test.cmd',
      label: 'Test',
      category: 'Navigation',
      execute: vi.fn(),
    })

    const wrapper = mount(CommandPalette)
    store.open()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const cat = document.querySelector('.palette-item-category')
    expect(cat).not.toBeNull()
    expect(cat!.textContent).toBe('Navigation')
    wrapper.unmount()
  })
})
