/**
 * Command palette store — manages the command registry and palette state.
 *
 * Commands are registered by feature modules and surfaced in the
 * command palette (Ctrl+K / Cmd+K). Each command has a label,
 * optional shortcut, category, and an execute function.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Command {
  /** Unique command identifier. */
  id: string
  /** Display label. */
  label: string
  /** Optional keyboard shortcut description (e.g. "Ctrl+K"). */
  shortcut?: string
  /** Category for grouping in the palette. */
  category?: string
  /** Optional icon name (lucide icon). */
  icon?: string
  /** Whether this command is currently available. */
  enabled?: boolean
  /** The function to execute. */
  execute: () => void | Promise<void>
}

export const useCommandsStore = defineStore('commands', () => {
  // ── State ──────────────────────────────────────────────────────────────

  const isOpen = ref(false)
  const query = ref('')
  const registry = ref<Map<string, Command>>(new Map())

  // ── Derived ────────────────────────────────────────────────────────────

  const allCommands = computed<Command[]>(() =>
    Array.from(registry.value.values()).filter((c) => c.enabled !== false),
  )

  const filteredCommands = computed<Command[]>(() => {
    const q = query.value.toLowerCase().trim()
    if (!q) return allCommands.value

    return allCommands.value.filter((cmd) => {
      const searchable = `${cmd.label} ${cmd.category ?? ''} ${cmd.id}`.toLowerCase()
      return searchable.includes(q)
    })
  })

  const groupedCommands = computed(() => {
    const groups = new Map<string, Command[]>()
    for (const cmd of filteredCommands.value) {
      const cat = cmd.category ?? 'General'
      const group = groups.get(cat) ?? []
      group.push(cmd)
      groups.set(cat, group)
    }
    return groups
  })

  // ── Actions ────────────────────────────────────────────────────────────

  function register(command: Command): void {
    registry.value.set(command.id, command)
  }

  function registerMany(commands: Command[]): void {
    for (const cmd of commands) {
      registry.value.set(cmd.id, cmd)
    }
  }

  function unregister(id: string): void {
    registry.value.delete(id)
  }

  function open(): void {
    query.value = ''
    isOpen.value = true
  }

  function close(): void {
    isOpen.value = false
    query.value = ''
  }

  function toggle(): void {
    if (isOpen.value) close()
    else open()
  }

  async function executeCommand(id: string): Promise<void> {
    const cmd = registry.value.get(id)
    if (!cmd || cmd.enabled === false) return
    close()
    await cmd.execute()
  }

  function setQuery(q: string): void {
    query.value = q
  }

  return {
    // State
    isOpen,
    query,
    // Derived
    allCommands,
    filteredCommands,
    groupedCommands,
    // Actions
    register,
    registerMany,
    unregister,
    open,
    close,
    toggle,
    executeCommand,
    setQuery,
  }
})
