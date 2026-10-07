import React, { useState } from 'react';
import {
  Sparkles,
  X,
  Search,
  ArrowRight,
  ShieldCheck,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  CornerDownLeft,
  FileText,
  ExternalLink
} from 'lucide-react';
import { sampleAiQueries } from '../data/mockData';

export default function AiAgentPanel({
  isOpen,
  onClose,
  setActiveTab
}) {
  const [selectedPrompt, setSelectedPrompt] = useState(sampleAiQueries[0]);
  const [inputVal, setInputVal] = useState('');
  const [showEvidence, setShowEvidence] = useState(false);
  const [actionConfirmed, setActionConfirmed] = useState(false);

  if (!isOpen) return null;

  const handleSelectQuery = (q) => {
    setSelectedPrompt(q);
    setInputVal('');
    setShowEvidence(false);
    setActionConfirmed(false);
  };

  const handleCustomSubmit = (e) => {
    e.preventDefault();
    if (!inputVal.trim()) return;

    // Match or create responsive response
    const match = sampleAiQueries.find(q =>
      q.query.toLowerCase().includes(inputVal.toLowerCase()) ||
      inputVal.toLowerCase().includes(q.query.toLowerCase())
    );

    if (match) {
      setSelectedPrompt(match);
    } else {
      setSelectedPrompt({
        query: inputVal,
        answer: `Ledger Ai analyzed active October 2026 journal vouchers for "${inputVal}": Identified 8 relevant entries with a net operating impact of ₹1,48,200.`,
        breakdown: [
          { category: "Primary Ledger Voucher", amount: "₹84,000", detail: "Verified institutional feed match" },
          { category: "Secondary Accruals", amount: "₹64,200", detail: "Unadjusted month-end accrual" },
        ],
        actionSuggestion: "Review line-level journal evidence and append audit verification note.",
        evidenceCount: 8,
      });
    }
    setInputVal('');
    setShowEvidence(false);
    setActionConfirmed(false);
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        bottom: 0,
        width: '100%',
        maxWidth: '560px',
        backgroundColor: 'var(--navy-900)',
        color: '#FFFFFF',
        zIndex: 100,
        boxShadow: 'var(--shadow-panel)',
        display: 'flex',
        flexDirection: 'column',
        borderLeft: '1px solid var(--border-dark)',
        animation: 'fadeIn 180ms ease-out',
      }}
    >
      {/* Panel Header */}
      <div
        style={{
          padding: '20px 24px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '28px',
              height: '28px',
              borderRadius: '6px',
              backgroundColor: 'rgba(35, 199, 184, 0.2)',
              border: '1px solid rgba(35, 199, 184, 0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Sparkles size={16} color="var(--teal-400)" />
          </div>
          <div>
            <div style={{ fontWeight: '800', fontSize: '15px', color: '#FFFFFF', letterSpacing: '-0.01em' }}>
              Ledger Ai Workspace
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-light-muted)' }}>
              Analytical & Operational Accounting Agent
            </div>
          </div>
        </div>

        <button
          onClick={onClose}
          style={{
            padding: '6px',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--text-light-muted)',
            cursor: 'pointer',
          }}
          title="Close panel"
        >
          <X size={18} />
        </button>
      </div>

      {/* Context-Aware Badge Bar */}
      <div
        style={{
          padding: '10px 24px',
          backgroundColor: 'rgba(255, 255, 255, 0.04)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '11px',
          color: 'var(--text-light-muted)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--teal-400)' }} />
          <span>Context: <strong>Acme Technologies • Q3 Books Open</strong></span>
        </div>
        <span style={{ color: 'var(--teal-300)', fontWeight: '600' }}>
          Read-Only Inspection Mode
        </span>
      </div>

      {/* Main Content Area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
        {/* Suggested Queries Chips */}
        <div style={{ marginBottom: '22px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-light-muted)', marginBottom: '8px' }}>
            Recommended Accounting Inquiries
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {sampleAiQueries.map((q, idx) => (
              <button
                key={idx}
                onClick={() => handleSelectQuery(q)}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  padding: '9px 12px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: selectedPrompt.query === q.query ? 'rgba(35, 199, 184, 0.15)' : 'rgba(255, 255, 255, 0.04)',
                  border: selectedPrompt.query === q.query ? '1px solid var(--teal-500)' : '1px solid rgba(255, 255, 255, 0.08)',
                  color: selectedPrompt.query === q.query ? '#FFFFFF' : 'rgba(255, 255, 255, 0.8)',
                  fontSize: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  transition: 'all var(--transition-fast)'
                }}
              >
                <span>“{q.query}”</span>
                <ChevronRight size={14} color="var(--teal-400)" />
              </button>
            ))}
          </div>
        </div>

        {/* Operational Analytical Answer Card */}
        {selectedPrompt && (
          <div
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.06)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: 'var(--radius-lg)',
              padding: '20px',
              marginBottom: '20px'
            }}
          >
            {/* User Prompt Echo */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px', color: 'var(--teal-300)', fontSize: '12px', fontWeight: '700' }}>
              <Sparkles size={14} />
              <span>Query: {selectedPrompt.query}</span>
            </div>

            {/* Direct Finding */}
            <p style={{ fontSize: '14px', lineHeight: 1.6, color: '#FFFFFF', marginBottom: '18px', fontWeight: '500' }}>
              {selectedPrompt.answer}
            </p>

            {/* Top Contributors Breakdown */}
            <div style={{ marginBottom: '18px' }}>
              <div style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-light-muted)', marginBottom: '8px' }}>
                Variance Decomposition & Contributors
              </div>
              <div
                style={{
                  backgroundColor: 'rgba(0, 0, 0, 0.25)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  overflow: 'hidden'
                }}
              >
                {selectedPrompt.breakdown.map((item, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: '10px 14px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      borderBottom: idx < selectedPrompt.breakdown.length - 1 ? '1px solid rgba(255, 255, 255, 0.06)' : 'none',
                      fontSize: '12px'
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: '600', color: '#FFFFFF' }}>{item.category}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-light-muted)' }}>{item.detail}</div>
                    </div>
                    <div className="mono-num" style={{ fontWeight: '700', color: 'var(--teal-400)' }}>
                      {item.amount}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Evidence & Provenance Link */}
            <div style={{ marginBottom: '18px' }}>
              <button
                onClick={() => setShowEvidence(!showEvidence)}
                style={{
                  fontSize: '12px',
                  color: 'var(--teal-300)',
                  fontWeight: '600',
                  padding: 0,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <FileText size={14} />
                <span>{showEvidence ? 'Hide referenced records' : `View ${selectedPrompt.evidenceCount} related journal transactions`}</span>
              </button>

              {showEvidence && (
                <div
                  style={{
                    marginTop: '10px',
                    padding: '12px',
                    backgroundColor: 'rgba(0, 0, 0, 0.3)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '11px',
                    color: 'var(--text-light-muted)',
                    fontFamily: 'var(--font-mono)'
                  }}
                >
                  <div>• Ref #JV-2026-0890: Stripe Settlement (₹8,40,000)</div>
                  <div>• Ref #JV-2026-0888: WeWork Workspace Lease (₹1,25,000)</div>
                  <div>• Ref #JV-2026-0886: Apex Laboratories Receipt (₹12,50,000)</div>
                  <div>• Ref #JV-2026-0884: Stripe Commission Fee (₹32,450)</div>
                </div>
              )}
            </div>

            {/* Recommended Action with Confirmation Requirement */}
            <div
              style={{
                paddingTop: '16px',
                borderTop: '1px solid rgba(255, 255, 255, 0.1)',
              }}
            >
              <div style={{ fontSize: '12px', color: 'rgba(255, 255, 255, 0.85)', marginBottom: '10px' }}>
                <strong>Recommended Next Step:</strong> {selectedPrompt.actionSuggestion}
              </div>

              {actionConfirmed ? (
                <div
                  style={{
                    padding: '10px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'rgba(16, 185, 129, 0.2)',
                    border: '1px solid #10B981',
                    color: '#6EE7B7',
                    fontSize: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                  }}
                >
                  <CheckCircle2 size={15} />
                  <span>Operation dispatched. Audit trail recorded.</span>
                </div>
              ) : (
                <button
                  onClick={() => setActionConfirmed(true)}
                  className="btn-teal btn-sm"
                  style={{ width: '100%', padding: '8px 14px' }}
                >
                  <Sparkles size={14} />
                  <span>Execute Action With Review</span>
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Input Prompt Box at Bottom */}
      <form
        onSubmit={handleCustomSubmit}
        style={{
          padding: '16px 24px',
          borderTop: '1px solid rgba(255, 255, 255, 0.1)',
          backgroundColor: 'rgba(0, 0, 0, 0.2)',
          display: 'flex',
          alignItems: 'center',
          gap: '10px'
        }}
      >
        <input
          type="text"
          placeholder="Ask about variances, reconciliation, invoices..."
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          style={{
            flex: 1,
            backgroundColor: 'rgba(255, 255, 255, 0.08)',
            border: '1px solid rgba(255, 255, 255, 0.18)',
            color: '#FFFFFF',
            borderRadius: 'var(--radius-md)',
            padding: '10px 14px',
            fontSize: '13px'
          }}
        />

        <button
          type="submit"
          className="btn-teal"
          style={{ padding: '10px 16px', borderRadius: 'var(--radius-md)' }}
        >
          <CornerDownLeft size={16} />
        </button>
      </form>
    </div>
  );
}
