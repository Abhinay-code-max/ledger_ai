import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import React from 'react'
import { REQUIRED_PROVENANCE_PATH, validate11NodeProvenancePath } from '../lib/provenance-models'

export function ProvenanceViewer({ pathNodes }: { pathNodes: Array<{ type: string; id: string; label: string }> }) {
  const nodeTypes = pathNodes.map(n => n.type)
  const validation = validate11NodeProvenancePath(nodeTypes)

  return (
    <div className="provenance-viewer" role="region" aria-label="Statement to source document provenance">
      <h3>Statement-to-Source Provenance Chain</h3>
      <div className="provenance-integrity">
        Integrity:{' '}
        <span className={validation.valid ? 'badge-verified' : 'badge-broken'}>
          {validation.valid ? '11-NODE CHAIN VERIFIED' : 'CHAIN INCOMPLETE'}
        </span>
      </div>

      <ol className="provenance-chain">
        {pathNodes.map((node, index) => (
          <li key={node.id} className="provenance-node" data-node-type={node.type}>
            <span className="node-index">{index + 1}</span>
            <div className="node-content">
              <strong>{node.label}</strong>
              <small>{node.type}</small>
              <code className="node-id">{node.id}</code>
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}

describe('Provenance Rendering Component', () => {
  const full11NodeChain = [
    { type: 'statement_line', id: 'sl-101', label: 'Trial Balance Line (Cash at Bank)' },
    { type: 'posted_journal', id: 'pj-201', label: 'Posted Journal Entry #JE-8942' },
    { type: 'posting_confirmation', id: 'pc-301', label: 'Posting Confirmation (Role 2 engine)' },
    { type: 'journal_proposal', id: 'jp-401', label: 'Journal Proposal #JP-104' },
    { type: 'policy_decision', id: 'pd-501', label: 'Evaluated Policy Decision (ALLOW_WITH_REVIEW)' },
    { type: 'approval_action', id: 'aa-601', label: 'Reviewer Approval Action (nova-reviewer)' },
    { type: 'match_proposal', id: 'mp-701', label: 'Reconciliation Match Proposal (Score 0.98)' },
    { type: 'bank_transaction', id: 'bt-801', label: 'Imported Bank Transaction #TX-001' },
    { type: 'document_extraction', id: 'de-901', label: 'Model Document Extraction (Role 1)' },
    { type: 'document_version', id: 'dv-1001', label: 'Immutable Document Version (v1 SHA256)' },
    { type: 'source_evidence', id: 'se-1101', label: 'Source Evidence (NOVA_SYNTHETIC_INVOICE_001.pdf)' },
  ]

  it('renders all 11 nodes from statement line down to source evidence', () => {
    render(<ProvenanceViewer pathNodes={full11NodeChain} />)

    expect(screen.getByText('11-NODE CHAIN VERIFIED')).toBeInTheDocument()
    expect(screen.getByText('Trial Balance Line (Cash at Bank)')).toBeInTheDocument()
    expect(screen.getByText('Posted Journal Entry #JE-8942')).toBeInTheDocument()
    expect(screen.getByText('Source Evidence (NOVA_SYNTHETIC_INVOICE_001.pdf)')).toBeInTheDocument()

    const listItems = screen.getAllByRole('listitem')
    expect(listItems).toHaveLength(11)
  })

  it('flags broken or incomplete provenance paths', () => {
    // Drop 3 nodes
    const brokenChain = full11NodeChain.slice(0, 8)
    render(<ProvenanceViewer pathNodes={brokenChain} />)

    expect(screen.getByText('CHAIN INCOMPLETE')).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(8)
  })
})
