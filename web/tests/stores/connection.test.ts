/**
 * Connection store tests.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useConnectionStore } from '@/stores/connection'

describe('ConnectionStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts in connecting state', () => {
    const store = useConnectionStore()
    expect(store.state).toBe('connecting')
    expect(store.isConnected).toBe(false)
    expect(store.isDisconnected).toBe(false)
  })

  it('transitions to connected', () => {
    const store = useConnectionStore()
    store.setConnected('0.1.0')
    expect(store.state).toBe('connected')
    expect(store.version).toBe('0.1.0')
    expect(store.isConnected).toBe(true)
    expect(store.isDisconnected).toBe(false)
    expect(store.lastError).toBeNull()
    expect(store.lastChecked).toBeInstanceOf(Date)
    expect(store.reconnectAttempts).toBe(0)
  })

  it('transitions to disconnected', () => {
    const store = useConnectionStore()
    store.setDisconnected('Connection refused')
    expect(store.state).toBe('disconnected')
    expect(store.lastError).toBe('Connection refused')
    expect(store.isDisconnected).toBe(true)
    expect(store.reconnectAttempts).toBe(1)
  })

  it('transitions to error', () => {
    const store = useConnectionStore()
    store.setError('Timeout')
    expect(store.state).toBe('error')
    expect(store.lastError).toBe('Timeout')
    expect(store.isDisconnected).toBe(true)
    expect(store.reconnectAttempts).toBe(1)
  })

  it('transitions back to connecting', () => {
    const store = useConnectionStore()
    store.setDisconnected()
    store.setConnecting()
    expect(store.state).toBe('connecting')
  })

  it('increments reconnect attempts', () => {
    const store = useConnectionStore()
    store.setDisconnected()
    store.setDisconnected()
    store.setError('err')
    expect(store.reconnectAttempts).toBe(3)
  })

  it('resets reconnect attempts on successful connection', () => {
    const store = useConnectionStore()
    store.setDisconnected()
    store.setDisconnected()
    store.setConnected('0.1.0')
    expect(store.reconnectAttempts).toBe(0)
  })

  it('provides default disconnect message', () => {
    const store = useConnectionStore()
    store.setDisconnected()
    expect(store.lastError).toBe('Backend unavailable')
  })

  it('updates lastChecked on state changes', () => {
    const store = useConnectionStore()
    const before = new Date()
    store.setConnected('0.1.0')
    expect(store.lastChecked!.getTime()).toBeGreaterThanOrEqual(before.getTime())
  })
})
