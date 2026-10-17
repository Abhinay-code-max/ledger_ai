import React from 'react'
import {
  Building,
  Layers,
  LogOut,
  RefreshCw,
  ShieldCheck,
  User,
  Wifi,
  WifiOff,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import Brand from '../Brand'

export const WorkspaceHeader: React.FC = () => {
  const {
    principal,
    workspaceCode,
    organizations,
    legalEntities,
    selectedOrgId,
    selectedLegalEntityId,
    selectOrganization,
    selectLegalEntity,
    sseStatus,
    logout,
  } = useAuth()

  return (
    <header className="ws-dashboard-header-real">
      <div className="ws-header-left">
        <div className="ws-header-brand">
          <Brand />
          <span className="ws-header-env-badge">FULL-STACK RELEASE</span>
        </div>

        {/* Tenant / Organization / Legal Entity Context */}
        <div className="ws-context-selectors">
          <div className="ws-context-item">
            <Layers size={13} />
            <span className="ws-context-label">Workspace:</span>
            <span className="ws-context-value">{workspaceCode}</span>
          </div>

          {organizations.length > 0 && (
            <div className="ws-context-select-group">
              <Building size={13} />
              <select
                aria-label="Select Organization"
                value={selectedOrgId || ''}
                onChange={(e) => selectOrganization(e.target.value)}
                className="ws-context-select"
              >
                {organizations.map((org) => (
                  <option key={org.id} value={org.id}>
                    {org.name} ({org.code})
                  </option>
                ))}
              </select>
            </div>
          )}

          {legalEntities.length > 0 && (
            <div className="ws-context-select-group">
              <ShieldCheck size={13} />
              <select
                aria-label="Select Legal Entity"
                value={selectedLegalEntityId || ''}
                onChange={(e) => selectLegalEntity(e.target.value)}
                className="ws-context-select"
              >
                {legalEntities.map((entity) => (
                  <option key={entity.id} value={entity.id}>
                    {entity.display_name || entity.legal_name} ({entity.country_code})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      <div className="ws-header-right">
        {/* SSE Live Status Indicator */}
        <div
          className={`ws-sse-badge ws-sse-${sseStatus.toLowerCase()}`}
          title={`Server Progress Stream: ${sseStatus}`}
        >
          {sseStatus === 'CONNECTED' ? (
            <>
              <Wifi size={13} className="sse-icon pulse" />
              <span>LIVE SSE CONNECTED</span>
            </>
          ) : sseStatus === 'CONNECTING' ? (
            <>
              <RefreshCw size={13} className="sse-icon spinning" />
              <span>SSE RECONNECTING...</span>
            </>
          ) : (
            <>
              <WifiOff size={13} className="sse-icon" />
              <span>SSE DISCONNECTED</span>
            </>
          )}
        </div>

        {/* Principal and Roles */}
        {principal && (
          <div className="ws-user-pill">
            <div className="ws-user-avatar">
              <User size={13} />
            </div>
            <div className="ws-user-info">
              <span className="ws-user-name">{principal.external_subject}</span>
              <span className="ws-user-roles">{principal.roles.join(', ')}</span>
            </div>
          </div>
        )}

        <button
          onClick={logout}
          className="ws-signout-btn"
          aria-label="Sign out of workspace"
          title="Sign out of workspace"
        >
          <LogOut size={15} />
          <span>Sign Out</span>
        </button>
      </div>
    </header>
  )
}
