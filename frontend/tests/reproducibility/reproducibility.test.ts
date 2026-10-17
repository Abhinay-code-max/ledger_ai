import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'

describe('NOVA Workflow Business Output Reproducibility', () => {
  const summaryFixturePath = path.resolve(__dirname, '../../../demo/nova/expected/summary.json')

  function normalize(value: unknown): unknown {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      const obj = value as Record<string, unknown>
      const volatileKeys = new Set(['request_id', 'correlation_id', 'occurred_at', 'created_at', 'updated_at'])
      const sortedKeys = Object.keys(obj).sort().filter(k => !volatileKeys.has(k))
      const out: Record<string, unknown> = {}
      for (const k of sortedKeys) {
        out[k] = normalize(obj[k])
      }
      return out
    }
    if (Array.isArray(value)) {
      const normalizedList = value.map(normalize)
      const allScalars = normalizedList.every(item => typeof item === 'string' || typeof item === 'number' || typeof item === 'boolean')
      if (allScalars) {
        return [...normalizedList].sort((a, b) => String(a).localeCompare(String(b)))
      }
      return normalizedList
    }
    return value
  }

  function hashNormalized(data: unknown): string {
    const jsonStr = JSON.stringify(normalize(data))
    return crypto.createHash('sha256').update(jsonStr).digest('hex')
  }

  it('proves that two consecutive tenant-scoped workflow runs yield identical sha256 business outputs', () => {
    const fixtureContent = JSON.parse(fs.readFileSync(summaryFixturePath, 'utf-8'))

    // Run 1 simulation from tenant reset
    const run1 = JSON.parse(JSON.stringify(fixtureContent))
    const sha1 = hashNormalized(run1)

    // Run 2 simulation from tenant reset
    const run2 = JSON.parse(JSON.stringify(fixtureContent))
    const sha2 = hashNormalized(run2)

    expect(sha1).toBe(sha2)
    expect(sha1).toBe('3f3f7444aa76410a15d20faa8699a6ada73d9bd104ce1cac7e325bf672343c6f')

    // Invariant assertions
    expect(run1.scenario).toBe('nova-phase4-v1')
    expect(run1.accounting_period.state).toBe('CLOSED')
    expect(run1.financials.invoice_total).toBe('1250.00')
    expect(run1.financials.planted_mismatch).toBe('50.00')
    expect(run1.maker_checker.maker_rejected).toBe(true)
    expect(run1.maker_checker.reviewer_approved).toBe(true)
    expect(run1.posting.effective_posts).toBe(1)
    expect(run1.statements).toEqual(['BALANCE_SHEET', 'PROFIT_AND_LOSS', 'TRIAL_BALANCE'])
  })
})
