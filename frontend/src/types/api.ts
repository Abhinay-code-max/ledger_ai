/**
 * Strictly typed definitions matching the frozen Role 4 OpenAPI contract.
 */

export type Uuid = string

export interface FieldError {
  field: string
  message: string
  code?: string
}

export type ErrorCategory =
  | 'INPUT_VALIDATION'
  | 'AUTHENTICATION'
  | 'AUTHORIZATION'
  | 'CONFLICT'
  | 'STATE_TRANSITION'
  | 'RATE_LIMIT'
  | 'DOWNSTREAM'
  | 'INTERNAL'

export interface ApiErrorEnvelope {
  schema_version: '1.0'
  category: ErrorCategory
  code: string
  message: string
  request_id: Uuid
  correlation_id?: Uuid | null
  field_errors?: FieldError[]
  help_reference?: string | null
  internal_error_id?: Uuid | null
  retryable?: boolean | null
}

export class Role4ApiError extends Error {
  readonly category: ErrorCategory
  readonly code: string
  readonly requestId: string
  readonly correlationId: string | null
  readonly fieldErrors: FieldError[]
  readonly retryable: boolean
  readonly status: number

  constructor(status: number, envelope: ApiErrorEnvelope | { code: string; message: string; [key: string]: unknown }) {
    super(envelope.message || `API error ${status} (${envelope.code || 'UNKNOWN'})`)
    this.name = 'Role4ApiError'
    this.status = status
    this.category = ('category' in envelope ? envelope.category : 'INTERNAL') as ErrorCategory
    this.code = envelope.code || `HTTP_${status}`
    this.requestId = ('request_id' in envelope && typeof envelope.request_id === 'string' ? envelope.request_id : '')
    this.correlationId = ('correlation_id' in envelope && typeof envelope.correlation_id === 'string' ? envelope.correlation_id : null)
    this.fieldErrors = ('field_errors' in envelope && Array.isArray(envelope.field_errors) ? envelope.field_errors : [])
    this.retryable = ('retryable' in envelope ? Boolean(envelope.retryable) : status >= 500 && status !== 501)
  }
}

export interface PrincipalResponse {
  principal_id: Uuid
  external_subject: string
  tenant_id: Uuid
  organization_id: Uuid | null
  legal_entity_id: Uuid | null
  membership_id: Uuid
  roles: string[]
  permissions: string[]
}

export interface OrganizationResponse {
  id: Uuid
  tenant_id: Uuid
  name: string
  code: string
  status: string
}

export interface OrganizationList {
  items: OrganizationResponse[]
  limit: number
  offset: number
}

export interface LegalEntityResponse {
  id: Uuid
  tenant_id: Uuid
  organization_id: Uuid
  legal_name: string
  display_name: string
  code: string
  country_code: string
  status: string
}

export interface LegalEntityList {
  items: LegalEntityResponse[]
  limit: number
  offset: number
}

export interface UploadInitiateRequest {
  original_filename: string
  media_type: string
  byte_size: number
  sha256: string
}

export interface UploadInitiateResponse {
  upload_id: Uuid
  document_id: Uuid
  document_version_id: Uuid
  upload_url: string
  object_key: string
  expires_at: string
}

export interface UploadCompleteRequest {
  sha256: string
  byte_size: number
}

export interface DocumentResponse {
  id: Uuid
  tenant_id: Uuid
  organization_id: Uuid
  legal_entity_id: Uuid
  original_filename: string
  status: 'PENDING_SCAN' | 'ACCEPTED' | 'REJECTED_SCAN' | 'QUARANTINED' | string
  created_at: string
  updated_at?: string
}

export interface DocumentVersionResponse {
  id: Uuid
  document_id: Uuid
  version_number: number
  status: string
  actual_sha256: string | null
  byte_size: number
  storage_version: string
  scan_status: string
  expected_media_type?: string | null
  created_at?: string
}

export interface DocumentList {
  items: DocumentResponse[]
  next_cursor?: Uuid | null
}

export interface TransactionImportResponse {
  id: Uuid
  bank_account_id: Uuid
  filename: string
  status: string
  rows_total: number
  rows_accepted: number
  rows_rejected: number
  created_at?: string
}

export interface ImportErrorResponse {
  row_number: number
  field_name: string | null
  error_code: string
  message: string
}

export interface BankTransactionResponse {
  id: Uuid
  bank_account_id: Uuid
  import_id: Uuid
  source_row_number: number
  booking_date: string
  value_date: string | null
  amount: string | number
  currency: string
  direction: 'DEBIT' | 'CREDIT'
  narration: string | null
  reference: string | null
  counterparty_name: string | null
  external_source_id?: string | null
}

export interface BankTransactionList {
  items: BankTransactionResponse[]
  next_cursor?: Uuid | null
}

export interface ExtractionRequest {
  document_version_id?: Uuid
}

export interface ExtractionResponse {
  id: Uuid
  document_id: Uuid
  document_version_id: Uuid
  extraction_version: number
  status: string
  validation_outcome: string
  contract_payload?: {
    fields?: Array<{
      field_name: string
      value: unknown
      confidence?: number
      bounding_box?: unknown
    }>
    [key: string]: unknown
  }
  created_at?: string
}

