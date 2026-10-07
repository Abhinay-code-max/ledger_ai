import React, { useState } from 'react';
import {
  FileText,
  Clock,
  AlertCircle,
  CheckCircle2,
  Send,
  Plus,
  Download,
  Filter,
  DollarSign
} from 'lucide-react';

export default function InvoicesView({ invoices, currency, currentUser, requirePermission }) {
  const [invoiceList, setInvoiceList] = useState(invoices);
  const [toastMsg, setToastMsg] = useState(null);

  const showToast = (msg) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  const handleSendReminder = (inv) => {
    if (requirePermission) {
      const allowed = requirePermission(
        'canDispatchInvoices',
        `Send Payment Reminder for ${inv.id}`,
        'accountant',
        'Auditor accounts possess read-only inspection access and cannot dispatch external client communications.'
      );
      if (!allowed) return;
    }

    showToast(`Dispatched payment reminder email & SMS link to ${inv.client}`);
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

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontSize: '22px', fontWeight: '800', color: 'var(--navy-900)', letterSpacing: '-0.02em', marginBottom: '3px' }}>
            Invoices & Accounts Receivable
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            Track client billing, overdue aging terms, and automated dunning cadence.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={() => showToast('Batch dispatched 3 payment reminders for overdue invoices')}
            className="btn-teal btn-sm"
            style={{ padding: '7px 14px' }}
          >
            <Send size={13} />
            <span>Remind All Overdue (3)</span>
          </button>

          <button
            onClick={() => showToast('Drafting new invoice in modal...')}
            className="btn-primary btn-sm"
            style={{ padding: '7px 14px' }}
          >
            <Plus size={14} />
            <span>Create Invoice</span>
          </button>
        </div>
      </div>

      {/* Aging Metric Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px', marginBottom: '24px' }}>
        <div className="panel" style={{ padding: '16px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '4px' }}>
            Total Outstanding AR
          </div>
          <div className="mono-num" style={{ fontSize: '20px', fontWeight: '800', color: 'var(--navy-900)' }}>
            ₹28,40,000
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>6 open accounts</div>
        </div>

        <div className="panel" style={{ padding: '16px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: 'var(--alert-red-text)', marginBottom: '4px' }}>
            Critically Overdue (&gt;Net 30)
          </div>
          <div className="mono-num" style={{ fontSize: '20px', fontWeight: '800', color: 'var(--alert-red-text)' }}>
            ₹4,85,000
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>3 client invoices</div>
        </div>

        <div className="panel" style={{ padding: '16px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '4px' }}>
            Current (Within Terms)
          </div>
          <div className="mono-num" style={{ fontSize: '20px', fontWeight: '800', color: 'var(--navy-900)' }}>
            ₹11,00,000
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Due in 15–30 days</div>
        </div>

        <div className="panel" style={{ padding: '16px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: 'var(--alert-emerald-text)', marginBottom: '4px' }}>
            Collected This Month
          </div>
          <div className="mono-num" style={{ fontSize: '20px', fontWeight: '800', color: 'var(--alert-emerald-text)' }}>
            ₹20,90,000
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>99% payment accuracy</div>
        </div>
      </div>

      {/* Invoices Table */}
      <div className="panel" style={{ overflow: 'hidden' }}>
        <table className="ledger-table">
          <thead>
            <tr>
              <th>Invoice #</th>
              <th>Client</th>
              <th>Issue Date</th>
              <th>Due Date</th>
              <th>Deliverable Scope</th>
              <th style={{ textAlign: 'right' }}>Amount</th>
              <th>Status</th>
              <th style={{ textAlign: 'right' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {invoiceList.map((inv) => (
              <tr key={inv.id}>
                <td className="mono-num" style={{ fontWeight: '700', fontSize: '12px', color: 'var(--navy-700)' }}>
                  {inv.id}
                </td>
                <td style={{ fontWeight: '600', color: 'var(--navy-900)' }}>
                  {inv.client}
                </td>
                <td className="mono-num" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  {inv.issueDate}
                </td>
                <td className="mono-num" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  {inv.dueDate}
                </td>
                <td style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  {inv.items}
                </td>
                <td className="mono-num" style={{ textAlign: 'right', fontWeight: '700', fontSize: '13px', color: 'var(--navy-900)' }}>
                  {inv.amount}
                </td>
                <td>
                  <span className={`badge badge-${inv.statusBadge}`}>
                    {inv.status}
                  </span>
                </td>
                <td style={{ textAlign: 'right' }}>
                  {inv.statusBadge === 'red' ? (
                    <button
                      onClick={() => handleSendReminder(inv)}
                      className="btn-secondary btn-sm"
                      style={{ fontSize: '11px', padding: '3px 8px' }}
                    >
                      <Send size={11} />
                      <span>Remind</span>
                    </button>
                  ) : (
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
