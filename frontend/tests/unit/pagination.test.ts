import { describe, it, expect } from 'vitest'
import { paginate } from '../lib/state-reducers'

describe('Pagination Logic', () => {
  const dataset = Array.from({ length: 45 }, (_, i) => ({ id: `item-${i + 1}`, value: i + 1 }))

  it('paginates first page correctly', () => {
    const result = paginate(dataset, 1, 10)
    expect(result.items.length).toBe(10)
    expect(result.items[0].id).toBe('item-1')
    expect(result.items[9].id).toBe('item-10')
    expect(result.total).toBe(45)
    expect(result.totalPages).toBe(5)
    expect(result.hasPrev).toBe(false)
    expect(result.hasNext).toBe(true)
  })

  it('paginates last page correctly with remaining items', () => {
    const result = paginate(dataset, 5, 10)
    expect(result.items.length).toBe(5)
    expect(result.items[0].id).toBe('item-41')
    expect(result.items[4].id).toBe('item-45')
    expect(result.hasPrev).toBe(true)
    expect(result.hasNext).toBe(false)
  })

  it('handles empty collection safely', () => {
    const result = paginate([], 1, 10)
    expect(result.items.length).toBe(0)
    expect(result.total).toBe(0)
    expect(result.totalPages).toBe(1)
    expect(result.hasPrev).toBe(false)
    expect(result.hasNext).toBe(false)
  })

  it('clamps out-of-range page requests', () => {
    const over = paginate(dataset, 999, 10)
    expect(over.items.length).toBe(5) // Clamped to last page
    expect(over.hasPrev).toBe(true)
    expect(over.hasNext).toBe(false)

    const under = paginate(dataset, -5, 10)
    expect(under.items.length).toBe(10) // Clamped to page 1
    expect(under.hasPrev).toBe(false)
    expect(under.hasNext).toBe(true)
  })
})
