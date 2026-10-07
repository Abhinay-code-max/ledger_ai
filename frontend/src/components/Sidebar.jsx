import React from 'react';
import {
  LayoutDashboard,
  ArrowLeftRight,
  Landmark,
  FileText,
  CreditCard,
  CheckCircle2,
  BarChart3,
  FolderArchive,
  Sparkles,
  Blocks,
  Users,
  Settings,
  ChevronLeft,
  ChevronRight,
  Building2
} from 'lucide-react';

export default function Sidebar({
  activeTab,
  setActiveTab,
  isCollapsed,
  setIsCollapsed,
  needsAttentionCount,
  uncategorizedCount
}) {
  const mainNavItems = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'transactions', label: 'Transactions', icon: ArrowLeftRight, badge: uncategorizedCount > 0 ? uncategorizedCount : null, badgeColor: 'amber' },
    { id: 'accounts', label: 'Accounts', icon: Landmark },
    { id: 'invoices', label: 'Invoices', icon: FileText, badge: 3, badgeColor: 'red' },
    { id: 'expenses', label: 'Expenses', icon: CreditCard },
    { id: 'reconciliation', label: 'Reconciliation', icon: CheckCircle2, badge: 2, badgeColor: 'amber' },
    { id: 'reports', label: 'Reports', icon: BarChart3 },
    { id: 'documents', label: 'Documents', icon: FolderArchive },
    { id: 'ai-agent', label: 'Ledger Ai Agent', icon: Sparkles, highlight: true },
  ];

  const secondaryNavItems = [
    { id: 'intelligence', label: 'Ledger Intelligence', icon: Sparkles },
    { id: 'integrations', label: 'Integrations', icon: Blocks },
    { id: 'team', label: 'Team', icon: Users },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside
      style={{
        width: isCollapsed ? '72px' : '260px',
        backgroundColor: 'var(--navy-900)',
        borderRight: '1px solid var(--border-dark)',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        position: 'sticky',
        top: 0,
        zIndex: 40,
        transition: 'width var(--transition-normal)',
        userSelect: 'none',
        flexShrink: 0
      }}
    >
      {/* Brand Header */}
      <div
        style={{
          padding: isCollapsed ? '20px 14px' : '20px 20px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: isCollapsed ? 'center' : 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Logo Mark: Ledger Structure + AI Dot */}
          <div
            style={{
              width: '34px',
              height: '34px',
              borderRadius: '8px',
              backgroundColor: 'var(--navy-800)',
              border: '1px solid rgba(35, 199, 184, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 8px rgba(0, 0, 0, 0.25)',
              position: 'relative',
              flexShrink: 0
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M4 6H18M4 12H14M4 18H18" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" />
              <circle cx="19" cy="12" r="2.5" fill="#23C7B8" />
            </svg>
          </div>

          {!isCollapsed && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '16px', fontWeight: '800', color: '#FFFFFF', letterSpacing: '-0.02em' }}>
                  Ledger
                </span>
                <span style={{ fontSize: '16px', fontWeight: '800', color: 'var(--teal-400)' }}>
                  Ai
                </span>
              </div>
              <span style={{ fontSize: '10px', color: 'var(--text-light-muted)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                Financial Control
              </span>
            </div>
          )}
        </div>

        {!isCollapsed && (
          <button
            onClick={() => setIsCollapsed(true)}
            style={{
              color: 'var(--text-light-muted)',
              padding: '4px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
            title="Collapse sidebar"
          >
            <ChevronLeft size={16} />
          </button>
        )}
      </div>

      {/* Organization Entity Selector */}
      {!isCollapsed && (
        <div
          style={{
            margin: '12px 14px',
            padding: '10px 12px',
            backgroundColor: 'rgba(255, 255, 255, 0.04)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '12px',
            color: '#FFFFFF'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
            <Building2 size={15} color="var(--teal-400)" />
            <div style={{ overflow: 'hidden' }}>
              <div style={{ fontWeight: '600', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>
                Acme Technologies
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-light-muted)' }}>
                FY 2026 • Books Open
              </div>
            </div>
          </div>
          <span style={{ fontSize: '9px', backgroundColor: 'rgba(35, 199, 184, 0.2)', color: 'var(--teal-300)', padding: '2px 5px', borderRadius: '4px', fontWeight: '700' }}>
            LIVE
          </span>
        </div>
      )}

      {/* Main Navigation */}
      <div style={{ flex: 1, overflowY: 'auto', padding: isCollapsed ? '10px 8px' : '10px 12px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
        <div style={{ fontSize: '10px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-light-muted)', padding: '6px 10px 2px', display: isCollapsed ? 'none' : 'block' }}>
          Workspace
        </div>

        {mainNavItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: isCollapsed ? 'center' : 'flex-start',
                gap: '12px',
                padding: isCollapsed ? '10px 0' : '9px 12px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: isActive
                  ? 'rgba(35, 199, 184, 0.12)'
                  : 'transparent',
                color: isActive
                  ? '#FFFFFF'
                  : 'rgba(255, 255, 255, 0.72)',
                border: isActive ? '1px solid rgba(35, 199, 184, 0.35)' : '1px solid transparent',
                fontSize: '13px',
                fontWeight: isActive ? '600' : '500',
                position: 'relative',
                transition: 'all var(--transition-fast)',
                cursor: 'pointer'
              }}
              title={isCollapsed ? item.label : undefined}
            >
              <Icon
                size={18}
                color={isActive ? 'var(--teal-400)' : item.highlight ? 'var(--teal-300)' : 'rgba(255, 255, 255, 0.65)'}
              />
              {!isCollapsed && (
                <span style={{ flex: 1, textAlign: 'left' }}>
                  {item.label}
                </span>
              )}

              {!isCollapsed && item.badge && (
                <span
                  style={{
                    backgroundColor: item.badgeColor === 'red' ? 'rgba(239, 68, 68, 0.25)' : 'rgba(217, 119, 6, 0.25)',
                    color: item.badgeColor === 'red' ? '#FCA5A5' : '#FCD34D',
                    border: item.badgeColor === 'red' ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid rgba(217, 119, 6, 0.4)',
                    padding: '1px 6px',
                    borderRadius: '10px',
                    fontSize: '11px',
                    fontWeight: '700',
                    fontFamily: 'var(--font-mono)'
                  }}
                >
                  {item.badge}
                </span>
              )}

              {!isCollapsed && item.highlight && (
                <span
                  style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--teal-400)',
                    boxShadow: '0 0 6px var(--teal-400)'
                  }}
                />
              )}
            </button>
          );
        })}

        <div style={{ fontSize: '10px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-light-muted)', padding: '16px 10px 4px', display: isCollapsed ? 'none' : 'block' }}>
          Operations & Settings
        </div>

        {secondaryNavItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: isCollapsed ? 'center' : 'flex-start',
                gap: '12px',
                padding: isCollapsed ? '10px 0' : '8px 12px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: isActive ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
                color: isActive ? '#FFFFFF' : 'rgba(255, 255, 255, 0.65)',
                fontSize: '13px',
                fontWeight: isActive ? '600' : '500',
                cursor: 'pointer'
              }}
              title={isCollapsed ? item.label : undefined}
            >
              <Icon size={17} color={isActive ? '#FFFFFF' : 'rgba(255, 255, 255, 0.5)'} />
              {!isCollapsed && <span>{item.label}</span>}
            </button>
          );
        })}
      </div>

      {/* Expand Button for Collapsed View */}
      {isCollapsed && (
        <div style={{ padding: '12px', display: 'flex', justifyContent: 'center' }}>
          <button
            onClick={() => setIsCollapsed(false)}
            style={{
              color: 'var(--text-light-muted)',
              padding: '6px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
            title="Expand sidebar"
          >
            <ChevronRight size={18} />
          </button>
        </div>
      )}

      {/* User Footer Profile */}
      <div
        style={{
          padding: isCollapsed ? '16px 8px' : '14px 16px',
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          backgroundColor: 'rgba(0, 0, 0, 0.15)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: isCollapsed ? 'center' : 'flex-start',
          gap: '10px'
        }}
      >
        <div
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            backgroundColor: 'var(--teal-600)',
            color: '#FFFFFF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '13px',
            fontWeight: '700',
            flexShrink: 0
          }}
        >
          AV
        </div>

        {!isCollapsed && (
          <div style={{ overflow: 'hidden' }}>
            <div style={{ fontSize: '13px', fontWeight: '600', color: '#FFFFFF' }}>
              Alex Vance
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-light-muted)' }}>
              Finance Lead (Owner)
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
