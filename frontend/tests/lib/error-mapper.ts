import { Role4ApiError } from './api-client'

export interface UserFacingError {
  title: string
  detail: string
  actionableMessage: string
  isAuthError: boolean
  isConflict: boolean
  isForbidden: boolean
  fieldErrors: Record<string, string>
}

export function mapApiErrorToUserFacing(error: unknown): UserFacingError {
  if (error instanceof Role4ApiError) {
    const fieldErrors: Record<string, string> = {}
    for (const f of error.fieldErrors) {
      fieldErrors[f.field] = f.message
    }

    switch (error.code) {
      case 'MAKER_CHECKER_VIOLATION':
        return {
          title: 'Maker-Checker Policy Enforcement',
          detail: 'Self-approval is prohibited. The maker who created or requested this proposal cannot approve it.',
          actionableMessage: 'An authorized independent reviewer must review and approve this record.',
          isAuthError: false,
          isConflict: false,
          isForbidden: true,
          fieldErrors,
        }

      case 'STALE_APPROVAL':
        return {
          title: 'Version Conflict (409)',
          detail: 'The proposal was updated after this review view was loaded.',
          actionableMessage: 'Please reload the latest proposal version before submitting an approval.',
          isAuthError: false,
          isConflict: true,
          isForbidden: false,
          fieldErrors,
        }

      case 'AUTHENTICATION_EXPIRED':
      case 'UNAUTHORIZED':
        return {
          title: 'Session Expired',
          detail: error.message || 'Your authentication session has expired or is invalid.',
          actionableMessage: 'Please sign in again to continue.',
          isAuthError: true,
          isConflict: false,
          isForbidden: false,
          fieldErrors,
        }

      case 'TENANT_MISMATCH':
        return {
          title: 'Tenant Boundary Violation',
          detail: 'Cross-tenant resource access is strictly forbidden.',
          actionableMessage: 'Select your authorized tenant and legal entity before accessing resources.',
          isAuthError: false,
          isConflict: false,
          isForbidden: true,
          fieldErrors,
        }

      case 'DUPLICATE_IDEMPOTENCY_KEY':
        return {
          title: 'Duplicate Submission',
          detail: 'A mutation with this idempotency key was already processed.',
          actionableMessage: 'The existing operation result has been retrieved.',
          isAuthError: false,
          isConflict: true,
          isForbidden: false,
          fieldErrors,
        }

      case 'REQUEST_TOO_LARGE':
        return {
          title: 'Payload Too Large (413)',
          detail: 'The request body or uploaded file exceeds the configured maximum byte limit.',
          actionableMessage: 'Please upload files smaller than 25MB.',
          isAuthError: false,
          isConflict: false,
          isForbidden: false,
          fieldErrors,
        }

      case 'REQUEST_TIMEOUT':
        return {
          title: 'Gateway Timeout (504)',
          detail: 'A downstream processing adapter did not respond within the allocated timeout.',
          actionableMessage: 'Please retry the operation or check downstream service health.',
          isAuthError: false,
          isConflict: false,
          isForbidden: false,
          fieldErrors,
        }

      default:
        return {
          title: `Error (${error.status})`,
          detail: error.message || 'An unexpected error occurred.',
          actionableMessage: 'Please contact support or retry the operation.',
          isAuthError: error.status === 401,
          isConflict: error.status === 409,
          isForbidden: error.status === 403,
          fieldErrors,
        }
    }
  }

  const message = error instanceof Error ? error.message : 'Unknown error'
  return {
    title: 'Network or Client Error',
    detail: message,
    actionableMessage: 'Please verify network connectivity and backend availability.',
    isAuthError: false,
    isConflict: false,
    isForbidden: false,
    fieldErrors: {},
  }
}
