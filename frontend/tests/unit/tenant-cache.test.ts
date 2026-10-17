import { describe, it, expect } from 'vitest'
import { TenantCacheManager } from '../lib/state-reducers'

describe('Tenant Switch Cache Eviction', () => {
  it('clears all cached state when tenant or legal entity switches', () => {
    const cache = new TenantCacheManager<{ id: string; name: string }>()

    const novaTenant = '00000000-0000-0000-0000-000000000001'
    const novaEntity = '11111111-1111-1111-1111-111111111111'
    const foreignTenant = '99999999-9999-9999-9999-999999999999'
    const foreignEntity = '88888888-8888-8888-8888-888888888888'

    // Set scope to NOVA
    const switch1 = cache.setScope(novaTenant, novaEntity)
    expect(switch1.changed).toBe(false) // Initial scope

    cache.set('document:1', { id: 'doc-1', name: 'NOVA Invoice.pdf' })
    cache.set('statements', { id: 'stmt-1', name: 'Balance Sheet' })
    expect(cache.size()).toBe(2)
    expect(cache.get('document:1')?.name).toBe('NOVA Invoice.pdf')

    // Switch scope to foreign tenant
    const switch2 = cache.setScope(foreignTenant, foreignEntity)
    expect(switch2.changed).toBe(true)

    // Verify cache was cleared completely
    expect(cache.size()).toBe(0)
    expect(cache.get('document:1')).toBeUndefined()
    expect(cache.get('statements')).toBeUndefined()

    // Add record for foreign tenant
    cache.set('document:9', { id: 'doc-9', name: 'Foreign Doc.pdf' })
    expect(cache.size()).toBe(1)
    expect(cache.get('document:9')?.name).toBe('Foreign Doc.pdf')

    // Switch back to NOVA
    const switch3 = cache.setScope(novaTenant, novaEntity)
    expect(switch3.changed).toBe(true)

    // Foreign data is gone, and NOVA data was safely evicted
    expect(cache.size()).toBe(0)
    expect(cache.get('document:9')).toBeUndefined()
  })
})
