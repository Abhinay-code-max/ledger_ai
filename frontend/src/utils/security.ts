/**
 * Hostile content safety utilities.
 *
 * All external text, filenames, OCR outputs, supplier names, descriptions,
 * model explanations, and CSV cell values are treated as untrusted.
 */

/**
 * Defends against CSV Formula Injection (CWE-1236).
 *
 * If a cell starts with `=`, `+`, `-`, `@`, `\t`, or `\r`, spreadsheet engines
 * (Excel, Calc, Sheets) may interpret it as a formula. We neutralize this by
 * prepending a single quote `'` and escaping quotes.
 */
export function sanitizeCsvCell(value: unknown): string {
  if (value === null || value === undefined) {
    return '""'
  }

  let text = String(value)
  // Check for dangerous formula trigger prefix
  if (/^[=+\-@\t\r]/.test(text)) {
    text = `'${text}`
  }

  // Escape double quotes and enclose in quotes
  return `"${text.replace(/"/g, '""')}"`
}

/**
 * Builds a safe downloadable CSV string from headers and rows.
 */
export function buildSafeCsv(headers: string[], rows: unknown[][]): string {
  const headerLine = headers.map(sanitizeCsvCell).join(',')
  const dataLines = rows.map((row) => row.map(sanitizeCsvCell).join(','))
  return [headerLine, ...dataLines].join('\r\n')
}

/**
 * Validates that a dynamic link is safe and cannot execute arbitrary scripts.
 * Rejects javascript: and data: URIs.
 */
export function isSafeUrl(url: string | null | undefined): boolean {
  if (!url) return false
  const trimmed = url.trim().toLowerCase()
  if (trimmed.startsWith('javascript:') || trimmed.startsWith('vbscript:') || trimmed.startsWith('data:text/html')) {
    return false
  }
  return true
}

/**
 * Formats monetary amounts safely without using dangerous HTML injection.
 */
export function formatCurrency(amount: string | number | null | undefined, currency = 'INR'): string {
  if (amount === null || amount === undefined) return '—'
  const numeric = typeof amount === 'number' ? amount : parseFloat(String(amount))
  if (isNaN(numeric)) return String(amount)

  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: currency || 'INR',
      maximumFractionDigits: 2,
    }).format(numeric)
  } catch {
    return `${currency} ${numeric.toFixed(2)}`
  }
}
