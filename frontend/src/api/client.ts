/**
 * Strict Role 4 typed API client.
 *
 * Implements bounded retries for safe reads, idempotency enforcement,
 * tenant/workspace context injection, correlation tracking, and safe error parsing.
 * Direct browser calls to internal roles (Role 1, 2, 3, 6) or datastores are prohibited.
 */

import {
  Role4ApiError,
  type AccountingPeriodCreate,
  type AccountingPeriodResponse,
  type ApprovalActionRequest,
  type ApprovalActionResponse,
  type ApprovalRequestResponse,
  type AuditEventResponse,
  type BankTransactionList,
  type BankTransactionResponse,
  type CloseRunResponse,
  type DocumentList,
  type DocumentResponse,
  type DocumentVersionResponse,
  type ErrorCategory,
  type ExceptionResolveRequest,
  type ExceptionResponse,
  type ExtractionRequest,
  type ExtractionResponse,
  type ImportErrorResponse,
  type JournalProposalResponse,
  type LegalEntityList,
  type LegalEntityResponse,
  type MatchProposalResponse,
  type OrganizationList,
  type OrganizationResponse,
  type Page,
  type PostingOperationCreate,
  type PostingOperationResponse,
  type PrincipalResponse,
  type ProvenanceTraceResponse,
  type ReconciliationCreateRequest,
  type ReconciliationWorkflowResponse,
  type StatementSnapshotResponse,
  type TransactionImportResponse,
  type UploadCompleteRequest,
  type UploadInitiateRequest,
  type UploadInitiateResponse,
  type Uuid,
} from '../types/api'

export interface ClientContext {
  token: string | null
  workspaceCode: string
  organizationId?: string | null
  legalEntityId?: string | null
  correlationId?: string
  onAuthExpired?: () => void
}

export interface RequestOptions {
  idempotencyKey?: string
  expectedVersion?: number
  signal?: AbortSignal
  retryCount?: number
  headers?: Record<string, string>
}

export class Role4ApiClient {
  private readonly baseUrl: string
  private context: ClientContext

  constructor(context?: Partial<ClientContext>, baseUrl?: string) {
    const rawUrl = baseUrl || (import.meta.env.VITE_API_BASE_URL as string | undefined) || ''
    this.baseUrl = rawUrl.replace(/\/+$/, '')
    this.context = {
      token: context?.token ?? null,
      workspaceCode: context?.workspaceCode || 'nova',
      organizationId: context?.organizationId ?? null,
      legalEntityId: context?.legalEntityId ?? null,
      correlationId: context?.correlationId || crypto.randomUUID(),
      onAuthExpired: context?.onAuthExpired,
    }
  }

  setContext(context: Partial<ClientContext>): void {
    this.context = { ...this.context, ...context }
  }

  getContext(): Readonly<ClientContext> {
    return this.context
  }

  private buildHeaders(
    options?: RequestOptions,
    isMultipart = false,
  ): Record<string, string> {
    const headers: Record<string, string> = {
      'X-Workspace-Code': this.context.workspaceCode,
      'X-Correlation-ID': this.context.correlationId || crypto.randomUUID(),
      'X-Request-ID': crypto.randomUUID(),
    }

    if (!isMultipart) {
      headers['Content-Type'] = 'application/json'
    }

    if (this.context.token) {
      headers['Authorization'] = `Bearer ${this.context.token}`
    }

    if (this.context.organizationId) {
      headers['X-Organization-ID'] = this.context.organizationId
    }

    if (this.context.legalEntityId) {
      headers['X-Legal-Entity-ID'] = this.context.legalEntityId
    }

    if (options?.idempotencyKey) {
      headers['Idempotency-Key'] = options.idempotencyKey
    }

    if (options?.expectedVersion !== undefined) {
      headers['If-Match'] = String(options.expectedVersion)
    }

    if (options?.headers) {
      Object.assign(headers, options.headers)
    }

    return headers
  }

  private async parseErrorResponse(response: Response): Promise<Role4ApiError> {
    try {
      const data = await response.json()
      if (data && typeof data === 'object') {
        return new Role4ApiError(response.status, data)
      }
    } catch {
      // Body not JSON
    }
    return new Role4ApiError(response.status, {
      code: `HTTP_${response.status}`,
      message: response.statusText || 'An unexpected server error occurred.',
      category: (response.status >= 500 ? 'INTERNAL' : 'INPUT_VALIDATION') as ErrorCategory,
      request_id: crypto.randomUUID(),
    })
  }

