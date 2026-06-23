/**
 * Tests for the mock gateway.
 *
 * Verifies that the mock gateway returns deterministic fixtures
 * for every resource family and handles all operation states.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { createMockGateway } from '@/gateway/mock'
import { StudioError } from '@/gateway/error'
import type { StudioGateway } from '@/gateway/types'
import { IDS } from '@/gateway/mock/fixtures'

describe('MockGateway', () => {
  let gw: StudioGateway

  beforeEach(() => {
    gw = createMockGateway()
  })

  // ── Health ──────────────────────────────────────────────────────────

  describe('health', () => {
    it('returns health status', async () => {
      const health = await gw.health.check()
      expect(health.status).toBe('ok')
      expect(health.version).toBe('0.1.0')
      expect(health.schemaVersion).toBe(4)
    })

    it('respects abort signal', async () => {
      const controller = new AbortController()
      controller.abort()
      await expect(gw.health.check({ signal: controller.signal })).rejects.toThrow(StudioError)
    })
  })

  // ── Projects ────────────────────────────────────────────────────────

  describe('projects', () => {
    it('lists all projects', async () => {
      const projects = await gw.projects.list()
      expect(projects).toHaveLength(2)
      expect(projects[0]!.name).toBe('Default')
      expect(projects[0]!.isDefault).toBe(true)
    })

    it('gets a project by ID', async () => {
      const project = await gw.projects.get(IDS.project)
      expect(project.id).toBe(IDS.project)
      expect(project.name).toBe('Default')
    })

    it('throws NOT_FOUND for unknown project', async () => {
      await expect(gw.projects.get('nonexistent')).rejects.toThrow(StudioError)
      try {
        await gw.projects.get('nonexistent')
      } catch (err) {
        expect(err).toBeInstanceOf(StudioError)
        expect((err as StudioError).code).toBe('NOT_FOUND')
        expect((err as StudioError).status).toBe(404)
      }
    })

    it('creates a project', async () => {
      const project = await gw.projects.create({ name: 'Test', description: 'A test' })
      expect(project.name).toBe('Test')
      expect(project.description).toBe('A test')
      expect(project.id).toContain('proj-mock-')
    })

    it('prevents modifying the default project', async () => {
      await expect(
        gw.projects.update(IDS.project, { name: 'Changed' }),
      ).rejects.toThrow(StudioError)
      try {
        await gw.projects.update(IDS.project, { name: 'Changed' })
      } catch (err) {
        expect((err as StudioError).code).toBe('CONFLICT')
      }
    })

    it('prevents deleting the default project', async () => {
      await expect(gw.projects.delete(IDS.project)).rejects.toThrow(StudioError)
      try {
        await gw.projects.delete(IDS.project)
      } catch (err) {
        expect((err as StudioError).code).toBe('CONFLICT')
      }
    })

    it('updates a non-default project', async () => {
      const project = await gw.projects.update(IDS.projectAlt, { name: 'Renamed' })
      expect(project.name).toBe('Renamed')
    })

    it('deletes a non-default project', async () => {
      await expect(gw.projects.delete(IDS.projectAlt)).resolves.toBeUndefined()
      await expect(gw.projects.get(IDS.projectAlt)).rejects.toThrow(StudioError)
    })
  })

  // ── Collections ─────────────────────────────────────────────────────

  describe('collections', () => {
    it('lists collections for a project', async () => {
      const cols = await gw.collections.list(IDS.project)
      expect(cols.length).toBeGreaterThan(0)
      expect(cols[0]!.projectId).toBe(IDS.project)
    })

    it('gets a collection by ID', async () => {
      const col = await gw.collections.get(IDS.project, IDS.collection)
      expect(col.name).toBe('API Tests')
      expect(col.items.length).toBeGreaterThan(0)
    })

    it('creates a collection', async () => {
      const col = await gw.collections.create(IDS.project, { name: 'New Col' })
      expect(col.name).toBe('New Col')
      expect(col.items).toEqual([])
    })
  })

  // ── Requests ────────────────────────────────────────────────────────

  describe('requests', () => {
    it('lists requests', async () => {
      const reqs = await gw.requests.list(IDS.project)
      expect(reqs.length).toBeGreaterThan(0)
    })

    it('gets a request by ID', async () => {
      const req = await gw.requests.get(IDS.project, IDS.request)
      expect(req.method).toBe('GET')
      expect(req.url).toContain('jsonplaceholder')
    })

    it('executes a request', async () => {
      const result = await gw.requests.execute(IDS.project, IDS.request)
      expect(result.statusCode).toBe(200)
      expect(result.duration).toBeGreaterThan(0)
    })
  })

  // ── Environments ────────────────────────────────────────────────────

  describe('environments', () => {
    it('lists environments', async () => {
      const envs = await gw.environments.list(IDS.project)
      expect(envs.length).toBeGreaterThan(0)
      expect(envs[0]!.variables.length).toBeGreaterThan(0)
    })
  })

  // ── Workflows ───────────────────────────────────────────────────────

  describe('workflows', () => {
    it('lists workflows', async () => {
      const wfs = await gw.workflows.list(IDS.project)
      expect(wfs.length).toBeGreaterThan(0)
      expect(wfs[0]!.steps.length).toBeGreaterThan(0)
    })

    it('runs a workflow and returns a queued operation', async () => {
      const op = await gw.workflows.run(IDS.project, IDS.workflow)
      expect(op.status).toBe('queued')
      expect(op.type).toBe('workflow_run')
    })
  })

  // ── Functions ───────────────────────────────────────────────────────

  describe('functions', () => {
    it('lists functions', async () => {
      const fns = await gw.functions.list(IDS.project)
      expect(fns.length).toBeGreaterThan(0)
      expect(fns[0]!.name).toBeTruthy()
    })
  })

  // ── Plugins ─────────────────────────────────────────────────────────

  describe('plugins', () => {
    it('lists plugins', async () => {
      const plugins = await gw.plugins.list(IDS.project)
      expect(plugins.length).toBeGreaterThan(0)
      expect(plugins[0]!.status).toBe('active')
    })
  })

  // ── Monitors ────────────────────────────────────────────────────────

  describe('monitors', () => {
    it('lists monitors', async () => {
      const monitors = await gw.monitors.list(IDS.project)
      expect(monitors.length).toBeGreaterThan(0)
      expect(monitors[0]!.status).toBe('running')
    })

    it('starts a monitor', async () => {
      const op = await gw.monitors.start(IDS.project, IDS.monitor)
      expect(op.status).toBe('queued')
      expect(op.type).toBe('monitor_start')
    })

    it('stops a monitor', async () => {
      const op = await gw.monitors.stop(IDS.project, IDS.monitor)
      expect(op.status).toBe('queued')
      expect(op.type).toBe('monitor_stop')
    })

    it('gets monitor events', async () => {
      const events = await gw.monitors.events(IDS.project, IDS.monitor)
      expect(events.length).toBeGreaterThan(0)
    })
  })

  // ── Runs (Operations) ───────────────────────────────────────────────

  describe('runs', () => {
    it('lists all operations', async () => {
      const ops = await gw.runs.list(IDS.project)
      expect(ops.length).toBe(6) // All 6 states
    })

    it('lists operations filtered by status', async () => {
      const queued = await gw.runs.list(IDS.project, 'queued')
      expect(queued.length).toBe(1)
      expect(queued[0]!.status).toBe('queued')

      const succeeded = await gw.runs.list(IDS.project, 'succeeded')
      expect(succeeded.length).toBe(1)
      expect(succeeded[0]!.status).toBe('succeeded')
    })

    it('gets an operation by ID', async () => {
      const op = await gw.runs.get(IDS.project, IDS.opSucceeded)
      expect(op.status).toBe('succeeded')
      expect(op.progress).toBe(1)
      expect(op.result).not.toBeNull()
    })

    it('cancels a queued operation', async () => {
      const op = await gw.runs.cancel(IDS.project, IDS.opQueued)
      expect(op.status).toBe('cancelled')
    })

    it('transitions running to cancelling', async () => {
      const op = await gw.runs.cancel(IDS.project, IDS.opRunning)
      expect(op.status).toBe('cancelling')
    })

    it('rejects cancellation of terminal operations', async () => {
      await expect(gw.runs.cancel(IDS.project, IDS.opSucceeded)).rejects.toThrow(StudioError)
      try {
        await gw.runs.cancel(IDS.project, IDS.opSucceeded)
      } catch (err) {
        expect((err as StudioError).code).toBe('CONFLICT')
      }
    })
  })

  // ── Batches ─────────────────────────────────────────────────────────

  describe('batches', () => {
    it('runs a batch and returns a queued operation', async () => {
      const op = await gw.batches.run(IDS.project, [IDS.request, IDS.requestPost])
      expect(op.status).toBe('queued')
      expect(op.type).toBe('batch_run')
    })
  })

  // ── Transfers ───────────────────────────────────────────────────────

  describe('transfers', () => {
    it('exports data', async () => {
      const job = await gw.transfers.export(IDS.project, { format: 'csv' })
      expect(job.format).toBe('csv')
    })

    it('gets export presets', async () => {
      const presets = await gw.transfers.presets(IDS.project)
      expect(presets.length).toBeGreaterThan(0)
    })
  })

  // ── Settings ────────────────────────────────────────────────────────

  describe('settings', () => {
    it('gets settings', async () => {
      const settings = await gw.settings.get()
      expect(settings.theme).toBe('system')
      expect(settings.defaultTimeout).toBe(30000)
    })

    it('updates settings', async () => {
      const settings = await gw.settings.update({ theme: 'dark' })
      expect(settings.theme).toBe('dark')
    })
  })

  // ── Events ──────────────────────────────────────────────────────────

  describe('events', () => {
    it('subscribe returns an unsubscribe function', () => {
      const unsub = gw.events.subscribe(IDS.project, () => {})
      expect(typeof unsub).toBe('function')
      unsub()
    })
  })
})
