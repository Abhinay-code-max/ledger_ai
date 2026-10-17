export function sanitizeAndEscapeText(input: unknown): string {
  if (input === null || input === undefined) return ''
  const str = String(input)

  // Strip null bytes and dangerous control characters
  const cleaned = str.replace(/\0/g, '').replace(/\u202E/g, '')

  // Escape HTML entities to prevent DOM injection
  return cleaned
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
}

export function detectHostilePayload(input: string): { isSuspicious: boolean; detectedPatterns: string[] } {
  const patterns: Array<{ name: string; regex: RegExp }> = [
    { name: 'XSS Script Tag', regex: /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi },
    { name: 'XSS Inline Handler', regex: /on\w+\s*=/gi },
    { name: 'XSS Javascript Protocol', regex: /javascript\s*:/gi },
    { name: 'XSS Data URI HTML', regex: /data:text\/html/gi },
    { name: 'Template Injection', regex: /\{\{.*\}\}|\$\{.*\}/g },
    { name: 'SQL Injection Sequence', regex: /(--|\/\*|\*\/|;\s*(?:drop|select|insert|delete|update)\b)/gi },
    { name: 'Null Byte Injection', regex: /\0/ },
    { name: 'Unicode BiDi Override', regex: /[\u202A-\u202E]/ },
  ]

  const detected: string[] = []
  for (const p of patterns) {
    if (p.regex.test(input)) {
      detected.push(p.name)
    }
  }

  return {
    isSuspicious: detected.length > 0,
    detectedPatterns: detected,
  }
}
