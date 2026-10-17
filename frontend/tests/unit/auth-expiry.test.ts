import { describe, it, expect, vi } from 'vitest'
import { Role4ApiClient, Role4ApiError } from '../lib/api-client'
import { mapApiErrorToUserFacing } from '../lib/error-mapper'

describe('Authentication Expiry', () => {
  it('clears session and redirects on 401 token expiry', async () => {
    let sessionUser: { name: string; token: string } | null = { name: 'Maker', token: 'expired-token' }
    let redirectPath = ''

    function handleAuthFailure(err: unknown, currentPath: string) {
      const mapped = mapApiErrorToUserFacing(err)
      if (mapped.isAuthError) {
        sessionUser = null
        // Never put raw token in redirect URL
        redirectPath = `/login?return_to=${encodeURIComponent(currentPath)}`
      }
    }

    const client = new Role4ApiClient({
      baseUrl: 'http://127.0.0.1:8000',
      token: sessionUser.token,
    })

    // Mock fetch to simulate 401 from backend
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({
        schema_version: '1.0',
        category: 'AUTHENTICATION',
        code: 'AUTHENTICATION_EXPIRED',
        message: 'The provided access token is expired.',
        request_id: '12345678-1234-1234-1234-123456789abc',
        correlation_id: '87654321-4321-4321-4321-cba987654321',
        field_errors: [],
      }),
    })

    try {
      await client.request('/api/v1/me')
    } catch (err) {
      handleAuthFailure(err, '/dashboard/maker')
    }

    expect(sessionUser).toBeNull()
    expect(redirectPath).toBe('/login?return_to=%2Fdashboard%2Fmaker')
    expect(redirectPath).not.toContain('token')
    expect(redirectPath).not.toContain('expired-token')
  })

  it('rejects tokens encoded in URL query parameters', () => {
    const dangerousUrls = [
      'https://ledgerai.example.com/dashboard?token=eyJhbGciOi...',
      'https://ledgerai.example.com/callback#access_token=secret123',
      '/workspace?auth_token=super-secret',
    ]

    function sanitizeNavigationUrl(url: string): { safe: boolean; cleanedUrl: string } {
      const parsed = new URL(url, 'https://ledgerai.example.com')
      const tokenKeys = ['token', 'access_token', 'auth_token', 'jwt', 'secret', 'key']
      let foundToken = false

      for (const k of tokenKeys) {
        if (parsed.searchParams.has(k)) {
          foundToken = true
          parsed.searchParams.delete(k)
        }
      }
      if (parsed.hash.includes('token=')) {
        foundToken = true
        parsed.hash = ''
      }

      return {
        safe: !foundToken,
        cleanedUrl: `${parsed.pathname}${parsed.search}${parsed.hash}`,
      }
    }

    for (const url of dangerousUrls) {
      const res = sanitizeNavigationUrl(url)
      expect(res.safe).toBe(false)
      expect(res.cleanedUrl).not.toContain('token=')
      expect(res.cleanedUrl).not.toContain('secret123')
    }
  })
})
