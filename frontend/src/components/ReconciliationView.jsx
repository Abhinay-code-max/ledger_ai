import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Sparkles,
  Link2,
  PlusCircle,
  HelpCircle,
  Check,
  RefreshCw,
  Landmark,
  BookOpen
} from 'lucide-react';

export default function ReconciliationView({
  reconciliationData,
  currency,
  currentUser,
  requirePermission
}) {
  const [bankItems, setBankItems] = useState(reconciliationData.bankRecords);
  const [ledgerItems, setLedgerItems] = useState(reconciliationData.ledgerRecords);
  const [selectedBankId, setSelectedBankId] = useState(null);
  const [toastMsg, setToastMsg] = useState(null);

  const showToast = (msg) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  const handleMatch = (bankId, ledgerId) => {
    if (requirePermission) {
      const allowed = requirePermission(
        'canReconcile',
        'Match Bank Record with Ledger',
        'accountant',
        'Auditors possess read-only inspection access and cannot match or alter reconciliation records.'
      );
      if (!allowed) return;
    }

    setBankItems((prev) =>
      prev.map((b) => (b.id === bankId ? { ...b, reconciled: true, matchedLedgerId: ledgerId } : b))
    );
    setLedgerItems((prev) =>
      prev.map((l) => (l.id === ledgerId ? { ...l, reconciled: true, matchedBankId: bankId } : l))
    );
    showToast(`Matched bank record ${bankId} with ledger voucher ${ledgerId}`);
  };

  const handleAutoReconcileAll = () => {
    if (requirePermission) {
      const allowed = requirePermission(
        'canReconcile',
        'Auto-Reconcile High Confidence Pairs',
        'accountant',
        'Auditors possess read-only inspection access and cannot execute reconciliation write updates.'
      );
      if (!allowed) return;
    }

    setBankItems((prev) =>
      prev.map((b) => (b.matchedLedgerId ? { ...b, reconciled: true } : b))
    );
    setLedgerItems((prev) =>
      prev.map((l) => (l.matchedBankId ? { ...l, reconciled: true } : l))
    );
    showToast('Auto-reconciled all high-confidence matching pairs (95%+ confidence)');
  };

  const handleCreateVoucher = (bankItem) => {
    if (requirePermission) {
      const allowed = requirePermission(
        'canEdit',
        'Create Journal Voucher',
        'accountant',
        'Auditors possess read-only inspection access and cannot create journal vouchers.'
      );
      if (!allowed) return;
    }

    showToast(`Drafted Journal Entry voucher for "${bankItem.description}" (-₹32,450)`);
  };

  const reconciledBankCount = bankItems.filter((b) => b.reconciled).length;
  const totalBankCount = bankItems.length;

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
            Split-Screen Bank Reconciliation
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            Authoritative statement feed alignment against internal double-entry ledger vouchers.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              padding: '6px 14px',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-light)',
              borderRadius: 'var(--radius-md)',
              fontSize: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <span style={{ color: 'var(--text-muted)' }}>Status:</span>
            <strong style={{ color: reconciledBankCount === totalBankCount ? 'var(--alert-emerald-text)' : 'var(--alert-amber-text)' }}>
              {reconciledBankCount} of {totalBankCount} Reconciled ({Math.round((reconciledBankCount / totalBankCount) * 100)}%)
            </strong>
          </div>

          <button
            onClick={handleAutoReconcileAll}
            className="btn-teal btn-sm"
            style={{ padding: '7px 14px' }}
          >
            <Sparkles size={14} />
            <span>Auto-Match Verified Pairs</span>
          </button>
        </div>
      </div>

      {/* Split Screen Container */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '20px',
          alignItems: 'start'
        }}
      >
        {/* LEFT COLUMN: Bank Statement Feed */}
        <div className="panel">
          <div className="panel-header" style={{ backgroundColor: 'var(--bg-canvas)' }}>
            <div className="panel-title">
              <Landmark size={16} color="var(--navy-900)" />
              <span>HDFC Bank Statement Feed (Authoritative)</span>
            </div>
            <span className="badge badge-navy">Bank Source</span>
          </div>

          <div style={{ padding: '12px' }}>
            {bankItems.map((b) => {
              const isSelected = selectedBankId === b.id;

              return (
                <div
                  key={b.id}
                  onClick={() => setSelectedBankId(isSelected ? null : b.id)}
                  style={{
                    padding: '14px',
                    borderRadius: 'var(--radius-md)',
                    border: b.reconciled
                      ? '1px solid var(--alert-emerald-border)'
                      : b.matchedLedgerId
                      ? '1px solid rgba(14, 170, 165, 0.35)'
                      : '1px solid var(--alert-amber-border)',
                    backgroundColor: b.reconciled
                      ? 'var(--alert-emerald-bg)'
                      : isSelected
                      ? '#FAFBFD'
                      : '#FFFFFF',
                    marginBottom: '10px',
                    transition: 'all var(--transition-fast)',
                    cursor: 'pointer',
                    boxShadow: 'var(--shadow-xs)'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span className="mono-num" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {b.date}
                      </span>
                      <span className="mono-num" style={{ fontSize: '11px', color: 'var(--navy-700)', fontWeight: '600' }}>
                        {b.reference}
                      </span>
                    </div>

                    <div
                      className="mono-num"
                      style={{
                        fontWeight: '800',
                        fontSize: '14px',
                        color: b.type === 'credit' ? '#047857' : 'var(--navy-900)'
                      }}
                    >
                      {b.amount}
                    </div>
                  </div>

                  <div style={{ fontSize: '13px', fontWeight: '600', color: 'var(--navy-900)', marginBottom: '8px' }}>
                    {b.description}
                  </div>

                  {/* AI Recommendation / Confidence Badge */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '8px', borderTop: '1px dashed var(--border-subtle)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {b.reconciled ? (
                        <span style={{ fontSize: '11px', color: '#047857', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <CheckCircle2 size={13} /> Reconciled
                        </span>
                      ) : b.matchedLedgerId ? (
                        <span
                          style={{
                            fontSize: '11px',
                            color: 'var(--teal-700)',
                            backgroundColor: 'var(--teal-50)',
                            padding: '2px 7px',
                            borderRadius: '4px',
                            fontWeight: '700',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px'
                          }}
                        >
                          <Sparkles size={11} /> {b.confidence}
                        </span>
                      ) : (
                        <span
                          style={{
                            fontSize: '11px',
                            color: 'var(--alert-amber-text)',
                            backgroundColor: 'var(--alert-amber-bg)',
                            padding: '2px 7px',
                            borderRadius: '4px',
                            fontWeight: '700',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px'
                          }}
                        >
                          <AlertTriangle size={11} /> {b.confidence}
                        </span>
                      )}
                    </div>

                    <div>
                      {!b.reconciled && b.matchedLedgerId && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleMatch(b.id, b.matchedLedgerId);
                          }}
                          className="btn-teal btn-sm"
                          style={{ fontSize: '11px', padding: '3px 10px' }}
                        >
                          <Link2 size={12} />
                          <span>Confirm Match</span>
                        </button>
                      )}

                      {!b.reconciled && !b.matchedLedgerId && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCreateVoucher(b);
                            }}
                            className="btn-secondary btn-sm"
                            style={{ fontSize: '11px', padding: '3px 8px' }}
                          >
                            <PlusCircle size={12} />
                            <span>Create Entry</span>
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              showToast(`Ledger Ai investigating bank memo ${b.reference}...`);
                            }}
                            className="btn-ghost btn-sm"
                            style={{ fontSize: '11px', padding: '3px 8px' }}
                          >
                            Investigate
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* RIGHT COLUMN: Ledger Records */}
        <div className="panel">
          <div className="panel-header" style={{ backgroundColor: 'var(--bg-canvas)' }}>
            <div className="panel-title">
              <BookOpen size={16} color="var(--teal-600)" />
              <span>Internal General Ledger Records (ERP)</span>
            </div>
            <span className="badge badge-teal">Books Record</span>
          </div>

          <div style={{ padding: '12px' }}>
            {ledgerItems.map((l) => {
              return (
                <div
                  key={l.id}
                  style={{
                    padding: '14px',
                    borderRadius: 'var(--radius-md)',
                    border: l.reconciled
                      ? '1px solid var(--alert-emerald-border)'
                      : l.matchedBankId
                      ? '1px solid rgba(14, 170, 165, 0.35)'
                      : '1px solid var(--border-light)',
                    backgroundColor: l.reconciled
                      ? 'var(--alert-emerald-bg)'
                      : '#FFFFFF',
                    marginBottom: '10px',
                    transition: 'all var(--transition-fast)',
                    boxShadow: 'var(--shadow-xs)'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span className="mono-num" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {l.date}
                      </span>
                      <span className="mono-num" style={{ fontSize: '11px', color: 'var(--navy-700)', fontWeight: '600' }}>
                        {l.voucherNumber}
                      </span>
                    </div>

                    <div
                      className="mono-num"
                      style={{
                        fontWeight: '800',
                        fontSize: '14px',
                        color: l.type === 'credit' ? '#047857' : 'var(--navy-900)'
                      }}
                    >
                      {l.amount}
                    </div>
                  </div>

                  <div style={{ fontSize: '13px', fontWeight: '600', color: 'var(--navy-900)', marginBottom: '2px' }}>
                    {l.description}
                  </div>

                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px' }}>
                    Chart Account: <strong>{l.account}</strong>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '8px', borderTop: '1px dashed var(--border-subtle)' }}>
                    <div style={{ fontSize: '11px', color: l.reconciled ? '#047857' : 'var(--text-secondary)' }}>
                      {l.reconciled ? (
                        <span style={{ fontWeight: '700', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <CheckCircle2 size={13} /> Reconciled
                        </span>
                      ) : l.matchedBankId ? (
                        <span>Linked to bank record <strong>{l.matchedBankId}</strong></span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>Unmatched manual entry</span>
                      )}
                    </div>

                    <div>
                      {!l.reconciled && l.matchedBankId && (
                        <button
                          onClick={() => handleMatch(l.matchedBankId, l.id)}
                          className="btn-teal btn-sm"
                          style={{ fontSize: '11px', padding: '3px 10px' }}
                        >
                          Match
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
