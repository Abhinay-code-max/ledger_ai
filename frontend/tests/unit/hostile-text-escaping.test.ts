import { describe, it, expect } from 'vitest'
import { sanitizeAndEscapeText, detectHostilePayload } from '../lib/security-utils'

describe('Hostile OCR and Model Text Escaping', () => {
  it('detects and neutralizes dangerous XSS payloads', () => {
    const rawHtmlPayloads = [
      '<script>alert("XSS")</script>',
      '<img src=x onerror=alert(1)>',
      '<svg onload=alert(document.domain)>',
    ]

    for (const payload of rawHtmlPayloads) {
      const detection = detectHostilePayload(payload)
      expect(detection.isSuspicious).toBe(true)

      const escaped = sanitizeAndEscapeText(payload)
      expect(escaped).not.toContain('<script>')
      expect(escaped).not.toContain('<img')
      expect(escaped).not.toContain('<svg')
      expect(escaped).toContain('&lt;')
      expect(escaped).toContain('&gt;')
    }

    const dataUri = 'data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg=='
    expect(detectHostilePayload(dataUri).isSuspicious).toBe(true)

    const jsUrl = 'javascript:alert("hacked")'
    const jsDetect = detectHostilePayload(jsUrl)
    expect(jsDetect.isSuspicious).toBe(true)
    const jsEscaped = sanitizeAndEscapeText(jsUrl)
    expect(jsEscaped).toContain('&quot;')
  })

  it('strips null bytes and BiDi override characters', () => {
    const hostile = 'Invoice_Oct\0_Confidential\u202Efdp.exe'
    const cleaned = sanitizeAndEscapeText(hostile)
    expect(cleaned).not.toContain('\0')
    expect(cleaned).not.toContain('\u202E')
  })

  it('safely handles non-string and null/undefined values', () => {
    expect(sanitizeAndEscapeText(null)).toBe('')
    expect(sanitizeAndEscapeText(undefined)).toBe('')
    expect(sanitizeAndEscapeText(12345.67)).toBe('12345.67')
  })
})
