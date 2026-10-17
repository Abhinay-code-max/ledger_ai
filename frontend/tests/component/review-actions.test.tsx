import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import React, { useState } from 'react'

export function ReviewActionPanel({
  isMaker,
  proposalVersion,
  onApprove,
}: {
  isMaker: boolean
  proposalVersion: number
  onApprove: (reason: string, version: number) => Promise<void>
}) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [success, setSuccess] = useState(false)

  async function handleApprove() {
    setError(null)
    if (isMaker) {
      setError('Maker-Checker Violation: You are the author/maker of this proposal and cannot approve it.')
      return
    }
    setBusy(true)
    try {
      await onApprove(reason, proposalVersion)
      setSuccess(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Approval failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="review-action-panel" role="region" aria-label="Review and approval actions">
      <h3>Review Decision</h3>
      <label htmlFor="approval-reason">Review Rationale</label>
      <textarea
        id="approval-reason"
        value={reason}
        onChange={e => setReason(e.target.value)}
        placeholder="Enter verification notes and approval justification..."
      />

      {error && (
        <div role="alert" className="review-error">
          {error}
        </div>
      )}

      {success && (
        <div role="status" className="review-success">
          Approval recorded successfully. Single posting initiated.
        </div>
      )}

      <button
        type="button"
        className="button-approve"
        disabled={busy || !reason.trim()}
        onClick={handleApprove}
      >
        {busy ? 'Recording Approval...' : 'Approve Proposal'}
      </button>
    </div>
  )
}

describe('Review Actions Component', () => {
  it('blocks maker self-approval with immediate policy alert', () => {
    const onApprove = vi.fn()
    render(<ReviewActionPanel isMaker={true} proposalVersion={1} onApprove={onApprove} />)

    const textarea = screen.getByLabelText(/Review Rationale/i)
    fireEvent.change(textarea, { target: { value: 'Maker approving own proposal' } })

    const approveBtn = screen.getByRole('button', { name: /Approve Proposal/i })
    fireEvent.click(approveBtn)

    expect(screen.getByRole('alert')).toHaveTextContent(/Maker-Checker Violation/i)
    expect(onApprove).not.toHaveBeenCalled()
  })

  it('allows authorized reviewer to record approval', async () => {
    const onApprove = vi.fn().mockResolvedValue(undefined)
    render(<ReviewActionPanel isMaker={false} proposalVersion={1} onApprove={onApprove} />)

    const textarea = screen.getByLabelText(/Review Rationale/i)
    fireEvent.change(textarea, { target: { value: 'Approved after inspecting discrepancy row.' } })

    const approveBtn = screen.getByRole('button', { name: /Approve Proposal/i })
    fireEvent.click(approveBtn)

    expect(onApprove).toHaveBeenCalledWith('Approved after inspecting discrepancy row.', 1)
    const successMsg = await screen.findByRole('status')
    expect(successMsg).toHaveTextContent(/Approval recorded successfully/)
  })

  it('displays conflict message on stale version error', async () => {
    const onApprove = vi.fn().mockRejectedValue(new Error('Version Conflict (409): Proposal was updated. Please reload.'))
    render(<ReviewActionPanel isMaker={false} proposalVersion={1} onApprove={onApprove} />)

    const textarea = screen.getByLabelText(/Review Rationale/i)
    fireEvent.change(textarea, { target: { value: 'Reviewer approval attempt' } })

    const approveBtn = screen.getByRole('button', { name: /Approve Proposal/i })
    fireEvent.click(approveBtn)

    const errorAlert = await screen.findByRole('alert')
    expect(errorAlert).toHaveTextContent(/Version Conflict \(409\)/i)
  })
})
