import React, { useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  GitFork,
  Loader2,
  RefreshCw,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import type {
  AccountingPeriodResponse,
  StatementSnapshotResponse,
} from '../../types/api'
import { buildSafeCsv, formatCurrency } from '../../utils/security'

interface FinancialStatementsWorkflowProps {
  currentPeriod: AccountingPeriodResponse | null
  onTraceLineSelected?: (statementLineId: string) => void
}

type StatementType = 'TRIAL_BALANCE' | 'PROFIT_AND_LOSS' | 'BALANCE_SHEET'

export const FinancialStatementsWorkflow: React.FC<FinancialStatementsWorkflowProps> = ({
  currentPeriod,
  onTraceLineSelected,
}) => {
  const { client, hasPermission } = useAuth()
  const [activeTab, setActiveTab] = useState<StatementType>('TRIAL_BALANCE')
  const [snapshots, setSnapshots] = useState<Record<StatementType, StatementSnapshotResponse | null>>({
    TRIAL_BALANCE: null,
    PROFIT_AND_LOSS: null,
    BALANCE_SHEET: null,
  })
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const handleCaptureStatement = async (type: StatementType) => {
    if (!currentPeriod) {
      setError('Please select or close an accounting period first.')
      return
    }

    setIsLoading(true)
    setError(null)
    setSuccessMsg(null)

    try {
      const snap = await client.captureStatement(currentPeriod.id, type)
      setSnapshots((prev) => ({ ...prev, [type]: snap }))
      setSuccessMsg(
        `${type.replace(/_/g, ' ')} successfully captured from Role 2 (Snapshot #${snap.id.slice(0, 8)}…)`,
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to capture ${type}.`)
    } finally {
      setIsLoading(false)
    }
  }

  const activeSnapshot = snapshots[activeTab]

  const handleExportCsv = () => {
    if (!activeSnapshot) return
    const headers = ['Line ID', 'Account Reference', 'Label', 'Amount', 'Currency', 'Snapshot ID']
    const rows = activeSnapshot.lines.map((l) => [
      l.line_id,
      l.account_reference,
      l.label,
      l.amount,
      l.currency,
      activeSnapshot.id,
    ])

    const csvContent = buildSafeCsv(headers, rows)
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `${activeTab.toLowerCase()}_${activeSnapshot.id.slice(0, 8)}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  return (
    <div className="ws-workflow-section">
      <div className="ws-section-header">
        <div>
          <h2>Role 2 Financial Statements</h2>
          <p>
            Cryptographically sealed and contract-bound Trial Balance, Profit & Loss, and Balance Sheet
            snapshots.
          </p>
        </div>
        <div className="ws-header-actions">
          {activeSnapshot && (
            <button onClick={handleExportCsv} className="button secondary" title="Export sanitized CSV">
              <Download size={14} />
              <span>Export CSV</span>
            </button>
          )}
          <button
            onClick={() => handleCaptureStatement(activeTab)}
            disabled={isLoading || !currentPeriod || !hasPermission('financial-statement:read')}
            className="button primary"
          >
            {isLoading ? <Loader2 size={14} className="spinning" /> : <RefreshCw size={14} />}
            <span>Capture {activeTab.replace(/_/g, ' ')}</span>
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

      {/* Statement Type Tabs */}
      <div className="ws-tab-row">
        {(['TRIAL_BALANCE', 'PROFIT_AND_LOSS', 'BALANCE_SHEET'] as StatementType[]).map((type) => (
          <button
            key={type}
            className={`ws-tab-btn ${activeTab === type ? 'active' : ''}`}
            onClick={() => setActiveTab(type)}
          >
            {type.replace(/_/g, ' ')}
            {snapshots[type] && <CheckCircle2 size={13} className="tab-check" />}
          </button>
        ))}
      </div>

      {/* Statement View Panel */}
      <div className="ws-panel">
        {activeSnapshot ? (
          <div>
            <div className="ws-panel-title">
              <div>
                <h3>
                  {activeSnapshot.statement_type.replace(/_/g, ' ')} — {activeSnapshot.currency}
                </h3>
                <p className="ws-subtext">
                  Snapshot ID: {activeSnapshot.id} | Role 2 Core Engine Version:{' '}
                  {activeSnapshot.role2_version} | As of: {new Date(activeSnapshot.as_of).toLocaleDateString()}
                </p>
              </div>
              <span className="ws-badge success">ROLE 2 VERIFIED SNAPSHOT</span>
            </div>

            <div className="ws-table-overflow">
              <table className="ws-record-table">
                <thead>
                  <tr>
                    <th>Account Ref</th>
                    <th>Account Label</th>
                    <th>Line Key</th>
                    <th>Amount</th>
                    <th>Provenance Action</th>
                  </tr>
                </thead>
                <tbody>
                  {activeSnapshot.lines.map((line) => (
                    <tr key={line.id}>
                      <td>
                        <strong>{line.account_reference}</strong>
                      </td>
                      <td>{line.label}</td>
                      <td>
                        <code>{line.line_id}</code>
                      </td>
                      <td>
                        <strong>{formatCurrency(line.amount, line.currency)}</strong>
                      </td>
                      <td>
                        <button
                          onClick={() => onTraceLineSelected && onTraceLineSelected(line.id)}
                          className="button secondary small"
                          title="Trace statement line back to source evidence"
                        >
                          <GitFork size={13} />
                          <span>Trace Provenance</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                  {activeSnapshot.lines.length === 0 && (
                    <tr>
                      <td colSpan={5} style={{ textAlign: 'center', padding: '2rem' }}>
                        No ledger entries present in this statement snapshot.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="ws-empty">
            <FileSpreadsheet size={28} />
            <h3>No Snapshot Captured for {activeTab.replace(/_/g, ' ')}</h3>
            <p>
              Click "Capture {activeTab.replace(/_/g, ' ')}" to request an immutable calculation from
              Role 2.
            </p>
            <button
              onClick={() => handleCaptureStatement(activeTab)}
              disabled={isLoading || !currentPeriod}
              className="button primary small"
            >
              Generate Snapshot
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
