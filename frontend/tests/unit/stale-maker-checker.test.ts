import { describe, it, expect, vi } from 'vitest'
import { Role4ApiClient, Role4ApiError } from '../lib/api-client'
import { mapApiErrorToUserFacing } from '../lib/error-mapper'

describe('Maker-Checker and Stale Version Errors', () => {
  it('throws and maps MAKER_CHECKER_VIOLATION when maker attempts self-approval', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({
        schema_version: '1.0',
        category: 'AUTHORIZATION',
        code: 'MAKER_CHECKER_VIOLATION',
        message: 'The maker cannot approve their own proposal.',
        request_id: '12345678-1234-1234-1234-123456789abc',
        correlation_id: '87654321-4321-4321-4321-cba987654321',
        field_errors: [],
      }),
    })

    const client = new Role4ApiClient({
      baseUrl: 'http://127.0.0.1:8000',
      token: 'synthetic-maker-token-for-nova',
    })

    let caughtError: Role4ApiError | null = null
    try {
      await client.request('/api/v1/approval-requests/req-001/approve', {
        method: 'POST',
        ifMatch: '1',
        body: JSON.stringify({ reviewed_resource_version: '1', reason: 'Maker self approval attempt' }),
      })
    } catch (err) {
      if (err instanceof Role4ApiError) {
        caughtError = err
      }
    }

    expect(caughtError).not.toBeNull()
    expect(caughtError?.status).toBe(403)
    expect(caughtError?.code).toBe('MAKER_CHECKER_VIOLATION')

    const userFacing = mapApiErrorToUserFacing(caughtError)
    expect(userFacing.isForbidden).toBe(true)
    expect(userFacing.detail).toContain('Self-approval is prohibited')
  })

  it('throws and maps STALE_APPROVAL when If-Match version is outdated', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({
        schema_version: '1.0',
        category: 'CONCURRENCY',
        code: 'STALE_APPROVAL',
        message: 'Resource version changed. Current version is 2, If-Match was 1.',
        request_id: 'aaaa1111-1234-1234-1234-123456789abc',
        correlation_id: 'bbbb2222-4321-4321-4321-cba987654321',
        field_errors: [],
      }),
    })

    const client = new Role4ApiClient({
      baseUrl: 'http://127.0.0.1:8000',
      token: 'synthetic-reviewer-token-for-nova',
    })

    let caughtError: Role4ApiError | null = null
    try {
      await client.request('/api/v1/approval-requests/req-001/approve', {
        method: 'POST',
        ifMatch: '1',
        body: JSON.stringify({ reviewed_resource_version: '1', reason: 'Reviewer approval' }),
      })
    } catch (err) {
      if (err instanceof Role4ApiError) {
        caughtError = err
      }
    }

    expect(caughtError).not.toBeNull()
    expect(caughtError?.status).toBe(409)
    expect(caughtError?.code).toBe('STALE_APPROVAL')

    const userFacing = mapApiErrorToUserFacing(caughtError)
    expect(userFacing.isConflict).toBe(true)
    expect(userFacing.actionableMessage).toContain('reload the latest proposal version')
  })
})
