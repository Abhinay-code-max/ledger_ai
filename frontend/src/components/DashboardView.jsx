import React, { useState } from 'react';
import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  Sparkles,
  ArrowRight,
  ShieldAlert,
  Clock,
  Landmark,
  FileText,
  CreditCard,
  DollarSign,
  Maximize2,
  Filter,
  Check
} from 'lucide-react';

export default function DashboardView({
  currency,
  kpis,
  needsAttention,
  setNeedsAttention,
  setActiveTab,
  setIsAiOpen,
  connectedAccounts,
  currentUser,
  requirePermission
}) {
  const [selectedAttentionItem, setSelectedAttentionItem] = useState(null);
  const [resolvedIds, setResolvedIds] = useState(new Set());
  const [toastMessage, setToastMessage] = useState(null);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleResolveAction = (e, item) => {
    e.stopPropagation();

    // Enforce Institutional Role-Based Access Control
    if (requirePermission) {
      if (item.id === 'att-3') {
        const allowed = requirePermission(
          'canApprove',
          'Reconciliation Discrepancy Write-Off',
          'cfo',
          'Under institutional controls, only the Chief Financial Officer (Alex Vance) can approve and write off reconciliation variances.'
        );
        if (!allowed) return;
      } else {
        const allowed = requirePermission(
          'canEdit',
          item.title,
          'accountant',
          'Auditor accounts possess read-only inspection status and cannot execute ledger resolutions.'
        );
        if (!allowed) return;
      }
    }

    const updated = new Set(resolvedIds);
    if (updated.has(item.id)) {
      updated.delete(item.id);
      showToast(`Action reopened: ${item.title}`);
    } else {
      updated.add(item.id);
      showToast(`Resolved: ${item.title}`);
    }
    setResolvedIds(updated);

    // Update parent state
    setNeedsAttention(prev =>
      prev.map(i => i.id === item.id ? { ...i, resolved: !i.resolved } : i)
    );
  };

  const unresolvedCount = needsAttention.filter(i => !resolvedIds.has(i.id)).length;

  return (
    <div className="animate-fade-in" style={{ padding: '28px', maxWidth: '1440px', margin: '0 auto', width: '100%' }}>
      {/* Toast Notification */}
      {toastMessage && (
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
            animation: 'fadeIn 200ms ease-out'
          }}
        >
          <CheckCircle2 size={16} color="var(--teal-400)" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top Header Greeting & Context */}
      <div style={{ marginBottom: '24px', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: '800', color: 'var(--navy-900)', letterSpacing: '-0.02em', marginBottom: '4px' }}>
            Good morning, Alex.
          </h1>
          <p style={{ fontSize: '14px', color: 'var(--text-muted)' }}>
            Here’s what needs your attention today across Acme Technologies.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              padding: '6px 12px',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-light)',
              borderRadius: 'var(--radius-md)',
              fontSize: '12px',
              color: 'var(--text-secondary)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Clock size={13} color="var(--text-muted)" />
            <span>Last audit synced: <strong>2 minutes ago</strong></span>
          </div>

          <button
            onClick={() => setIsAiOpen(true)}
            className="btn-teal"
            style={{ fontSize: '13px', padding: '7px 14px' }}
          >
            <Sparkles size={14} />
            <span>Generate Executive Brief</span>
          </button>
        </div>
      </div>

      {/* Compact Financial Status KPI Bar (5 Core Accounting Pillars) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
          gap: '14px',
          marginBottom: '28px'
        }}
      >
        {/* Cash Balance */}
        <div className="panel" style={{ padding: '16px 18px', position: 'relative', overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
              Cash Balance
            </span>
            <span style={{ fontSize: '11px', color: 'var(--alert-emerald-text)', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '2px' }}>
              <TrendingUp size={12} /> {kpis.cashBalance.change}
            </span>
          </div>
          <div className="mono-num" style={{ fontSize: '22px', fontWeight: '800', color: 'var(--navy-900)', marginBottom: '4px' }}>
            {currency === 'INR' ? kpis.cashBalance.inr : kpis.cashBalance.usd}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            {kpis.cashBalance.subtitle}
          </div>
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '3px', backgroundColor: 'var(--teal-500)' }} />
        </div>

        {/* Accounts Receivable */}
        <div className="panel" style={{ padding: '16px 18px', position: 'relative', overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
              Accounts Receivable
            </span>
            <span style={{ fontSize: '11px', color: 'var(--alert-red-text)', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '2px' }}>
              <AlertCircle size={12} /> {kpis.accountsReceivable.change}
            </span>
          </div>
          <div className="mono-num" style={{ fontSize: '22px', fontWeight: '800', color: 'var(--navy-900)', marginBottom: '4px' }}>
            {currency === 'INR' ? kpis.accountsReceivable.inr : kpis.accountsReceivable.usd}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            {kpis.accountsReceivable.subtitle}
          </div>
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '3px', backgroundColor: '#F59E0B' }} />
        </div>

        {/* Accounts Payable */}
        <div className="panel" style={{ padding: '16px 18px', position: 'relative', overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
              Accounts Payable
            </span>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: '600' }}>
              {kpis.accountsPayable.change}
            </span>
          </div>
          <div className="mono-num" style={{ fontSize: '22px', fontWeight: '800', color: 'var(--navy-900)', marginBottom: '4px' }}>
            {currency === 'INR' ? kpis.accountsPayable.inr : kpis.accountsPayable.usd}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            {kpis.accountsPayable.subtitle}
          </div>
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '3px', backgroundColor: 'var(--border-medium)' }} />
        </div>

        {/* Monthly Revenue */}
        <div className="panel" style={{ padding: '16px 18px', position: 'relative', overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
              Monthly Revenue
            </span>
            <span style={{ fontSize: '11px', color: 'var(--alert-emerald-text)', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '2px' }}>
              <TrendingUp size={12} /> {kpis.monthlyRevenue.change}
            </span>
          </div>
          <div className="mono-num" style={{ fontSize: '22px', fontWeight: '800', color: 'var(--navy-900)', marginBottom: '4px' }}>
            {currency === 'INR' ? kpis.monthlyRevenue.inr : kpis.monthlyRevenue.usd}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            {kpis.monthlyRevenue.subtitle}
          </div>
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '3px', backgroundColor: '#10B981' }} />
        </div>

        {/* Monthly Expenses */}
        <div className="panel" style={{ padding: '16px 18px', position: 'relative', overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
              Monthly Expenses
            </span>
            <span style={{ fontSize: '11px', color: 'var(--alert-red-text)', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '2px' }}>
              <TrendingUp size={12} /> {kpis.monthlyExpenses.change}
            </span>
          </div>
          <div className="mono-num" style={{ fontSize: '22px', fontWeight: '800', color: 'var(--navy-900)', marginBottom: '4px' }}>
            {currency === 'INR' ? kpis.monthlyExpenses.inr : kpis.monthlyExpenses.usd}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            {kpis.monthlyExpenses.subtitle}
          </div>
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '3px', backgroundColor: '#EF4444' }} />
        </div>
      </div>

      {/* CORE COMMAND CENTER: NEEDS ATTENTION */}
      <section style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h2 style={{ fontSize: '17px', fontWeight: '800', color: 'var(--navy-900)', letterSpacing: '-0.01em' }}>
              Needs Attention
            </h2>
            <span
              style={{
                fontSize: '11px',
                fontWeight: '700',
                padding: '2px 8px',
                borderRadius: '12px',
                backgroundColor: unresolvedCount > 0 ? 'var(--alert-amber-bg)' : 'var(--alert-emerald-bg)',
                color: unresolvedCount > 0 ? 'var(--alert-amber-text)' : 'var(--alert-emerald-text)',
                border: unresolvedCount > 0 ? '1px solid var(--alert-amber-border)' : '1px solid var(--alert-emerald-border)',
                fontFamily: 'var(--font-mono)'
              }}
            >
              {unresolvedCount} Active Action Items
            </span>
          </div>

          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Prioritized by financial impact and ledger accuracy
          </div>
        </div>

        {/* Command Center Layout: Rich List with Urgency, Impact & 1-Click Action */}
        <div
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-light)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
            boxShadow: 'var(--shadow-sm)'
          }}
        >
          {needsAttention.map((item, index) => {
            const isResolved = resolvedIds.has(item.id);
            const isExpanded = selectedAttentionItem === item.id;

            return (
              <div
                key={item.id}
                style={{
                  borderBottom: index < needsAttention.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                  backgroundColor: isResolved ? 'rgba(240, 244, 248, 0.4)' : isExpanded ? '#FAFBFD' : '#FFFFFF',
                  transition: 'background var(--transition-fast)'
                }}
              >
                {/* Main Item Row */}
                <div
                  onClick={() => setSelectedAttentionItem(isExpanded ? null : item.id)}
                  style={{
                    padding: '16px 20px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '16px',
                    cursor: 'pointer',
                    opacity: isResolved ? 0.65 : 1
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flex: 1 }}>
                    {/* Urgency Badge */}
                    <span
                      style={{
                        padding: '3px 8px',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '11px',
                        fontWeight: '700',
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em',
                        backgroundColor:
                          item.urgency === 'Critical' ? 'var(--alert-red-bg)' :
                          item.urgency === 'High' ? 'var(--alert-amber-bg)' : 'var(--teal-50)',
                        color:
                          item.urgency === 'Critical' ? 'var(--alert-red-text)' :
                          item.urgency === 'High' ? 'var(--alert-amber-text)' : 'var(--teal-700)',
                        border:
                          item.urgency === 'Critical' ? '1px solid var(--alert-red-border)' :
                          item.urgency === 'High' ? '1px solid var(--alert-amber-border)' : '1px solid rgba(14, 170, 165, 0.3)',
                        flexShrink: 0
                      }}
                    >
                      {item.urgency}
                    </span>

                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '2px' }}>
                        <span style={{ fontSize: '14px', fontWeight: '700', color: 'var(--navy-900)' }}>
                          {item.title}
                        </span>
                        <span className="mono-num" style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-secondary)' }}>
                          {item.amount}
                        </span>
                      </div>
                      <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                        {item.issue}
                      </p>
                    </div>
                  </div>

                  {/* Actions & Resolution Button */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
                    <button
                      onClick={(e) => handleResolveAction(e, item)}
                      className={isResolved ? "btn-secondary btn-sm" : "btn-teal btn-sm"}
                      style={{
                        padding: '6px 14px',
                        fontWeight: '600',
                        backgroundColor: isResolved ? 'var(--bg-subtle)' : undefined,
                        color: isResolved ? 'var(--text-muted)' : undefined
                      }}
                    >
                      {isResolved ? (
                        <>
                          <Check size={14} color="#10B981" />
                          <span>Resolved</span>
                        </>
                      ) : (
                        <>
                          <Sparkles size={13} />
                          <span>{item.actionLabel}</span>
                        </>
                      )}
                    </button>

                    <span
                      style={{
                        color: 'var(--text-muted)',
                        transform: isExpanded ? 'rotate(90deg)' : 'none',
                        transition: 'transform var(--transition-fast)'
                      }}
                    >
                      <ChevronRight size={16} />
                    </span>
                  </div>
                </div>

                {/* Expanded Intelligent Drawer */}
                {isExpanded && (
                  <div
                    style={{
                      padding: '0 20px 20px 52px',
                      backgroundColor: '#FAFBFD',
                      borderTop: '1px dashed var(--border-light)'
                    }}
                  >
                    <div
                      style={{
                        padding: '16px',
                        backgroundColor: 'var(--bg-surface)',
                        border: '1px solid var(--border-light)',
                        borderRadius: 'var(--radius-md)',
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                        gap: '16px',
                        marginTop: '12px'
                      }}
                    >
                      <div>
                        <div style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '4px' }}>
                          Financial Impact & Risk
                        </div>
                        <p style={{ fontSize: '13px', color: 'var(--text-primary)', lineHeight: 1.5 }}>
                          {item.impact}
                        </p>
                      </div>

                      <div>
                        <div style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: 'var(--teal-700)', marginBottom: '4px' }}>
                          Ledger Ai Recommended Next Step
                        </div>
                        <p style={{ fontSize: '13px', color: 'var(--text-primary)', lineHeight: 1.5 }}>
                          {item.recommendedAction}
                        </p>
                      </div>

                      <div style={{ gridColumn: '1 / -1', borderTop: '1px solid var(--border-subtle)', paddingTop: '10px' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span><strong>Evidence Provenance:</strong> {item.evidence}</span>
                          <button
                            onClick={() => {
                              if (item.type === 'categorization') setActiveTab('transactions');
                              else if (item.type === 'invoice') setActiveTab('invoices');
                              else if (item.type === 'reconciliation') setActiveTab('reconciliation');
                              else setActiveTab('intelligence');
                            }}
                            style={{ color: 'var(--teal-600)', fontWeight: '600', fontSize: '12px', padding: 0 }}
                          >
                            Open in {item.type.toUpperCase()} Workspace →
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* Two-Column Supporting Operations Area */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '24px' }}>
        {/* Connected Accounts Snapshot */}
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">
              <Landmark size={16} color="var(--navy-900)" />
              <span>Connected Financial Feeds</span>
            </div>
            <button
              onClick={() => setActiveTab('accounts')}
              className="btn-ghost btn-sm"
              style={{ fontSize: '12px' }}
            >
              View All (5) →
            </button>
          </div>
          <div style={{ padding: '8px 0' }}>
            {connectedAccounts.slice(0, 4).map((acc) => (
              <div
                key={acc.id}
                style={{
                  padding: '12px 18px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  borderBottom: '1px solid var(--border-subtle)'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{ fontSize: '18px' }}>{acc.institutionLogo}</span>
                  <div>
                    <div style={{ fontWeight: '600', fontSize: '13px', color: 'var(--navy-900)' }}>
                      {acc.name}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      {acc.accountNumber} • Synced {acc.lastSynced}
                    </div>
                  </div>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <div className="mono-num" style={{ fontWeight: '700', fontSize: '14px', color: 'var(--navy-900)' }}>
                    {acc.balance}
                  </div>
                  <span
                    style={{
                      fontSize: '10px',
                      fontWeight: '700',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      backgroundColor: acc.statusType === 'emerald' ? 'var(--alert-emerald-bg)' : acc.statusType === 'amber' ? 'var(--alert-amber-bg)' : 'var(--alert-red-bg)',
                      color: acc.statusType === 'emerald' ? 'var(--alert-emerald-text)' : acc.statusType === 'amber' ? 'var(--alert-amber-text)' : 'var(--alert-red-text)'
                    }}
                  >
                    {acc.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Ledger Intelligence Fast Pulse */}
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">
              <Sparkles size={16} color="var(--teal-500)" />
              <span>Ledger Intelligence Snapshot</span>
            </div>
            <button
              onClick={() => setActiveTab('intelligence')}
              className="btn-ghost btn-sm"
              style={{ fontSize: '12px' }}
            >
              Full Analysis →
            </button>
          </div>
          <div style={{ padding: '16px' }}>
            <div
              style={{
                backgroundColor: 'var(--teal-50)',
                border: '1px solid rgba(14, 170, 165, 0.25)',
                borderRadius: 'var(--radius-md)',
                padding: '14px',
                marginBottom: '12px'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                <span className="badge badge-teal">Working Capital Finding</span>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Analyzed across 1,840 txns</span>
              </div>
              <div style={{ fontWeight: '700', fontSize: '13px', color: 'var(--navy-900)', marginBottom: '4px' }}>
                Client payments arriving 4.8 days later than last quarter.
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '10px' }}>
                DSO expanded from 30.0 to 34.8 days. ₹18,40,000 delayed in receivables.
              </p>
              <button
                onClick={() => setActiveTab('invoices')}
                className="btn-secondary btn-sm"
                style={{ fontSize: '11px' }}
              >
                Review Aging Report & Dunning Cadence
              </button>
            </div>

            <div
              style={{
                backgroundColor: 'var(--bg-canvas)',
                border: '1px solid var(--border-light)',
                borderRadius: 'var(--radius-md)',
                padding: '14px'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                <span className="badge badge-amber">Runway Projection</span>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Based on October burn rate</span>
              </div>
              <div style={{ fontWeight: '700', fontSize: '13px', color: 'var(--navy-900)', marginBottom: '4px' }}>
                Operating runway extends to 8.4 months at current net burn.
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                Cash reserves of ₹1,42,85,600 offset by net burn of ₹17,08,000/month.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
