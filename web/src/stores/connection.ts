/**
 * Connection store — tracks backend health and SSE connection status.
 *
 * Provides a reactive connection state used by the top bar status
 * indicator and error boundaries.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'error'

export const useConnectionStore = defineStore('connection', () => {
  // ── State ──────────────────────────────────────────────────────────────

  const state = ref<ConnectionState>('connecting')
  const version = ref<string | null>(null)
  const lastError = ref<string | null>(null)
  const lastChecked = ref<Date | null>(null)
  const reconnectAttempts = ref(0)

  // ── Derived ────────────────────────────────────────────────────────────

  const isConnected = computed(() => state.value === 'connected')
  const isDisconnected = computed(
    () => state.value === 'disconnected' || state.value === 'error',
  )

  // ── Actions ────────────────────────────────────────────────────────────

  function setConnected(ver: string): void {
    state.value = 'connected'
    version.value = ver
    lastError.value = null
    lastChecked.value = new Date()
    reconnectAttempts.value = 0
  }

  function setConnecting(): void {
    state.value = 'connecting'
    lastChecked.value = new Date()
  }

  function setDisconnected(error?: string): void {
    state.value = 'disconnected'
    lastError.value = error ?? 'Backend unavailable'
    lastChecked.value = new Date()
    reconnectAttempts.value++
  }

  function setError(error: string): void {
    state.value = 'error'
    lastError.value = error
    lastChecked.value = new Date()
    reconnectAttempts.value++
  }

  return {
    // State
    state,
    version,
    lastError,
    lastChecked,
    reconnectAttempts,
    // Derived
    isConnected,
    isDisconnected,
    // Actions
    setConnected,
    setConnecting,
    setDisconnected,
    setError,
  }
})
