export type WorkflowStage =
  | 'IDLE'
  | 'DOCUMENT_UPLOADED'
  | 'DOCUMENT_SCANNED'
  | 'DOCUMENT_ACCEPTED'
  | 'TRANSACTIONS_IMPORTED'
  | 'DOCUMENT_EXTRACTED'
  | 'DOCUMENT_VALIDATED'
  | 'RECONCILIATION_PROPOSED'
  | 'EXCEPTION_CREATED'
  | 'EXCEPTION_RESOLVED'
  | 'JOURNAL_PROPOSED'
  | 'POLICY_EVALUATED'
  | 'APPROVAL_RECORDED'
  | 'JOURNAL_POSTING_REQUESTED'
  | 'JOURNAL_POSTING_UNKNOWN'
  | 'JOURNAL_POSTING_CONFIRMED'
  | 'PERIOD_CLOSE_REQUESTED'
  | 'PERIOD_CLOSE_CONFIRMED'
  | 'STATEMENT_CAPTURED'
  | 'FAILED'

export interface ProgressState {
  currentStage: WorkflowStage
  completedStages: WorkflowStage[]
  documentId?: string
  documentStatus?: string
  importId?: string
  transactionCount?: number
  reconciliationId?: string
  exceptionId?: string
  exceptionStatus?: string
  approvalRequestId?: string
  journalProposalId?: string
  postingOperationId?: string
  postingState?: string
  periodId?: string
  periodState?: string
  capturedStatements: string[]
  error?: string
  receivedEventIds: Set<string>
  lastEventId?: string
}

export const initialProgressState: ProgressState = {
  currentStage: 'IDLE',
  completedStages: [],
  capturedStatements: [],
  receivedEventIds: new Set<string>(),
}

export type ProgressAction =
  | { type: 'SSE_EVENT'; eventId: string; action: string; payload?: Record<string, unknown> }
  | { type: 'UPLOAD_STARTED'; documentId: string }
  | { type: 'UPLOAD_COMPLETED'; documentId: string; status: string }
  | { type: 'IMPORT_COMPLETED'; importId: string; count: number }
  | { type: 'RECONCILIATION_COMPLETED'; reconciliationId: string; exceptionId?: string; approvalRequestId?: string; journalProposalId?: string }
  | { type: 'EXCEPTION_RESOLVED'; exceptionId: string }
  | { type: 'APPROVAL_RECORDED'; approvalRequestId: string }
  | { type: 'POSTING_STARTED'; operationId: string; state: string }
  | { type: 'POSTING_CONFIRMED'; operationId: string }
  | { type: 'PERIOD_CLOSED'; periodId: string }
  | { type: 'STATEMENT_LOADED'; statementType: string }
  | { type: 'FAIL'; error: string }
  | { type: 'RESET' }

export function progressReducer(state: ProgressState, action: ProgressAction): ProgressState {
  switch (action.type) {
    case 'SSE_EVENT': {
      // Duplicate suppression
      if (state.receivedEventIds.has(action.eventId)) {
        return state
      }
      const updatedIds = new Set(state.receivedEventIds)
      updatedIds.add(action.eventId)

      const stage = action.action as WorkflowStage
      const completed = state.completedStages.includes(stage)
        ? state.completedStages
        : [...state.completedStages, stage]

      return {
        ...state,
        currentStage: stage,
        completedStages: completed,
        lastEventId: action.eventId,
        receivedEventIds: updatedIds,
      }
    }

    case 'UPLOAD_STARTED':
      return {
        ...state,
        currentStage: 'DOCUMENT_UPLOADED',
        documentId: action.documentId,
        completedStages: [...state.completedStages, 'DOCUMENT_UPLOADED'],
      }

    case 'UPLOAD_COMPLETED':
      return {
        ...state,
        currentStage: action.status === 'ACCEPTED' ? 'DOCUMENT_ACCEPTED' : 'DOCUMENT_SCANNED',
        documentStatus: action.status,
        completedStages: [...state.completedStages, 'DOCUMENT_ACCEPTED'],
      }

    case 'IMPORT_COMPLETED':
      return {
        ...state,
        currentStage: 'TRANSACTIONS_IMPORTED',
        importId: action.importId,
        transactionCount: action.count,
        completedStages: [...state.completedStages, 'TRANSACTIONS_IMPORTED'],
      }

    case 'RECONCILIATION_COMPLETED':
      return {
        ...state,
        currentStage: action.exceptionId ? 'EXCEPTION_CREATED' : 'RECONCILIATION_PROPOSED',
        reconciliationId: action.reconciliationId,
        exceptionId: action.exceptionId,
        exceptionStatus: action.exceptionId ? 'OPEN' : undefined,
        approvalRequestId: action.approvalRequestId,
        journalProposalId: action.journalProposalId,
        completedStages: [...state.completedStages, 'RECONCILIATION_PROPOSED'],
      }

    case 'EXCEPTION_RESOLVED':
      return {
        ...state,
        currentStage: 'EXCEPTION_RESOLVED',
        exceptionStatus: 'RESOLVED',
        completedStages: [...state.completedStages, 'EXCEPTION_RESOLVED'],
      }

    case 'APPROVAL_RECORDED':
      return {
        ...state,
        currentStage: 'APPROVAL_RECORDED',
        completedStages: [...state.completedStages, 'APPROVAL_RECORDED'],
      }

    case 'POSTING_STARTED':
      return {
        ...state,
        currentStage: action.state === 'UNKNOWN' ? 'JOURNAL_POSTING_UNKNOWN' : 'JOURNAL_POSTING_REQUESTED',
        postingOperationId: action.operationId,
        postingState: action.state,
        completedStages: [...state.completedStages, 'JOURNAL_POSTING_REQUESTED'],
      }

    case 'POSTING_CONFIRMED':
      return {
        ...state,
        currentStage: 'JOURNAL_POSTING_CONFIRMED',
        postingState: 'CONFIRMED',
        completedStages: [...state.completedStages, 'JOURNAL_POSTING_CONFIRMED'],
      }

    case 'PERIOD_CLOSED':
      return {
        ...state,
        currentStage: 'PERIOD_CLOSE_CONFIRMED',
        periodId: action.periodId,
        periodState: 'CLOSED',
        completedStages: [...state.completedStages, 'PERIOD_CLOSE_CONFIRMED'],
      }

    case 'STATEMENT_LOADED': {
      const statements = state.capturedStatements.includes(action.statementType)
        ? state.capturedStatements
        : [...state.capturedStatements, action.statementType]
      return {
        ...state,
        currentStage: 'STATEMENT_CAPTURED',
        capturedStatements: statements,
        completedStages: [...state.completedStages, 'STATEMENT_CAPTURED'],
      }
    }

    case 'FAIL':
      return {
        ...state,
        currentStage: 'FAILED',
        error: action.error,
      }

    case 'RESET':
      return {
        ...initialProgressState,
        receivedEventIds: new Set<string>(),
      }

    default:
      return state
  }
}

