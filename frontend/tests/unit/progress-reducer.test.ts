import { describe, it, expect } from 'vitest'
import { progressReducer, initialProgressState } from '../lib/state-reducers'

describe('Progress State Reducer', () => {
  it('transitions sequentially through the NOVA demo lifecycle', () => {
    let state = initialProgressState
    expect(state.currentStage).toBe('IDLE')

    // Upload
    state = progressReducer(state, { type: 'UPLOAD_STARTED', documentId: 'doc-001' })
    expect(state.currentStage).toBe('DOCUMENT_UPLOADED')
    expect(state.documentId).toBe('doc-001')

    state = progressReducer(state, { type: 'UPLOAD_COMPLETED', documentId: 'doc-001', status: 'ACCEPTED' })
    expect(state.currentStage).toBe('DOCUMENT_ACCEPTED')

    // Transactions
    state = progressReducer(state, { type: 'IMPORT_COMPLETED', importId: 'imp-001', count: 2 })
    expect(state.currentStage).toBe('TRANSACTIONS_IMPORTED')
    expect(state.transactionCount).toBe(2)

    // Reconciliation & exception
    state = progressReducer(state, {
      type: 'RECONCILIATION_COMPLETED',
      reconciliationId: 'rec-001',
      exceptionId: 'exc-001',
      approvalRequestId: 'appr-001',
      journalProposalId: 'prop-001',
    })
    expect(state.currentStage).toBe('EXCEPTION_CREATED')
    expect(state.exceptionStatus).toBe('OPEN')

    // Resolve exception
    state = progressReducer(state, { type: 'EXCEPTION_RESOLVED', exceptionId: 'exc-001' })
    expect(state.currentStage).toBe('EXCEPTION_RESOLVED')
    expect(state.exceptionStatus).toBe('RESOLVED')

    // Approval
    state = progressReducer(state, { type: 'APPROVAL_RECORDED', approvalRequestId: 'appr-001' })
    expect(state.currentStage).toBe('APPROVAL_RECORDED')

    // Posting
    state = progressReducer(state, { type: 'POSTING_STARTED', operationId: 'post-001', state: 'UNKNOWN' })
    expect(state.currentStage).toBe('JOURNAL_POSTING_UNKNOWN')

    state = progressReducer(state, { type: 'POSTING_CONFIRMED', operationId: 'post-001' })
    expect(state.currentStage).toBe('JOURNAL_POSTING_CONFIRMED')

    // Period close
    state = progressReducer(state, { type: 'PERIOD_CLOSED', periodId: 'prd-001' })
    expect(state.currentStage).toBe('PERIOD_CLOSE_CONFIRMED')

    // Statements
    state = progressReducer(state, { type: 'STATEMENT_LOADED', statementType: 'TRIAL_BALANCE' })
    state = progressReducer(state, { type: 'STATEMENT_LOADED', statementType: 'PROFIT_AND_LOSS' })
    state = progressReducer(state, { type: 'STATEMENT_LOADED', statementType: 'BALANCE_SHEET' })
    expect(state.currentStage).toBe('STATEMENT_CAPTURED')
    expect(state.capturedStatements).toEqual(['TRIAL_BALANCE', 'PROFIT_AND_LOSS', 'BALANCE_SHEET'])
  })

  it('suppresses duplicate SSE events by event ID', () => {
    let state = initialProgressState

    state = progressReducer(state, {
      type: 'SSE_EVENT',
      eventId: 'evt-001',
      action: 'DOCUMENT_SCANNED',
    })
    expect(state.currentStage).toBe('DOCUMENT_SCANNED')
    expect(state.completedStages).toHaveLength(1)
    expect(state.lastEventId).toBe('evt-001')

    // Repeat identical event
    const nextState = progressReducer(state, {
      type: 'SSE_EVENT',
      eventId: 'evt-001',
      action: 'DOCUMENT_SCANNED',
    })
    // Must be exact same state instance or unchanged
    expect(nextState.completedStages).toHaveLength(1)
    expect(nextState.receivedEventIds.size).toBe(1)
  })

  it('records error state on failure', () => {
    let state = initialProgressState
    state = progressReducer(state, { type: 'FAIL', error: 'Downstream timeout' })
    expect(state.currentStage).toBe('FAILED')
    expect(state.error).toBe('Downstream timeout')
  })
})
