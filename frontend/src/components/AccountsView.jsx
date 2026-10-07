import React, { useState } from 'react';
import {
  Landmark,
  CreditCard,
  Building2,
  RefreshCw,
  Plus,
  CheckCircle2,
  AlertTriangle,
  ArrowUpRight,
  ExternalLink,
  ShieldCheck
} from 'lucide-react';

export default function AccountsView({
  connectedAccounts,
  currency
}) {
  const [accounts, setAccounts] = useState(connectedAccounts);
  const [isSyncing, setIsSyncing] = useState(false);
  const [toastMsg, setToastMsg] = useState(null);

  const showToast = (msg) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  const handleSyncAll = () => {
    setIsSyncing(true);
    setTimeout(() => {
      setIsSyncing(false);
      setAccounts(prev => prev.map(a => ({ ...a, lastSynced: 'Just now' })));
      showToast('All 5 financial institutions synced successfully.');
    }, 1200);
  };

  return (
    <div className="animate-fade-in" style={{ padding: '28px', maxWidth: '1440px', margin: '0 auto', width: '100%' }}>
      {toastMsg && (
        <div
          style={{
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            backgroundColor: 'var(--navy-900)',
            color: '#FFFFFF',
            padding: '12px 18px',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-lg)',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            zIndex: 100,
            fontSize: '13px',
            border: '1px solid var(--teal-500)',
          }}
        >
          <CheckCircle2 size={16} color="var(--teal-400)" />
          <span>{toastMsg}</span>
        </div>
      )}

      {/* Header Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontSize: '22px', fontWeight: '800', color: 'var(--navy-900)', letterSpacing: '-0.02em', marginBottom: '3px' }}>
            Connected Financial Accounts
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            Authoritative banking APIs, treasury hubs, corporate cards, and payment processors.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={handleSyncAll}
            disabled={isSyncing}
            className="btn-secondary btn-sm"
            style={{ padding: '7px 14px' }}
          >
            <RefreshCw size={13} className={isSyncing ? "animate-spin" : ""} />
            <span>{isSyncing ? 'Syncing Feeds...' : 'Sync All Feeds'}</span>
          </button>

          <button
            onClick={() => showToast('Connecting institutional Plaid/Finvu gateway...')}
            className="btn-teal btn-sm"
            style={{ padding: '7px 14px' }}
          >
            <Plus size={14} />
            <span>Connect Account</span>
          </button>
        </div>
      </div>

      {/* Security & Provenance Banner */}
      <div
        style={{
          padding: '12px 18px',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-light)',
          borderRadius: 'var(--radius-md)',
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '12px',
          color: 'var(--text-secondary)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldCheck size={16} color="var(--teal-600)" />
          <span>Institutional Read-Only Feed • 256-bit AES Encryption • Zero direct credential storage</span>
        </div>
        <div className="mono-num" style={{ color: 'var(--text-muted)' }}>
          Total Liquidity: <strong>₹1,42,85,600</strong> ($1.72M)
        </div>
      </div>

      {/* Compact List/Grid Hybrid Layout */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))',
          gap: '16px'
        }}
      >
        {accounts.map((acc) => {
          return (
            <div
              key={acc.id}
              className="panel"
              style={{
                padding: '20px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                transition: 'all var(--transition-fast)'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--teal-500)';
                e.currentTarget.style.boxShadow = 'var(--shadow-md)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--border-light)';
                e.currentTarget.style.boxShadow = 'var(--shadow-xs)';
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div
                      style={{
                        width: '36px',
                        height: '36px',
                        borderRadius: '8px',
                        backgroundColor: 'var(--bg-canvas)',
                        border: '1px solid var(--border-light)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '18px'
                      }}
                    >
                      {acc.institutionLogo}
                    </div>

                    <div>
                      <div style={{ fontWeight: '700', fontSize: '14px', color: 'var(--navy-900)' }}>
                        {acc.name}
                      </div>
                      <div className="mono-num" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {acc.accountNumber} • {acc.type}
                      </div>
                    </div>
                  </div>

                  <span
                    className={`badge badge-${
                      acc.statusType === 'emerald' ? 'emerald' :
                      acc.statusType === 'teal' ? 'teal' :
                      acc.statusType === 'amber' ? 'amber' : 'red'
                    }`}
                  >
                    {acc.status}
                  </span>
                </div>

                {/* Balance Area */}
                <div style={{ margin: '14px 0' }}>
                  <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: '700', letterSpacing: '0.04em', marginBottom: '2px' }}>
                    Current Ledger Balance
                  </div>
                  <div className="mono-num" style={{ fontSize: '24px', fontWeight: '800', color: 'var(--navy-900)' }}>
                    {acc.balance}
                  </div>
                </div>
              </div>

              {/* Footer Specs */}
              <div
                style={{
                  paddingTop: '14px',
                  borderTop: '1px solid var(--border-subtle)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '12px',
                  color: 'var(--text-secondary)'
                }}
              >
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Movement: </span>
                  <strong>{acc.recentMovement}</strong>
                </div>

                <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                  Synced {acc.lastSynced}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