  async request<T>(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    path: string,
    body?: unknown,
    options?: RequestOptions,
  ): Promise<T> {
    const url = `${this.baseUrl}${path.startsWith('/') ? path : `/${path}`}`
    const isMultipart = body instanceof FormData
    const isSafeRead = method === 'GET'
    const maxRetries = isSafeRead ? Math.min(options?.retryCount ?? 3, 4) : (options?.idempotencyKey ? 2 : 0)

    let attempt = 0
    let lastError: Error | null = null

    while (attempt <= maxRetries) {
      const headers = this.buildHeaders(options, isMultipart)
      const fetchOptions: RequestInit = {
        method,
        headers,
        signal: options?.signal,
      }

      if (body !== undefined) {
        fetchOptions.body = isMultipart ? body : JSON.stringify(body)
      }

      try {
        const response = await fetch(url, fetchOptions)

        if (response.status === 401) {
          if (this.context.onAuthExpired) {
            this.context.onAuthExpired()
          }
          throw await this.parseErrorResponse(response)
        }

        if (!response.ok) {
          const apiError = await this.parseErrorResponse(response)
          // If server is 5xx or transient, retry safe reads
          if (attempt < maxRetries && isSafeRead && [502, 503, 504].includes(response.status)) {
            attempt++
            const delay = Math.min(250 * 2 ** attempt, 2000)
            await new Promise((r) => setTimeout(r, delay))
            continue
          }
          throw apiError
        }

        if (response.status === 204) {
          return undefined as unknown as T
        }

        return (await response.json()) as T
      } catch (err) {
        if (err instanceof Role4ApiError) {
          throw err
        }
        if (options?.signal?.aborted) {
          throw err
        }
        lastError = err instanceof Error ? err : new Error(String(err))
        if (attempt < maxRetries && isSafeRead) {
          attempt++
          const delay = Math.min(250 * 2 ** attempt, 2000)
          await new Promise((r) => setTimeout(r, delay))
          continue
        }
        throw new Role4ApiError(0, {
          code: 'NETWORK_ERROR',
          message: lastError.message || 'Unable to connect to Role 4 API. Verify network status.',
          category: 'DOWNSTREAM',
          request_id: crypto.randomUUID(),
          retryable: true,
        })
      }
    }

    throw lastError || new Error('Request failed after bounded retries.')
  }

  // --- Auth & Tenancy ---

  async getMe(options?: RequestOptions): Promise<PrincipalResponse> {
    return this.request<PrincipalResponse>('GET', '/api/v1/me', undefined, options)
  }

  async listOrganizations(limit = 50, offset = 0, options?: RequestOptions): Promise<OrganizationList> {
    return this.request<OrganizationList>(
      'GET',
      `/api/v1/organizations?limit=${limit}&offset=${offset}`,
      undefined,
      options,
    )
  }

  async getOrganization(id: Uuid, options?: RequestOptions): Promise<OrganizationResponse> {
    return this.request<OrganizationResponse>('GET', `/api/v1/organizations/${id}`, undefined, options)
  }

  async listLegalEntities(limit = 50, offset = 0, options?: RequestOptions): Promise<LegalEntityList> {
    return this.request<LegalEntityList>(
      'GET',
      `/api/v1/legal-entities?limit=${limit}&offset=${offset}`,
      undefined,
      options,
    )
  }

  async getLegalEntity(id: Uuid, options?: RequestOptions): Promise<LegalEntityResponse> {
    return this.request<LegalEntityResponse>('GET', `/api/v1/legal-entities/${id}`, undefined, options)
  }

  // --- Ingestion & Documents ---

  async initiateDocumentUpload(
    body: UploadInitiateRequest,
    options?: RequestOptions,
  ): Promise<UploadInitiateResponse> {
    const idempotencyKey = options?.idempotencyKey || `upload-init-${crypto.randomUUID()}`
    return this.request<UploadInitiateResponse>('POST', '/api/v1/documents/uploads', body, {
      ...options,
      idempotencyKey,
    })
  }

