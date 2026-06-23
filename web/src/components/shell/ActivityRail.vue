/**
 * ActivityRail — vertical sidebar navigation.
 *
 * Shows icon buttons for each workspace section (Collections, Workflows,
 * etc.) plus bottom-aligned utility icons (Settings, Theme toggle).
 * Keyboard-accessible with arrow-key navigation.
 */

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useCommandsStore } from '@/stores/commands'
import { useThemeStore } from '@/stores/theme'
import {
  FolderOpen,
  GitBranch,
  Radio,
  History,
  Puzzle,
  Settings,
  Sun,
  Moon,
  Monitor,
  Command,
  Home,
  ScrollText,
} from 'lucide-vue-next'

interface RailItem {
  id: string
  icon: typeof Home
  label: string
  route: string
  shortcut?: string
}

const router = useRouter()
const route = useRoute()
const commands = useCommandsStore()
const themeStore = useThemeStore()

const topItems: RailItem[] = [
  { id: 'home', icon: Home, label: 'Home', route: '/' },
  { id: 'collections', icon: FolderOpen, label: 'Collections', route: '/collections' },
  { id: 'workflows', icon: GitBranch, label: 'Workflows', route: '/workflows' },
  { id: 'monitors', icon: Radio, label: 'Monitors', route: '/monitors' },
  { id: 'history', icon: History, label: 'History', route: '/history' },
  { id: 'plugins', icon: Puzzle, label: 'Plugins', route: '/plugins' },
  { id: 'logs', icon: ScrollText, label: 'Logs', route: '/logs' },
]

const railRef = ref<HTMLElement | null>(null)
const focusedIndex = ref(0)

function isActive(item: RailItem): boolean {
  if (item.route === '/') return route.path === '/'
  return route.path.startsWith(item.route)
}

function navigate(item: RailItem): void {
  router.push(item.route)
}

function toggleTheme(): void {
  themeStore.cycleTheme()
}

function handleKeydown(e: KeyboardEvent): void {
  const items = [...topItems, ...bottomItems]
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    focusedIndex.value = (focusedIndex.value + 1) % items.length
    focusItem(focusedIndex.value)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    focusedIndex.value = (focusedIndex.value - 1 + items.length) % items.length
    focusItem(focusedIndex.value)
  } else if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    const item = items[focusedIndex.value]
    if (item && 'route' in item) navigate(item as RailItem)
  }
}

function focusItem(index: number): void {
  const buttons = railRef.value?.querySelectorAll<HTMLButtonElement>('[role="button"]')
  buttons?.[index]?.focus()
}

const bottomItems = [
  { id: 'command', icon: Command, label: 'Command Palette', action: () => commands.open() },
  { id: 'theme', icon: Monitor, label: 'Toggle Theme', action: toggleTheme },
  { id: 'settings', icon: Settings, label: 'Settings', route: '/settings' },
]

onMounted(() => {
  // Register command palette command
  commands.register({
    id: 'palette.open',
    label: 'Open Command Palette',
    shortcut: 'Ctrl+K',
    category: 'General',
    icon: 'Command',
    execute: () => commands.open(),
  })
})
</script>

<template>
  <nav
    ref="railRef"
    class="activity-rail"
    role="navigation"
    aria-label="Workspace navigation"
    @keydown="handleKeydown"
  >
    <div class="rail-top">
      <button
        v-for="(item, idx) in topItems"
        :key="item.id"
        class="rail-button"
        :class="{ active: isActive(item) }"
        role="button"
        :aria-label="item.label"
        :aria-current="isActive(item) ? 'page' : undefined"
        :tabindex="idx === focusedIndex ? 0 : -1"
        @click="navigate(item)"
      >
        <component :is="item.icon" :size="20" />
        <span class="rail-tooltip">{{ item.label }}</span>
      </button>
    </div>

    <div class="rail-bottom">
      <template v-for="(item, idx) in bottomItems" :key="item.id">
        <button
          class="rail-button"
          role="button"
          :aria-label="item.label"
          :tabindex="topItems.length + idx === focusedIndex ? 0 : -1"
          @click="'action' in item ? item.action() : 'route' in item ? navigate(item as RailItem) : undefined"
        >
          <component :is="item.icon" :size="20" />
          <span class="rail-tooltip">{{ item.label }}</span>
        </button>
      </template>
    </div>
  </nav>
</template>

<style scoped>
.activity-rail {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  width: var(--density-rail-width);
  min-width: var(--density-rail-width);
  background: var(--surface-base);
  border-right: 1px solid var(--surface-border);
  padding: var(--density-space-2) 0;
  user-select: none;
}

.rail-top,
.rail-bottom {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--density-space-1);
}

.rail-button {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: calc(var(--density-rail-width) - var(--density-space-3));
  height: calc(var(--density-rail-width) - var(--density-space-3));
  border: none;
  border-radius: var(--density-radius-md);
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.rail-button:hover {
  color: var(--text-primary);
  background: var(--surface-raised);
}

.rail-button:focus-visible {
  box-shadow: var(--focus-ring);
}

.rail-button.active {
  color: var(--accent-primary);
  background: var(--accent-primary-muted);
}

/* Tooltip on hover */
.rail-tooltip {
  position: absolute;
  left: calc(100% + var(--density-space-2));
  top: 50%;
  transform: translateY(-50%);
  padding: var(--density-space-1) var(--density-space-2);
  background: var(--surface-overlay);
  color: var(--text-primary);
  font-size: var(--density-font-xs);
  border-radius: var(--density-radius-sm);
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  transition: opacity var(--transition-fast);
  box-shadow: var(--shadow-md);
  z-index: 100;
}

.rail-button:hover .rail-tooltip,
.rail-button:focus-visible .rail-tooltip {
  opacity: 1;
}
</style>
