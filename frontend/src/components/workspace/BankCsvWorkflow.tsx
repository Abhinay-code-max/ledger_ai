import React, { useEffect, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  FileUp,
  Loader2,
  RefreshCw,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import type { BankTransactionResponse, TransactionImportResponse } from '../../types/api'
import { formatCurrency } from '../../utils/security'

interface BankCsvWorkflowProps {
  onSelectedTransactionsChange?: (txIds: string[]) => void
}

export const BankCsvWorkflow: React.FC<BankCsvWorkflowProps> = ({
  onSelectedTransactionsChange,
}) => {
  const { client, hasPermission } = useAuth()
  const [transactions, setTransactions] = useState<BankTransactionResponse[]>([])
  const [selectedTxIds, setSelectedTxIds] = useState<Set<string>>(new Set())
  const [isLoading, setIsLoading] = useState(false)
  const [isImporting, setIsImporting] = useState(false)
  const [importResult, setImportResult] = useState<TransactionImportResponse | null>(null)
  const [importError, setImportError] = useState<string | null>(null)
  const [cursor, setCursor] = useState<string | null>(null)
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [prevCursors, setPrevCursors] = useState<string[]>([])
  const [bankAccountId, setBankAccountId] = useState('15c191c2-81d1-4f79-8a38-7d8543649c71')

  const loadTransactions = async (afterCursor?: string | null) => {
    setIsLoading(true)
    try {
      const res = await client.listTransactions(10, afterCursor || undefined)
      setTransactions(res.items)
      setNextCursor(res.next_cursor || null)
    } catch (err) {
      console.error('Failed to list transactions:', err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadTransactions()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleNextPage = () => {
    if (!nextCursor) return
    setPrevCursors((prev) => [...prev, cursor || ''])
    setCursor(nextCursor)
    void loadTransactions(nextCursor)
  }

  const handlePrevPage = () => {
    if (prevCursors.length === 0) return
    const prev = prevCursors[prevCursors.length - 1]
    setPrevCursors((p) => p.slice(0, -1))
    setCursor(prev || null)
    void loadTransactions(prev || null)
  }

  const handleCsvUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setIsImporting(true)
    setImportError(null)
    setImportResult(null)

    try {
      const result = await client.importTransactionsCsv(
        file,
        file.name,
        bankAccountId,
        JSON.stringify({}),
      )
      setImportResult(result)
      await loadTransactions()
    } catch (err) {
      setImportError(err instanceof Error ? err.message : 'CSV import failed.')
    } finally {
      setIsImporting(false)
      event.target.value = ''
    }
  }

  const toggleSelectTx = (id: string) => {
    const next = new Set(selectedTxIds)
    if (next.has(id)) {
      next.delete(id)
    } else {
      next.add(id)
    }
    setSelectedTxIds(next)
    if (onSelectedTransactionsChange) {
      onSelectedTransactionsChange(Array.from(next))
    }
  }

  const selectAll = () => {
    if (selectedTxIds.size === transactions.length) {
      setSelectedTxIds(new Set())
      if (onSelectedTransactionsChange) onSelectedTransactionsChange([])
    } else {
      const allIds = transactions.map((t) => t.id)
      setSelectedTxIds(new Set(allIds))
      if (onSelectedTransactionsChange) onSelectedTransactionsChange(allIds)
    }
  }

  return (
    <div className="ws-workflow-section">
      <div className="ws-section-header">
        <div>
          <h2>Bank Transaction Ingestion & Feed</h2>
          <p>Import bank statement CSVs, review parsed records, and select items for reconciliation.</p>
        </div>
        <div className="ws-header-actions">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Account:</span>
            <input
              type="text"
              value={bankAccountId}
              onChange={(e) => setBankAccountId(e.target.value)}
              title="Bank Account ID"
              style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem', width: '200px', background: '#1e293b', border: '1px solid #334155', borderRadius: '4px', color: '#f8fafc' }}
            />
          </div>
          <label className="button primary ws-upload-btn">
            <FileUp size={14} />
            <span>Import Bank CSV</span>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={handleCsvUpload}
              disabled={isImporting || !hasPermission('document:write')}
              style={{ display: 'none' }}
            />
          </label>
          <button
            onClick={() => loadTransactions(cursor)}
            disabled={isLoading}
            className="button secondary"
            title="Refresh transactions"
          >
            <RefreshCw size={14} className={isLoading ? 'spinning' : ''} />
          </button>
        </div>
      </div>

      {isImporting && (
        <div className="ws-status-banner info">
          <Loader2 size={16} className="spinning" />
          <span>Ingesting bank statement and validating row signatures…</span>
        </div>
      )}

      {importResult && (
        <div className="ws-status-banner success">
          <CheckCircle2 size={16} />
          <span>
            CSV Imported: {importResult.rows_accepted} rows accepted, {importResult.rows_rejected}{' '}
            rows rejected (Total: {importResult.rows_total}).
          </span>
        </div>
      )}

      {importError && (
        <div className="ws-status-banner error" role="alert">
          <AlertCircle size={16} />
          <span>{importError}</span>
        </div>
      )}

      {/* Transactions Table with Keyset Pagination */}
      <div className="ws-panel">
        <div className="ws-panel-title">
          <div>
            <h3>Bank Statement Transactions</h3>
            <p className="ws-subtext">
              Select one or more transactions to match against pending invoice extractions.
            </p>
          </div>
          <span className="ws-badge info">
            {selectedTxIds.size} of {transactions.length} selected
          </span>
        </div>

        <div className="ws-table-overflow">
          <table className="ws-record-table">
            <thead>
              <tr>
                <th style={{ width: '40px' }}>
                  <input
                    type="checkbox"
                    aria-label="Select all transactions on current page"
                    checked={transactions.length > 0 && selectedTxIds.size === transactions.length}
                    onChange={selectAll}
                  />
                </th>
                <th>Booking Date</th>
                <th>Direction</th>
                <th>Amount</th>
                <th>Counterparty</th>
                <th>Reference</th>
                <th>Narration</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((tx) => {
                const isChecked = selectedTxIds.has(tx.id)
                return (
                  <tr
                    key={tx.id}
                    className={isChecked ? 'row-selected' : ''}
                    onClick={() => toggleSelectTx(tx.id)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleSelectTx(tx.id)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </td>
                    <td>{tx.booking_date}</td>
                    <td>
                      <span className={`ws-badge ${tx.direction === 'DEBIT' ? 'warning' : 'success'}`}>
                        {tx.direction}
                      </span>
                    </td>
                    <td>
                      <strong>{formatCurrency(tx.amount, tx.currency)}</strong>
                    </td>
                    <td>{tx.counterparty_name || '—'}</td>
                    <td>
                      <code>{tx.reference || '—'}</code>
                    </td>
                    <td>{tx.narration || '—'}</td>
                  </tr>
                )
              })}
              {transactions.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }}>
                    No transactions found. Import a CSV to populate transactions.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Keyset Pagination Controls */}
        <div className="ws-pagination-bar">
          <button
            onClick={handlePrevPage}
            disabled={prevCursors.length === 0 || isLoading}
            className="button secondary small"
          >
            <ChevronLeft size={14} /> Previous
          </button>
          <span className="ws-subtext">Keyset cursor paging</span>
          <button
            onClick={handleNextPage}
            disabled={!nextCursor || isLoading}
            className="button secondary small"
          >
            Next <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}
