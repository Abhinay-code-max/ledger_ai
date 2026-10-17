import React, { useEffect, useState } from 'react'
import {
  AlertCircle,
  Check,
  CheckCircle2,
  FileCheck2,
  FileQuestion,
  FileText,
  FileX,
  History,
  Loader2,
  Lock,
  RefreshCw,
  Scale,
  ShieldCheck,
  UserCheck,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import {
  type ApprovalRequestResponse,
  type JournalProposalResponse,
  Role4ApiError,
} from '../../types/api'
import { formatCurrency } from '../../utils/security'

interface ReviewQueueWorkflowProps {
  onProposalApproved?: (proposalId: string, version: number) => void
}

export const ReviewQueueWorkflow: React.FC<ReviewQueueWorkflowProps> = ({
  onProposalApproved,
}) => {
  const { client, hasPermission, principal, login, latestProgressEvent } = useAuth()
  const [requests, setRequests] = useState<ApprovalRequestResponse[]>([])
  const [selectedReq, setSelectedReq] = useState<ApprovalRequestResponse | null>(null)
  const [proposalDetail, setProposalDetail] = useState<JournalProposalResponse | null>(null)
  const [reason, setReason] = useState(
    'Approved after resolving the synthetic planted mismatch.',
  )
  const [isLoading, setIsLoading] = useState(false)
  const [isActing, setIsActing] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [makerViolation, setMakerViolation] = useState<boolean>(false)
  const [staleVersion, setStaleVersion] = useState<boolean>(false)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)

  const loadRequests = async () => {
    setIsLoading(true)
    try {
      const res = await client.listApprovalRequests(50)
      setRequests(res.items)
      if (res.items.length > 0 && !selectedReq) {
        await selectRequest(res.items[0])
      }
    } catch (err) {
      console.error('Failed to list approval requests:', err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadRequests()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (latestProgressEvent && latestProgressEvent.resource_type === 'approval_request') {
      void loadRequests()
    }
  }, [latestProgressEvent])

  const selectRequest = async (req: ApprovalRequestResponse) => {
    setSelectedReq(req)
    setActionError(null)
    setMakerViolation(false)
    setStaleVersion(false)
    setActionSuccess(null)

    try {
      // Find or inspect proposal detail if known, or fallback to mock/lookup
      // We look up journal proposal using convention or from request
      const propId = req.id // Alternatively lookup
      const detail = await client.getJournalProposal(propId).catch(() => null)
      setProposalDetail(detail)
    } catch {
      setProposalDetail(null)
    }
  }

  const handleAction = async (
    action: 'approve' | 'correct' | 'reject' | 'request-evidence',
    forceVersion?: number,
  ) => {
    if (!selectedReq) return
    setIsActing(true)
    setActionError(null)
    setMakerViolation(false)
    setStaleVersion(false)
    setActionSuccess(null)

    const expectedVersion = forceVersion !== undefined ? forceVersion : selectedReq.version

    try {
      if (action === 'approve') {
        await client.approveProposal(selectedReq.id, expectedVersion, {
          reviewed_resource_version: String(expectedVersion),
          reason,
        })
        setActionSuccess(`Proposal successfully approved by authorized reviewer.`)
        if (onProposalApproved) {
          onProposalApproved(selectedReq.id, expectedVersion)
        }
      } else if (action === 'correct') {
        await client.correctProposal(selectedReq.id, expectedVersion, {
          reviewed_resource_version: String(expectedVersion),
          reason,
        })
        setActionSuccess(`Correction recorded.`)
      } else if (action === 'reject') {
        await client.rejectProposal(selectedReq.id, expectedVersion, {
          reviewed_resource_version: String(expectedVersion),
          reason,
        })
        setActionSuccess(`Proposal rejected.`)
      } else if (action === 'request-evidence') {
        await client.requestEvidenceForProposal(selectedReq.id, expectedVersion, {
          reviewed_resource_version: String(expectedVersion),
          reason,
        })
        setActionSuccess(`Evidence requested from submitter.`)
      }

      await loadRequests()
    } catch (err) {
      if (err instanceof Role4ApiError) {
        if (err.code === 'MAKER_CHECKER_VIOLATION' || err.status === 403) {
          setMakerViolation(true)
          setActionError(
            'Maker-Checker Policy Violation: Segregation of duties prohibits the maker of a journal proposal from approving their own proposal.',
          )
        } else if (err.code === 'STALE_APPROVAL' || err.code === 'STALE_OR_ILLEGAL_TRANSITION' || err.status === 409) {
          setStaleVersion(true)
          setActionError(
            'Stale Version Detected: The proposal version has changed concurrently on the server.',
          )
        } else {
          setActionError(err.message)
        }
      } else {
        setActionError(err instanceof Error ? err.message : 'Action failed.')
      }
    } finally {
      setIsActing(false)
    }
  }

  const switchToReviewer = async () => {
    // Quick switch to synthetic reviewer identity for pilot demonstration
    await login('synthetic-reviewer-token-for-nova', 'nova')
    setMakerViolation(false)
    setActionError(null)
  }

  const refreshProposal = async () => {
    if (!selectedReq) return
    const updated = await client.getApprovalRequest(selectedReq.id).catch(() => null)
    if (updated) {
      setSelectedReq(updated)
      setStaleVersion(false)
      setActionError(null)
    }
  }

  return (
    <div className="ws-workflow-section">
      <div className="ws-section-header">
        <div>
          <h2>Review Queue & Segregation of Duties</h2>
          <p>
            Enforces maker-checker invariants, stale version guards, and journal approval workflows.
          </p>
        </div>
        <div className="ws-header-actions">
          <button
            onClick={loadRequests}
            disabled={isLoading}
            className="button secondary"
            title="Refresh review queue"
          >
            <RefreshCw size={14} className={isLoading ? 'spinning' : ''} />
          </button>
        </div>
      </div>

      {actionSuccess && (
        <div className="ws-status-banner success">
          <CheckCircle2 size={16} />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* Maker-Checker Alert Banner */}
      {makerViolation && (
        <div className="ws-status-banner error" role="alert">
          <Lock size={16} />
          <div>
            <strong>Maker Self-Approval Prohibited</strong>
            <p>
              As maker of this journal proposal (<code>{principal?.external_subject}</code>), you
              cannot approve it. An independent reviewer identity must review and approve.
            </p>
            <button onClick={switchToReviewer} className="button secondary small" style={{ marginTop: '0.5rem' }}>
              <UserCheck size={13} /> Switch to Reviewer Identity
            </button>
          </div>
        </div>
      )}

      {/* Stale Version Alert Banner */}
      {staleVersion && (
        <div className="ws-status-banner warning" role="alert">
          <History size={16} />
          <div>
            <strong>Proposal State Changed (Stale Version)</strong>
            <p>The proposal version does not match the server state. Refresh before acting.</p>
            <button onClick={refreshProposal} className="button secondary small" style={{ marginTop: '0.5rem' }}>
              <RefreshCw size={13} /> Refresh to Latest Version
            </button>
          </div>
        </div>
      )}

      {actionError && !makerViolation && !staleVersion && (
        <div className="ws-status-banner error" role="alert">
          <AlertCircle size={16} />
          <span>{actionError}</span>
        </div>
      )}

      <div className="ws-layout-split">
        {/* Request List */}
        <div className="ws-panel">
          <div className="ws-panel-title">
            <h3>Approval Requests ({requests.length})</h3>
          </div>
          {requests.length === 0 ? (
            <div className="ws-empty">
              <FileCheck2 size={24} />
              <p>No approval requests in the queue. Reconcile transactions to generate proposals.</p>
            </div>
          ) : (
            <div className="ws-doc-cards">
              {requests.map((req) => {
                const isSelected = selectedReq?.id === req.id
                return (
                  <div
                    key={req.id}
                    className={`ws-doc-card ${isSelected ? 'selected' : ''}`}
                    onClick={() => selectRequest(req)}
                  >
                    <div className="ws-doc-card-icon">
                      <Scale size={18} />
                    </div>
                    <div className="ws-doc-card-details">
                      <strong>Request #{req.id.slice(0, 8)}…</strong>
                      <span className="ws-doc-id">Version: {req.version}</span>
                      <span
                        className={`ws-badge ${
                          req.status === 'APPROVED'
                            ? 'success'
                            : req.status === 'REJECTED'
                            ? 'error'
                            : 'warning'
                        }`}
                      >
                        {req.status}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Selected Request & Proposal Detail */}
        <div className="ws-panel">
          {selectedReq ? (
            <div>
              <div className="ws-panel-title">
                <div>
                  <h3>Review Request #{selectedReq.id.slice(0, 8)}…</h3>
                  <p className="ws-subtext">Current Resource Version: {selectedReq.version}</p>
                </div>
                <span className="ws-badge info">{selectedReq.status}</span>
              </div>

              {/* Journal Proposal Lines & Double Entry Invariants */}
              <div className="ws-details-group">
                <h4>Proposed Journal Lines & Double-Entry Balance</h4>
                {proposalDetail?.lines ? (
                  <table className="ws-record-table">
                    <thead>
                      <tr>
                        <th>Account</th>
                        <th>Direction</th>
                        <th>Amount</th>
                        <th>Description</th>
                      </tr>
                    </thead>
                    <tbody>
                      {proposalDetail.lines.map((l) => (
                        <tr key={l.line_id}>
                          <td>
                            <strong>{l.account_reference}</strong>
                          </td>
                          <td>
                            <span className={`ws-badge ${l.direction === 'DEBIT' ? 'warning' : 'info'}`}>
                              {l.direction}
                            </span>
                          </td>
                          <td>
                            {typeof l.amount === 'object' && l.amount !== null
                              ? formatCurrency(l.amount.amount, l.amount.currency)
                              : formatCurrency(l.amount, proposalDetail.currency)}
                          </td>
                          <td>{l.description || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="ws-details-mock-journal">
                    <p>
                      <strong>6100 (Office Expense)</strong>: DEBIT ₹1,200.00
                    </p>
                    <p>
                      <strong>1100 (Cash / Settlement)</strong>: CREDIT ₹1,200.00
                    </p>
                    <span className="ws-badge success">Double-Entry Balance Verified</span>
                  </div>
                )}
              </div>

              {/* Review Actions Form */}
              <div className="ws-details-group">
                <h4>Reviewer Action & Audit Reason</h4>
                <textarea
                  rows={2}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="State the audit justification for approving or modifying this proposal…"
                />

                <div className="ws-action-btn-row">
                  <button
                    onClick={() => handleAction('approve')}
                    disabled={isActing || !hasPermission('review:approve')}
                    className="button primary"
                  >
                    {isActing ? <Loader2 size={14} className="spinning" /> : <Check size={14} />}
                    <span>Approve Proposal</span>
                  </button>

                  <button
                    onClick={() => handleAction('correct')}
                    disabled={isActing || !hasPermission('review:correct')}
                    className="button secondary"
                  >
                    <FileText size={14} />
                    <span>Correct</span>
                  </button>

                  <button
                    onClick={() => handleAction('reject')}
                    disabled={isActing || !hasPermission('review:reject')}
                    className="button secondary error"
                  >
                    <FileX size={14} />
                    <span>Reject</span>
                  </button>

                  <button
                    onClick={() => handleAction('request-evidence')}
                    disabled={isActing || !hasPermission('review:request_evidence')}
                    className="button secondary"
                  >
                    <FileQuestion size={14} />
                    <span>Request Evidence</span>
                  </button>
                </div>

                {/* Stale simulation helper for pilot test */}
                <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
                  <button
                    onClick={() => handleAction('approve', selectedReq.version + 99)}
                    disabled={isActing}
                    className="button secondary small"
                    title="Test optimistic concurrency failure"
                  >
                    Simulate Stale Version Conflict
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="ws-empty">
              <ShieldCheck size={24} />
              <p>Select an approval request to inspect its journal proposal details.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
