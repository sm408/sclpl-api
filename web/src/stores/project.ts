/**
 * Project store — manages the active project context.
 *
 * Tracks which project is selected, provides the full project list,
 * and coordinates project switching (including dirty-tab review).
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getGateway } from '@/gateway'
import type { Project } from '@/types/api'

const STORAGE_KEY_PROJECT = 'sclplapi:activeProject'

function readPersistedProjectId(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY_PROJECT)
  } catch {
    return null
  }
}

export const useProjectStore = defineStore('project', () => {
  // ── State ──────────────────────────────────────────────────────────────

  const projects = ref<Project[]>([])
  const activeProjectId = ref<string | null>(readPersistedProjectId())
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ── Derived ────────────────────────────────────────────────────────────

  const activeProject = computed<Project | undefined>(() =>
    projects.value.find((p) => p.id === activeProjectId.value),
  )

  const defaultProject = computed<Project | undefined>(() =>
    projects.value.find((p) => p.isDefault),
  )

  // ── Actions ────────────────────────────────────────────────────────────

  async function loadProjects(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const gw = getGateway()
      projects.value = await gw.projects.list()
      // If no active project or the active one no longer exists, pick default
      if (
        !activeProjectId.value ||
        !projects.value.some((p) => p.id === activeProjectId.value)
      ) {
        activeProjectId.value = defaultProject.value?.id ?? projects.value[0]?.id ?? null
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load projects'
    } finally {
      loading.value = false
    }
  }

  function setActiveProject(id: string): void {
    activeProjectId.value = id
    try {
      localStorage.setItem(STORAGE_KEY_PROJECT, id)
    } catch {
      // localStorage may be unavailable
    }
  }

  async function createProject(name: string, description?: string): Promise<Project> {
    const gw = getGateway()
    const project = await gw.projects.create({ name, description })
    projects.value.push(project)
    return project
  }

  async function deleteProject(id: string): Promise<void> {
    const gw = getGateway()
    await gw.projects.delete(id)
    projects.value = projects.value.filter((p) => p.id !== id)
    if (activeProjectId.value === id) {
      activeProjectId.value = defaultProject.value?.id ?? projects.value[0]?.id ?? null
    }
  }

  return {
    // State
    projects,
    activeProjectId,
    loading,
    error,
    // Derived
    activeProject,
    defaultProject,
    // Actions
    loadProjects,
    setActiveProject,
    createProject,
    deleteProject,
  }
})
