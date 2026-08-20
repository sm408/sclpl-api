/**
 * CommandPalette — modal command launcher (Ctrl+K / Cmd+K).
 *
 * Shows a searchable list of registered commands grouped by category.
 * Keyboard-navigable with arrow keys, Enter to execute, Escape to close.
 */

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useCommandsStore } from '@/stores/commands'
import type { Command } from '@/stores/commands'
import { Search, CornerDownLeft } from 'lucide-vue-next'

const commands = useCommandsStore()

const inputRef = ref<HTMLInputElement | null>(null)
const listRef = ref<HTMLElement | null>(null)
const selectedIndex = ref(0)

// Focus input when palette opens
watch(
  () => commands.isOpen,
  async (open) => {
    if (open) {
      selectedIndex.value = 0
      await nextTick()
      inputRef.value?.focus()
    }
  },
)

// Reset selection when query changes
watch(
  () => commands.query,
  () => {
    selectedIndex.value = 0
  },
)

const flatCommands = computed<Command[]>(() => commands.filteredCommands)

function handleInput(e: Event): void {
  const target = e.target as HTMLInputElement
  commands.setQuery(target.value)
}

function selectCommand(cmd: Command): void {
  commands.executeCommand(cmd.id)
}

function handleKeydown(e: KeyboardEvent): void {
  const total = flatCommands.value.length

  switch (e.key) {
    case 'ArrowDown':
      e.preventDefault()
      selectedIndex.value = (selectedIndex.value + 1) % Math.max(total, 1)
      scrollToSelected()
      break
    case 'ArrowUp':
      e.preventDefault()
      selectedIndex.value = (selectedIndex.value - 1 + total) % Math.max(total, 1)
      scrollToSelected()
      break
    case 'Enter':
      e.preventDefault()
      {
        const cmd = flatCommands.value[selectedIndex.value]
        if (cmd) selectCommand(cmd)
      }
      break
    case 'Escape':
      e.preventDefault()
      commands.close()
      break
  }
}

function scrollToSelected(): void {
  nextTick(() => {
    const el = listRef.value?.querySelector(`[data-index="${selectedIndex.value}"]`)
    el?.scrollIntoView({ block: 'nearest' })
  })
}

// Global keyboard shortcut
function handleGlobalKeydown(e: KeyboardEvent): void {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault()
    commands.toggle()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleGlobalKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleGlobalKeydown)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="palette">
      <div
        v-if="commands.isOpen"
        class="palette-backdrop"
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        @click.self="commands.close()"
      >
        <div class="palette-container">
          <!-- Search input -->
          <div class="palette-input-wrap">
            <Search :size="16" class="palette-search-icon" />
            <input
              ref="inputRef"
              class="palette-input"
              type="text"
              placeholder="Type a command..."
              :value="commands.query"
              aria-label="Search commands"
              @input="handleInput"
              @keydown="handleKeydown"
            />
          </div>

          <!-- Command list -->
          <div
            ref="listRef"
            class="palette-list"
            role="listbox"
            aria-label="Commands"
          >
            <template v-if="flatCommands.length === 0">
              <div class="palette-empty">No matching commands</div>
            </template>

            <template v-else>
              <div
                v-for="(cmd, idx) in flatCommands"
                :key="cmd.id"
                class="palette-item"
                :class="{ selected: idx === selectedIndex }"
                role="option"
                :aria-selected="idx === selectedIndex"
                :data-index="idx"
                @click="selectCommand(cmd)"
                @mouseenter="selectedIndex = idx"
              >
                <span class="palette-item-label">{{ cmd.label }}</span>
                <span v-if="cmd.category" class="palette-item-category">{{ cmd.category }}</span>
                <kbd v-if="cmd.shortcut" class="palette-item-shortcut">{{ cmd.shortcut }}</kbd>
              </div>
            </template>
          </div>

          <!-- Footer hint -->
          <div class="palette-footer">
            <span class="palette-hint">
              <CornerDownLeft :size="12" /> to select
            </span>
            <span class="palette-hint">
              &uarr;&darr; to navigate
            </span>
            <span class="palette-hint">
              Esc to close
            </span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.palette-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 15vh;
  z-index: 200;
}

.palette-container {
  width: 100%;
  max-width: 560px;
  background: var(--surface-overlay);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-lg);
  box-shadow: var(--shadow-overlay);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 400px;
}

/* ── Input ────────────────────────────────────────────────────────── */

.palette-input-wrap {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
  padding: var(--density-space-3);
  border-bottom: 1px solid var(--surface-border);
}

.palette-search-icon {
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.palette-input {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: var(--density-font-md);
  font-family: var(--font-sans);
  outline: none;
}

.palette-input::placeholder {
  color: var(--text-disabled);
}

/* ── List ─────────────────────────────────────────────────────────── */

.palette-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--density-space-1);
}

.palette-empty {
  padding: var(--density-space-4);
  text-align: center;
  color: var(--text-tertiary);
  font-size: var(--density-font-sm);
}

.palette-item {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
  padding: var(--density-space-2) var(--density-space-3);
  border-radius: var(--density-radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.palette-item:hover,
.palette-item.selected {
  background: var(--surface-raised);
}

.palette-item-label {
  flex: 1;
  font-size: var(--density-font-sm);
  color: var(--text-primary);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.palette-item-category {
  font-size: var(--density-font-xs);
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.palette-item-shortcut {
  font-size: var(--density-font-xs);
  font-family: var(--font-mono);
  padding: 0 var(--density-space-1);
  background: var(--surface-border);
  border-radius: var(--density-radius-sm);
  color: var(--text-secondary);
  flex-shrink: 0;
}

/* ── Footer ───────────────────────────────────────────────────────── */

.palette-footer {
  display: flex;
  align-items: center;
  gap: var(--density-space-3);
  padding: var(--density-space-2) var(--density-space-3);
  border-top: 1px solid var(--surface-border);
  background: var(--surface-ground);
}

.palette-hint {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  font-size: var(--density-font-xs);
  color: var(--text-tertiary);
}

/* ── Transitions ──────────────────────────────────────────────────── */

.palette-enter-active,
.palette-leave-active {
  transition: opacity var(--transition-normal);
}

.palette-enter-active .palette-container,
.palette-leave-active .palette-container {
  transition: transform var(--transition-normal), opacity var(--transition-normal);
}

.palette-enter-from,
.palette-leave-to {
  opacity: 0;
}

.palette-enter-from .palette-container,
.palette-leave-to .palette-container {
  transform: translateY(-10px);
  opacity: 0;
}
</style>
