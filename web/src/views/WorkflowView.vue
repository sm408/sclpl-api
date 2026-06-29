<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { getGateway } from '@/gateway'
import { useProjectStore } from '@/stores/project'
import type { WorkflowDef } from '@/types/api'
import { ArrowLeft, Play, Save, Trash2, Download, Loader2 } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const queryClient = useQueryClient()
const gateway = getGateway()
const projectId = computed(() => projectStore.activeProjectId)
const workflowId = computed(() => route.params.workflowId as string)

const { data: workflow, isLoading } = useQuery({
  queryKey: ['workflow', projectId, workflowId],
  queryFn: () => gateway.workflows.get(projectId.value!, workflowId.value),
  enabled: computed(() => !!projectId.value && !!workflowId.value),
})

const name = ref('')
const description = ref('')
const variablesText = ref('')
const stepsText = ref('')
const saveError = ref('')
const runStatus = ref<string | null>(null)

function syncForm(): void {
  if (!workflow.value) return
  name.value = workflow.value.name
  description.value = workflow.value.description ?? ''
  variablesText.value = JSON.stringify(workflow.value.variables ?? {}, null, 2)
  stepsText.value = JSON.stringify(workflow.value.steps ?? [], null, 2)
}

onMounted(() => {
  saveError.value = ''
  runStatus.value = null
  syncForm()
})

watch(() => workflow.value, syncForm)

const updateMutation = useMutation({
  mutationFn: () => {
    const variables = (() => {
      try { return JSON.parse(variablesText.value || '{}') } catch { throw new Error('Invalid variables JSON') }
    })()
    const steps = (() => {
      try { return JSON.parse(stepsText.value || '[]') } catch { throw new Error('Invalid steps JSON') }
    })()
    return gateway.workflows.update(projectId.value!, workflowId.value, {
      name: name.value,
      description: description.value,
      variables,
      steps,
    })
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['workflows'] })
    queryClient.invalidateQueries({ queryKey: ['workflow', projectId, workflowId] })
    saveError.value = ''
  },
  onError: (err: unknown) => {
    saveError.value = err instanceof Error ? err.message : 'Failed to save workflow'
  },
})

const deleteMutation = useMutation({
  mutationFn: () => gateway.workflows.delete(projectId.value!, workflowId.value),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['workflows'] })
    router.push('/workflows')
  },
})

const runMutation = useMutation({
  mutationFn: () => gateway.workflows.run(projectId.value!, workflowId.value),
  onSuccess: () => {
    runStatus.value = 'Run started'
  },
})

function handleSave(): void {
  saveError.value = ''
  updateMutation.mutate()
}

function handleDelete(): void {
  if (confirm('Delete this workflow?')) {
    deleteMutation.mutate()
  }
}

function handleRun(): void {
  runStatus.value = 'Running...'
  runMutation.mutate()
}

function exportWorkflow(): void {
  if (!workflow.value) return
  const payload = {
    id: workflow.value.id,
    name: workflow.value.name,
    description: workflow.value.description ?? '',
    variables: workflow.value.variables ?? {},
    steps: workflow.value.steps ?? [],
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${name.value.replace(/[^a-z0-9_-]/gi, '_').toLowerCase()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function goBack(): void {
  router.push('/workflows')
}
</script>

<template>
  <div class="workflow-editor">
    <header class="toolbar">
      <button class="btn btn-ghost" @click="goBack">
        <ArrowLeft :size="16" /> Back
      </button>
      <div class="actions">
        <button class="btn btn-ghost" @click="exportWorkflow">
          <Download :size="16" />
        </button>
        <button class="btn btn-ghost" @click="handleRun" :disabled="runMutation.isPending">
          <Play :size="16" /> Run
        </button>
        <button class="btn" @click="handleSave" :disabled="updateMutation.isPending">
          <Save :size="16" /> Save
        </button>
        <button class="btn btn-ghost danger" @click="handleDelete" :disabled="deleteMutation.isPending">
          <Trash2 :size="16" />
        </button>
      </div>
    </header>

    <div v-if="isLoading" class="state">
      <Loader2 class="spin" :size="18" />
      <span>Loading workflow...</span>
    </div>

    <div v-else-if="!workflow" class="state">
      <p>Workflow not found.</p>
    </div>

    <form v-else class="form" @submit.prevent="handleSave">
      <label class="field">
        <span>Name</span>
        <input v-model="name" />
      </label>

      <label class="field">
        <span>Description</span>
        <input v-model="description" />
      </label>

      <label class="field">
        <span>Variables (JSON)</span>
        <textarea v-model="variablesText" class="code" rows="4"></textarea>
      </label>

      <label class="field">
        <span>Steps (JSON)</span>
        <textarea v-model="stepsText" class="code" rows="10"></textarea>
      </label>

      <p v-if="saveError" class="error">{{ saveError }}</p>
      <p v-if="runStatus" class="status">{{ runStatus }}</p>
    </form>
  </div>
</template>

<style scoped>
.workflow-editor {
  display: flex;
  flex-direction: column;
  gap: var(--density-space-4);
  max-width: 960px;
  margin: 0 auto;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.actions {
  display: flex;
  gap: var(--density-space-2);
}

.state {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
  color: var(--text-secondary);
  padding: var(--density-space-4);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.form {
  display: flex;
  flex-direction: column;
  gap: var(--density-space-4);
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

.field input,
.field .code {
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-sm);
  background: var(--surface-base);
  color: var(--text-primary);
  font-size: var(--density-font-sm);
  padding: var(--density-space-2) var(--density-space-3);
  outline: none;
}

.field .code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  resize: vertical;
}

.field input:focus,
.field .code:focus {
  border-color: var(--accent-primary);
}

.error {
  color: var(--semantic-error);
  font-size: var(--density-font-sm);
}

.status {
  color: var(--accent-primary);
  font-size: var(--density-font-sm);
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
</style>
