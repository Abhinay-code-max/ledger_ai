import React, { useState } from 'react';
import {
  Search,
  Filter,
  Download,
  Sparkles,
  Check,
  Edit2,
  CheckCircle2,
  AlertCircle,
  FileCheck,
  ChevronDown,
  X
} from 'lucide-react';

export default function TransactionsView({
  transactions,
  setTransactions,
  currency,
  currentUser,
  requirePermission
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedAccount, setSelectedAccount] = useState('ALL');
  const [selectedCategory, setSelectedCategory] = useState('ALL');
  const [selectedStatus, setSelectedStatus] = useState('ALL');
  const [selectedTxnIds, setSelectedTxnIds] = useState(new Set());
  const [activeProvenanceTxn, setActiveProvenanceTxn] = useState(null);
  const [toastMsg, setToastMsg] = useState(null);

  const showToast = (msg) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  // Filter transactions
  const filtered = transactions.filter((t) => {
    const matchesSearch =
      t.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.category.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesAccount =
      selectedAccount === 'ALL' || t.account.includes(selectedAccount);

    const matchesCategory =
      selectedCategory === 'ALL' || t.category === selectedCategory;

    const matchesStatus =
      selectedStatus === 'ALL' ||
      (selectedStatus === 'NEEDS_CATEGORY' && t.aiSuggested) ||
      t.status.toLowerCase().includes(selectedStatus.toLowerCase());

    return matchesSearch && matchesAccount && matchesCategory && matchesStatus;
  });

  const handleSelectAll = (e) => {
    if (e.target.checked) {
      setSelectedTxnIds(new Set(filtered.map((t) => t.id)));
    } else {
      setSelectedTxnIds(new Set());
    }
  };

  const handleToggleSelect = (id) => {
    const next = new Set(selectedTxnIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedTxnIds(next);
  };

  const handleAcceptSuggestion = (txn) => {
    if (requirePermission) {
      const allowed = requirePermission(
        'canEdit',
        `Classify Transaction ${txn.id}`,
        'accountant',
        'Auditor accounts possess read-only inspection access and cannot modify transaction classifications.'
      );
      if (!allowed) return;
    }

    setTransactions((prev) =>
      prev.map((t) =>
        t.id === txn.id
          ? {
              ...t,
              category: t.aiSuggested,
              status: 'Verified',
              statusBadge: 'emerald',
              aiSuggested: null,
            }
          : t
      )
    );
    showToast(`Categorized ${txn.id} as ${txn.aiSuggested}`);
  };

  const handleBatchAccept = () => {
    if (requirePermission) {
      const allowed = requirePermission(
        'canEdit',
        'Batch Transaction Categorization',
        'accountant',
        'Auditor accounts possess read-only inspection access and cannot modify transaction classifications.'
      );
      if (!allowed) return;
    }

    const targetIds = selectedTxnIds.size > 0 ? selectedTxnIds : new Set(filtered.filter(t => t.aiSuggested).map(t => t.id));
    setTransactions((prev) =>
      prev.map((t) =>
        targetIds.has(t.id) && t.aiSuggested
          ? {
              ...t,
              category: t.aiSuggested,
              status: 'Verified',
              statusBadge: 'emerald',
              aiSuggested: null,
            }
          : t
      )
    );
    showToast(`Batch classified selected transactions`);
    setSelectedTxnIds(new Set());
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
            Financial Transactions
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            High-integrity double-entry journal records, automated categorization, and provenance links.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={handleBatchAccept}
            className="btn-teal btn-sm"
            style={{ padding: '7px 14px' }}
          >
            <Sparkles size={14} />
            <span>Auto-Accept AI Categories</span>
          </button>

          <button
            onClick={() => showToast('Exporting certified journal entries to CSV...')}
            className="btn-secondary btn-sm"
            style={{ padding: '7px 14px' }}
          >
            <Download size={14} />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div
        className="panel"
        style={{
          padding: '14px 18px',
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, minWidth: '280px' }}>
          <div style={{ position: 'relative', width: '100%', maxWidth: '340px' }}>
            <Search
              size={15}
              color="var(--text-muted)"
              style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }}
            />
            <input
              type="text"
              placeholder="Search vendor, description, or txn ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ width: '100%', paddingLeft: '32px' }}
            />
          </div>

          {/* Account Filter */}
          <select
            value={selectedAccount}
            onChange={(e) => setSelectedAccount(e.target.value)}
            style={{ padding: '7px 12px', fontSize: '12px' }}
          >
            <option value="ALL">All Accounts</option>
            <option value="HDFC">HDFC Bank Current</option>
            <option value="Silicon Valley">SVB USD Operating</option>
            <option value="Brex">Brex Corporate Card</option>
            <option value="Stripe">Stripe Clearing</option>
          </select>

          {/* Category Filter */}
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            style={{ padding: '7px 12px', fontSize: '12px' }}
          >
            <option value="ALL">All Categories</option>
            <option value="Software & Cloud">Software & Cloud</option>
            <option value="Revenue / Sales">Revenue / Sales</option>
            <option value="Salaries & Payroll">Salaries & Payroll</option>
            <option value="Office & Facilities">Office & Facilities</option>
            <option value="Bank Fees & Processing">Bank Fees & Processing</option>
            <option value="Uncategorized">Uncategorized</option>
          </select>

          {/* Status Filter */}
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            style={{ padding: '7px 12px', fontSize: '12px' }}
          >
            <option value="ALL">All Statuses</option>
            <option value="NEEDS_CATEGORY">Needs AI Categorization</option>
            <option value="Verified">Verified</option>
            <option value="Reconciled">Reconciled</option>
            <option value="Duplicate">Flagged Duplicate</option>
          </select>
        </div>

        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Showing <strong>{filtered.length}</strong> of {transactions.length} records
        </div>
      </div>

      {/* Bulk Selection Bar */}
      {selectedTxnIds.size > 0 && (
        <div
          style={{
            padding: '10px 16px',
            backgroundColor: 'var(--navy-900)',
            color: '#FFFFFF',
            borderRadius: 'var(--radius-md)',
            marginBottom: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px' }}>
            <span style={{ fontWeight: '700', color: 'var(--teal-400)' }}>
              {selectedTxnIds.size} transactions selected
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={handleBatchAccept}
              className="btn-teal btn-sm"
              style={{ fontSize: '11px', padding: '4px 10px' }}
            >
              Batch Accept AI Suggestion
            </button>
            <button
              onClick={() => {
                setTransactions(prev => prev.map(t => selectedTxnIds.has(t.id) ? { ...t, status: 'Verified', statusBadge: 'emerald' } : t));
                setSelectedTxnIds(new Set());
                showToast('Marked selected records as Verified');
              }}
              className="btn-secondary btn-sm"
              style={{ fontSize: '11px', padding: '4px 10px', backgroundColor: 'transparent', color: '#FFFFFF', borderColor: 'rgba(255,255,255,0.3)' }}
            >
              Mark Verified
            </button>
            <button
              onClick={() => setSelectedTxnIds(new Set())}
              style={{ color: 'var(--text-light-muted)', fontSize: '12px', padding: '4px 8px' }}
            >
              Deselect
            </button>
          </div>
        </div>
      )}

      {/* Primary Financial Ledger Table */}
      <div className="panel" style={{ overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table className="ledger-table">
            <thead>
              <tr>
                <th style={{ width: '40px', textAlign: 'center' }}>
                  <input
                    type="checkbox"
                    checked={filtered.length > 0 && selectedTxnIds.size === filtered.length}
                    onChange={handleSelectAll}
                  />
                </th>
                <th>Date</th>
                <th>Description</th>
                <th>Account</th>
                <th>Category</th>
                <th style={{ textAlign: 'right' }}>Amount</th>
                <th>Status</th>
                <th style={{ width: '40px' }}></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((txn) => {
                const isSelected = selectedTxnIds.has(txn.id);

                return (
                  <tr
                    key={txn.id}
                    className={isSelected ? 'row-selected' : undefined}
                    style={{ cursor: 'pointer' }}
                    onClick={() => setActiveProvenanceTxn(activeProvenanceTxn?.id === txn.id ? null : txn)}
                  >
                    <td style={{ textAlign: 'center' }} onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => handleToggleSelect(txn.id)}
                      />
                    </td>
                    <td className="mono-num" style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                      {txn.date}
                    </td>
                    <td>
                      <div style={{ fontWeight: '600', color: 'var(--navy-900)' }}>
                        {txn.description}
                      </div>
                      <div className="mono-num" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {txn.id}
                      </div>
                    </td>
                    <td>
                      <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        {txn.account}
                      </span>
                    </td>
                    <td>
                      {txn.aiSuggested ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }} onClick={(e) => e.stopPropagation()}>
                          <div
                            style={{
                              padding: '3px 8px',
                              backgroundColor: 'var(--teal-50)',
                              border: '1px solid rgba(14, 170, 165, 0.3)',
                              borderRadius: 'var(--radius-sm)',
                              fontSize: '11px',
                              color: 'var(--teal-700)',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px'
                            }}
                          >
                            <Sparkles size={11} color="var(--teal-600)" />
                            <span>Ledger Ai: <strong>{txn.aiSuggested}</strong></span>
                            <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>({txn.confidence})</span>
                          </div>

                          <button
                            onClick={() => handleAcceptSuggestion(txn)}
                            className="btn-teal btn-sm"
                            style={{ padding: '2px 8px', fontSize: '11px', height: '24px' }}
                            title="Accept AI classification"
                          >
                            Accept
                          </button>
                        </div>
                      ) : (
                        <span
                          style={{
                            fontSize: '12px',
                            color: txn.category === 'Uncategorized' ? 'var(--alert-amber-text)' : 'var(--text-secondary)',
                            fontWeight: txn.category === 'Uncategorized' ? '700' : '500'
                          }}
                        >
                          {txn.category}
                        </span>
                      )}
                    </td>
                    <td
                      className="mono-num"
                      style={{
                        textAlign: 'right',
                        fontWeight: '700',
                        fontSize: '13px',
                        color: txn.type === 'credit' ? '#047857' : 'var(--navy-900)'
                      }}
                    >
                      {txn.amount}
                    </td>
                    <td>
                      <span
                        className={`badge badge-${
                          txn.statusBadge === 'emerald' ? 'emerald' :
                          txn.statusBadge === 'teal' ? 'teal' :
                          txn.statusBadge === 'amber' ? 'amber' : 'red'
                        }`}
                      >
                        {txn.status}
                      </span>
                    </td>
                    <td style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                      <FileCheck size={14} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Line-level Audit & Provenance Drawer */}
      {activeProvenanceTxn && (
        <div
          style={{
            position: 'fixed',
            bottom: '24px',
            left: '50%',
            transform: 'translateX(-50%)',
            width: '90%',
            maxWidth: '840px',
            backgroundColor: 'var(--navy-900)',
            color: '#FFFFFF',
            borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-panel)',
            padding: '18px 24px',
            zIndex: 90,
            border: '1px solid var(--border-dark)',
            animation: 'fadeIn 200ms ease-out'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span className="badge badge-teal">Immutable Evidence Provenance</span>
              <span className="mono-num" style={{ fontSize: '13px', fontWeight: '700' }}>{activeProvenanceTxn.id}</span>
            </div>
            <button
              onClick={() => setActiveProvenanceTxn(null)}
              style={{ color: 'var(--text-light-muted)', cursor: 'pointer' }}
            >
              <X size={16} />
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px', fontSize: '12px' }}>
            <div>
              <div style={{ color: 'var(--text-light-muted)', marginBottom: '2px' }}>Description / Vendor</div>
              <div style={{ fontWeight: '600' }}>{activeProvenanceTxn.description}</div>
            </div>
            <div>
              <div style={{ color: 'var(--text-light-muted)', marginBottom: '2px' }}>Ledger Account</div>
              <div style={{ fontWeight: '600' }}>{activeProvenanceTxn.account}</div>
            </div>
            <div>
              <div style={{ color: 'var(--text-light-muted)', marginBottom: '2px' }}>Evidence Reference</div>
              <div style={{ color: 'var(--teal-300)', fontFamily: 'var(--font-mono)' }}>{activeProvenanceTxn.provenance}</div>
            </div>
            <div>
              <div style={{ color: 'var(--text-light-muted)', marginBottom: '2px' }}>Double-Entry Journal Status</div>
              <div style={{ color: '#10B981', fontWeight: '600' }}>Balanced • Append-Only Snapshot</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
