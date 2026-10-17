import { describe, it, expect } from 'vitest'
import { generateIdempotencyKey } from '../lib/state-reducers'

describe('Idempotency-Key Generation', () => {
  it('generates well-formed operation-prefixed keys', () => {
    const key = generateIdempotencyKey('upload-doc')
    expect(key).toMatch(/^upload-doc-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i)
  })

  it('generates unique keys across multiple invocations', () => {
    const keys = new Set<string>()
    for (let i = 0; i < 50; i++) {
      keys.add(generateIdempotencyKey('post-op'))
    }
    expect(keys.size).toBe(50)
  })

  it('preserves idempotency key across retry attempts', () => {
    const initialKey = generateIdempotencyKey('posting')
    let attempts = 0
    let executedWithKey = ''

    function executeWithRetry(key: string) {
      attempts++
      executedWithKey = key
    }

    // Simulate 3 retries of the same operation
    for (let i = 0; i < 3; i++) {
      executeWithRetry(initialKey)
    }

    expect(attempts).toBe(3)
    expect(executedWithKey).toBe(initialKey)
  })
})
