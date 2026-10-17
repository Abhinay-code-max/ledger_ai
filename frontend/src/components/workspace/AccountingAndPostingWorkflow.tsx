import React, { useEffect, useState } from 'react'
import {
  AlertCircle,
  AlertTriangle,
  Calendar,
  CheckCircle2,
  Clock,
  Coins,
  FolderLock,
  Loader2,
  Plus,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import type {
  AccountingPeriodResponse,
  CloseRunResponse,
  PostingOperationResponse,
} from '../../types/api'

interface AccountingAndPostingWorkflowProps {
  approvedProposalId?: string | null
  onPeriodClosed?: (period: AccountingPeriodResponse) => void
}

export const AccountingAndPostingWorkflow: React.FC<AccountingAndPostingWorkflowProps> = ({
  approvedProposalId,
  onPeriodClosed,
}) => {
  const { client, hasPermission, latestProgressEvent } = useAuth()
  const [periods, setPeriods] = useState<AccountingPeriodResponse[]>([])
  const [selectedPeriod, setSelectedPeriod] = useState<AccountingPeriodResponse | null>(null)
  const [activePosting, setActivePosting] = useState<PostingOperationResponse | null>(null)
  const [activeClose, setActiveClose] = useState<CloseRunResponse | null>(null)
  const [proposalIdInput, setProposalIdInput] = useState(approvedProposalId || '')
  const [isLoading, setIsLoading] = useState(false)
  const [isPosting, setIsPosting] = useState(false)
  const [isClosing, setIsClosing] = useState(false)
  const [isRecovering, setIsRecovering] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // New period form
  const [newPeriodStart, setNewPeriodStart] = useState('2026-09-01')
  const [newPeriodEnd, setNewPeriodEnd] = useState('2026-09-30')
  const [newPeriodCurrency, setNewPeriodCurrency] = useState('INR')

  useEffect(() => {
    if (approvedProposalId) {
      setProposalIdInput(approvedProposalId)
    }
  }, [approvedProposalId])

  const loadPeriods = async () => {
    setIsLoading(true)
    try {
      const list = await client.listAccountingPeriods(100)
      setPeriods(list)
      if (list.length > 0 && !selectedPeriod) {
        setSelectedPeriod(list[0])
      }
    } catch (err) {
      console.error('Failed to list accounting periods:', err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadPeriods()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (
      latestProgressEvent &&
      (latestProgressEvent.resource_type === 'accounting_period' ||
        latestProgressEvent.resource_type === 'posting_operation')
    ) {
      void loadPeriods()
    }
  }, [latestProgressEvent])

  const handleCreatePeriod = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)
    setSuccessMsg(null)

    try {
      const created = await client.createAccountingPeriod({
        period_start: newPeriodStart,
        period_end: newPeriodEnd,
        currency: newPeriodCurrency,
      })
      setSelectedPeriod(created)
      setSuccessMsg(`Accounting Period created: ${created.period_start} to ${created.period_end}`)
      await loadPeriods()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create accounting period.')
    } finally {
      setIsLoading(false)
    }
  }

  const handlePostJournal = async () => {
    if (!selectedPeriod) {
      setError('Select an open accounting period first.')
      return
    }
    const propId = proposalIdInput.trim()
    if (!propId) {
      setError('Approved Journal Proposal ID is required.')
      return
    }

    setIsPosting(true)
    setError(null)
    setSuccessMsg(null)

    try {
      const op = await client.startPosting({
        journal_proposal_id: propId,
        proposal_version: 1,
        accounting_period_id: selectedPeriod.id,
      })
      setActivePosting(op)

      if (op.state === 'CONFIRMED') {
        setSuccessMsg(
          `Journal successfully posted and confirmed by Role 2 (Confirmation #${op.confirmation?.confirmation_id.slice(0, 8)}…)`,
        )
      } else if (op.state === 'UNKNOWN') {
        setError(
          'Posting outcome is UNKNOWN (downstream check pending). Accounting period remains OPEN. Recovery action available.',
        )
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Posting operation failed.')
    } finally {
      setIsPosting(false)
    }
  }

  const handleRecoverPosting = async () => {
    if (!activePosting) return
    setIsRecovering(true)
    setError(null)

    try {
      const recovered = await client.recoverPosting(activePosting.operation_id)
      setActivePosting(recovered)
      if (recovered.state === 'CONFIRMED') {
        setSuccessMsg(
          `Posting state successfully resolved: CONFIRMED by Role 2 (Journal #${recovered.confirmation?.role2_journal_id.slice(0, 8)}…)`,
        )
      } else {
        setError(`Recovered state is ${recovered.state}.`)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Posting recovery failed.')
    } finally {
      setIsRecovering(false)
    }
  }

  const handleClosePeriod = async () => {
    if (!selectedPeriod) return
    setIsClosing(true)
    setError(null)
    setSuccessMsg(null)

    try {
      const run = await client.closeAccountingPeriod(selectedPeriod.id)
      setActiveClose(run)

      if (run.state === 'CONFIRMED') {
        setSuccessMsg(
          `Accounting period closed and confirmed by Role 2 (Core Version: ${run.role2_version}).`,
        )
        const updatedPeriods = await client.listAccountingPeriods(100)
        setPeriods(updatedPeriods)
        const closed = updatedPeriods.find((p) => p.id === selectedPeriod.id)
        if (closed) {
          setSelectedPeriod(closed)
          if (onPeriodClosed) onPeriodClosed(closed)
        }
      } else if (run.state === 'UNKNOWN') {
        setError('Period close returned UNKNOWN. Downstream recovery check required.')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Period close request failed.')
    } finally {
      setIsClosing(false)
    }
  }

  const handleRecoverClose = async () => {
    if (!activeClose) return
    setIsRecovering(true)
    setError(null)

    try {
      const recovered = await client.recoverPeriodClose(activeClose.operation_id)
      setActiveClose(recovered)
      if (recovered.state === 'CONFIRMED') {
        setSuccessMsg('Period close successfully recovered and confirmed.')
        await loadPeriods()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Period close recovery failed.')
    } finally {
      setIsRecovering(false)
    }
  }

  return (
    <div className="ws-workflow-section">
      <div className="ws-section-header">
        <div>
          <h2>Accounting Periods & Role 2 Posting</h2>
          <p>
            Guarded double-entry journal posting, unknown outcome recovery, and period close
            invariants.
          </p>
        </div>
        <div className="ws-header-actions">
          <button
            onClick={loadPeriods}
            disabled={isLoading}
            className="button secondary"
            title="Refresh periods"
          >
            <RefreshCw size={14} className={isLoading ? 'spinning' : ''} />
          </button>
        </div>
      </div>

      {successMsg && (
        <div className="ws-status-banner success">
          <CheckCircle2 size={16} />
          <span>{successMsg}</span>
        </div>
      )}

      {error && (
        <div className="ws-status-banner error" role="alert">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      <div className="ws-layout-split">
        {/* Accounting Periods Panel */}
        <div className="ws-panel">
          <div className="ws-panel-title">
            <h3>Accounting Periods ({periods.length})</h3>
          </div>

          <div className="ws-doc-cards">
            {periods.map((p) => {
              const isSelected = selectedPeriod?.id === p.id
              return (
                <div
                  key={p.id}
                  className={`ws-doc-card ${isSelected ? 'selected' : ''}`}
                  onClick={() => setSelectedPeriod(p)}
                >
                  <div className="ws-doc-card-icon">
                    <Calendar size={18} />
                  </div>
                  <div className="ws-doc-card-details">
                    <strong>
                      {p.period_start} → {p.period_end} ({p.currency})
                    </strong>
                    <span className="ws-doc-id">Period ID: {p.id.slice(0, 8)}…</span>
                    <span
                      className={`ws-badge ${
                        p.state === 'CLOSED' ? 'info' : p.state === 'CLOSING' ? 'warning' : 'success'
                      }`}
                    >
                      {p.state}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Create Period Form */}
          <form onSubmit={handleCreatePeriod} className="ws-period-create-form">
            <h4>Open New Accounting Period</h4>
            <div className="ws-form-grid-3">
              <label>
                Start Date
                <input
                  type="date"
                  value={newPeriodStart}
                  onChange={(e) => setNewPeriodStart(e.target.value)}
                  required
                />
              </label>
              <label>
                End Date
                <input
                  type="date"
                  value={newPeriodEnd}
                  onChange={(e) => setNewPeriodEnd(e.target.value)}
                  required
                />
              </label>
              <label>
                Currency
                <input
                  type="text"
                  maxLength={3}
                  value={newPeriodCurrency}
                  onChange={(e) => setNewPeriodCurrency(e.target.value.toUpperCase())}
                  required
                />
              </label>
            </div>
            <button
              type="submit"
              disabled={isLoading || !hasPermission('period-close:request')}
              className="button secondary small"
            >
              <Plus size={13} />
              <span>Create Period</span>
            </button>
          </form>
        </div>

        {/* Posting Operations & Period Close Action Panel */}
        <div className="ws-panel">
          <div className="ws-panel-title">
            <div>
              <h3>Role 2 Ledger Posting & Assurance</h3>
              <p className="ws-subtext">
                The UI must never display a journal as posted until Role 2 confirmation is returned.
              </p>
            </div>
          </div>

          {selectedPeriod ? (
            <div>
              <div className="ws-period-summary-box">
                <div>
                  <strong>Target Period:</strong> {selectedPeriod.period_start} to{' '}
                  {selectedPeriod.period_end} ({selectedPeriod.currency})
                </div>
                <span
                  className={`ws-badge ${
                    selectedPeriod.state === 'CLOSED' ? 'info' : 'success'
                  }`}
                >
                  {selectedPeriod.state}
                </span>
              </div>

              {/* Journal Proposal Posting Section */}
              <div className="ws-details-group">
                <h4>Execute Approved Journal Posting</h4>
                <label>
                  Approved Journal Proposal ID
                  <input
                    type="text"
                    value={proposalIdInput}
                    onChange={(e) => setProposalIdInput(e.target.value)}
                    placeholder="e.g. nova:demo:journal:..."
                  />
                </label>

                <div className="ws-action-btn-row">
                  <button
                    onClick={handlePostJournal}
                    disabled={isPosting || !proposalIdInput.trim() || selectedPeriod.state === 'CLOSED'}
                    className="button primary"
                  >
                    {isPosting ? <Loader2 size={14} className="spinning" /> : <Coins size={14} />}
                    <span>Post Journal to Role 2</span>
                  </button>
                </div>

                {/* Posting State Badge & Assurance Invariant Display */}
                {activePosting && (
                  <div className="ws-posting-result-card">
                    <div className="ws-posting-state-header">
                      <span>Posting State:</span>
                      <span
                        className={`ws-badge ${
                          activePosting.state === 'CONFIRMED'
                            ? 'success'
                            : activePosting.state === 'PENDING'
                            ? 'warning'
                            : activePosting.state === 'UNKNOWN'
                            ? 'error'
                            : 'error'
                        }`}
                      >
                        {activePosting.state}
                      </span>
                    </div>

                    {activePosting.state === 'PENDING' && (
                      <div className="ws-inline-notice">
                        <Clock size={14} />
                        <span>Posting is in progress. Awaiting Role 2 confirmation envelope.</span>
                      </div>
                    )}

                    {activePosting.state === 'UNKNOWN' && (
                      <div className="ws-posting-unknown-box">
                        <AlertTriangle size={16} />
                        <div>
                          <strong>Outcome Unknown: Role 2 State Ambiguous</strong>
                          <p>
                            Period state remains {selectedPeriod.state}. The journal is NOT marked
                            posted.
                          </p>
                          <button
                            onClick={handleRecoverPosting}
                            disabled={isRecovering}
                            className="button secondary small"
                          >
                            {isRecovering ? (
                              <Loader2 size={13} className="spinning" />
                            ) : (
                              <RotateCcw size={13} />
                            )}
                            <span>Recover Posting Outcome</span>
                          </button>
                        </div>
                      </div>
                    )}

                    {activePosting.state === 'CONFIRMED' && activePosting.confirmation && (
                      <div className="ws-posting-confirmed-box">
                        <ShieldCheck size={20} />
                        <div>
                          <strong>Role 2 Posting Confirmed & Immutable</strong>
                          <p>
                            Role 2 Journal ID: <code>{activePosting.confirmation.role2_journal_id}</code>
                          </p>
                          <p>
                            Confirmation ID: <code>{activePosting.confirmation.confirmation_id}</code>
                          </p>
                          <p>
                            Accounting Engine Version: {activePosting.confirmation.role2_version} |{' '}
                            Posted At: {new Date(activePosting.confirmation.posted_at).toLocaleString()}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Period Close Section */}
              <div className="ws-details-group">
                <h4>Period Close Workflow</h4>
                <p className="ws-subtext">
                  Closing an accounting period seals the ledger against further postings and enables
                  official financial statement snapshots.
                </p>

                <div className="ws-action-btn-row">
                  <button
                    onClick={handleClosePeriod}
                    disabled={isClosing || selectedPeriod.state === 'CLOSED'}
                    className="button primary"
                  >
                    {isClosing ? <Loader2 size={14} className="spinning" /> : <FolderLock size={14} />}
                    <span>{selectedPeriod.state === 'CLOSED' ? 'Period Closed' : 'Request Period Close'}</span>
                  </button>

                  {activeClose?.state === 'UNKNOWN' && (
                    <button
                      onClick={handleRecoverClose}
                      disabled={isRecovering}
                      className="button secondary small"
                    >
                      {isRecovering ? <Loader2 size={13} className="spinning" /> : <RotateCcw size={13} />}
                      <span>Recover Close Operation</span>
                    </button>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="ws-empty">
              <Calendar size={24} />
              <p>Select or create an accounting period to manage postings and close operations.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
