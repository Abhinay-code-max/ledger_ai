export type StatementType = 'TRIAL_BALANCE' | 'PROFIT_AND_LOSS' | 'BALANCE_SHEET'

export interface StatementLine {
  line_id: string
  account_code: string
  account_name: string
  amount: string // Decimal string
  debit?: string
  credit?: string
  provenance_id?: string
}

export interface FinancialStatement {
  id: string
  period_id: string
  statement_type: StatementType
  currency: string
  role2_version: string
  lines: StatementLine[]
  generated_at: string
}

export function parseDecimal(amount: string): number {
  const n = parseFloat(amount)
  if (isNaN(n)) throw new Error(`Invalid decimal amount: ${amount}`)
  return Math.round(n * 100) / 100
}

export function validateStatementInvariants(statement: FinancialStatement): { balanced: boolean; discrepancy: number } {
  if (statement.statement_type === 'TRIAL_BALANCE') {
    let totalDebit = 0
    let totalCredit = 0
    for (const line of statement.lines) {
      if (line.debit) totalDebit += parseDecimal(line.debit)
      if (line.credit) totalCredit += parseDecimal(line.credit)
    }
    const diff = Math.abs(Math.round((totalDebit - totalCredit) * 100) / 100)
    return { balanced: diff === 0, discrepancy: diff }
  }

  if (statement.statement_type === 'BALANCE_SHEET') {
    let assets = 0
    let liabilitiesAndEquity = 0
    for (const line of statement.lines) {
      const val = parseDecimal(line.amount)
      if (line.account_code.startsWith('1')) {
        assets += val
      } else if (line.account_code.startsWith('2') || line.account_code.startsWith('3')) {
        liabilitiesAndEquity += val
      }
    }
    const diff = Math.abs(Math.round((assets - liabilitiesAndEquity) * 100) / 100)
    return { balanced: diff === 0, discrepancy: diff }
  }

  return { balanced: true, discrepancy: 0 }
}
