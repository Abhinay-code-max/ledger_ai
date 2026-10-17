/**
 * Authenticated Server-Sent Events (SSE) progress client.
 *
 * Uses fetch + ReadableStream to safely provide Authorization headers without
 * exposing bearer tokens in URLs. Enforces Last-Event-ID resume, bounded exponential
 * backoff, duplicate suppression, and 409 retention-gap reset.
 */

import type { ProgressEventResponse } from '../types/api'
import type { ClientContext } from './client'

export type SseConnectionStatus = 'CONNECTING' | 'CONNECTED' | 'DISCONNECTED' | 'ERROR'

export interface SseClientOptions {
  context: ClientContext
  baseUrl?: string
  onEvent: (event: ProgressEventResponse) => void
  onStatusChange?: (status: SseConnectionStatus) => void
  onError?: (error: Error) => void
}

export class Role4ProgressStream {
  private options: SseClientOptions
  private abortController: AbortController | null = null
  private lastEventId: string | null = null
  private seenEventIds = new Set<string>()
  private isRunning = false
  private retryDelayMs = 1000
  private readonly maxRetryDelayMs = 15000

  constructor(options: SseClientOptions) {
    this.options = options
  }

  updateContext(context: Partial<ClientContext>): void {
    const prevToken = this.options.context.token
    const prevOrg = this.options.context.organizationId
    const prevLegal = this.options.context.legalEntityId
    this.options.context = { ...this.options.context, ...context }

    // If tenant or token changed, reset cursor and seen cache to prevent cross-tenant reuse
    if (prevToken !== this.options.context.token || prevOrg !== this.options.context.organizationId || prevLegal !== this.options.context.legalEntityId) {
      this.lastEventId = null
      this.seenEventIds.clear()
      if (this.isRunning) {
        this.stop()
        this.start()
      }
    }
  }

  start(): void {
    if (this.isRunning) return
    this.isRunning = true
    this.retryDelayMs = 1000
    void this.connectLoop()
  }

  stop(): void {
    this.isRunning = false
    if (this.abortController) {
      this.abortController.abort()
      this.abortController = null
    }
    this.emitStatus('DISCONNECTED')
  }

  private emitStatus(status: SseConnectionStatus): void {
    if (this.options.onStatusChange) {
      this.options.onStatusChange(status)
    }
  }

  private async connectLoop(): Promise<void> {
    while (this.isRunning) {
      if (!this.options.context.token) {
        this.emitStatus('DISCONNECTED')
        await new Promise((r) => setTimeout(r, 1000))
        continue
      }

      this.emitStatus('CONNECTING')
      this.abortController = new AbortController()
      const signal = this.abortController.signal

      const rawUrl = this.options.baseUrl || (import.meta.env.VITE_API_BASE_URL as string | undefined) || ''
      const baseUrl = rawUrl.replace(/\/+$/, '')
      const streamUrl = `${baseUrl}/api/v1/progress-stream`

      const headers: Record<string, string> = {
        'Accept': 'text/event-stream',
        'Authorization': `Bearer ${this.options.context.token}`,
        'X-Workspace-Code': this.options.context.workspaceCode || 'nova',
        'X-Correlation-ID': this.options.context.correlationId || crypto.randomUUID(),
        'X-Request-ID': crypto.randomUUID(),
      }

      if (this.options.context.organizationId) {
        headers['X-Organization-ID'] = this.options.context.organizationId
      }
      if (this.options.context.legalEntityId) {
        headers['X-Legal-Entity-ID'] = this.options.context.legalEntityId
      }
      if (this.lastEventId) {
        headers['Last-Event-ID'] = this.lastEventId
      }

      try {
        const response = await fetch(streamUrl, {
          method: 'GET',
          headers,
          signal,
        })

        // Retention gap: 409 PROGRESS_CURSOR_UNKNOWN
        if (response.status === 409) {
          this.lastEventId = null
          this.retryDelayMs = 1000
          continue
        }

        if (response.status === 401) {
          this.emitStatus('ERROR')
          if (this.options.context.onAuthExpired) {
            this.options.context.onAuthExpired()
          }
          this.stop()
          return
        }

        if (!response.ok || !response.body) {
          throw new Error(`SSE HTTP error ${response.status}: ${response.statusText}`)
        }

        this.emitStatus('CONNECTED')
        this.retryDelayMs = 1000 // Reset backoff on successful connect

        await this.readStream(response.body, signal)
      } catch (err) {
        if (!this.isRunning || signal.aborted) {
          return
        }

        this.emitStatus('ERROR')
        if (this.options.onError) {
          this.options.onError(err instanceof Error ? err : new Error(String(err)))
        }

        // Bounded exponential backoff
        await new Promise((resolve) => setTimeout(resolve, this.retryDelayMs))
        this.retryDelayMs = Math.min(this.retryDelayMs * 2, this.maxRetryDelayMs)
      }
    }
  }

  private async readStream(stream: ReadableStream<Uint8Array>, signal: AbortSignal): Promise<void> {
    const reader = stream.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (this.isRunning && !signal.aborted) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const messages = buffer.split('\n\n')
        // Keep the last partial chunk in buffer
        buffer = messages.pop() ?? ''

        for (const block of messages) {
          this.processEventBlock(block)
        }
      }
    } finally {
      reader.releaseLock()
    }
  }

  private processEventBlock(block: string): void {
    const lines = block.split('\n')
    let eventType = 'message'
    let eventId: string | null = null
    let data = ''

    for (const rawLine of lines) {
      const line = rawLine.trim()
      if (!line || line.startsWith(':')) {
        // Comment or heartbeat
        continue
      }
      if (line.startsWith('id:')) {
        eventId = line.slice(3).trim()
      } else if (line.startsWith('event:')) {
        eventType = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        data += (data ? '\n' : '') + line.slice(5).trim()
      }
    }

    if (eventId) {
      this.lastEventId = eventId
      if (this.seenEventIds.has(eventId)) {
        return // Suppress duplicates
      }
      this.seenEventIds.add(eventId)
      if (this.seenEventIds.size > 2000) {
        // Prune older event tracking to keep memory bounded
        const entries = Array.from(this.seenEventIds)
        for (let i = 0; i < 500; i++) {
          this.seenEventIds.delete(entries[i])
        }
      }
    }

    if (eventType === 'progress' && data) {
      try {
        const parsed = JSON.parse(data) as ProgressEventResponse
        this.options.onEvent(parsed)
      } catch {
        // Ignore unparseable data line
      }
    }
  }
}
