/**
 * TopBar — header with project switcher, environment selector,
 * connection status, and command palette trigger.
 */

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useProjectStore } from '@/stores/project'
import { useConnectionStore } from '@/stores/connection'
import { useCommandsStore } from '@/stores/commands'
import { useTabsStore } from '@/stores/tabs'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import {
  ChevronDown,
  Search,
  Wifi,
  WifiOff,
  Loader2,
} from 'lucide-vue-next'

const projectStore = useProjectStore()
const connectionStore = useConnectionStore()
const commands = useCommandsStore()
const tabsStore = useTabsStore()

const showProjectDropdown = ref(false)
const dropdownRef = ref<HTMLElement | null>(null)
const showDirtyDialog = ref(false)
const pendingProjectId = ref<string | null>(null)

const projectName = computed(() => projectStore.activeProject?.name ?? 'No Project')
const connectionLabel = computed(() => {
  switch (connectionStore.state) {
    case 'connected': return `v${connectionStore.version ?? '?'}`
    case 'connecting': return 'Connecting...'
    case 'disconnected': return 'Disconnected'
    case 'error': return 'Error'
  }
})

const dirtyTabCount = computed(() => {
  if (!pendingProjectId.value) return 0
  return tabsStore.getDirtyTabsForProject(projectStore.activeProjectId ?? '').length
})

function selectProject(id: string): void {
  const dirtyTabs = tabsStore.getDirtyTabsForProject(projectStore.activeProjectId ?? '')
  if (dirtyTabs.length > 0) {
    pendingProjectId.value = id
    showDirtyDialog.value = true
    showProjectDropdown.value = false
    return
  }
  projectStore.setActiveProject(id)
  showProjectDropdown.value = false
}

function confirmProjectSwitch(): void {
  if (pendingProjectId.value) {
    tabsStore.discardDirtyForProject(projectStore.activeProjectId ?? '')
    projectStore.setActiveProject(pendingProjectId.value)
  }
  showDirtyDialog.value = false
  pendingProjectId.value = null
}

function cancelProjectSwitch(): void {
  showDirtyDialog.value = false
  pendingProjectId.value = null
}

function handleClickOutside(e: MouseEvent): void {
  if (dropdownRef.value && !dropdownRef.value.contains(e.target as Node)) {
    showProjectDropdown.value = false
  }
}

function handleKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape') {
    showProjectDropdown.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <header class="topbar" role="banner">
    <!-- Left: Project switcher -->
    <div class="topbar-left">
      <div
        ref="dropdownRef"
        class="project-switcher"
        role="combobox"
        aria-expanded="showProjectDropdown"
        aria-haspopup="listbox"
        aria-label="Switch project"
      >
        <button
          class="project-trigger"
          @click.stop="showProjectDropdown = !showProjectDropdown"
          @keydown.enter="showProjectDropdown = !showProjectDropdown"
          @keydown.space.prevent="showProjectDropdown = !showProjectDropdown"
        >
          <span class="project-name">{{ projectName }}</span>
          <ChevronDown :size="14" />
        </button>

        <div
          v-if="showProjectDropdown"
          class="project-dropdown"
          role="listbox"
          aria-label="Projects"
        >
          <button
            v-for="project in projectStore.projects"
            :key="project.id"
            class="dropdown-item"
            :class="{ selected: project.id === projectStore.activeProjectId }"
            role="option"
            :aria-selected="project.id === projectStore.activeProjectId"
            @click="selectProject(project.id)"
          >
            <span>{{ project.name }}</span>
            <span v-if="project.isDefault" class="badge">Default</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Center: Search / Command palette trigger -->
    <div class="topbar-center">
      <button
        class="search-trigger"
        aria-label="Open command palette"
        @click="commands.open()"
      >
        <Search :size="14" />
        <span>Search commands...</span>
        <kbd>Ctrl+K</kbd>
      </button>
    </div>

    <!-- Right: Connection status -->
    <div class="topbar-right">
      <div
        class="connection-status"
        :class="connectionStore.state"
        role="status"
        :aria-label="`Backend ${connectionStore.state}`"
      >
        <Loader2
          v-if="connectionStore.state === 'connecting'"
          :size="14"
          class="spin"
        />
        <Wifi
          v-else-if="connectionStore.isConnected"
          :size="14"
        />
        <WifiOff
          v-else
          :size="14"
        />
        <span class="connection-label">{{ connectionLabel }}</span>
      </div>
    </div>
  </header>

  <!-- Dirty-tab review dialog -->
  <ConfirmDialog
    :open="showDirtyDialog"
    title="Unsaved Changes"
    :message="`You have ${dirtyTabCount} unsaved tab(s) in the current project. Switching projects will discard these changes.`"
    confirm-label="Discard & Switch"
    cancel-label="Cancel"
    variant="danger"
    @confirm="confirmProjectSwitch"
    @cancel="cancelProjectSwitch"
  />