  /**
   * Safe upload to scoped short-lived storage URL issued by Role 4.
   * Direct MinIO permanent credentials are NEVER used by the browser.
   */
  async uploadToScopedStorageUrl(
    uploadUrl: string,
    content: Blob | ArrayBuffer | Uint8Array,
    mediaType: string,
    byteSize: number,
  ): Promise<void> {
    const headers: Record<string, string> = {
      'Content-Type': mediaType,
      'x-amz-server-side-encryption': 'AES256',
      'x-amz-meta-expected-size': String(byteSize),
    }

    const response = await fetch(uploadUrl, {
      method: 'PUT',
      headers,
      body: content instanceof Uint8Array ? new Blob([content as unknown as BlobPart], { type: mediaType }) : content,
    })

    if (!response.ok) {
      throw new Role4ApiError(response.status, {
        code: 'STORAGE_UPLOAD_FAILED',
        message: `Scoped object storage upload failed with status ${response.status}.`,
        category: 'DOWNSTREAM',
        request_id: crypto.randomUUID(),
        retryable: true,
      })
    }
  }

  async completeDocumentUpload(
    uploadId: Uuid,
    body: UploadCompleteRequest,
    options?: RequestOptions,
  ): Promise<DocumentResponse> {
    const idempotencyKey = options?.idempotencyKey || `upload-complete-${crypto.randomUUID()}`
    return this.request<DocumentResponse>(
      'POST',
      `/api/v1/documents/uploads/${uploadId}/complete`,
      body,
      { ...options, idempotencyKey },
    )
  }

  async listDocuments(limit = 50, after?: Uuid, options?: RequestOptions): Promise<DocumentList> {
    const query = new URLSearchParams({ limit: String(limit) })
    if (after) query.set('after', after)
    return this.request<DocumentList>('GET', `/api/v1/documents?${query.toString()}`, undefined, options)
  }

  async getDocument(id: Uuid, options?: RequestOptions): Promise<DocumentResponse> {
    return this.request<DocumentResponse>('GET', `/api/v1/documents/${id}`, undefined, options)
  }

  async getDocumentVersions(id: Uuid, options?: RequestOptions): Promise<DocumentVersionResponse[]> {
    return this.request<DocumentVersionResponse[]>(
      'GET',
      `/api/v1/documents/${id}/versions`,
      undefined,
      options,
    )
  }

  async importTransactionsCsv(
    file: File | Blob,
    filename: string,
    bankAccountId: Uuid,
    mappingJson = '{}',
    options?: RequestOptions,
  ): Promise<TransactionImportResponse> {
    const idempotencyKey = options?.idempotencyKey || `tx-import-${crypto.randomUUID()}`
    const formData = new FormData()
    formData.append('bank_account_id', bankAccountId)
    formData.append('mapping_json', mappingJson)
    formData.append('file', file, filename)

    return this.request<TransactionImportResponse>('POST', '/api/v1/transaction-imports', formData, {
      ...options,
      idempotencyKey,
    })
  }

  async getTransactionImport(id: Uuid, options?: RequestOptions): Promise<TransactionImportResponse> {
    return this.request<TransactionImportResponse>(
      'GET',
      `/api/v1/transaction-imports/${id}`,
      undefined,
      options,
    )
  }

  async getTransactionImportErrors(
    importId: Uuid,
    limit = 100,
    options?: RequestOptions,
  ): Promise<ImportErrorResponse[]> {
    return this.request<ImportErrorResponse[]>(
      'GET',
      `/api/v1/transaction-imports/${importId}/errors?limit=${limit}`,
      undefined,
      options,
    )
  }

  async listTransactions(
    limit = 50,
    after?: Uuid,
    importId?: Uuid,
    options?: RequestOptions,
  ): Promise<BankTransactionList> {
    const query = new URLSearchParams({ limit: String(limit) })
    if (after) query.set('after', after)
    if (importId) query.set('import_id', importId)
    return this.request<BankTransactionList>(
      'GET',
      `/api/v1/transactions?${query.toString()}`,
      undefined,
      options,
    )
  }

  async getTransaction(id: Uuid, options?: RequestOptions): Promise<BankTransactionResponse> {
    return this.request<BankTransactionResponse>('GET', `/api/v1/transactions/${id}`, undefined, options)
  }

  // --- Extractions & Reconciliation ---

  async triggerDocumentExtraction(
    documentId: Uuid,
    body?: ExtractionRequest,
    options?: RequestOptions,
  ): Promise<ExtractionResponse> {
    return this.request<ExtractionResponse>(
      'POST',
      `/api/v1/documents/${documentId}/extractions`,
      body || {},
      options,
    )
  }

  async createReconciliation(
    body: ReconciliationCreateRequest,
    options?: RequestOptions,
  ): Promise<ReconciliationWorkflowResponse> {
    return this.request<ReconciliationWorkflowResponse>(
      'POST',
      '/api/v1/reconciliations',
      body,
      options,
    )
  }

