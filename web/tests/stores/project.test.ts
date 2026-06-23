/**
 * Project store tests.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useProjectStore } from '@/stores/project'
import { setGateway } from '@/gateway'
import type { StudioGateway } from '@/gateway'

function createMockGateway(): StudioGateway {
  return {
    health: { check: vi.fn() },
    projects: {
      list: vi.fn().mockResolvedValue([
        { id: 'proj-1', name: 'Default', isDefault: true },
        { id: 'proj-2', name: 'Workspace', isDefault: false },
      ]),
      get: vi.fn(),
      create: vi.fn().mockImplementation((input: { name: string }) => Promise.resolve({ id: 'proj-3', name: input.name, isDefault: false })),
      update: vi.fn(),
      delete: vi.fn().mockResolvedValue(undefined),
    },
    collections: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
    requests: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn(), execute: vi.fn() },
    environments: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
    workflows: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn(), run: vi.fn() },
    functions: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
    plugins: { list: vi.fn(), get: vi.fn() },
    monitors: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn(), start: vi.fn(), stop: vi.fn(), events: vi.fn() },
    runs: { list: vi.fn(), get: vi.fn(), cancel: vi.fn() },
    batches: { run: vi.fn() },
    transfers: { export: vi.fn(), import: vi.fn(), presets: vi.fn() },
    settings: { get: vi.fn(), update: vi.fn() },
    events: { subscribe: vi.fn() },
  } as unknown as StudioGateway
}

describe('ProjectStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    setGateway(createMockGateway())
  })

  it('starts with empty projects', () => {
    const store = useProjectStore()
    expect(store.projects).toEqual([])
    expect(store.activeProjectId).toBeNull()
  })

  it('loads projects from gateway', async () => {
    const store = useProjectStore()
    await store.loadProjects()
    expect(store.projects).toHaveLength(2)
    expect(store.projects[0]!.name).toBe('Default')
  })

  it('sets active project to default when loading', async () => {
    const store = useProjectStore()
    await store.loadProjects()
    expect(store.activeProjectId).toBe('proj-1')
  })

  it('persists active project to localStorage', async () => {
    const store = useProjectStore()
    await store.loadProjects()
    store.setActiveProject('proj-2')
    expect(localStorage.getItem('sclplapi:activeProject')).toBe('proj-2')
  })

  it('reads persisted project from localStorage', () => {
    localStorage.setItem('sclplapi:activeProject', 'proj-2')
    const store = useProjectStore()
    expect(store.activeProjectId).toBe('proj-2')
  })

  it('returns active project', async () => {
    const store = useProjectStore()
    await store.loadProjects()
    store.setActiveProject('proj-2')
    expect(store.activeProject?.name).toBe('Workspace')
  })

  it('returns default project', async () => {
    const store = useProjectStore()
    await store.loadProjects()
    expect(store.defaultProject?.name).toBe('Default')
  })

  it('creates a project', async () => {
    const store = useProjectStore()
    await store.loadProjects()
    const project = await store.createProject('New Project')
    expect(project.name).toBe('New Project')
    expect(store.projects).toHaveLength(3)
  })

  it('deletes a project', async () => {
    const store = useProjectStore()
    await store.loadProjects()
    await store.deleteProject('proj-2')
    expect(store.projects).toHaveLength(1)
  })

  it('sets loading state', async () => {
    const store = useProjectStore()
    expect(store.loading).toBe(false)
    const promise = store.loadProjects()
    expect(store.loading).toBe(true)
    await promise
    expect(store.loading).toBe(false)
  })

  it('handles load error', async () => {
    const gw = createMockGateway()
    vi.mocked(gw.projects.list).mockRejectedValue(new Error('Network error'))
    setGateway(gw)

    const store = useProjectStore()
    await store.loadProjects()
    expect(store.error).toBe('Network error')
    expect(store.loading).toBe(false)
  })

  it('falls back to first project if persisted id does not exist', async () => {
    localStorage.setItem('sclplapi:activeProject', 'nonexistent')
    const store = useProjectStore()
    await store.loadProjects()
    expect(store.activeProjectId).toBe('proj-1')
  })
})
