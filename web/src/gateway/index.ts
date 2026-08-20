/**
 * Gateway initialization and access.
 *
 * Feature code imports `getGateway()` to obtain the StudioGateway
 * instance. The concrete implementation (HTTP or mock) is selected
 * at startup based on VITE_GATEWAY_MODE and is never imported
 * directly by feature code.
 */

import type { StudioGateway } from './types'

let _gateway: StudioGateway | null = null

/**
 * Initialize the gateway based on the current environment.
 * Must be called once before any `getGateway()` calls.
 */
export async function initGateway(): Promise<void> {
  const mode = import.meta.env.VITE_GATEWAY_MODE ?? 'http'

  if (mode === 'mock') {
    const { createMockGateway } = await import('./mock')
    _gateway = createMockGateway()
  } else {
    const { createHttpGateway } = await import('./http')
    const baseUrl = import.meta.env.VITE_API_BASE_URL ?? ''
    _gateway = createHttpGateway(baseUrl)
  }
}

/**
 * Get the active gateway instance.
 * Throws if `initGateway()` has not been called.
 */
export function getGateway(): StudioGateway {
  if (!_gateway) {
    throw new Error('Gateway not initialized. Call initGateway() first.')
  }
  return _gateway
}

/**
 * Replace the active gateway (for testing).
 */
export function setGateway(gateway: StudioGateway): void {
  _gateway = gateway
}

// Re-export types for convenience
export type { StudioGateway } from './types'
export type { GatewayOptions } from './types'
export { StudioError } from './error'
