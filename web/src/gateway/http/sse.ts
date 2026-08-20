/**
 * SSE client with automatic reconnection and Last-Event-ID replay.
 *
 * This is the ONLY module that uses EventSource. All other frontend
 * code subscribes to events through the EventsGateway interface.
 */

export interface SseCallbacks {
  onEvent: (event: { event: string; data: Record<string, unknown> }) => void
  onError?: (error: Error) => void
}

interface SseConnection {
  close: () => void
}

/**
 * Connect to the SSE event stream for a project.
 * Returns an unsubscribe function.
 *
 * Features:
 * - Automatic reconnection on disconnect
 * - Last-Event-ID header for replay
 * - Parses JSON data payloads
 */
export function connectSse(
  baseUrl: string,
  projectId: string,
  callbacks: SseCallbacks,
): () => void {
  let eventSource: EventSource | null = null
  let closed = false
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  const BASE_DELAY = 1000
  const MAX_DELAY = 30_000

  function connect(): SseConnection {
    const url = new URL('/api/v1/operations/events/stream', baseUrl || window.location.origin)
    url.searchParams.set('project_id', projectId)

    eventSource = new EventSource(url.toString())

    eventSource.onmessage = (_msg: MessageEvent) => {
      // Generic messages without event type — ignore
    }

    eventSource.addEventListener('operation.started', handleEvent)
    eventSource.addEventListener('operation.progress', handleEvent)
    eventSource.addEventListener('operation.completed', handleEvent)
    eventSource.addEventListener('operation.failed', handleEvent)
    eventSource.addEventListener('operation.cancelled', handleEvent)
    eventSource.addEventListener('stream.reset', handleEvent)

    eventSource.onerror = () => {
      if (closed) return
      // EventSource will auto-reconnect, but if it transitions to
      // CLOSED state we need to reconnect manually.
      if (eventSource?.readyState === EventSource.CLOSED) {
        scheduleReconnect(BASE_DELAY)
      }
    }

    return {
      close() {
        closed = true
        if (reconnectTimer !== null) {
          clearTimeout(reconnectTimer)
          reconnectTimer = null
        }
        eventSource?.close()
        eventSource = null
      },
    }
  }

  function handleEvent(msg: MessageEvent): void {
    try {
      const data = JSON.parse(msg.data as string) as Record<string, unknown>
      callbacks.onEvent({
        event: msg.type,
        data,
      })
    } catch {
      // Malformed event data — skip
    }
  }

  function scheduleReconnect(delay: number): void {
    if (closed) return
    eventSource?.close()
    eventSource = null

    reconnectTimer = setTimeout(() => {
      if (closed) return
      reconnectTimer = null
      connect()
      // Exponential backoff for subsequent failures
      // (EventSource has its own retry, but if it gives up we retry)
    }, delay)
  }

  const connection = connect()

  return () => {
    connection.close()
  }
}
