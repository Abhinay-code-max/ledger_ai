import { describe, it, expect } from 'vitest'
import { validateUploadFile, MAX_FILE_SIZE_BYTES } from '../lib/state-reducers'

describe('Upload Validation', () => {
  it('accepts valid synthetic PDF invoice', () => {
    const result = validateUploadFile({
      name: 'NOVA_SYNTHETIC_INVOICE_001.pdf',
      size: 15420,
      type: 'application/pdf',
    })
    expect(result.valid).toBe(true)
    expect(result.error).toBeUndefined()
  })

  it('accepts valid bank transactions CSV', () => {
    const result = validateUploadFile({
      name: 'bank-transactions.csv',
      size: 512,
      type: 'text/csv',
    })
    expect(result.valid).toBe(true)
  })

  it('rejects files larger than 25MB limit', () => {
    const result = validateUploadFile({
      name: 'large-scan.pdf',
      size: MAX_FILE_SIZE_BYTES + 1024,
      type: 'application/pdf',
    })
    expect(result.valid).toBe(false)
    expect(result.error).toContain('exceeds 25MB maximum limit')
  })

  it('rejects zero-byte empty files', () => {
    const result = validateUploadFile({
      name: 'empty.pdf',
      size: 0,
      type: 'application/pdf',
    })
    expect(result.valid).toBe(false)
    expect(result.error).toContain('empty')
  })

  it('rejects hostile executable extensions', () => {
    const hostileFiles = [
      { name: 'malware.exe', size: 1024, type: 'application/octet-stream' },
      { name: 'script.sh', size: 512, type: 'application/x-sh' },
      { name: 'payload.bat', size: 256, type: 'text/plain' },
      { name: 'exploit.js', size: 1024, type: 'text/javascript' },
    ]

    for (const f of hostileFiles) {
      const result = validateUploadFile(f)
      expect(result.valid).toBe(false)
      expect(result.error).toContain('Forbidden file extension')
    }
  })
})
