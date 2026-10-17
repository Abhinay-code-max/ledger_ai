import { describe, it, expect } from 'vitest'
import { Role4ApiError } from '../lib/api-client'
import { mapApiErrorToUserFacing } from '../lib/error-mapper'

describe('API Error Mapping', () => {
  it('maps MAKER_CHECKER_VIOLATION to clear human guidance and forbidden status', () => {
    const error = new Role4ApiError(403, {
      schema_version: '1.0',
      category: 'AUTHORIZATION',
      code: 'MAKER_CHECKER_VIOLATION',
      message: 'The maker cannot approve their own journal proposal.',
      request_id: '11111111-1111-1111-1111-111111111111',
      correlation_id: '22222222-2222-2222-2222-222222222222',
      field_errors: [],
    })

    const mapped = mapApiErrorToUserFacing(error)
    expect(mapped.isForbidden).toBe(true)
    expect(mapped.isAuthError).toBe(false)
    expect(mapped.title).toContain('Maker-Checker')
    expect(mapped.detail).toContain('Self-approval is prohibited')
    expect(mapped.actionableMessage).toContain('independent reviewer')
  })

  it('maps STALE_APPROVAL 409 conflict with prompt to reload', () => {
    const error = new Role4ApiError(409, {
      schema_version: '1.0',
      category: 'CONCURRENCY',
      code: 'STALE_APPROVAL',
      message: 'Resource version mismatch. Resource was modified.',
      request_id: '33333333-3333-3333-3333-333333333333',
      correlation_id: '44444444-4444-4444-4444-444444444444',
      field_errors: [],
    })

    const mapped = mapApiErrorToUserFacing(error)
    expect(mapped.isConflict).toBe(true)
    expect(mapped.title).toContain('Version Conflict')
    expect(mapped.actionableMessage).toContain('reload the latest proposal version')
  })

  it('maps AUTHENTICATION_EXPIRED 401 with sign-in prompt', () => {
    const error = new Role4ApiError(401, {
      schema_version: '1.0',
      category: 'AUTHENTICATION',
      code: 'AUTHENTICATION_EXPIRED',
      message: 'Bearer token expired.',
      request_id: '55555555-5555-5555-5555-555555555555',
      correlation_id: '66666666-6666-6666-6666-666666666666',
      field_errors: [],
    })

    const mapped = mapApiErrorToUserFacing(error)
    expect(mapped.isAuthError).toBe(true)
    expect(mapped.title).toContain('Session Expired')
    expect(mapped.actionableMessage).toContain('sign in again')
  })

  it('maps TENANT_MISMATCH with access denial', () => {
    const error = new Role4ApiError(403, {
      schema_version: '1.0',
      category: 'AUTHORIZATION',
      code: 'TENANT_MISMATCH',
      message: 'Attempted to access foreign tenant resource.',
      request_id: '77777777-7777-7777-7777-777777777777',
      correlation_id: '88888888-8888-8888-8888-888888888888',
      field_errors: [],
    })

    const mapped = mapApiErrorToUserFacing(error)
    expect(mapped.isForbidden).toBe(true)
    expect(mapped.title).toContain('Tenant Boundary Violation')
  })

  it('maps DUPLICATE_IDEMPOTENCY_KEY to duplicate submission notice', () => {
    const error = new Role4ApiError(409, {
      schema_version: '1.0',
      category: 'CONCURRENCY',
      code: 'DUPLICATE_IDEMPOTENCY_KEY',
      message: 'Idempotency key collision.',
      request_id: '99999999-9999-9999-9999-999999999999',
      correlation_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
      field_errors: [],
    })

    const mapped = mapApiErrorToUserFacing(error)
    expect(mapped.isConflict).toBe(true)
    expect(mapped.title).toContain('Duplicate Submission')
  })

  it('maps REQUEST_TOO_LARGE 413 to file size explanation', () => {
    const error = new Role4ApiError(413, {
      schema_version: '1.0',
      category: 'INPUT_VALIDATION',
      code: 'REQUEST_TOO_LARGE',
      message: 'The request is too large.',
      request_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
      correlation_id: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
      field_errors: [],
    })

    const mapped = mapApiErrorToUserFacing(error)
    expect(mapped.title).toContain('Payload Too Large')
    expect(mapped.actionableMessage).toContain('25MB')
  })

  it('maps REQUEST_TIMEOUT 504 to gateway timeout explanation', () => {
    const error = new Role4ApiError(504, {
      schema_version: '1.0',
      category: 'DOWNSTREAM',
      code: 'REQUEST_TIMEOUT',
      message: 'The request timed out.',
      request_id: 'dddddddd-dddd-dddd-dddd-dddddddddddd',
      correlation_id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
      field_errors: [],
    })

    const mapped = mapApiErrorToUserFacing(error)
    expect(mapped.title).toContain('Gateway Timeout')
    expect(mapped.actionableMessage).toContain('retry')
  })

  it('preserves field validation errors in the mapped object', () => {
    const error = new Role4ApiError(422, {
      schema_version: '1.0',
      category: 'INPUT_VALIDATION',
      code: 'VALIDATION_ERROR',
      message: 'Validation failed.',
      request_id: 'ffffffff-ffff-ffff-ffff-ffffffffffff',
      correlation_id: '00000000-0000-0000-0000-000000000000',
      field_errors: [
        { field: 'currency', code: 'INVALID_CURRENCY', message: 'Must be ISO 4217' },
        { field: 'period_start', code: 'REQUIRED', message: 'Field required' },
      ],
    })

    const mapped = mapApiErrorToUserFacing(error)
    expect(mapped.fieldErrors['currency']).toBe('Must be ISO 4217')
    expect(mapped.fieldErrors['period_start']).toBe('Field required')
  })
})
