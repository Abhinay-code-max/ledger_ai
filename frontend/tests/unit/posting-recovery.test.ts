import { describe, it, expect, vi } from 'vitest'
import { Role4ApiClient } from '../lib/api-client'
import { progressReducer, initialProgressState } from '../lib/state-reducers'

describe('Posting Unknown State and Recovery Lifecycle', () => {
  it('handles UNKNOWN posting response and executes recovery until CONFIRMED', async () => {
    let callIndex = 0

    global.fetch = vi.fn().mockImplementation(url => {
      callIndex++
      if (url.includes('/posting-operations') && !url.includes('/recover')) {
        // Initial posting returns 202 with UNKNOWN state
        return Promise.resolve({
          ok: true,
          status: 202,
          json: async () => ({
            operation_id: 'op-001',
            state: 'UNKNOWN',
            last_error_code: 'DOWNSTREAM_UNAVAILABLE',
            confirmation: null,
          }),
        })
      }
      if (url.includes('/recover')) {
        // Recovery call returns 200 with CONFIRMED state
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            operation_id: 'op-001',
            state: 'CONFIRMED',
            confirmation: {
              posted_at: '2026-10-16T12:00:00Z',
              journal_entry_id: 'je-001',
              hash: 'abc123hash',
            },
          }),
        })
      }
      return Promise.reject(new Error(`Unhandled URL: ${url}`))
    })

    const client = new Role4ApiClient({
      baseUrl: 'http://127.0.0.1:8000',
      token: 'maker-token',
    })

    let state = initialProgressState

    // 1. Submit posting operation
    interface PostingResponse {
      operation_id: string
      state: string
      confirmation: unknown
    }

    const postResponse = await client.request<PostingResponse>('/api/v1/posting-operations', {
      method: 'POST',
      body: JSON.stringify({ journal_proposal_id: 'prop-001', proposal_version: 1, accounting_period_id: 'prd-001' }),
    })

    state = progressReducer(state, {
      type: 'POSTING_STARTED',
      operationId: postResponse.operation_id,
      state: postResponse.state,
    })

    expect(state.currentStage).toBe('JOURNAL_POSTING_UNKNOWN')
    expect(state.postingState).toBe('UNKNOWN')

    // In UNKNOWN state, the period must NOT be closed!
    expect(state.completedStages).not.toContain('PERIOD_CLOSE_CONFIRMED')

    // 2. Perform recovery
    const recoverResponse = await client.request<PostingResponse>(`/api/v1/posting-operations/${postResponse.operation_id}/recover`, {
      method: 'POST',
    })

    state = progressReducer(state, {
      type: 'POSTING_CONFIRMED',
      operationId: recoverResponse.operation_id,
    })

    expect(state.currentStage).toBe('JOURNAL_POSTING_CONFIRMED')
    expect(state.postingState).toBe('CONFIRMED')
  })
})
