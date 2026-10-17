import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import React from 'react'
import { FinancialStatement, validateStatementInvariants } from '../lib/statement-models'

// Statement View Component under test
export function StatementViewer({ statement }: { statement: FinancialStatement }) {
  const { balanced, discrepancy } = validateStatementInvariants(statement)

  return (
    <div className="statement-viewer" role="region" aria-label={`${statement.statement_type} report`}>
      <header className="statement-header">
        <h2>{statement.statement_type.replace(/_/g, ' ')}</h2>
        <span className="statement-badge">{statement.currency}</span>
        <span className="role2-version">Engine: v{statement.role2_version}</span>
      </header>

      {!balanced && (
        <div role="alert" className="balance-warning">
          Warning: Statement is out of balance by {statement.currency} {discrepancy.toFixed(2)}
        </div>
      )}

      <table className="statement-table">
        <thead>
          <tr>
            <th>Account Code</th>
            <th>Account Name</th>
            {statement.statement_type === 'TRIAL_BALANCE' ? (
              <>
                <th>Debit</th>
                <th>Credit</th>
              </>
            ) : (
              <th>Amount</th>
            )}
          </tr>
        </thead>
        <tbody>
          {statement.lines.map(line => (
            <tr key={line.line_id}>
              <td>{line.account_code}</td>
              <td>{line.account_name}</td>
              {statement.statement_type === 'TRIAL_BALANCE' ? (
                <>
                  <td className="amount debit">{line.debit || '-'}</td>
                  <td className="amount credit">{line.credit || '-'}</td>
                </>
              ) : (
                <td className="amount">{line.amount}</td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <footer className="statement-footer">
        Status: <span className={balanced ? 'text-success' : 'text-danger'}>{balanced ? 'BALANCED' : 'UNBALANCED'}</span>
      </footer>
    </div>
  )
}

describe('Financial Statement Rendering Component', () => {
  const sampleTrialBalance: FinancialStatement = {
    id: 'stmt-001',
    period_id: 'prd-001',
    statement_type: 'TRIAL_BALANCE',
    currency: 'INR',
    role2_version: '1.0.0',
    generated_at: '2026-10-16T12:00:00Z',
    lines: [
      { line_id: 'line-1', account_code: '1001', account_name: 'Cash at Bank', amount: '12400.00', debit: '12400.00', credit: '0.00' },
      { line_id: 'line-2', account_code: '2001', account_name: 'Accounts Payable', amount: '12400.00', debit: '0.00', credit: '12400.00' },
    ],
  }

  const sampleBalanceSheet: FinancialStatement = {
    id: 'stmt-002',
    period_id: 'prd-001',
    statement_type: 'BALANCE_SHEET',
    currency: 'INR',
    role2_version: '1.0.0',
    generated_at: '2026-10-16T12:00:00Z',
    lines: [
      { line_id: 'bs-1', account_code: '1001', account_name: 'Operating Cash', amount: '50000.00' },
      { line_id: 'bs-2', account_code: '2001', account_name: 'Vendor Payables', amount: '20000.00' },
      { line_id: 'bs-3', account_code: '3001', account_name: 'Retained Earnings', amount: '30000.00' },
    ],
  }

  it('renders Trial Balance with exact amounts and balanced status', () => {
    render(<StatementViewer statement={sampleTrialBalance} />)
    expect(screen.getByText('TRIAL BALANCE')).toBeInTheDocument()
    expect(screen.getByText('Cash at Bank')).toBeInTheDocument()
    expect(screen.getByText('Accounts Payable')).toBeInTheDocument()
    expect(screen.getByText('BALANCED')).toBeInTheDocument()
    expect(screen.getByText('Engine: v1.0.0')).toBeInTheDocument()
  })

  it('renders Balance Sheet and validates Assets = Liabilities + Equity', () => {
    render(<StatementViewer statement={sampleBalanceSheet} />)
    expect(screen.getByText('BALANCE SHEET')).toBeInTheDocument()
    expect(screen.getByText('Operating Cash')).toBeInTheDocument()
    expect(screen.getByText('50000.00')).toBeInTheDocument()
    expect(screen.getByText('BALANCED')).toBeInTheDocument()
  })

  it('warns when a statement is unbalanced', () => {
    const unbalanced: FinancialStatement = {
      ...sampleTrialBalance,
      lines: [
        { line_id: 'line-1', account_code: '1001', account_name: 'Cash', amount: '10000.00', debit: '10000.00', credit: '0.00' },
        { line_id: 'line-2', account_code: '2001', account_name: 'Payable', amount: '8000.00', debit: '0.00', credit: '8000.00' },
      ],
    }

    render(<StatementViewer statement={unbalanced} />)
    expect(screen.getByRole('alert')).toHaveTextContent(/Statement is out of balance by INR 2000.00/)
    expect(screen.getByText('UNBALANCED')).toBeInTheDocument()
  })
})
