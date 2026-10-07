import React, { useState, useRef, useEffect } from 'react';
import {
  Search,
  Sparkles,
  Bell,
  Plus,
  Home,
  Menu,
  ShieldCheck,
  CheckCircle,
  HelpCircle,
  User,
  ChevronDown,
  LogOut,
  UserCheck,
  Lock,
  Eye,
  Sliders
} from 'lucide-react';
import { DEMO_USERS } from '../data/authUsers';

export default function Header({
  currency,
  setCurrency,
  viewMode,
  setViewMode,
  setIsAiOpen,
  needsAttentionCount,
  onOpenNeedsAttention,
  setIsMobileMenuOpen,
  currentUser,
  onSwitchRole,
  onOpenAuth,
  onLogout,
  onNavigateHome
}) {
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const profileMenuRef = useRef(null);

  // Close profile dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(e.target)) {
        setIsProfileOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const roleColorMap = {
    cfo: { bg: 'var(--navy-900)', text: '#FFFFFF', badge: 'badge-navy' },
    accountant: { bg: 'var(--teal-600)', text: '#FFFFFF', badge: 'badge-teal' },
    auditor: { bg: '#D97706', text: '#FFFFFF', badge: 'badge-amber' }
  };

  const currentRoleStyle = roleColorMap[currentUser?.role] || roleColorMap.cfo;

  return (
    <header
      style={{
        height: '64px',
        backgroundColor: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border-light)',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        zIndex: 30,
        boxShadow: 'var(--shadow-xs)'
      }}
    >
      {/* Left Area: Mobile Menu + Home Shortcut + AI Command Bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flex: 1, maxWidth: '640px' }}>
        <button
          className="mobile-only"
          onClick={() => setIsMobileMenuOpen(prev => !prev)}
          style={{
            padding: '8px',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-light)',
            color: 'var(--text-secondary)'
          }}
        >
          <Menu size={18} />
        </button>

        {/* Quick Return to Home Page button */}
        <button
          onClick={onNavigateHome}
          className="btn-secondary"
          style={{
            fontSize: '12px',
            padding: '6px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            borderColor: 'var(--border-light)'
          }}
          title="Return to Public Home Page"
        >
          <Home size={15} color="var(--teal-600)" />
          <span className="desktop-only" style={{ fontWeight: '600' }}>Home</span>
        </button>

        {/* Persistent AI Command Bar */}
        <div
          onClick={() => setIsAiOpen(true)}
          style={{
            flex: 1,
            backgroundColor: 'var(--bg-canvas)',
            border: '1px solid var(--border-light)',
            borderRadius: 'var(--radius-md)',
            padding: '8px 14px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            cursor: 'pointer',
            transition: 'all var(--transition-fast)',
            color: 'var(--text-muted)'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--teal-500)';
            e.currentTarget.style.backgroundColor = '#FFFFFF';
            e.currentTarget.style.boxShadow = '0 0 0 3px rgba(14, 170, 165, 0.08)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--border-light)';
            e.currentTarget.style.backgroundColor = 'var(--bg-canvas)';
            e.currentTarget.style.boxShadow = 'none';
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '9px', fontSize: '13px' }}>
            <Sparkles size={16} color="var(--teal-500)" />
            <span>Ask Ledger Ai... <span style={{ color: 'var(--text-tertiary)', fontSize: '12px' }}>("Categorize debits", "Reconcile HDFC")</span></span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <kbd
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                padding: '2px 6px',
                borderRadius: '4px',
                backgroundColor: 'var(--bg-subtle)',
                border: '1px solid var(--border-medium)',
                color: 'var(--text-secondary)'
              }}
            >
              ⌘K
            </kbd>
          </div>
        </div>
      </div>

      {/* Right Controls: Currency Toggle, Role Badge & Switcher, Notifications, Actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        {/* Books Status Pill */}
        <div
          className="desktop-only"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            color: 'var(--text-secondary)',
            padding: '5px 10px',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: 'var(--bg-canvas)',
            border: '1px solid var(--border-light)'
          }}
        >
          <span style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: '#10B981' }} />
          <span>Books: <strong>October 2026</strong></span>
        </div>

        {/* Currency Selector */}
        <div
          style={{
            display: 'flex',
            border: '1px solid var(--border-light)',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--bg-canvas)',
            padding: '2px'
          }}
        >
          <button
            onClick={() => setCurrency('INR')}
            style={{
              padding: '4px 8px',
              fontSize: '11px',
              fontWeight: currency === 'INR' ? '700' : '500',
              backgroundColor: currency === 'INR' ? 'var(--navy-900)' : 'transparent',
              color: currency === 'INR' ? '#FFFFFF' : 'var(--text-muted)',
              borderRadius: 'var(--radius-xs)',
              transition: 'all var(--transition-fast)'
            }}
          >
            ₹ INR
          </button>
          <button
            onClick={() => setCurrency('USD')}
            style={{
              padding: '4px 8px',
              fontSize: '11px',
              fontWeight: currency === 'USD' ? '700' : '500',
              backgroundColor: currency === 'USD' ? 'var(--navy-900)' : 'transparent',
              color: currency === 'USD' ? '#FFFFFF' : 'var(--text-muted)',
              borderRadius: 'var(--radius-xs)',
              transition: 'all var(--transition-fast)'
            }}
          >
            $ USD
          </button>
        </div>

        {/* Auditor Read-Only Warning Indicator */}
        {currentUser?.permissions?.isReadOnly && (
          <div
            className="desktop-only animate-fade-in"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '5px 10px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--alert-amber-bg)',
              border: '1px solid var(--alert-amber-border)',
              color: 'var(--alert-amber-text)',
              fontSize: '11px',
              fontWeight: '700'
            }}
            title="Logged in with read-only inspection credentials"
          >
            <Lock size={13} />
            <span>Auditor (Read-Only)</span>
          </div>
        )}

        {/* Needs Attention Alert Bell */}
        <button
          onClick={onOpenNeedsAttention}
          style={{
            position: 'relative',
            padding: '8px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-light)',
            backgroundColor: 'var(--bg-surface)',
            color: 'var(--text-secondary)'
          }}
          title={`${needsAttentionCount} items need attention`}
        >
          <Bell size={17} />
          {needsAttentionCount > 0 && (
            <span
              style={{
                position: 'absolute',
                top: '-3px',
                right: '-3px',
                width: '18px',
                height: '18px',
                borderRadius: '50%',
                backgroundColor: 'var(--alert-amber-badge)',
                color: '#FFFFFF',
                fontSize: '10px',
                fontWeight: '800',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 0 0 2px #FFFFFF',
                fontFamily: 'var(--font-mono)'
              }}
            >
              {needsAttentionCount}
            </span>
          )}
        </button>

        {/* User Profile & Role Switcher Menu */}
        <div style={{ position: 'relative' }} ref={profileMenuRef}>
          {currentUser ? (
            <button
              onClick={() => setIsProfileOpen(prev => !prev)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '4px 10px 4px 6px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-light)',
                backgroundColor: 'var(--bg-surface)',
                cursor: 'pointer',
                transition: 'all var(--transition-fast)'
              }}
            >
              <div
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '50%',
                  backgroundColor: currentRoleStyle.bg,
                  color: currentRoleStyle.text,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '11px',
                  fontWeight: '700'
                }}
              >
                {currentUser.avatar || 'US'}
              </div>
              <div style={{ textAlign: 'left', display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontSize: '12px', fontWeight: '700', color: 'var(--navy-900)', lineHeight: 1.2 }}>
                  {currentUser.name}
                </span>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                  {currentUser.roleBadge || currentUser.roleTitle}
                </span>
              </div>
              <ChevronDown size={14} color="var(--text-muted)" />
            </button>
          ) : (
            <button
              onClick={() => onOpenAuth('signin')}
              className="btn-primary"
              style={{ fontSize: '12px', padding: '6px 12px', backgroundColor: 'var(--navy-900)' }}
            >
              Sign In
            </button>
          )}

          {/* Profile & Role Switcher Dropdown */}
          {isProfileOpen && currentUser && (
            <div
              className="animate-fade-in"
              style={{
                position: 'absolute',
                top: '100%',
                right: 0,
                marginTop: '8px',
                width: '280px',
                backgroundColor: '#FFFFFF',
                borderRadius: 'var(--radius-lg)',
                boxShadow: 'var(--shadow-panel)',
                border: '1px solid var(--border-light)',
                zIndex: 60,
                overflow: 'hidden'
              }}
            >
              {/* User Header */}
              <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-canvas)' }}>
                <div style={{ fontSize: '13px', fontWeight: '800', color: 'var(--navy-900)' }}>
                  {currentUser.name}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  {currentUser.email}
                </div>
                <div style={{ marginTop: '6px' }}>
                  <span className={`badge ${currentRoleStyle.badge}`} style={{ fontSize: '10px' }}>
                    {currentUser.roleBadge}
                  </span>
                </div>
              </div>

              {/* Fast 1-Click Role Switcher */}
              <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '10px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', marginBottom: '8px' }}>
                  Simulate Institutional Role (RBAC)
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {Object.keys(DEMO_USERS).map((roleKey) => {
                    const u = DEMO_USERS[roleKey];
                    const isCurrent = currentUser.role === roleKey;
                    return (
                      <button
                        key={roleKey}
                        onClick={() => {
                          onSwitchRole(roleKey);
                          setIsProfileOpen(false);
                        }}
                        style={{
                          width: '100%',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '7px 10px',
                          borderRadius: 'var(--radius-sm)',
                          border: 'none',
                          backgroundColor: isCurrent ? 'var(--teal-50)' : 'transparent',
                          color: isCurrent ? 'var(--teal-900)' : 'var(--text-primary)',
                          fontSize: '12px',
                          fontWeight: isCurrent ? '700' : '500',
                          cursor: 'pointer',
                          textAlign: 'left'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: roleKey === 'cfo' ? 'var(--navy-900)' : roleKey === 'accountant' ? 'var(--teal-600)' : 'var(--alert-amber-badge)' }} />
                          <span>{u.name} ({u.roleBadge})</span>
                        </div>
                        {isCurrent && <UserCheck size={14} color="var(--teal-600)" />}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Footer Actions */}
              <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <button
                  onClick={() => {
                    onNavigateHome();
                    setIsProfileOpen(false);
                  }}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '7px 10px',
                    borderRadius: 'var(--radius-sm)',
                    border: 'none',
                    backgroundColor: 'transparent',
                    color: 'var(--text-secondary)',
                    fontSize: '12px',
                    fontWeight: '600',
                    cursor: 'pointer'
                  }}
                >
                  <Home size={14} />
                  <span>Public Home Page</span>
                </button>

                <button
                  onClick={() => {
                    onLogout();
                    setIsProfileOpen(false);
                  }}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '7px 10px',
                    borderRadius: 'var(--radius-sm)',
                    border: 'none',
                    backgroundColor: 'transparent',
                    color: 'var(--alert-red-text)',
                    fontSize: '12px',
                    fontWeight: '600',
                    cursor: 'pointer'
                  }}
                >
                  <LogOut size={14} />
                  <span>Sign Out</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Primary Action Button */}
        <button
          onClick={() => setIsAiOpen(true)}
          className="btn-primary desktop-only"
          style={{
            fontSize: '12px',
            padding: '7px 14px',
            backgroundColor: 'var(--navy-900)'
          }}
        >
          <Plus size={14} />
          <span>New Action</span>
        </button>
      </div>
    </header>
  );
}
