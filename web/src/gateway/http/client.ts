/**
 * Low-level HTTP client for the gateway.
 *
 * This is the ONLY module that touches `fetch`. All other frontend
 * code must go through the gateway interfaces.
 */

import { StudioError } from '../error'
import type { ErrorResponse } from '@/types/api'

export interface FetchOptions {
  method?: string
  body?: unknown
  signal?: AbortSignal
  headers?: Record<string, string>
  query?: Record<string, string | undefined>
}

/**
 * Make an API request and return the parsed JSON body.
 * Throws StudioError on non-2xx responses.
 */
export async function apiFetch<T>(
  baseUrl: string,
  path: string,
  opts: FetchOptions = {},
): Promise<T> {
  const url = new URL(path, baseUrl || window.location.origin)

  // Append query parameters
  if (opts.query) {
    for (const [key, value] of Object.entries(opts.query)) {
      if (value !== undefined) {
        url.searchParams.set(key, value)
      }
    }
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...opts.headers,
  }

  const init: RequestInit = {
    method: opts.method ?? 'GET',
    headers,
    signal: opts.signal,
  }

  if (opts.body !== undefined && opts.method !== 'GET') {
    init.body = JSON.stringify(opts.body)
  }

  let response: Response
  try {
    response = await fetch(url.toString(), init)
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new StudioError({
        message: 'Request was cancelled',
        code: 'ABORTED',
        status: 0,
      })
    }
    throw new StudioError({
      message: err instanceof Error ? err.message : 'Network error',
      code: 'NETWORK_ERROR',
      status: 0,
    })
  }

  if (!response.ok) {
    await throwApiError(response)
  }

  // 204 No Content — return undefined as T
  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

/**
 * Parse a non-2xx response and throw a StudioError.
 */
async function throwApiError(response: Response): Promise<never> {
  let body: ErrorResponse | null = null
  try {
    body = (await response.json()) as ErrorResponse
  } catch {
    // Response body is not JSON
  }

  if (body?.error) {
    throw new StudioError({
      message: body.error.message,
      code: body.error.code,
      status: response.status,
      fieldErrors: body.error.fieldErrors,
      correlationId: body.error.correlationId,
    })
  }

  throw new StudioError({
    message: `HTTP ${response.status}: ${response.statusText}`,
    code: 'HTTP_ERROR',
    status: response.status,
  })
}
