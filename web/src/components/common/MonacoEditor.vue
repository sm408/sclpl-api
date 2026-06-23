/**
 * MonacoEditor — thin wrapper around monaco-editor for Vue.
 *
 * Mounts a Monaco editor instance into the container div on mount,
 * syncs value changes via v-model, and disposes on unmount.
 */

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, shallowRef } from 'vue'
import * as monaco from 'monaco-editor'

const props = withDefaults(defineProps<{
  modelValue: string
  language?: string
  readOnly?: boolean
  minimap?: boolean
  lineNumbers?: 'on' | 'off' | 'relative' | 'interval'
  tabSize?: number
  placeholder?: string
}>(), {
  language: 'python',
  readOnly: false,
  minimap: false,
  lineNumbers: 'on',
  tabSize: 4,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const editor = shallowRef<monaco.editor.IStandaloneCodeEditor | null>(null)

onMounted(() => {
  if (!containerRef.value) return

  editor.value = monaco.editor.create(containerRef.value, {
    value: props.modelValue,
    language: props.language,
    readOnly: props.readOnly,
    minimap: { enabled: props.minimap },
    lineNumbers: props.lineNumbers,
    tabSize: props.tabSize,
    automaticLayout: true,
    scrollBeyondLastLine: false,
    wordWrap: 'on',
    fontFamily: "'Cascadia Code', 'Fira Code', Consolas, monospace",
    fontSize: 13,
    lineHeight: 22,
    padding: { top: 12, bottom: 12 },
    renderLineHighlight: 'line',
    smoothScrolling: true,
    cursorSmoothCaretAnimation: 'on',
    bracketPairColorization: { enabled: true },
    theme: 'vs-dark',
  })

  editor.value.onDidChangeModelContent(() => {
    const val = editor.value?.getValue() ?? ''
    emit('update:modelValue', val)
  })
})

watch(() => props.modelValue, (newVal) => {
  if (editor.value && editor.value.getValue() !== newVal) {
    editor.value.setValue(newVal)
  }
})

watch(() => props.readOnly, (ro) => {
  editor.value?.updateOptions({ readOnly: ro })
})

onBeforeUnmount(() => {
  editor.value?.dispose()
})
</script>

<template>
  <div ref="containerRef" class="monaco-container" />
</template>

<style scoped>
.monaco-container {
  width: 100%;
  height: 100%;
  min-height: 200px;
}
</style>
