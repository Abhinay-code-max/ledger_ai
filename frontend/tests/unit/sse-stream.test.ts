import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ResilientSSEClient } from '../lib/sse-client'

describe('SSE Stream Duplicate Suppression and Resume', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('suppresses duplicate events and preserves highest event ID', async () => {
    const received: string[] = []
    const client = new ResilientSSEClient({
      url: 'http://127.0.0.1:8000/api/v1/progress-stream',
      token: 'synthetic-token',
      onMessage: msg => {
        received.push(msg.data)
      },
    })

    // Simulate SSE payload with a duplicate event ID
    const streamData =
      'id: 101\nevent: progress\ndata: {"stage":"UPLOADED"}\n\n' +
      'id: 102\nevent: progress\ndata: {"stage":"SCANNED"}\n\n' +
      'id: 101\nevent: progress\ndata: {"stage":"UPLOADED_DUPLICATE"}\n\n' +
      'id: 103\nevent: progress\ndata: {"stage":"ACCEPTED"}\n\n'

    // Mock fetch with stream
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => {
          let read = false
          return {
            read: async () => {
              if (!read) {
                read = true
                return { done: false, value: new TextEncoder().encode(streamData) }
              }
              return { done: true, value: undefined }
            },
          }
        },
      },
    })

    client.connect()
    await vi.runAllTimersAsync()

    // Event 101 duplicate must be suppressed
    expect(received).toHaveLength(3)
    expect(received[0]).toContain('UPLOADED')
    expect(received[1]).toContain('SCANNED')
    expect(received[2]).toContain('ACCEPTED')
    expect(client.getLastEventId()).toBe('103')
    expect(client.getSeenEventCount()).toBe(3)
    client.disconnect()
  })

  it('resumes with Last-Event-ID on reconnection', async () => {
    let capturedHeaders: Record<string, string> = {}
    let callCount = 0

    global.fetch = vi.fn().mockImplementation((_, init) => {
      callCount++
      capturedHeaders = init?.headers || {}

      if (callCount === 1) {
        // First stream delivers event 201 then abruptly fails
        return Promise.resolve({
          ok: true,
          body: {
            getReader: () => {
              let doneOnce = false
              return {
                read: async () => {
                  if (!doneOnce) {
                    doneOnce = true
                    return {
                      done: false,
                      value: new TextEncoder().encode('id: 201\nevent: progress\ndata: {"stage":"STAGE_1"}\n\n'),
                    }
                  }
                  throw new Error('Connection terminated by server')
                },
              }
            },
          },
        })
      }

      // Reconnect response
      return Promise.resolve({
        ok: true,
        body: {
          getReader: () => ({
            read: async () => ({ done: true, value: undefined }),
          }),
        },
      })
    })

    const reconnects: number[] = []
    const client = new ResilientSSEClient({
      url: 'http://127.0.0.1:8000/api/v1/progress-stream',
      token: 'synthetic-token',
      baseReconnectDelayMs: 50,
      onMessage: () => {},
      onReconnect: attempt => {
        reconnects.push(attempt)
      },
    })

    client.connect()
    await vi.runAllTimersAsync()

    expect(client.getLastEventId()).toBe('201')
    expect(reconnects.length).toBeGreaterThan(0)
    // Check that second call included Last-Event-ID: 201
    expect(capturedHeaders['Last-Event-ID']).toBe('201')
    client.disconnect()
  })
})
