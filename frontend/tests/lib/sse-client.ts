export interface SSEMessage {
  id?: string
  event?: string
  data: string
}

export interface SSEClientOptions {
  url: string
  token: string
  headers?: Record<string, string>
  onMessage: (message: SSEMessage) => void
  onError?: (error: Error) => void
  onReconnect?: (attempt: number, delayMs: number) => void
  maxReconnectAttempts?: number
  baseReconnectDelayMs?: number
  maxReconnectDelayMs?: number
}

export class ResilientSSEClient {
  private options: SSEClientOptions
  private lastEventId: string | null = null
  private seenEventIds = new Set<string>()
  private reconnectAttempts = 0
  private aborted = false
  private currentController: AbortController | null = null

  constructor(options: SSEClientOptions) {
    this.options = {
      maxReconnectAttempts: 5,
      baseReconnectDelayMs: 100,
      maxReconnectDelayMs: 3000,
      ...options,
    }
  }

  getLastEventId(): string | null {
    return this.lastEventId
  }

  getReconnectAttempts(): number {
    return this.reconnectAttempts
  }

  getSeenEventCount(): number {
    return this.seenEventIds.size
  }

  connect(): void {
    if (this.aborted) return
    this.currentController = new AbortController()

    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.options.token}`,
      Accept: 'text/event-stream',
      ...this.options.headers,
    }

    if (this.lastEventId) {
      headers['Last-Event-ID'] = this.lastEventId
    }

    fetch(this.options.url, {
      headers,
      signal: this.currentController.signal,
    })
      .then(async response => {
        if (!response.ok) {
          throw new Error(`SSE stream returned HTTP ${response.status}`)
        }
        this.reconnectAttempts = 0 // Reset on successful connection

        if (!response.body) {
          throw new Error('ReadableStream not supported on response body')
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (!this.aborted) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          let currentMessage: Partial<SSEMessage> = {}
          for (const line of lines) {
            const trimmed = line.trim()
            if (trimmed === '') {
              if (currentMessage.data) {
                this.handleParsedMessage(currentMessage as SSEMessage)
                currentMessage = {}
              }
              continue
            }
            if (trimmed.startsWith('id:')) {
              currentMessage.id = trimmed.slice(3).trim()
            } else if (trimmed.startsWith('event:')) {
              currentMessage.event = trimmed.slice(6).trim()
            } else if (trimmed.startsWith('data:')) {
              currentMessage.data = trimmed.slice(5).trim()
            }
          }
        }
      })
      .catch(error => {
        if (this.aborted) return
        this.options.onError?.(error instanceof Error ? error : new Error(String(error)))
        this.scheduleReconnect()
      })
  }

  private handleParsedMessage(msg: SSEMessage): void {
    if (msg.id) {
      // Duplicate suppression
      if (this.seenEventIds.has(msg.id)) {
        return
      }
      this.seenEventIds.add(msg.id)
      this.lastEventId = msg.id
    }
    this.options.onMessage(msg)
  }

  private scheduleReconnect(): void {
    if (this.aborted) return
    const maxAttempts = this.options.maxReconnectAttempts || 5
    if (this.reconnectAttempts >= maxAttempts) {
      this.options.onError?.(new Error(`Exceeded maximum reconnect attempts (${maxAttempts})`))
      return
    }

    this.reconnectAttempts++
    const baseDelay = this.options.baseReconnectDelayMs || 100
    const maxDelay = this.options.maxReconnectDelayMs || 3000
    const delay = Math.min(baseDelay * Math.pow(2, this.reconnectAttempts - 1), maxDelay)

    this.options.onReconnect?.(this.reconnectAttempts, delay)
    setTimeout(() => {
      if (!this.aborted) {
        this.connect()
      }
    }, delay)
  }

  disconnect(): void {
    this.aborted = true
    if (this.currentController) {
      this.currentController.abort()
      this.currentController = null
    }
  }
}