</template>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--density-topbar-height);
  min-height: var(--density-topbar-height);
  padding: 0 var(--density-space-3);
  background: var(--surface-base);
  border-bottom: 1px solid var(--surface-border);
  gap: var(--density-space-3);
}

.topbar-left,
.topbar-right {
  display: flex;
  align-items: center;
  min-width: 0;
}

.topbar-center {
  flex: 1;
  display: flex;
  justify-content: center;
  max-width: 480px;
}

/* ── Project switcher ─────────────────────────────────────────────── */

.project-switcher {
  position: relative;
}

.project-trigger {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  padding: var(--density-space-1) var(--density-space-2);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-md);
  background: var(--surface-raised);
  color: var(--text-primary);
  font-size: var(--density-font-sm);
  cursor: pointer;
  transition: border-color var(--transition-fast);
}

.project-trigger:hover {
  border-color: var(--accent-primary);
}

.project-name {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-dropdown {
  position: absolute;
  top: calc(100% + var(--density-space-1));
  left: 0;
  min-width: 200px;
  background: var(--surface-overlay);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-md);
  box-shadow: var(--shadow-lg);
  z-index: 50;
  padding: var(--density-space-1);
}

.dropdown-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: var(--density-space-2) var(--density-space-3);
  border: none;
  border-radius: var(--density-radius-sm);
  background: transparent;
  color: var(--text-primary);
  font-size: var(--density-font-sm);
  cursor: pointer;
  text-align: left;
}

.dropdown-item:hover {
  background: var(--surface-raised);
}

.dropdown-item.selected {
  background: var(--accent-primary-muted);
  color: var(--accent-primary);
}

.badge {
  font-size: var(--density-font-xs);
  padding: 1px var(--density-space-1);
  border-radius: var(--density-radius-full);
  background: var(--surface-border);
  color: var(--text-secondary);
}

/* ── Search trigger ───────────────────────────────────────────────── */

.search-trigger {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
  width: 100%;
  max-width: 400px;
  padding: var(--density-space-1) var(--density-space-3);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-md);
  background: var(--surface-raised);
  color: var(--text-tertiary);
  font-size: var(--density-font-sm);
  cursor: pointer;
  transition: border-color var(--transition-fast);
}

.search-trigger:hover {
  border-color: var(--accent-primary);
}

.search-trigger kbd {
  margin-left: auto;
  padding: 0 var(--density-space-1);
  font-size: var(--density-font-xs);
  font-family: var(--font-mono);
  background: var(--surface-border);
  border-radius: var(--density-radius-sm);
  color: var(--text-secondary);
}

/* ── Connection status ────────────────────────────────────────────── */

.connection-status {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  font-size: var(--density-font-xs);
  color: var(--text-tertiary);
}

.connection-status.connected {
  color: var(--color-success);
}

.connection-status.disconnected,
.connection-status.error {
  color: var(--color-error);
}

.connection-status.connecting {
  color: var(--color-warning);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.connection-label {
  font-family: var(--font-mono);
}
</style>
