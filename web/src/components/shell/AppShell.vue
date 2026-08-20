/**
 * AppShell — main application layout.
 *
 * Composes ActivityRail, TopBar, ExplorerHost, TabBar, and the
 * main content area with router-view. Handles initial data loading
 * and theme initialization.
 */

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { useProjectStore } from '@/stores/project'
import { useConnectionStore } from '@/stores/connection'
import { getGateway } from '@/gateway'
import ActivityRail from './ActivityRail.vue'
import TopBar from './TopBar.vue'
import ExplorerHost from './ExplorerHost.vue'
import TabBar from './TabBar.vue'
import CommandPalette from './CommandPalette.vue'
import ErrorBoundary from './ErrorBoundary.vue'
import type { TreeNode } from './ExplorerHost.vue'

const router = useRouter()
const route = useRoute()
const themeStore = useThemeStore()
const projectStore = useProjectStore()
const connectionStore = useConnectionStore()

const explorerNodes = ref<TreeNode[]>([])
const explorerLoading = ref(false)
const explorerWidth = ref(240)

// Compute which sections are visible based on route
const showExplorer = computed(() => {
  const path = route.path
  return (
    path.startsWith('/collections') ||
    path.startsWith('/workflows') ||
    path.startsWith('/monitors') ||
    path.startsWith('/functions')
  )
})

async function loadExplorerData(): Promise<void> {
  if (!projectStore.activeProjectId) return
  explorerLoading.value = true
  try {
    const gw = getGateway()
    const pid = projectStore.activeProjectId

    const [collections, workflows, monitors, functions] = await Promise.all([
      gw.collections.list(pid).catch(() => []),
      gw.workflows.list(pid).catch(() => []),
      gw.monitors.list(pid).catch(() => []),
      gw.functions.list(pid).catch(() => []),
    ])

    const nodes: TreeNode[] = []

    if (collections.length > 0) {
      nodes.push({
        id: 'collections-root',
        label: 'Collections',
        kind: 'request',
        expandable: true,
        children: collections.map((c) => ({
          id: c.id,
          label: c.name,
          kind: 'request' as const,
          expandable: c.items.length > 0,
          route: `/collections/${c.id}`,
          children: c.items.map((item) => ({
            id: item.id,
            label: item.name,
            kind: 'request' as const,
            route: item.requestId ? `/requests/${item.requestId}` : undefined,
          })),
        })),
      })
    }

    if (workflows.length > 0) {
      nodes.push({
        id: 'workflows-root',
        label: 'Workflows',
        kind: 'workflow',
        expandable: true,
        children: workflows.map((w) => ({
          id: w.id,
          label: w.name,
          kind: 'workflow' as const,
          route: `/workflows/${w.id}`,
        })),
      })
    }

    if (monitors.length > 0) {
      nodes.push({
        id: 'monitors-root',
        label: 'Monitors',
        kind: 'monitor',
        expandable: true,
        children: monitors.map((m) => ({
          id: m.id,
          label: m.name,
          kind: 'monitor' as const,
          route: `/monitors/${m.id}`,
        })),
      })
    }

    if (functions.length > 0) {
      nodes.push({
        id: 'functions-root',
        label: 'Functions',
        kind: 'function',
        expandable: true,
        children: functions.map((f) => ({
          id: f.id,
          label: f.name,
          kind: 'function' as const,
          route: `/functions/${f.id}`,
        })),
      })
    }

    explorerNodes.value = nodes
  } catch {
    explorerNodes.value = []
  } finally {
    explorerLoading.value = false
  }
}

async function initConnection(): Promise<void> {
  connectionStore.setConnecting()
  try {
    const gw = getGateway()
    const health = await gw.health.check()
    connectionStore.setConnected(health.version)
  } catch (err) {
    connectionStore.setDisconnected(
      err instanceof Error ? err.message : 'Connection failed',
    )
  }
}

onMounted(async () => {
  // Apply persisted theme
  themeStore.init()

  // Check backend connection
  await initConnection()

  // Load project list
  await projectStore.loadProjects()

  // Load explorer data for active project
  if (projectStore.activeProjectId) {
    await loadExplorerData()
  }
})
</script>

<template>
  <div class="app-shell">
    <ActivityRail />

    <div class="app-main">
      <TopBar />

      <div class="app-body">
        <ExplorerHost
          v-if="showExplorer"
          :loading="explorerLoading"
          :nodes="explorerNodes"
          @resize="explorerWidth = $event"
        />

        <div class="app-content">
          <TabBar />
          <ErrorBoundary>
            <main class="app-view">
              <RouterView />
            </main>
          </ErrorBoundary>
        </div>
      </div>
    </div>

    <CommandPalette />
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--surface-ground);
  color: var(--text-primary);
}

.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.app-body {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

.app-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.app-view {
  flex: 1;
  overflow: auto;
  padding: var(--density-space-4);
}
</style>
