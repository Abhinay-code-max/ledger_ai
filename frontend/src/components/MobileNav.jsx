import React from 'react';
import {
  LayoutDashboard,
  AlertTriangle,
  ArrowLeftRight,
  Sparkles,
  FileText
} from 'lucide-react';

export default function MobileNav({
  activeTab,
  setActiveTab,
  setIsAiOpen,
  needsAttentionCount
}) {
  return (
    <div
      className="mobile-only"
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        height: '62px',
        backgroundColor: 'var(--navy-900)',
        borderTop: '1px solid var(--border-dark)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-around',
        zIndex: 60,
        padding: '0 8px',
        boxShadow: '0 -4px 16px rgba(0,0,0,0.2)'
      }}
    >
      <button
        onClick={() => setActiveTab('overview')}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '3px',
          color: activeTab === 'overview' ? 'var(--teal-400)' : 'rgba(255,255,255,0.65)',
          fontSize: '10px',
          fontWeight: activeTab === 'overview' ? '700' : '500',
          padding: '6px'
        }}
      >
        <LayoutDashboard size={18} />
        <span>Overview</span>
      </button>

      <button
        onClick={() => setActiveTab('overview')}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '3px',
          color: 'rgba(255,255,255,0.65)',
          fontSize: '10px',
          fontWeight: '500',
          padding: '6px',
          position: 'relative'
        }}
      >
        <AlertTriangle size={18} color="var(--alert-amber-badge)" />
        <span>Attention</span>
        {needsAttentionCount > 0 && (
          <span
            style={{
              position: 'absolute',
              top: '2px',
              right: '6px',
              width: '14px',
              height: '14px',
              borderRadius: '50%',
              backgroundColor: 'var(--alert-amber-badge)',
              color: '#FFFFFF',
              fontSize: '9px',
              fontWeight: '800',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            {needsAttentionCount}
          </span>
        )}
      </button>

      {/* Floating Center AI Action Button */}
      <button
        onClick={() => setIsAiOpen(true)}
        style={{
          width: '42px',
          height: '42px',
          borderRadius: '50%',
          backgroundColor: 'var(--teal-500)',
          color: '#FFFFFF',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 4px 12px rgba(14, 170, 165, 0.4)',
          marginTop: '-18px',
          border: '3px solid var(--navy-900)'
        }}
        title="Open Ledger Ai"
      >
        <Sparkles size={20} />
      </button>

      <button
        onClick={() => setActiveTab('transactions')}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '3px',
          color: activeTab === 'transactions' ? 'var(--teal-400)' : 'rgba(255,255,255,0.65)',
          fontSize: '10px',
          fontWeight: activeTab === 'transactions' ? '700' : '500',
          padding: '6px'
        }}
      >
        <ArrowLeftRight size={18} />
        <span>Txns</span>
      </button>

      <button
        onClick={() => setActiveTab('invoices')}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '3px',
          color: activeTab === 'invoices' ? 'var(--teal-400)' : 'rgba(255,255,255,0.65)',
          fontSize: '10px',
          fontWeight: activeTab === 'invoices' ? '700' : '500',
          padding: '6px'
        }}
      >
        <FileText size={18} />
        <span>Invoices</span>
      </button>
    </div>
  );
}
