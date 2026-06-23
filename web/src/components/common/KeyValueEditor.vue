/**
 * KeyValueEditor — editable key-value pair list.
 *
 * Used for headers, query params, and environment variables.
 * Supports add, remove, toggle enabled, and drag reorder.
 */

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Plus, Trash2, GripVertical } from 'lucide-vue-next'

export interface KeyValueEntry {
  key: string
  value: string
  enabled: boolean
}

const props = withDefaults(
  defineProps<{
    modelValue: KeyValueEntry[]
    keyLabel?: string
    valueLabel?: string
    showEnabled?: boolean
    showSecret?: boolean
    placeholder?: string
  }>(),
  {
    keyLabel: 'Key',
    valueLabel: 'Value',
    showEnabled: true,
    showSecret: false,
    placeholder: 'Add a new entry...',
  },
)

const emit = defineEmits<{
  'update:modelValue': [entries: KeyValueEntry[]]
}>()

const entries = ref<KeyValueEntry[]>([...props.modelValue])

watch(
  () => props.modelValue,
  (val) => {
    entries.value = [...val]
  },
  { deep: true },
)

function addEntry(): void {
  entries.value.push({ key: '', value: '', enabled: true })
  emitChange()
}

function removeEntry(index: number): void {
  entries.value.splice(index, 1)
  emitChange()
}

function toggleEntry(index: number): void {
  const entry = entries.value[index]
  if (entry) {
    entry.enabled = !entry.enabled
    emitChange()
  }
}

function updateKey(index: number, key: string): void {
  const entry = entries.value[index]
  if (entry) {
    entry.key = key
    emitChange()
  }
}

function updateValue(index: number, value: string): void {
  const entry = entries.value[index]
  if (entry) {
    entry.value = value
    emitChange()
  }
}

function emitChange(): void {
  emit('update:modelValue', entries.value.map((e) => ({ ...e })))
}

// Drag-and-drop state
const dragIndex = ref<number | null>(null)

function onDragStart(index: number, e: DragEvent): void {
  dragIndex.value = index
  e.dataTransfer!.effectAllowed = 'move'
}

function onDragOver(index: number, e: DragEvent): void {
  e.preventDefault()
  e.dataTransfer!.dropEffect = 'move'
}

function onDrop(index: number): void {
  if (dragIndex.value === null || dragIndex.value === index) return
  const item = entries.value.splice(dragIndex.value, 1)[0]
  if (item) {
    entries.value.splice(index, 0, item)
    emitChange()
  }
  dragIndex.value = null
}

function onDragEnd(): void {
  dragIndex.value = null
}
</script>

<template>
  <div class="kv-editor">
    <div class="kv-header">
      <span v-if="showEnabled" class="kv-col-toggle" />
      <span class="kv-col-drag" />
      <span class="kv-col-key">{{ keyLabel }}</span>
      <span class="kv-col-value">{{ valueLabel }}</span>
      <span class="kv-col-action" />
    </div>

    <div v-if="entries.length === 0" class="kv-empty">
      No entries
    </div>

    <div
      v-for="(entry, index) in entries"
      :key="index"
      class="kv-row"
      :class="{ disabled: !entry.enabled, dragging: dragIndex === index }"
      draggable="true"
      @dragstart="onDragStart(index, $event)"
      @dragover="onDragOver(index, $event)"
      @drop="onDrop(index)"
      @dragend="onDragEnd"
    >
      <button
        v-if="showEnabled"
        class="kv-toggle"
        :class="{ active: entry.enabled }"
        :title="entry.enabled ? 'Disable' : 'Enable'"
        @click="toggleEntry(index)"
      >
        <span class="toggle-dot" />
      </button>

      <span class="kv-drag-handle">
        <GripVertical :size="12" />
      </span>

      <input
        class="kv-input kv-key"
        type="text"
        :value="entry.key"
        :placeholder="keyLabel"
        @input="updateKey(index, ($event.target as HTMLInputElement).value)"
      />

      <input
        class="kv-input kv-value"
        type="text"
        :value="entry.value"
        :placeholder="valueLabel"
        @input="updateValue(index, ($event.target as HTMLInputElement).value)"
      />

      <button
        class="kv-remove"
        title="Remove"
        @click="removeEntry(index)"
      >
        <Trash2 :size="14" />
      </button>
    </div>

    <button class="kv-add" @click="addEntry">
      <Plus :size="14" />
      <span>{{ placeholder }}</span>
    </button>
  </div>
</template>

<style scoped>
.kv-editor {
  display: flex;
  flex-direction: column;
  gap: 0;
  font-size: var(--density-font-sm);
}

.kv-header {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  padding: var(--density-space-1) var(--density-space-2);
  color: var(--text-tertiary);
  font-size: var(--density-font-xs);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--surface-border-subtle);
}

.kv-col-toggle { width: 24px; flex-shrink: 0; }
.kv-col-drag { width: 16px; flex-shrink: 0; }
.kv-col-key { flex: 1; min-width: 80px; }
.kv-col-value { flex: 2; min-width: 120px; }
.kv-col-action { width: 28px; flex-shrink: 0; }

.kv-empty {
  padding: var(--density-space-3);
  color: var(--text-tertiary);
  text-align: center;
  font-style: italic;
}

.kv-row {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  padding: var(--density-space-1) var(--density-space-2);
  border-bottom: 1px solid var(--surface-border-subtle);
  transition: opacity var(--transition-fast);
}

.kv-row.disabled {
  opacity: 0.5;
}

.kv-row.dragging {
  opacity: 0.4;
  background: var(--surface-raised);
}

.kv-toggle {
  width: 24px;
  height: 16px;
  border: none;
  border-radius: var(--density-radius-full);
  background: var(--surface-border);
  cursor: pointer;
  position: relative;
  flex-shrink: 0;
  transition: background var(--transition-fast);
  padding: 0;
}

.kv-toggle.active {
  background: var(--accent-primary);
}

.toggle-dot {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: white;
  transition: transform var(--transition-fast);
}

.kv-toggle.active .toggle-dot {
  transform: translateX(8px);
}

.kv-drag-handle {
  width: 16px;
  flex-shrink: 0;
  color: var(--text-tertiary);
  cursor: grab;
  display: flex;
  align-items: center;
  justify-content: center;
}

.kv-drag-handle:active {
  cursor: grabbing;
}

.kv-input {
  border: 1px solid transparent;
  border-radius: var(--density-radius-sm);
  background: transparent;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: var(--density-font-sm);
  padding: var(--density-space-1) var(--density-space-2);
  outline: none;
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.kv-input:focus {
  border-color: var(--accent-primary);
  background: var(--surface-base);
}

.kv-input::placeholder {
  color: var(--text-disabled);
}

.kv-key {
  flex: 1;
  min-width: 80px;
}

.kv-value {
  flex: 2;
  min-width: 120px;
}

.kv-remove {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--density-radius-sm);
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  flex-shrink: 0;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.kv-remove:hover {
  color: var(--semantic-error);
  background: var(--surface-raised);
}

.kv-add {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
  padding: var(--density-space-2) var(--density-space-3);
  border: 1px dashed var(--surface-border);
  border-radius: var(--density-radius-sm);
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  font-size: var(--density-font-sm);
  transition: color var(--transition-fast), border-color var(--transition-fast);
}

.kv-add:hover {
  color: var(--accent-primary);
  border-color: var(--accent-primary);
}
</style>
