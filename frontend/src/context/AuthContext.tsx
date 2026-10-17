/**
 * Session, Tenant, and Security Context for LedgerAI Role 4.
 *
 * Keeps tokens in memory/sessionStorage (never localStorage), prevents token logging,
 * clears state on logout, and ensures strict tenant isolation.
 */

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { Role4ApiClient } from '../api/client'
import { Role4ProgressStream, type SseConnectionStatus } from '../api/sse'
import {
  type LegalEntityResponse,
  type OrganizationResponse,
  type PrincipalResponse,
  type ProgressEventResponse,
  Role4ApiError,
} from '../types/api'

interface AuthState {
  token: string | null
  principal: PrincipalResponse | null
  workspaceCode: string
  organizations: OrganizationResponse[]
  legalEntities: LegalEntityResponse[]
  selectedOrgId: string | null
  selectedLegalEntityId: string | null
  isLoading: boolean
  error: string | null
  sseStatus: SseConnectionStatus
  latestProgressEvent: ProgressEventResponse | null
}

interface AuthContextValue extends AuthState {
  client: Role4ApiClient
  login: (token: string, workspaceCode?: string) => Promise<void>
  logout: () => void
  selectOrganization: (orgId: string) => void
  selectLegalEntity: (entityId: string) => void
  hasPermission: (perm: string) => boolean
  hasRole: (role: string) => boolean
  clearError: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

const SESSION_TOKEN_KEY = 'ledgerai_session_token'
const SESSION_WS_KEY = 'ledgerai_session_ws'

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem(SESSION_TOKEN_KEY)
    } catch {
      return null
    }
  })
  const [workspaceCode, setWorkspaceCode] = useState<string>(() => {
    try {
      return sessionStorage.getItem(SESSION_WS_KEY) || 'nova'
    } catch {
      return 'nova'
    }
  })
  const [principal, setPrincipal] = useState<PrincipalResponse | null>(null)
  const [organizations, setOrganizations] = useState<OrganizationResponse[]>([])
  const [legalEntities, setLegalEntities] = useState<LegalEntityResponse[]>([])
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null)
  const [selectedLegalEntityId, setSelectedLegalEntityId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [sseStatus, setSseStatus] = useState<SseConnectionStatus>('DISCONNECTED')
  const [latestProgressEvent, setLatestProgressEvent] = useState<ProgressEventResponse | null>(null)

  const logout = useCallback(() => {
    setToken(null)
    setPrincipal(null)
    setOrganizations([])
    setLegalEntities([])
    setSelectedOrgId(null)
    setSelectedLegalEntityId(null)
    setError(null)
    setLatestProgressEvent(null)
    setSseStatus('DISCONNECTED')
    try {
      sessionStorage.removeItem(SESSION_TOKEN_KEY)
      sessionStorage.removeItem(SESSION_WS_KEY)
    } catch {
      // Storage unavailable
    }
  }, [])

  const client = useMemo(() => {
    return new Role4ApiClient({
      token,
      workspaceCode,
      organizationId: selectedOrgId,
      legalEntityId: selectedLegalEntityId,
      onAuthExpired: logout,
    })
  }, [token, workspaceCode, selectedOrgId, selectedLegalEntityId, logout])

  // Update client context when state changes
  useEffect(() => {
    client.setContext({
      token,
      workspaceCode,
      organizationId: selectedOrgId,
      legalEntityId: selectedLegalEntityId,
      onAuthExpired: logout,
    })
  }, [client, token, workspaceCode, selectedOrgId, selectedLegalEntityId, logout])

  // SSE Stream instance
  const sseStream = useMemo(() => {
    return new Role4ProgressStream({
      context: {
        token,
        workspaceCode,
        organizationId: selectedOrgId,
        legalEntityId: selectedLegalEntityId,
        onAuthExpired: logout,
      },
      onEvent: (event) => {
        setLatestProgressEvent(event)
      },
      onStatusChange: (status) => {
        setSseStatus(status)
      },
      onError: () => {
        // Suppress noisy logs, status callback indicates state
      },
    })
  }, [token, workspaceCode, selectedOrgId, selectedLegalEntityId, logout])

  useEffect(() => {
    if (token) {
      sseStream.start()
    } else {
      sseStream.stop()
    }
    return () => {
      sseStream.stop()
    }
  }, [token, sseStream])

  const initializeSession = useCallback(
    async (authToken: string, wsCode: string) => {
      setIsLoading(true)
      setError(null)

      try {
        const tempClient = new Role4ApiClient({
          token: authToken,
          workspaceCode: wsCode,
          onAuthExpired: logout,
        })

        const me = await tempClient.getMe()
        setPrincipal(me)

        // Load organizations and legal entities for this tenant
        const [orgs, entities] = await Promise.all([
          tempClient.listOrganizations(50, 0).catch(() => ({ items: [] })),
          tempClient.listLegalEntities(50, 0).catch(() => ({ items: [] })),
        ])

        setOrganizations(orgs.items)
        setLegalEntities(entities.items)

        // Set default entity context from principal or first item
        const orgId = me.organization_id || orgs.items[0]?.id || null
        const legalId = me.legal_entity_id || entities.items[0]?.id || null

        setSelectedOrgId(orgId)
        setSelectedLegalEntityId(legalId)

        setToken(authToken)
        setWorkspaceCode(wsCode)

        try {
          sessionStorage.setItem(SESSION_TOKEN_KEY, authToken)
          sessionStorage.setItem(SESSION_WS_KEY, wsCode)
        } catch {
          // ignore
        }
      } catch (err) {
        if (err instanceof Role4ApiError) {
          setError(err.message)
        } else {
          setError(err instanceof Error ? err.message : 'Authentication verification failed.')
        }
        logout()
      } finally {
        setIsLoading(false)
      }
    },
    [logout],
  )

  const login = useCallback(
    async (authToken: string, wsCode = 'nova') => {
      await initializeSession(authToken, wsCode)
    },
    [initializeSession],
  )

  const selectOrganization = useCallback((orgId: string) => {
    setSelectedOrgId(orgId)
  }, [])

  const selectLegalEntity = useCallback((entityId: string) => {
    setSelectedLegalEntityId(entityId)
  }, [])

  const hasPermission = useCallback(
    (perm: string): boolean => {
      if (!principal) return false
      return principal.permissions.includes(perm) || principal.roles.includes('tenant-administrator')
    },
    [principal],
  )

  const hasRole = useCallback(
    (role: string): boolean => {
      if (!principal) return false
      return principal.roles.includes(role)
    },
    [principal],
  )

  // Verify session on mount if token was in sessionStorage
  useEffect(() => {
    if (token) {
      void initializeSession(token, workspaceCode)
    } else {
      setIsLoading(false)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const value: AuthContextValue = {
    token,
    principal,
    workspaceCode,
    organizations,
    legalEntities,
    selectedOrgId,
    selectedLegalEntityId,
    isLoading,
    error,
    sseStatus,
    latestProgressEvent,
    client,
    login,
    logout,
    selectOrganization,
    selectLegalEntity,
    hasPermission,
    hasRole,
    clearError: () => setError(null),
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

const defaultClient = new Role4ApiClient()

const defaultAuthContextValue: AuthContextValue = {
  token: null,
  principal: null,
  workspaceCode: 'nova',
  organizations: [],
  legalEntities: [],
  selectedOrgId: null,
  selectedLegalEntityId: null,
  isLoading: false,
  error: null,
  sseStatus: 'DISCONNECTED',
  latestProgressEvent: null,
  client: defaultClient,
  login: async () => {},
  logout: () => {},
  selectOrganization: () => {},
  selectLegalEntity: () => {},
  hasPermission: () => false,
  hasRole: () => false,
  clearError: () => {},
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  return context || defaultAuthContextValue
}