  async listReconciliationProposals(
    limit = 50,
    after?: Uuid,
    options?: RequestOptions,
  ): Promise<Page<MatchProposalResponse>> {
    const query = new URLSearchParams({ limit: String(limit) })
    if (after) query.set('after', after)
    return this.request<Page<MatchProposalResponse>>(
      'GET',
      `/api/v1/reconciliation-proposals?${query.toString()}`,
      undefined,
      options,
    )
  }

  async getReconciliationProposal(
    id: Uuid,
    options?: RequestOptions,
  ): Promise<MatchProposalResponse> {
    return this.request<MatchProposalResponse>(
      'GET',
      `/api/v1/reconciliation-proposals/${id}`,
      undefined,
      options,
    )
  }

  // --- Exceptions ---

  async listExceptions(
    limit = 50,
    after?: Uuid,
    severity?: string,
    status?: string,
    options?: RequestOptions,
  ): Promise<Page<ExceptionResponse>> {
    const query = new URLSearchParams({ limit: String(limit) })
    if (after) query.set('after', after)
    if (severity) query.set('severity', severity)
    if (status) query.set('status', status)
    return this.request<Page<ExceptionResponse>>(
      'GET',
      `/api/v1/exceptions?${query.toString()}`,
      undefined,
      options,
    )
  }

  async getException(id: Uuid, options?: RequestOptions): Promise<ExceptionResponse> {
    return this.request<ExceptionResponse>('GET', `/api/v1/exceptions/${id}`, undefined, options)
  }

  async resolveException(
    exceptionId: Uuid,
    body: ExceptionResolveRequest,
    options?: RequestOptions,
  ): Promise<ExceptionResponse> {
    return this.request<ExceptionResponse>(
      'POST',
      `/api/v1/exceptions/${exceptionId}/resolve`,
      body,
      options,
    )
  }

  // --- Approvals & Review Queue ---

  async listApprovalRequests(
    limit = 50,
    after?: Uuid,
    status?: string,
    options?: RequestOptions,
  ): Promise<Page<ApprovalRequestResponse>> {
    const query = new URLSearchParams({ limit: String(limit) })
    if (after) query.set('after', after)
    if (status) query.set('status', status)
    return this.request<Page<ApprovalRequestResponse>>(
      'GET',
      `/api/v1/approval-requests?${query.toString()}`,
      undefined,
      options,
    )
  }

  async getApprovalRequest(id: Uuid, options?: RequestOptions): Promise<ApprovalRequestResponse> {
    return this.request<ApprovalRequestResponse>(
      'GET',
      `/api/v1/approval-requests/${id}`,
      undefined,
      options,
    )
  }

  async approveProposal(
    requestId: Uuid,
    expectedVersion: number,
    body: ApprovalActionRequest,
    options?: RequestOptions,
  ): Promise<ApprovalActionResponse> {
    const idempotencyKey = options?.idempotencyKey || `approve-${crypto.randomUUID()}`
    return this.request<ApprovalActionResponse>(
      'POST',
      `/api/v1/approval-requests/${requestId}/approve`,
      body,
      { ...options, expectedVersion, idempotencyKey },
    )
  }

  async correctProposal(
    requestId: Uuid,
    expectedVersion: number,
    body: ApprovalActionRequest,
    options?: RequestOptions,
  ): Promise<ApprovalActionResponse> {
    const idempotencyKey = options?.idempotencyKey || `correct-${crypto.randomUUID()}`
    return this.request<ApprovalActionResponse>(
      'POST',
      `/api/v1/approval-requests/${requestId}/correct`,
      body,
      { ...options, expectedVersion, idempotencyKey },
    )
  }

  async rejectProposal(
    requestId: Uuid,
    expectedVersion: number,
    body: ApprovalActionRequest,
    options?: RequestOptions,
  ): Promise<ApprovalActionResponse> {
    const idempotencyKey = options?.idempotencyKey || `reject-${crypto.randomUUID()}`
    return this.request<ApprovalActionResponse>(
      'POST',
      `/api/v1/approval-requests/${requestId}/reject`,
      body,
      { ...options, expectedVersion, idempotencyKey },
    )
  }

  async requestEvidenceForProposal(
    requestId: Uuid,
    expectedVersion: number,
    body: ApprovalActionRequest,
    options?: RequestOptions,
  ): Promise<ApprovalActionResponse> {
    const idempotencyKey = options?.idempotencyKey || `req-ev-${crypto.randomUUID()}`
    return this.request<ApprovalActionResponse>(
      'POST',
      `/api/v1/approval-requests/${requestId}/request-evidence`,
      body,
      { ...options, expectedVersion, idempotencyKey },
    )
  }

