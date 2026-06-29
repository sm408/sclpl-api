<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { getGateway } from '@/gateway'
import { useProjectStore } from '@/stores/project'
import { useTabsStore } from '@/stores/tabs'
import type { WorkflowDef } from '@/types/api'
import { Play, Plus, Trash2, Download, Loader2 } from 'lucide-vue-next'

const router = useRouter()
const projectStore = useProjectStore()
const tabsStore = useTabsStore()
const queryClient = useQueryClient()
const gateway = getGateway()
const projectId = computed(() => projectStore.activeProjectId)

const { data: workflows, isLoading } = useQuery({
  queryKey: ['workflows', projectId],
  queryFn: () => gateway.workflows.list(projectId.value!),
  enabled: computed(() => !!projectId.value),
})

const showCreateDialog = ref(false)
const newWorkflowName = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

const createMutation = useMutation({
  mutationFn: () =>
    gateway.workflows.create(projectId.value!, {
      name: newWorkflowName.value,
      description: '',
    }),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['workflows'] })
    showCreateDialog.value = false
    newWorkflowName.value = ''
  },
})

const deleteMutation = useMutation({
  mutationFn: (id: string) => gateway.workflows.delete(projectId.value!, id),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workflows'] }),
})

const runMutation = useMutation({
  mutationFn: (id: string) => gateway.workflows.run(projectId.value!, id),
})

function openCreate(): void {
  newWorkflowName.value = ''
  showCreateDialog.value = true
}

function handleCreate(): void {
  if (!newWorkflowName.value.trim()) return
  createMutation.mutate()
}

function openWorkflow(wf: WorkflowDef): void {
  tabsStore.openTab({
    id: `workflow-${wf.id}`,
    label: wf.name,
    kind: 'workflow',
    route: `/workflows/${wf.id}`,
    dirty: false,
    projectId: projectId.value || '',
    pinned: false,
  })
  router.push(`/workflows/${wf.id}`)
}

function handleRun(wf: WorkflowDef): void {
  runMutation.mutate(wf.id)
}

function handleDelete(wf: WorkflowDef): void {
  if (confirm(`Delete workflow "${wf.name}"?`)) {
    deleteMutation.mutate(wf.id)
  }
}

