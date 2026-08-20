/**
 * ErrorBoundary — catches and displays errors with recovery options.
 *
 * Wraps content in an error boundary that shows a friendly error state
 * when the backend is disconnected or an unexpected error occurs.
 */

<script setup lang="ts">
import { ref, onErrorCaptured, provide } from 'vue'
import { useConnectionStore } from '@/stores/connection'
import { AlertTriangle, RefreshCw, WifiOff } from 'lucide-vue-next'

const connectionStore = useConnectionStore()

const error = ref<Error | null>(null)
const errorInfo = ref<string | null>(null)

onErrorCaptured((err, _instance, info) => {
  error.value = err
  errorInfo.value = info
  // Prevent error from propagating further
  return false
})

function retry(): void {
  error.value = null
  errorInfo.value = null
}

function reload(): void {
  window.location.reload()
}

// Provide error boundary context to children
provide('errorBoundary', {
  captureError: (err: Error, info?: string) => {
    error.value = err
    errorInfo.value = info ?? null
  },
  clearError: () => {
    error.value = null
    errorInfo.value = null
  },
})
</script>

<template>
  <div class="error-boundary">
    <!-- Disconnection banner -->
    <div
      v-if="connectionStore.isDisconnected && !error"
      class="disconnect-banner"
      role="alert"
    >
      <WifiOff :size="14" />
      <span>{{ connectionStore.lastError ?? 'Backend disconnected' }}</span>
      <button class="banner-action" @click="reload">
        <RefreshCw :size="12" />
        Retry
      </button>
    </div>

    <!-- Error state -->
    <div v-if="error" class="error-state" role="alert">
      <div class="error-card">
        <AlertTriangle :size="32" class="error-icon" />
        <h2 class="error-title">Something went wrong</h2>
        <p class="error-message">{{ error.message }}</p>
        <p v-if="errorInfo" class="error-detail">{{ errorInfo }}</p>
        <div class="error-actions">
          <button class="error-btn primary" @click="retry">
            <RefreshCw :size="14" />
            Try Again
          </button>
          <button class="error-btn secondary" @click="reload">
            Reload Page
          </button>
        </div>
      </div>
    </div>

    <!-- Normal content -->
    <slot v-else />
  </div>
</template>

<style scoped>
.error-boundary {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

/* ── Disconnect banner ────────────────────────────────────────────── */

.disconnect-banner {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
  padding: var(--density-space-2) var(--density-space-3);
  background: var(--color-warning-muted);
  color: var(--color-warning);
  font-size: var(--density-font-sm);
  border-bottom: 1px solid var(--color-warning);
}

.banner-action {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  margin-left: auto;
  padding: var(--density-space-1) var(--density-space-2);
  border: 1px solid var(--color-warning);
  border-radius: var(--density-radius-sm);
  background: transparent;
  color: var(--color-warning);
  font-size: var(--density-font-xs);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.banner-action:hover {
  background: var(--color-warning-muted);
}

/* ── Error state ──────────────────────────────────────────────────── */

.error-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--density-space-6);
}

.error-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  max-width: 400px;
  gap: var(--density-space-3);
}

.error-icon {
  color: var(--color-error);
}

.error-title {
  font-size: var(--density-font-xl);
  font-weight: 600;
  color: var(--text-primary);
}

.error-message {
  font-size: var(--density-font-md);
  color: var(--text-secondary);
}

.error-detail {
  font-size: var(--density-font-sm);
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  padding: var(--density-space-2);
  background: var(--surface-raised);
  border-radius: var(--density-radius-md);
  max-width: 100%;
  overflow-x: auto;
}

.error-actions {
  display: flex;
  gap: var(--density-space-2);
  margin-top: var(--density-space-2);
}

.error-btn {
  display: flex;
  align-items: center;
  gap: var(--density-space-1);
  padding: var(--density-space-2) var(--density-space-4);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-md);
  font-size: var(--density-font-sm);
  cursor: pointer;
  transition: background var(--transition-fast), border-color var(--transition-fast);
}

.error-btn.primary {
  background: var(--accent-primary);
  border-color: var(--accent-primary);
  color: var(--text-inverse);
}

.error-btn.primary:hover {
  background: var(--accent-primary-hover);
}

.error-btn.secondary {
  background: transparent;
  color: var(--text-primary);
}

.error-btn.secondary:hover {
  background: var(--surface-raised);
}
</style>
