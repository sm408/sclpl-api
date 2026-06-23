/**
 * Tests for the HTTP gateway adapter.
 *
 * Uses a mocked global fetch to test the HTTP adapter without
 * requiring a running backend. Verifies normalization, error
 * handling, and abort support.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createHttpGateway } from '@/gateway/http'
import { StudioError } from '@/gateway/error'
import type { StudioGateway } from '@/gateway/types'

// ── Mock fetch setup ───────────────────────────────────────────────────

type FetchMock = ReturnType<typeof vi.fn>

interface MockResponse {
  url: string | RegExp
  method?: string
  status: number
  body: unknown
}

let fetchMock: FetchMock
let originalFetch: typeof globalThis.fetch

function mockFetch(responses: MockResponse[]) {
  fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    // Check abort
    if (init?.signal?.aborted) {
      return Promise.reject(new DOMException('The operation was aborted.', 'AbortError'))
    }

    const requestMethod = init?.method ?? 'GET'

    for (const resp of responses) {
      const urlMatches =
        typeof resp.url === 'string' ? url.includes(resp.url) : resp.url.test(url)
      const methodMatches = !resp.method || resp.method === requestMethod

      if (urlMatches && methodMatches) {
        return Promise.resolve(
          new Response(JSON.stringify(resp.body), {
            status: resp.status,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }
    }

    // Default: 404
    return Promise.resolve(
      new Response(
        JSON.stringify({
          error: { code: 'NOT_FOUND', message: 'Not found', fieldErrors: [], correlationId: '' },
        }),
        { status: 404, headers: { 'Content-Type': 'application/json' } },
      ),
    )
  })

  globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch
}

beforeEach(() => {
  originalFetch = globalThis.fetch
})

afterEach(() => {
  globalThis.fetch = originalFetch
})

// ── Tests ──────────────────────────────────────────────────────────────

describe('HttpGateway', () => {
  let gw: StudioGateway

  describe('health', () => {
    it('returns health response', async () => {
      mockFetch([
        { url: '/health', status: 200, body: { status: 'ok', version: '0.1.0', schemaVersion: 4 } },
      ])
      gw = createHttpGateway('http://localhost:8000')

      const health = await gw.health.check()
      expect(health.status).toBe('ok')
      expect(health.version).toBe('0.1.0')
      expect(fetchMock).toHaveBeenCalledOnce()
    })
  })

  describe('projects', () => {
    it('lists projects from paginated response', async () => {
      mockFetch([
        {
          url: '/api/v1/projects',
          method: 'GET',
          status: 200,
          body: {
            items: [
              { id: 'p1', name: 'Default', description: '', rootPath: '', isDefault: true, createdAt: null, updatedAt: null },
            ],
            total: 1,
            nextCursor: null,
          },
        },
      ])
      gw = createHttpGateway('http://localhost:8000')

      const projects = await gw.projects.list()
      expect(projects).toHaveLength(1)
      expect(projects[0]!.name).toBe('Default')
    })

    it('creates a project', async () => {
      mockFetch([
        {
          url: '/api/v1/projects',
          method: 'POST',
          status: 201,
          body: { id: 'p2', name: 'Test', description: '', rootPath: '', isDefault: false, createdAt: '2025-01-01', updatedAt: '2025-01-01' },
        },
      ])
      gw = createHttpGateway('http://localhost:8000')

      const project = await gw.projects.create({ name: 'Test' })
      expect(project.id).toBe('p2')
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/projects'),
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('throws StudioError on 404', async () => {
      mockFetch([
        {
          url: /\/api\/v1\/projects\/nonexistent$/,
          status: 404,
          body: { error: { code: 'NOT_FOUND', message: 'Project not found', fieldErrors: [], correlationId: 'abc' } },
        },
      ])
      gw = createHttpGateway('http://localhost:8000')

      try {
        await gw.projects.get('nonexistent')
        expect.fail('Should have thrown')
      } catch (err) {
        expect(err).toBeInstanceOf(StudioError)
        expect((err as StudioError).code).toBe('NOT_FOUND')
        expect((err as StudioError).status).toBe(404)
        expect((err as StudioError).correlationId).toBe('abc')
      }
    })

    it('throws StudioError on validation error with field errors', async () => {
      mockFetch([
        {
          url: '/api/v1/projects',
          method: 'POST',
          status: 422,
          body: {
            error: {
              code: 'VALIDATION_ERROR',
              message: 'Validation failed',
              fieldErrors: [{ field: 'name', message: 'Name is required' }],
              correlationId: 'xyz',
            },
          },
        },
      ])
      gw = createHttpGateway('http://localhost:8000')

      try {
        await gw.projects.create({ name: '' })
        expect.fail('Should have thrown')
      } catch (err) {
        expect(err).toBeInstanceOf(StudioError)
        expect((err as StudioError).code).toBe('VALIDATION_ERROR')
        expect((err as StudioError).isValidation).toBe(true)
        expect((err as StudioError).fieldErrors).toHaveLength(1)
        expect((err as StudioError).fieldErrors[0]!.field).toBe('name')
      }
    })
  })

  describe('operations', () => {
    it('lists operations', async () => {
      mockFetch([
        {
          url: '/api/v1/operations',
          method: 'GET',
          status: 200,
          body: {
            items: [
              { id: 'op1', projectId: 'p1', type: 'workflow_run', status: 'running', progress: 0.5, createdAt: '', startedAt: '', finishedAt: null, result: null, error: null },
            ],
            total: 1,
          },
        },
      ])
      gw = createHttpGateway('http://localhost:8000')

      const ops = await gw.runs.list('p1')
      expect(ops).toHaveLength(1)
      expect(ops[0]!.status).toBe('running')
    })

    it('cancels an operation', async () => {
      mockFetch([
        {
          url: /\/api\/v1\/operations\/op1/,
          method: 'DELETE',
          status: 200,
          body: { id: 'op1', projectId: 'p1', type: 'workflow_run', status: 'cancelled', progress: 0, createdAt: '', startedAt: null, finishedAt: '', result: null, error: null },
        },
      ])
      gw = createHttpGateway('http://localhost:8000')

      const op = await gw.runs.cancel('p1', 'op1')
      expect(op.status).toBe('cancelled')
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/operations/op1'),
        expect.objectContaining({ method: 'DELETE' }),
      )
    })
  })

  describe('abort handling', () => {
    it('throws ABORTED error when signal is aborted', async () => {
      mockFetch([{ url: '/health', status: 200, body: {} }])
      gw = createHttpGateway('http://localhost:8000')

      const controller = new AbortController()
      controller.abort()

      try {
        await gw.health.check({ signal: controller.signal })
        expect.fail('Should have thrown')
      } catch (err) {
        expect(err).toBeInstanceOf(StudioError)
        expect((err as StudioError).code).toBe('ABORTED')
      }
    })

    it('throws NETWORK_ERROR on fetch failure', async () => {
      globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
      gw = createHttpGateway('http://localhost:8000')

      try {
        await gw.health.check()
        expect.fail('Should have thrown')
      } catch (err) {
        expect(err).toBeInstanceOf(StudioError)
        expect((err as StudioError).code).toBe('NETWORK_ERROR')
        expect((err as StudioError).status).toBe(0)
      }
    })
  })

  describe('204 No Content', () => {
    it('returns undefined for 204 responses', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
      gw = createHttpGateway('http://localhost:8000')

      const result = await gw.projects.delete('p1')
      expect(result).toBeUndefined()
    })
  })
})
