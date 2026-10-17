export const REQUIRED_PROVENANCE_PATH = [
  'statement_line',
  'posted_journal',
  'posting_confirmation',
  'journal_proposal',
  'policy_decision',
  'approval_action',
  'match_proposal',
  'bank_transaction',
  'document_extraction',
  'document_version',
  'source_evidence',
] as const

export type ProvenanceNodeType = typeof REQUIRED_PROVENANCE_PATH[number]

export interface ProvenanceNode {
  type: ProvenanceNodeType
  id: string
  label: string
  metadata: Record<string, unknown>
  parent?: ProvenanceNode
}

export function validate11NodeProvenancePath(path: string[]): { valid: boolean; missing: string[]; orderCorrect: boolean } {
  const missing: string[] = []
  for (const expected of REQUIRED_PROVENANCE_PATH) {
    if (!path.includes(expected)) {
      missing.push(expected)
    }
  }

  let orderCorrect = true
  let lastIndex = -1
  for (const node of path) {
    const idx = (REQUIRED_PROVENANCE_PATH as readonly string[]).indexOf(node)
    if (idx !== -1) {
      if (idx < lastIndex) {
        orderCorrect = false
      }
      lastIndex = idx
    }
  }

  return {
    valid: missing.length === 0 && orderCorrect && path.length === 11,
    missing,
    orderCorrect,
  }
}
