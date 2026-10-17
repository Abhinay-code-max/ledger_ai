import { describe, it, expect, vi } from 'vitest'
import { Role4ApiClient } from '../lib/api-client'

describe('Review Actions and Concurrency Control', () => {
  it('sends If-Match version header and reviewed resource version in body', async () => {
    let capturedHeaders: Record<string, string> = {}
    let capturedBody: Record<string, unknown> = {}

    global.fetch = vi.fn().mockImplementation((_, init) => {
      capturedHeaders = init?.headers || {}
      capturedBody = JSON.parse(init?.body || '{}')
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({
          approval_id: 'appr-001',
          status: 'APPROVED',
          version: 2,
        }),
      })
    })

    const client = new Role4ApiClient({
      baseUrl: 'http://127.0.0.1:8000',
      token: 'reviewer-token',
      tenantId: '00000000-0000-0000-0000-000000000001',
      organizationId: '11111111-1111-1111-1111-111111111111',
      legalEntityId: '22222222-2222-2222-2222-222222222222',
    })

    const approvalResult = await client.request<{ status: string }>('/api/v1/approval-requests/req-001/approve', {
      method: 'POST',
      ifMatch: '1',
      idempotencyKey: 'idemp-approve-001',
      body: JSON.stringify({
        reviewed_resource_version: '1',
        reason: 'Approved by independent reviewer after resolving mismatch.',
      }),
    })

    expect(approvalResult.status).toBe('APPROVED')
    expect(capturedHeaders['If-Match']).toBe('1')
    expect(capturedHeaders['Idempotency-Key']).toBe('idemp-approve-001')
    expect(capturedBody.reviewed_resource_version).toBe('1')
    expect(capturedBody.reason).toContain('independent reviewer')
  })
})
