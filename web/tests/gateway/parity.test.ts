/**
 * Parity tests: demonstrate identical feature behavior through
 * mock and HTTP adapters.
 *
 * These tests verify that a feature (e.g., listing projects) produces
 * the same shape of data regardless of which gateway mode is active.
 * This ensures components work identically in both modes.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createMockGateway } from '@/gateway/mock'
import { createHttpGateway } from '@/gateway/http'
import { StudioError } from '@/gateway/error'
import type { StudioGateway } from '@/gateway/types'

// ── Mock fetch for HTTP gateway ────────────────────────────────────────

let originalFetch: typeof globalThis.fetch

function setupHttpFetch(): void {
  globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    if (init?.signal?.aborted) {
      return Promise.reject(new DOMException('Aborted', 'AbortError'))
    }

    // Health
    if (url.includes('/health')) {
      return Promise.resolve(
        new Response(JSON.stringify({ status: 'ok', version: '0.1.0', schemaVersion: 4 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    }

    // Projects list
    if (url.endsWith('/api/v1/projects') && (!init?.method || init.method === 'GET')) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            items: [
              { id: 'p1', name: 'Default', description: '', rootPath: '', isDefault: true, createdAt: null, updatedAt: null },
              { id: 'p2', name: 'Workspace', description: 'Test', rootPath: '', isDefault: false, createdAt: '2025-01-01', updatedAt: '2025-01-01' },
            ],
            total: 2,
            nextCursor: null,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
    }

    // Operations list
    if (url.includes('/api/v1/operations') && !url.includes('/events/') && (!init?.method || init.method === 'GET')) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            items: [
              { id: 'op1', projectId: 'p1', type: 'workflow_run', status: 'queued', progress: 0, createdAt: '2025-01-01', startedAt: null, finishedAt: null, result: null, error: null },
              { id: 'op2', projectId: 'p1', type: 'workflow_run', status: 'running', progress: 0.5, createdAt: '2025-01-01', startedAt: '2025-01-01', finishedAt: null, result: null, error: null },
              { id: 'op3', projectId: 'p1', type: 'workflow_run', status: 'succeeded', progress: 1, createdAt: '2025-01-01', startedAt: '2025-01-01', finishedAt: '2025-01-01', result: { output: 'ok' }, error: null },
            ],
            total: 3,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
    }

    // Default 404
    return Promise.resolve(
      new Response(
        JSON.stringify({ error: { code: 'NOT_FOUND', message: 'Not found', fieldErrors: [], correlationId: '' } }),
        { status: 404, headers: { 'Content-Type': 'application/json' } },
      ),
    )
  }) as unknown as typeof globalThis.fetch
}

beforeEach(() => {
  originalFetch = globalThis.fetch
})

afterEach(() => {
  globalThis.fetch = originalFetch
})

// ── Parity tests ───────────────────────────────────────────────────────

describe('Gateway parity: mock vs HTTP', () => {
  let mockGw: StudioGateway
  let httpGw: StudioGateway

  beforeEach(() => {
    mockGw = createMockGateway()
    setupHttpFetch()
    httpGw = createHttpGateway('http://localhost:8000')
  })

  it('health.check() returns the same shape', async () => {
    const [mockHealth, httpHealth] = await Promise.all([
      mockGw.health.check(),
      httpGw.health.check(),
    ])

    // Both return HealthResponse
    expect(typeof mockHealth.status).toBe('string')
    expect(typeof httpHealth.status).toBe('string')
    expect(typeof mockHealth.version).toBe('string')
    expect(typeof httpHealth.version).toBe('string')
    expect(typeof mockHealth.schemaVersion).toBe('number')
    expect(typeof httpHealth.schemaVersion).toBe('number')
  })

  it('projects.list() returns arrays of Project', async () => {
    const [mockProjects, httpProjects] = await Promise.all([
      mockGw.projects.list(),
      httpGw.projects.list(),
    ])

    // Both return arrays
    expect(Array.isArray(mockProjects)).toBe(true)
    expect(Array.isArray(httpProjects)).toBe(true)

    // Both have the same Project shape
    for (const p of [...mockProjects, ...httpProjects]) {
      expect(typeof p.id).toBe('string')
      expect(typeof p.name).toBe('string')
      expect(typeof p.description).toBe('string')
      expect(typeof p.isDefault).toBe('boolean')
    }
  })

  it('runs.list() returns arrays of Operation', async () => {
    const [mockOps, httpOps] = await Promise.all([
      mockGw.runs.list('proj-default-001'),
      httpGw.runs.list('p1'),
    ])

    expect(Array.isArray(mockOps)).toBe(true)
    expect(Array.isArray(httpOps)).toBe(true)

    // Both have the same Operation shape
    for (const op of [...mockOps, ...httpOps]) {
      expect(typeof op.id).toBe('string')
      expect(typeof op.projectId).toBe('string')
      expect(typeof op.type).toBe('string')
      expect(typeof op.status).toBe('string')
      expect(typeof op.progress).toBe('number')
      expect(typeof op.createdAt).toBe('string')
    }
  })

  it('projects.get() throws StudioError with same shape for not-found', async () => {
    const [mockErr, httpErr] = await Promise.allSettled([
      mockGw.projects.get('nonexistent'),
      httpGw.projects.get('nonexistent'),
    ])

    expect(mockErr.status).toBe('rejected')
    expect(httpErr.status).toBe('rejected')

    if (mockErr.status === 'rejected' && httpErr.status === 'rejected') {
      expect(mockErr.reason).toBeInstanceOf(StudioError)
      expect(httpErr.reason).toBeInstanceOf(StudioError)
      expect((mockErr.reason as StudioError).code).toBe('NOT_FOUND')
      expect((httpErr.reason as StudioError).code).toBe('NOT_FOUND')
      expect((mockErr.reason as StudioError).status).toBe(404)
      expect((httpErr.reason as StudioError).status).toBe(404)
    }
  })

  it('abort signal is respected by both adapters', async () => {
    const controller = new AbortController()
    controller.abort()

    const [mockErr, httpErr] = await Promise.allSettled([
      mockGw.health.check({ signal: controller.signal }),
      httpGw.health.check({ signal: controller.signal }),
    ])

    expect(mockErr.status).toBe('rejected')
    expect(httpErr.status).toBe('rejected')
    expect((mockErr.reason as StudioError).code).toBe('ABORTED')
    expect((httpErr.reason as StudioError).code).toBe('ABORTED')
  })

  it('events.subscribe() returns an unsubscribe function in both', () => {
    const mockUnsub = mockGw.events.subscribe('p1', () => {})
    expect(typeof mockUnsub).toBe('function')
    mockUnsub()

    // HTTP adapter uses EventSource which is not available in happy-dom
    // Skip the HTTP test in non-browser environments
    if (typeof globalThis.EventSource !== 'undefined') {
      const httpUnsub = httpGw.events.subscribe('p1', () => {})
      expect(typeof httpUnsub).toBe('function')
      httpUnsub()
    }
  })
})
