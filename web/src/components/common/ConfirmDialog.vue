/**
 * ConfirmDialog — reusable confirmation modal.
 *
 * Shows a title, message, and action buttons. Keyboard-accessible
 * with Escape to cancel and Enter to confirm.
 */

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'

const props = withDefaults(defineProps<{
  open: boolean
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: 'default' | 'danger'
}>(), {
  confirmLabel: 'Confirm',
  cancelLabel: 'Cancel',
  variant: 'default',
})

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const dialogRef = ref<HTMLElement | null>(null)
const confirmRef = ref<HTMLButtonElement | null>(null)

watch(
  () => props.open,
  async (isOpen) => {
    if (isOpen) {
      await nextTick()
      confirmRef.value?.focus()
    }
  },
)

function handleKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape') {
    e.preventDefault()
    emit('cancel')
  }
}

function handleBackdropClick(): void {
  emit('cancel')
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="dialog">
      <div
        v-if="open"
        class="dialog-backdrop"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
        @click.self="handleBackdropClick"
      >
        <div ref="dialogRef" class="dialog-container">
          <h2 class="dialog-title">{{ title }}</h2>
          <p class="dialog-message">{{ message }}</p>
          <div class="dialog-actions">
            <button
              class="dialog-btn cancel"
              @click="emit('cancel')"
            >
              {{ cancelLabel }}
            </button>
            <button
              ref="confirmRef"
              class="dialog-btn confirm"
              :class="variant"
              @click="emit('confirm')"
            >
              {{ confirmLabel }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 300;
}

.dialog-container {
  width: 100%;
  max-width: 400px;
  background: var(--surface-overlay);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-lg);
  box-shadow: var(--shadow-overlay);
  padding: var(--density-space-5);
  display: flex;
  flex-direction: column;
  gap: var(--density-space-3);
}

.dialog-title {
  font-size: var(--density-font-lg);
  font-weight: 600;
  color: var(--text-primary);
}

.dialog-message {
  font-size: var(--density-font-sm);
  color: var(--text-secondary);
  line-height: 1.5;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--density-space-2);
  margin-top: var(--density-space-2);
}

.dialog-btn {
  padding: var(--density-space-2) var(--density-space-4);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-md);
  font-size: var(--density-font-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.dialog-btn.cancel {
  background: transparent;
  color: var(--text-primary);
}

.dialog-btn.cancel:hover {
  background: var(--surface-raised);
}

.dialog-btn.confirm {
  background: var(--accent-primary);
  border-color: var(--accent-primary);
  color: var(--text-inverse);
}

.dialog-btn.confirm:hover {
  background: var(--accent-primary-hover);
}

.dialog-btn.confirm.danger {
  background: var(--color-error);
  border-color: var(--color-error);
}

.dialog-btn.confirm.danger:hover {
  opacity: 0.9;
}

/* Transitions */
.dialog-enter-active,
.dialog-leave-active {
  transition: opacity var(--transition-normal);
}

.dialog-enter-active .dialog-container,
.dialog-leave-active .dialog-container {
  transition: transform var(--transition-normal), opacity var(--transition-normal);
}

.dialog-enter-from,
.dialog-leave-to {
  opacity: 0;
}

.dialog-enter-from .dialog-container,
.dialog-leave-to .dialog-container {
  transform: scale(0.95);
  opacity: 0;
}
</style>