function exportWorkflow(wf: WorkflowDef): void {
  const payload = {
    id: wf.id,
    name: wf.name,
    description: wf.description ?? '',
    variables: wf.variables ?? {},
    steps: wf.steps ?? [],
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${wf.name.replace(/[^a-z0-9_-]/gi, '_').toLowerCase()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

async function importExample(path: string): Promise<void> {
  const response = await fetch(path)
  if (!response.ok) {
    alert('Failed to load example workflow')
    return
  }
  const data = (await response.json()) as WorkflowDef
  await gateway.workflows.create(projectId.value!, {
    name: data.name,
    description: data.description,
    definition: data,
    sclpllSource: '',
  })
  queryClient.invalidateQueries({ queryKey: ['workflows'] })
}

async function importFile(event: Event): Promise<void> {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  const text = await file.text()
  const data = JSON.parse(text) as WorkflowDef
  await gateway.workflows.create(projectId.value!, {
    name: data.name,
    description: data.description,
    definition: data,
    sclpllSource: '',
  })
  queryClient.invalidateQueries({ queryKey: ['workflows'] })
  if (fileInput.value) fileInput.value.value = ''
}

const examples = computed(() => [
  { name: 'Weather Pipeline', path: '/examples/weather_pipeline/workflow.json' },
  { name: 'Getting Started', path: '/examples/getting-started/workflow.json' },
  { name: 'API Testing', path: '/examples/api-testing/workflow.json' },
  { name: 'Data Pipeline', path: '/examples/data-pipeline/workflow.json' },
  { name: 'Financial Pipeline', path: '/examples/financial_pipeline/workflow.json' },
  { name: 'Job Tracker', path: '/examples/job_tracker_pipeline/workflow.json' },
  { name: 'Multi Provider', path: '/examples/multi_provider_aggregator/workflow.json' },
  { name: 'Advanced Logic', path: '/examples/advanced_logic/workflow.json' },
])
</script>

<template>
  <div class="workflows">
    <header class="toolbar">
      <h1>Workflows</h1>
      <div class="actions">
        <button class="btn" @click="openCreate">
          <Plus :size="16" /> New
        </button>
        <label class="btn">
          <Upload :size="16" /> Import
          <input
            ref="fileInput"
            type="file"
            accept=".json"
            class="file-input"
            @change="importFile"
          />
        </label>
      </div>
    </header>

    <div v-if="isLoading" class="state">
      <Loader2 class="spin" :size="18" />
      <span>Loading workflows...</span>
    </div>

    <div v-else-if="!workflows?.length" class="state empty">
      <p>No workflows yet.</p>
      <button class="btn" @click="openCreate">Create workflow</button>
      <p class="hint">Or import an example from the examples directory.</p>
    </div>

    <div v-else class="grid">
      <article v-for="wf in workflows" :key="wf.id" class="card">
        <div class="card-header">
          <h3 @click="openWorkflow(wf)">{{ wf.name }}</h3>
          <p v-if="wf.description">{{ wf.description }}</p>
        </div>
        <div class="card-meta">
          <span>{{ (wf.steps ?? []).length }} steps</span>
        </div>
        <div class="card-actions">
          <button class="btn btn-ghost" @click="openWorkflow(wf)">
            Open
          </button>
          <button class="btn btn-ghost" @click="handleRun(wf)">
            <Play :size="16" /> Run
          </button>
          <button class="btn btn-ghost" @click="exportWorkflow(wf)">
            <Download :size="16" />
          </button>
          <button class="btn btn-ghost danger" @click="handleDelete(wf)">
            <Trash2 :size="16" />
          </button>
        </div>
      </article>
    </div>

    <Teleport v-if="showCreateDialog" to="body">
      <div class="overlay" @click.self="showCreateDialog = false">
        <div class="dialog">
          <h2>New Workflow</h2>
          <label class="field">
            <span>Name</span>
            <input v-model="newWorkflowName" placeholder="Workflow name" />
          </label>
          <div class="actions">
            <button class="btn btn-ghost" @click="showCreateDialog = false">Cancel</button>
            <button class="btn" :disabled="!newWorkflowName.trim()" @click="handleCreate">
              Create
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.workflows {
  display: flex;
  flex-direction: column;
  gap: var(--density-space-4);
  padding: var(--density-space-4);
  max-width: 1200px;
  margin: 0 auto;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.toolbar h1 {
  margin: 0;
  font-size: var(--density-font-xl);
  font-weight: 700;
}

.actions {
  display: flex;
  gap: var(--density-space-2);
  align-items: center;
}

.file-input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: inherit;
}

.state {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
  color: var(--text-secondary);
  padding: var(--density-space-4);
  border: 1px dashed var(--surface-border);
  border-radius: var(--density-radius-md);
  flex-direction: column;
  align-items: stretch;
  gap: var(--density-space-3);
  text-align: center;
}

.state.empty p {
  margin: 0;
}

.state .hint {
  color: var(--text-tertiary);
  font-size: var(--density-font-sm);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--density-space-4);
}

.card {
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-lg);
  padding: var(--density-space-4);
  display: flex;
  flex-direction: column;
  gap: var(--density-space-3);
  background: var(--surface-base);
}

.card-header h3 {
  margin: 0;
  font-size: var(--density-font-lg);
  font-weight: 600;
  cursor: pointer;
}

.card-header h3:hover {
  color: var(--accent-primary);
}

.card-header p {
  margin: var(--density-space-1) 0 0;
  color: var(--text-secondary);
  font-size: var(--density-font-sm);
}

.card-meta {
  font-size: var(--density-font-xs);
  color: var(--text-tertiary);
}

.card-actions {
  display: flex;
  gap: var(--density-space-2);
  flex-wrap: wrap;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: var(--density-space-2);
  padding: var(--density-space-2) var(--density-space-3);
  border: none;
  border-radius: var(--density-radius-sm);
  background: var(--accent-primary);
  color: white;
  font-size: var(--density-font-sm);
  font-weight: 500;
  cursor: pointer;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-ghost {
  border: 1px solid var(--surface-border);
  background: transparent;
  color: var(--text-primary);
}

.btn-ghost:hover {
  background: var(--surface-raised);
}

.btn-ghost.danger {
  color: var(--semantic-error);
  border-color: var(--semantic-error);
}

.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog {
  width: 420px;
  background: var(--surface-overlay);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-lg);
  padding: var(--density-space-5);
  display: flex;
  flex-direction: column;
  gap: var(--density-space-4);
}

.dialog h2 {
  margin: 0;
  font-size: var(--density-font-lg);
  font-weight: 600;
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--density-space-1);
}

.field span {
  font-size: var(--density-font-sm);
  color: var(--text-secondary);
}

.field input {
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-sm);
  background: var(--surface-base);
  color: var(--text-primary);
  font-size: var(--density-font-sm);
  padding: var(--density-space-2) var(--density-space-3);
  outline: none;
}

.field input:focus {
  border-color: var(--accent-primary);
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--density-space-2);
}
</style>