// Tenant cache partitioner
export class TenantCacheManager<T> {
  private cache = new Map<string, T>()
  private currentScope = ''

  setScope(tenantId: string, entityId: string): { changed: boolean } {
    const newScope = `${tenantId}::${entityId}`
    const changed = this.currentScope !== '' && this.currentScope !== newScope
    this.currentScope = newScope
    if (changed) {
      // Clear all state when switching tenant context
      this.cache.clear()
    }
    return { changed }
  }

  get(key: string): T | undefined {
    return this.cache.get(`${this.currentScope}::${key}`)
  }

  set(key: string, value: T): void {
    this.cache.set(`${this.currentScope}::${key}`, value)
  }

  clear(): void {
    this.cache.clear()
    this.currentScope = ''
  }

  size(): number {
    return this.cache.size
  }
}

// Pagination helper
export interface PaginationState {
  page: number
  limit: number
  total: number
}

export function paginate<T>(items: T[], page: number, limit: number): { items: T[]; total: number; totalPages: number; hasNext: boolean; hasPrev: boolean } {
  const safeLimit = Math.max(1, limit)
  const total = items.length
  const totalPages = Math.max(1, Math.ceil(total / safeLimit))
  const safePage = Math.min(Math.max(1, page), totalPages)
  const offset = (safePage - 1) * safeLimit
  const paged = items.slice(offset, offset + safeLimit)

  return {
    items: paged,
    total,
    totalPages,
    hasNext: safePage < totalPages,
    hasPrev: safePage > 1,
  }
}

// Idempotency key generator
export function generateIdempotencyKey(operationName: string): string {
  // Use crypto.randomUUID if available, else standard v4 generator
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${operationName}-${crypto.randomUUID()}`
  }
  return `${operationName}-${'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })}`
}

// Upload validator
export interface UploadValidationResult {
  valid: boolean
  error?: string
}

export const MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024 // 25MB
export const ALLOWED_MIME_TYPES = new Set(['application/pdf', 'image/png', 'image/jpeg', 'text/csv'])
export const FORBIDDEN_EXTENSIONS = new Set(['.exe', '.sh', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.mjs', '.zip', '.tar', '.gz'])

export function validateUploadFile(file: { name: string; size: number; type: string }): UploadValidationResult {
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  if (FORBIDDEN_EXTENSIONS.has(ext)) {
    return { valid: false, error: `Forbidden file extension (${ext}). Executables and scripts are rejected.` }
  }
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return { valid: false, error: `File size exceeds 25MB maximum limit (${(file.size / (1024 * 1024)).toFixed(2)}MB).` }
  }
  if (file.size <= 0) {
    return { valid: false, error: 'File is empty.' }
  }
  if (file.type && !ALLOWED_MIME_TYPES.has(file.type)) {
    return { valid: false, error: `Unsupported media type (${file.type}). Allowed: PDF, PNG, JPEG, CSV.` }
  }
  return { valid: true }
}
