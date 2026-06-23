/**
 * Standardized error type for the gateway layer.
 *
 * Both the HTTP adapter and mock adapter throw StudioError so that
 * feature code has a single error type to handle regardless of mode.
 */

import type { FieldError } from '@/types/api'

export class StudioError extends Error {
  /** Machine-readable error code (NOT_FOUND, VALIDATION_ERROR, etc.) */
  readonly code: string
  /** HTTP status code (0 for network errors in mock mode) */
  readonly status: number
  /** Per-field validation errors */
  readonly fieldErrors: FieldError[]
  /** Correlation ID for tracing */
  readonly correlationId: string

  constructor(opts: {
    message: string
    code?: string
    status?: number
    fieldErrors?: FieldError[]
    correlationId?: string
  }) {
    super(opts.message)
    this.name = 'StudioError'
    this.code = opts.code ?? 'UNKNOWN'
    this.status = opts.status ?? 500
    this.fieldErrors = opts.fieldErrors ?? []
    this.correlationId = opts.correlationId ?? ''
  }

  /** Convenience: is this a not-found error? */
  get isNotFound(): boolean {
    return this.code === 'NOT_FOUND' || this.status === 404
  }

  /** Convenience: is this a validation error? */
  get isValidation(): boolean {
    return this.code === 'VALIDATION_ERROR' || this.status === 422
  }

  /** Convenience: is this a conflict error? */
  get isConflict(): boolean {
    return this.code === 'CONFLICT' || this.status === 409
  }
}
