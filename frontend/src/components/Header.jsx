import React from 'react';
import {
  Search,
  Sparkles,
  Bell,
  Plus,
  ArrowUpRight,
  Globe,
  Menu,
  ShieldCheck,
  CheckCircle,
  HelpCircle
} from 'lucide-react';

export default function Header({
  currency,
  setCurrency,
  viewMode,
  setViewMode,
  setIsAiOpen,
  needsAttentionCount,
  onOpenNeedsAttention,
  setIsMobileMenuOpen
}) {
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
      {/* Left Area: Mobile Menu + AI Command Bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flex: 1, maxWidth: '640px' }}>
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
            <span>Ask Ledger Ai... <span style={{ color: 'var(--text-tertiary)', fontSize: '12px' }}>("Why did expenses increase?", "Reconcile HDFC")</span></span>
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

      {/* Right Controls: Currency Toggle, View Switcher, Actions, Notifications */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
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

        {/* View Mode Switcher: Workspace vs Marketing Landing Page */}
        <button
          onClick={() => setViewMode(viewMode === 'app' ? 'landing' : 'app')}
          className="btn-secondary"
          style={{
            fontSize: '12px',
            padding: '6px 12px',
            borderColor: viewMode === 'landing' ? 'var(--teal-500)' : 'var(--border-light)',
            backgroundColor: viewMode === 'landing' ? 'var(--teal-50)' : 'var(--bg-surface)'
          }}
          title={viewMode === 'app' ? 'Preview Marketing Landing Page' : 'Return to Financial Control Room'}
        >
          <Globe size={14} color={viewMode === 'landing' ? 'var(--teal-600)' : 'var(--navy-800)'} />
          <span className="desktop-only">
            {viewMode === 'app' ? 'Product Website' : 'Return to App'}
          </span>
        </button>

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
