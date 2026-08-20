/**
 * Commands store tests.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useCommandsStore } from '@/stores/commands'

function makeCommand(overrides: Record<string, unknown> = {}) {
  return {
    id: 'test.command',
    label: 'Test Command',
    category: 'Test',
    execute: vi.fn(),
    ...overrides,
  }
}

describe('CommandsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts closed with no commands', () => {
    const store = useCommandsStore()
    expect(store.isOpen).toBe(false)
    expect(store.allCommands).toEqual([])
  })

  it('registers a command', () => {
    const store = useCommandsStore()
    store.register(makeCommand())
    expect(store.allCommands).toHaveLength(1)
    expect(store.allCommands[0]!.id).toBe('test.command')
  })

  it('registers multiple commands', () => {
    const store = useCommandsStore()
    store.registerMany([
      makeCommand({ id: 'cmd.1' }),
      makeCommand({ id: 'cmd.2' }),
    ])
    expect(store.allCommands).toHaveLength(2)
  })

  it('unregisters a command', () => {
    const store = useCommandsStore()
    store.register(makeCommand())
    store.unregister('test.command')
    expect(store.allCommands).toHaveLength(0)
  })

  it('opens the palette', () => {
    const store = useCommandsStore()
    store.open()
    expect(store.isOpen).toBe(true)
    expect(store.query).toBe('')
  })

  it('closes the palette', () => {
    const store = useCommandsStore()
    store.open()
    store.setQuery('test')
    store.close()
    expect(store.isOpen).toBe(false)
    expect(store.query).toBe('')
  })

  it('toggles the palette', () => {
    const store = useCommandsStore()
    store.toggle()
    expect(store.isOpen).toBe(true)
    store.toggle()
    expect(store.isOpen).toBe(false)
  })

  it('filters commands by query', () => {
    const store = useCommandsStore()
    store.register(makeCommand({ id: 'cmd.1', label: 'Open Settings' }))
    store.register(makeCommand({ id: 'cmd.2', label: 'Close All' }))
    store.setQuery('settings')
    expect(store.filteredCommands).toHaveLength(1)
    expect(store.filteredCommands[0]!.id).toBe('cmd.1')
  })

  it('filters commands case-insensitively', () => {
    const store = useCommandsStore()
    store.register(makeCommand({ id: 'cmd.1', label: 'Open Settings' }))
    store.setQuery('SETTINGS')
    expect(store.filteredCommands).toHaveLength(1)
  })

  it('filters by category', () => {
    const store = useCommandsStore()
    store.register(makeCommand({ id: 'cmd.1', label: 'Test', category: 'Navigation' }))
    store.register(makeCommand({ id: 'cmd.2', label: 'Other', category: 'General' }))
    store.setQuery('navigation')
    expect(store.filteredCommands).toHaveLength(1)
  })

  it('returns all commands when query is empty', () => {
    const store = useCommandsStore()
    store.register(makeCommand({ id: 'cmd.1' }))
    store.register(makeCommand({ id: 'cmd.2' }))
    store.setQuery('')
    expect(store.filteredCommands).toHaveLength(2)
  })

  it('excludes disabled commands', () => {
    const store = useCommandsStore()
    store.register(makeCommand({ id: 'cmd.1', enabled: true }))
    store.register(makeCommand({ id: 'cmd.2', enabled: false }))
    expect(store.allCommands).toHaveLength(1)
  })

  it('executes a command', async () => {
    const store = useCommandsStore()
    const execute = vi.fn()
    store.register(makeCommand({ id: 'cmd.1', execute }))
    await store.executeCommand('cmd.1')
    expect(execute).toHaveBeenCalled()
  })

  it('closes palette after executing a command', async () => {
    const store = useCommandsStore()
    store.open()
    store.register(makeCommand({ id: 'cmd.1' }))
    await store.executeCommand('cmd.1')
    expect(store.isOpen).toBe(false)
  })

  it('does not execute disabled commands', async () => {
    const store = useCommandsStore()
    const execute = vi.fn()
    store.register(makeCommand({ id: 'cmd.1', enabled: false, execute }))
    await store.executeCommand('cmd.1')
    expect(execute).not.toHaveBeenCalled()
  })

  it('does not execute unknown commands', async () => {
    const store = useCommandsStore()
    // Should not throw
    await store.executeCommand('unknown')
  })

  it('groups commands by category', () => {
    const store = useCommandsStore()
    store.register(makeCommand({ id: 'cmd.1', label: 'A', category: 'Nav' }))
    store.register(makeCommand({ id: 'cmd.2', label: 'B', category: 'Nav' }))
    store.register(makeCommand({ id: 'cmd.3', label: 'C', category: 'General' }))
    const groups = store.groupedCommands
    expect(groups.has('Nav')).toBe(true)
    expect(groups.get('Nav')).toHaveLength(2)
    expect(groups.has('General')).toBe(true)
    expect(groups.get('General')).toHaveLength(1)
  })

  it('groups commands without category under General', () => {
    const store = useCommandsStore()
    store.register(makeCommand({ id: 'cmd.1', category: undefined }))
    const groups = store.groupedCommands
    expect(groups.has('General')).toBe(true)
  })
})
