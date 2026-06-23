/**
 * Vue Router configuration with typed routes and deep-link resolution.
 *
 * Defines all feature-area routes with lazy loading. Route meta carries
 * the resource kind for tab integration and the explorer section for
 * sidebar highlighting.
 */

import {
  createRouter,
  createWebHistory,
  type RouteRecordRaw,
  type RouteMeta,
} from 'vue-router'

// ── Route meta types ──────────────────────────────────────────────────

export interface StudioRouteMeta extends RouteMeta {
  /** Resource kind for tab creation. */
  kind?: 'request' | 'workflow' | 'monitor' | 'function' | 'environment' | 'settings' | 'home'
  /** Explorer section this route belongs to. */
  section?: 'collections' | 'workflows' | 'monitors' | 'functions' | 'environments'
  /** Whether this route requires an active project. */
  requiresProject?: boolean
  /** Page title for document.title. */
  title?: string
}

// ── Route definitions ─────────────────────────────────────────────────

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: {
      kind: 'home',
      title: 'Home',
    } satisfies StudioRouteMeta,
  },
  {
    path: '/collections',
    name: 'collections',
    component: () => import('@/views/CollectionsView.vue'),
    meta: {
      kind: 'request',
      section: 'collections',
      requiresProject: true,
      title: 'Collections',
    } satisfies StudioRouteMeta,
  },
  {
    path: '/collections/:collectionId',
    name: 'collection-detail',
    component: () => import('@/views/placeholder/CollectionView.vue'),
    meta: {
      kind: 'request',
      section: 'collections',
      requiresProject: true,
      title: 'Collection',
    } satisfies StudioRouteMeta,
  },
  {
    path: '/requests/:requestId',
    name: 'request-detail',
    component: () => import('@/views/RequestEditorView.vue'),
    meta: {
      kind: 'request',
      section: 'collections',
      requiresProject: true,
      title: 'Request',
    } satisfies StudioRouteMeta,
  },
  {
    path: '/workflows',
    name: 'workflows',
    component: () => import('@/views/placeholder/WorkflowsView.vue'),
    meta: {
      kind: 'workflow',
      section: 'workflows',
      requiresProject: true,
      title: 'Workflows',
    } satisfies StudioRouteMeta,
  },
  {
    path: '/workflows/:workflowId',
    name: 'workflow-detail',
    component: () => import('@/views/placeholder/WorkflowView.vue'),
    meta: {
      kind: 'workflow',
      section: 'workflows',
      requiresProject: true,
      title: 'Workflow',
    } satisfies StudioRouteMeta,
  },
  {
    path: '/monitors',
    name: 'monitors',
    component: () => import('@/views/placeholder/MonitorsView.vue'),
    meta: {
      kind: 'monitor',
      section: 'monitors',
      requiresProject: true,
      title: 'Monitors',
    } satisfies StudioRouteMeta,
  },
  {
    path: '/monitors/:monitorId',
    name: 'monitor-detail',
    component: () => import('@/views/placeholder/MonitorView.vue'),
    meta: {
      kind: 'monitor',
      section: 'monitors',
      requiresProject: true,
      title: 'Monitor',
    } satisfies StudioRouteMeta,
  },
  {
    path: '/functions',
    name: 'functions',
    component: () => import('@/views/FunctionsView.vue'),
    meta: {
      kind: 'function',
      section: 'functions',
      requiresProject: true,
      title: 'Functions',
    } satisfies StudioRouteMeta,
  },
  {
    path: '/functions/:functionId',
    name: 'function-detail',
    component: () => import('@/views/FunctionsView.vue'),
    meta: {
      kind: 'function',
      section: 'functions',
      requiresProject: true,
      title: 'Function',
    } satisfies StudioRouteMeta,
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('@/views/HistoryView.vue'),
    meta: {
      kind: 'request',
      title: 'History',
    } satisfies StudioRouteMeta,
  },
  {
    path: '/plugins',
    name: 'plugins',
    component: () => import('@/views/PluginsView.vue'),
    meta: {
      title: 'Plugins',
    } satisfies StudioRouteMeta,
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: {
      kind: 'settings',
      title: 'Settings',
    } satisfies StudioRouteMeta,
  },
  {
    path: '/logs',
    name: 'logs',
    component: () => import('@/views/LogsView.vue'),
    meta: {
      title: 'Logs',
    } satisfies StudioRouteMeta,
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: {
      title: 'Not Found',
    } satisfies StudioRouteMeta,
  },
]

// ── Router instance ───────────────────────────────────────────────────

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

// ── Route guards ──────────────────────────────────────────────────────

router.beforeEach((to) => {
  // Update document title
  const meta = to.meta as StudioRouteMeta
  if (meta.title) {
    document.title = `${meta.title} - SCLPLAPI Studio`
  }
})

// ── Typed route helpers ───────────────────────────────────────────────

/**
 * Build a typed route location for deep-linking.
 * Usage: routeTo('request-detail', { requestId: 'abc' })
 */
export function routeTo(
  name: string,
  params?: Record<string, string>,
): { name: string; params?: Record<string, string> } {
  return { name, params }
}

/**
 * Resolve a resource type + ID to a route name.
 */
export function resolveRouteName(
  kind: string,
): string {
  const map: Record<string, string> = {
    request: 'request-detail',
    collection: 'collection-detail',
    workflow: 'workflow-detail',
    monitor: 'monitor-detail',
    function: 'function-detail',
    environment: 'settings',
    settings: 'settings',
  }
  return map[kind] ?? 'home'
}
