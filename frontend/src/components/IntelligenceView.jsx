import React, { useState } from 'react';
import {
  Sparkles,
  TrendingUp,
  AlertTriangle,
  Clock,
  ArrowRight,
  CheckCircle2,
  SlidersHorizontal,
  ChevronRight,
  ShieldAlert
} from 'lucide-react';

export default function IntelligenceView({ intelligenceInsights }) {
  const [toastMsg, setToastMsg] = useState(null);

  const showToast = (msg) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
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
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <Sparkles size={20} color="var(--teal-500)" />
          <h1 style={{ fontSize: '22px', fontWeight: '800', color: 'var(--navy-900)', letterSpacing: '-0.02em' }}>
            Ledger Intelligence
          </h1>
        </div>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
          Continuous algorithmic surveillance across transaction feeds, working capital, and budget variance.
        </p>
      </div>

      {/* 4 Deep Financial Insights Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
        {intelligenceInsights.map((ins) => (
          <div
            key={ins.id}
            className="panel"
            style={{
              padding: '24px',
              borderLeft: '4px solid var(--teal-500)',
              transition: 'all var(--transition-fast)'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginBottom: '14px' }}>
              <div>
                <span className="badge badge-teal" style={{ marginBottom: '6px' }}>
                  {ins.tag}
                </span>
                <h2 style={{ fontSize: '16px', fontWeight: '800', color: 'var(--navy-900)', marginTop: '4px' }}>
                  {ins.title}
                </h2>
              </div>

              <div
                className="mono-num"
                style={{
                  padding: '6px 12px',
                  backgroundColor: 'var(--bg-canvas)',
                  border: '1px solid var(--border-light)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '13px',
                  fontWeight: '700',
                  color: 'var(--navy-900)'
                }}
              >
                {ins.metric}
              </div>
            </div>

            {/* Why It Matters */}
            <div style={{ marginBottom: '16px' }}>
              <div style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '4px', letterSpacing: '0.04em' }}>
                Why This Matters
              </div>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {ins.whyItMatters}
              </p>
            </div>

            {/* Supporting Data Breakdown */}
            <div style={{ marginBottom: '18px' }}>
              <div style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '6px', letterSpacing: '0.04em' }}>
                Supporting Empirical Evidence
              </div>
              <div
                style={{
                  backgroundColor: 'var(--bg-canvas)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '10px 14px',
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                  gap: '8px'
                }}
              >
                {ins.supportingData.map((d, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>{d.name}</span>
                    <strong className="mono-num" style={{ color: 'var(--navy-900)' }}>{d.amount}</strong>
                  </div>
                ))}
              </div>
            </div>

            {/* Recommended Action */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                paddingTop: '14px',
                borderTop: '1px solid var(--border-subtle)',
                flexWrap: 'wrap',
                gap: '12px'
              }}
            >
              <div style={{ fontSize: '13px', color: 'var(--navy-800)' }}>
                <strong>Recommendation:</strong> {ins.recommendation}
              </div>

              <button
                onClick={() => showToast(`Executing action: ${ins.actionText}`)}
                className="btn-teal btn-sm"
                style={{ padding: '6px 14px' }}
              >
                <span>{ins.actionText}</span>
                <ArrowRight size={13} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
