export interface ErrorEnvelope {
  schema_version: string
  category: 'AUTHENTICATION' | 'AUTHORIZATION' | 'INPUT_VALIDATION' | 'BUSINESS_LOGIC' | 'CONCURRENCY' | 'DOWNSTREAM' | 'INTERNAL'
  code: string
  message: string
  internal_error_id?: string | null
  request_id: string
  correlation_id: string
  field_errors: Array<{ field: string; code: string; message: string }>
}

export class Role4ApiError extends Error {
  status: number
  category: string
  code: string
  requestId?: string
  correlationId?: string
  fieldErrors: Array<{ field: string; code: string; message: string }>

  constructor(status: number, envelope?: Partial<ErrorEnvelope>) {
    super(envelope?.message || `HTTP ${status}`)
    this.name = 'Role4ApiError'
    this.status = status
    this.category = envelope?.category || (status === 401 ? 'AUTHENTICATION' : status === 403 ? 'AUTHORIZATION' : 'INTERNAL')
    this.code = envelope?.code || (status === 401 ? 'UNAUTHORIZED' : status === 403 ? 'FORBIDDEN' : status === 409 ? 'CONFLICT' : 'ERROR')
    this.requestId = envelope?.request_id
    this.correlationId = envelope?.correlation_id
    this.fieldErrors = envelope?.field_errors || []
  }
}

export interface ClientConfig {
  baseUrl: string
  token?: string
  tenantId?: string
  organizationId?: string
  legalEntityId?: string
  workspaceCode?: string
}

export class Role4ApiClient {
  private config: ClientConfig

  constructor(config: ClientConfig) {
    this.validateTargetUrl(config.baseUrl)
    this.config = { ...config, workspaceCode: config.workspaceCode || 'nova' }
  }

  private validateTargetUrl(url: string): void {
    const forbiddenRoles = [':8101', ':8102', ':8103', ':8006', '/role1', '/role2', '/role3', '/role6']
    for (const forbidden of forbiddenRoles) {
      if (url.includes(forbidden)) {
        throw new Error(`SECURITY VIOLATION: Frontend is forbidden from directly accessing internal roles (${forbidden}). Only Role 4 public API is permitted.`)
      }
    }
  }

  setToken(token: string | undefined): void {
    this.config.token = token
  }

  setTenantContext(tenantId: string, orgId: string, entityId: string): void {
    this.config.tenantId = tenantId
    this.config.organizationId = orgId
    this.config.legalEntityId = entityId
  }

  clearTenantContext(): void {
    delete this.config.tenantId
    delete this.config.organizationId
    delete this.config.legalEntityId
  }

  private buildHeaders(custom?: Record<string, string>): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Workspace-Code': this.config.workspaceCode || 'nova',
    }
    if (this.config.token) {
      headers['Authorization'] = `Bearer ${this.config.token}`
    }
    if (this.config.organizationId) {
      headers['X-Organization-ID'] = this.config.organizationId
    }
    if (this.config.legalEntityId) {
      headers['X-Legal-Entity-ID'] = this.config.legalEntityId
    }
    return { ...headers, ...custom }
  }

  async request<T>(path: string, options: RequestInit & { idempotencyKey?: string; ifMatch?: string } = {}): Promise<T> {
    const customHeaders: Record<string, string> = {}
    if (options.idempotencyKey) {
      customHeaders['Idempotency-Key'] = options.idempotencyKey
    }
    if (options.ifMatch) {
      customHeaders['If-Match'] = options.ifMatch
    }
    const headers = this.buildHeaders(customHeaders)
    const url = `${this.config.baseUrl.replace(/\/$/, '')}${path}`

    const response = await fetch(url, {
      ...options,
      headers: { ...headers, ...(options.headers as Record<string, string>) },
    })

    if (!response.ok) {
      let envelope: Partial<ErrorEnvelope> | undefined
      try {
        envelope = await response.json()
      } catch {
        // Not a JSON error envelope
      }
      throw new Role4ApiError(response.status, envelope)
    }

    if (response.status === 204) {
      return {} as T
    }
    return (await response.json()) as T
  }
}