export interface ReconciliationCreateRequest {
  document_id: Uuid
  document_version_id: Uuid
  transaction_ids: Uuid[]
  correlation_id?: Uuid
}

export interface ReconciliationWorkflowResponse {
  match_proposal_id: Uuid
  exception_id: Uuid | null
  journal_proposal_id: Uuid
  policy_decision_id: Uuid
  approval_request_id: Uuid | null
}

export interface MatchProposalResponse {
  id: Uuid
  proposal_version: number
  match_type: string
  confidence: number | string | null
  status: string
  created_at?: string
}

export type ExceptionSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type ExceptionResolution = 'OPEN' | 'RESOLVED' | 'SUPPRESSED'

export interface ExceptionResponse {
  id: Uuid
  exception_type: string
  severity: ExceptionSeverity
  resolution_status: ExceptionResolution
  explanation: string
  evidence_payload?: Record<string, unknown>
  resolution_reference?: {
    reason?: string
    actor?: string
    [key: string]: unknown
  }
  version: number
  created_at?: string
}

export interface ExceptionResolveRequest {
  reason: string
}

export type ApprovalStatus = 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED' | 'ESCALATED' | 'EVIDENCE_REQUESTED' | string

export interface ApprovalRequestResponse {
  id: Uuid
  policy_decision_id: Uuid
  status: ApprovalStatus
  version: number
  created_at?: string
}

export interface ApprovalActionRequest {
  reviewed_resource_version: string
  reason: string
  corrections?: Record<string, unknown>
}

export interface ApprovalActionResponse {
  id: Uuid
  approval_request_id: Uuid
  action: string
  actor_id: string
  reason: string
  created_at?: string
}

export interface JournalProposalResponse {
  id: Uuid
  proposal_version: number
  proposed_journal_date: string
  currency: string
  lines: Array<{
    line_id: string
    account_reference: string
    direction: 'DEBIT' | 'CREDIT'
    amount: { amount: string | number; currency: string } | string | number
    description?: string
    source_evidence?: Array<{
      source_document_id: string
      document_version: string
      source_field: string
      evidence_hash: string
    }>
  }>
  explanation: string
  accounting_validation: string
  posting_status: string
  created_at?: string
}

export interface AccountingPeriodCreate {
  period_start: string
  period_end: string
  currency: string
}

export interface AccountingPeriodResponse {
  id: Uuid
  period_start: string
  period_end: string
  currency: string
  state: 'OPEN' | 'CLOSING' | 'CLOSED'
  created_at?: string
}

export interface PostingOperationCreate {
  journal_proposal_id: Uuid
  proposal_version: number
  accounting_period_id: Uuid
}

export interface PostingConfirmationResponse {
  confirmation_id: Uuid
  operation_id: Uuid
  role2_journal_id: Uuid
  role2_version: string
  posted_at: string
}

export type PostingState = 'PENDING' | 'CONFIRMED' | 'FAILED' | 'UNKNOWN'

export interface PostingOperationResponse {
  operation_id: Uuid
  journal_proposal_id: Uuid
  accounting_period_id: Uuid
  state: PostingState
  last_error_code: string | null
  confirmation: PostingConfirmationResponse | null
  created_at?: string
}

export interface CloseRunResponse {
  operation_id: Uuid
  accounting_period_id: Uuid
  state: 'PENDING' | 'CONFIRMED' | 'FAILED' | 'UNKNOWN'
  role2_version: string
  created_at?: string
}

export interface StatementLineResponse {
  id: Uuid
  line_id: string
  account_reference: string
  label: string
  amount: string | number
  currency: string
  ledger_references?: Record<string, unknown>
}

export interface StatementSnapshotResponse {
  id: Uuid
  role2_snapshot_id: Uuid
  accounting_period_id: Uuid
  statement_type: 'TRIAL_BALANCE' | 'PROFIT_AND_LOSS' | 'BALANCE_SHEET'
  currency: string
  as_of: string
  role2_version: string
  created_at: string
  lines: StatementLineResponse[]
}

export interface AuditEventResponse {
  id: Uuid
  action: string
  resource_type: string
  resource_id: Uuid
  resource_version: string
  outcome: string
  actor_id: string
  correlation_id: Uuid
  created_at: string
  metadata?: Record<string, unknown>
}

export interface ProvenanceNode {
  resource_type: string
  resource_id: string
  resource_version: string
  attributes?: Record<string, unknown>
}

export interface ProvenanceEdge {
  from_type: string
  from_id: string
  from_version: string
  to_type: string
  to_id: string
  to_version: string
  relation: string
}

export interface ProvenanceTraceResponse {
  target_type: string
  target_id: Uuid
  nodes: ProvenanceNode[]
  edges: ProvenanceEdge[]
  truncated: boolean
}

export interface ProgressProjectionResponse {
  resource_type: string
  resource_id: Uuid
  phase: string
  status: string
  percent_complete: number
  message: string
}

export interface ProgressEventResponse {
  progress_event_id: Uuid
  resource_type: string
  resource_id: Uuid
  phase: string
  status: string
  percent_complete: number
  message: string
  created_at?: string
}

export interface Page<T> {
  items: T[]
  next_cursor?: Uuid | null
}