  // --- Journal Proposals & Posting ---

  async getJournalProposal(id: Uuid, options?: RequestOptions): Promise<JournalProposalResponse> {
    return this.request<JournalProposalResponse>(
      'GET',
      `/api/v1/journal-proposals/${id}`,
      undefined,
      options,
    )
  }

  async listAccountingPeriods(limit = 100, options?: RequestOptions): Promise<AccountingPeriodResponse[]> {
    return this.request<AccountingPeriodResponse[]>(
      'GET',
      `/api/v1/accounting-periods?limit=${limit}`,
      undefined,
      options,
    )
  }

  async createAccountingPeriod(
    body: AccountingPeriodCreate,
    options?: RequestOptions,
  ): Promise<AccountingPeriodResponse> {
    return this.request<AccountingPeriodResponse>('POST', '/api/v1/accounting-periods', body, options)
  }

  async startPosting(
    body: PostingOperationCreate,
    options?: RequestOptions,
  ): Promise<PostingOperationResponse> {
    const idempotencyKey = options?.idempotencyKey || `post-op-${crypto.randomUUID()}`
    return this.request<PostingOperationResponse>('POST', '/api/v1/posting-operations', body, {
      ...options,
      idempotencyKey,
    })
  }

  async getPosting(operationId: Uuid, options?: RequestOptions): Promise<PostingOperationResponse> {
    return this.request<PostingOperationResponse>(
      'GET',
      `/api/v1/posting-operations/${operationId}`,
      undefined,
      options,
    )
  }

  async recoverPosting(
    operationId: Uuid,
    options?: RequestOptions,
  ): Promise<PostingOperationResponse> {
    return this.request<PostingOperationResponse>(
      'POST',
      `/api/v1/posting-operations/${operationId}/recover`,
      {},
      options,
    )
  }

  // --- Period Close & Statements ---

  async closeAccountingPeriod(
    periodId: Uuid,
    options?: RequestOptions,
  ): Promise<CloseRunResponse> {
    const idempotencyKey = options?.idempotencyKey || `close-period-${crypto.randomUUID()}`
    return this.request<CloseRunResponse>(
      'POST',
      `/api/v1/accounting-periods/${periodId}/close`,
      {},
      { ...options, idempotencyKey },
    )
  }

  async recoverPeriodClose(
    operationId: Uuid,
    options?: RequestOptions,
  ): Promise<CloseRunResponse> {
    return this.request<CloseRunResponse>(
      'POST',
      `/api/v1/period-close-operations/${operationId}/recover`,
      {},
      options,
    )
  }

  async captureStatement(
    periodId: Uuid,
    statementType: 'TRIAL_BALANCE' | 'PROFIT_AND_LOSS' | 'BALANCE_SHEET',
    options?: RequestOptions,
  ): Promise<StatementSnapshotResponse> {
    return this.request<StatementSnapshotResponse>(
      'POST',
      `/api/v1/accounting-periods/${periodId}/statements/${statementType}`,
      {},
      options,
    )
  }

  async getStatement(snapshotId: Uuid, options?: RequestOptions): Promise<StatementSnapshotResponse> {
    return this.request<StatementSnapshotResponse>(
      'GET',
      `/api/v1/financial-statements/${snapshotId}`,
      undefined,
      options,
    )
  }

  // --- Audit & Provenance ---

  async listAuditEvents(
    resourceType?: string,
    resourceId?: Uuid,
    limit = 100,
    options?: RequestOptions,
  ): Promise<AuditEventResponse[]> {
    const query = new URLSearchParams({ limit: String(limit) })
    if (resourceType) query.set('resource_type', resourceType)
    if (resourceId) query.set('resource_id', resourceId)
    return this.request<AuditEventResponse[]>(
      'GET',
      `/api/v1/audit-events?${query.toString()}`,
      undefined,
      options,
    )
  }

  async getProvenanceTrace(
    resourceType: string,
    resourceId: Uuid,
    options?: RequestOptions,
  ): Promise<ProvenanceTraceResponse> {
    return this.request<ProvenanceTraceResponse>(
      'GET',
      `/api/v1/provenance/${encodeURIComponent(resourceType)}/${encodeURIComponent(resourceId)}`,
      undefined,
      options,
    )
  }
}
