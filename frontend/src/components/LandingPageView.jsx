import React from 'react';
import {
  Sparkles,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  Lock,
  ArrowUpRight,
  Check,
  Layers,
  BarChart3,
  RefreshCw,
  Landmark,
  FileText,
  AlertTriangle,
  Building2,
  ChevronRight
} from 'lucide-react';

export default function LandingPageView({ onEnterApp }) {
  return (
    <div className="animate-fade-in" style={{ backgroundColor: 'var(--bg-canvas)', color: 'var(--navy-900)', minHeight: '100vh' }}>
      {/* Top Marketing Navigation */}
      <nav
        style={{
          borderBottom: '1px solid var(--border-light)',
          backgroundColor: '#FFFFFF',
          padding: '16px 36px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          position: 'sticky',
          top: 0,
          zIndex: 50
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '7px',
              backgroundColor: 'var(--navy-900)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: 'var(--shadow-xs)'
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M4 6H18M4 12H14M4 18H18" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" />
              <circle cx="19" cy="12" r="2.5" fill="#23C7B8" />
            </svg>
          </div>
          <span style={{ fontSize: '18px', fontWeight: '800', letterSpacing: '-0.02em', color: 'var(--navy-900)' }}>
            Ledger <span style={{ color: 'var(--teal-500)' }}>Ai</span>
          </span>
        </div>

        <div className="desktop-only" style={{ display: 'flex', alignItems: 'center', gap: '28px', fontSize: '13px', fontWeight: '600', color: 'var(--text-secondary)' }}>
          <a href="#overview" style={{ textDecoration: 'none', color: 'inherit' }}>Financial Overview</a>
          <a href="#transactions" style={{ textDecoration: 'none', color: 'inherit' }}>Transactions</a>
          <a href="#reconciliation" style={{ textDecoration: 'none', color: 'inherit' }}>Reconciliation</a>
          <a href="#intelligence" style={{ textDecoration: 'none', color: 'inherit' }}>Intelligence</a>
          <a href="#security" style={{ textDecoration: 'none', color: 'inherit' }}>Security & Trust</a>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={onEnterApp}
            className="btn-secondary"
            style={{ fontSize: '13px', padding: '8px 16px' }}
          >
            Sign In
          </button>
          <button
            onClick={onEnterApp}
            className="btn-primary"
            style={{ fontSize: '13px', padding: '8px 18px', backgroundColor: 'var(--navy-900)' }}
          >
            <span>Launch Workspace</span>
            <ArrowRight size={14} />
          </button>
        </div>
      </nav>

      {/* Hero Section — Editorial Swiss Fintech Tone */}
      <section
        className="ledger-grid-bg"
        style={{
          padding: '80px 24px 60px',
          textAlign: 'center',
          maxWidth: '1200px',
          margin: '0 auto',
          position: 'relative'
        }}
      >
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '5px 12px', borderRadius: '16px', backgroundColor: 'var(--teal-50)', border: '1px solid rgba(14, 170, 165, 0.25)', fontSize: '12px', fontWeight: '700', color: 'var(--teal-700)', marginBottom: '24px' }}>
          <Sparkles size={14} />
          <span>The Financial Operating System For High-Velocity Companies</span>
        </div>

        <h1
          style={{
            fontSize: '54px',
            lineHeight: 1.1,
            fontWeight: '800',
            letterSpacing: '-0.03em',
            color: 'var(--navy-900)',
            maxWidth: '880px',
            margin: '0 auto 20px'
          }}
        >
          Your accounts, handled intelligently.
        </h1>

        <p
          style={{
            fontSize: '18px',
            lineHeight: 1.6,
            color: 'var(--text-secondary)',
            maxWidth: '680px',
            margin: '0 auto 36px'
          }}
        >
          Ledger Ai monitors your financial activity, organizes your records, reconciles statements, and handles everyday accounting work automatically.
        </p>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '14px', flexWrap: 'wrap', marginBottom: '48px' }}>
          <button
            onClick={onEnterApp}
            className="btn-teal"
            style={{ padding: '12px 24px', fontSize: '15px', borderRadius: 'var(--radius-md)' }}
          >
            <span>Start using Ledger Ai</span>
            <ArrowRight size={16} />
          </button>

          <button
            onClick={onEnterApp}
            className="btn-secondary"
            style={{ padding: '12px 24px', fontSize: '15px', borderRadius: 'var(--radius-md)' }}
          >
            <span>See how it works</span>
          </button>
        </div>

        {/* Hero Interactive UI Preview (Featuring the Real Needs Attention Command Center) */}
        <div
          style={{
            maxWidth: '1060px',
            margin: '0 auto',
            backgroundColor: '#FFFFFF',
            border: '1px solid var(--border-light)',
            borderRadius: 'var(--radius-xl)',
            boxShadow: 'var(--shadow-panel)',
            overflow: 'hidden',
            textAlign: 'left'
          }}
        >
          {/* Mock Browser Header */}
          <div
            style={{
              padding: '12px 18px',
              backgroundColor: 'var(--navy-900)',
              color: '#FFFFFF',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '12px',
              borderBottom: '1px solid rgba(255, 255, 255, 0.08)'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ display: 'flex', gap: '6px' }}>
                <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#EF4444' }} />
                <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#F59E0B' }} />
                <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#10B981' }} />
              </div>
              <span className="mono-num" style={{ color: 'var(--text-light-muted)' }}>app.ledgerai.internal/workspace/overview</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="badge badge-teal" style={{ fontSize: '10px' }}>Active Control Room</span>
            </div>
          </div>

          {/* Interactive Preview Body */}
          <div style={{ padding: '24px' }}>
            {/* KPI preview */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '24px' }}>
              <div style={{ padding: '12px', backgroundColor: 'var(--bg-canvas)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: '600' }}>Cash Reserves</div>
                <div className="mono-num" style={{ fontSize: '18px', fontWeight: '800', color: 'var(--navy-900)' }}>₹1,42,85,600</div>
              </div>
              <div style={{ padding: '12px', backgroundColor: 'var(--bg-canvas)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: '600' }}>Receivables</div>
                <div className="mono-num" style={{ fontSize: '18px', fontWeight: '800', color: 'var(--navy-900)' }}>₹28,40,000</div>
              </div>
              <div style={{ padding: '12px', backgroundColor: 'var(--bg-canvas)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: '600' }}>Monthly Revenue</div>
                <div className="mono-num" style={{ fontSize: '18px', fontWeight: '800', color: '#047857' }}>₹64,20,000</div>
              </div>
              <div style={{ padding: '12px', backgroundColor: 'var(--bg-canvas)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: '600' }}>Net Burn Runway</div>
                <div className="mono-num" style={{ fontSize: '18px', fontWeight: '800', color: 'var(--teal-700)' }}>8.4 Months</div>
              </div>
            </div>

            {/* Needs Attention Command Center Highlight */}
            <div style={{ border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
              <div style={{ padding: '12px 16px', backgroundColor: 'var(--bg-canvas)', borderBottom: '1px solid var(--border-light)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ fontWeight: '700', fontSize: '13px', color: 'var(--navy-900)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <AlertTriangle size={15} color="var(--alert-amber-badge)" />
                  <span>Needs Attention (Command Center)</span>
                </div>
                <span className="badge badge-amber">Action Required</span>
              </div>

              {[
                { title: '7 transactions need categorization', tag: 'High', color: 'amber', action: 'Batch Accept All (7)' },
                { title: '3 invoices are overdue (₹4,85,000)', tag: 'Critical', color: 'red', action: 'Dispatch Reminders' },
                { title: 'HDFC Bank reconciliation discrepancy (₹32,450)', tag: 'High', color: 'amber', action: 'Match with Stripe Fee' },
              ].map((row, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: '12px 16px',
                    borderBottom: idx < 2 ? '1px solid var(--border-subtle)' : 'none',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span className={`badge badge-${row.color}`}>{row.tag}</span>
                    <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--navy-900)' }}>{row.title}</span>
                  </div>
                  <button onClick={onEnterApp} className="btn-secondary btn-sm" style={{ fontSize: '11px' }}>
                    {row.action}
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* 6 Feature Pillars Section */}
      <section id="overview" style={{ padding: '80px 24px', maxWidth: '1200px', margin: '0 auto' }}>
        <div style={{ textAlign: 'center', marginBottom: '54px' }}>
          <h2 style={{ fontSize: '32px', fontWeight: '800', letterSpacing: '-0.02em', color: 'var(--navy-900)', marginBottom: '12px' }}>
            Built for precision, clarity, and control.
          </h2>
          <p style={{ fontSize: '16px', color: 'var(--text-secondary)', maxWidth: '600px', margin: '0 auto' }}>
            Every interaction is calibrated for financial fidelity rather than generic conversational novelty.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '24px' }}>
          {/* Pillar 1 */}
          <div className="panel" style={{ padding: '28px' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '8px', backgroundColor: 'var(--teal-50)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px' }}>
              <Layers size={20} color="var(--teal-600)" />
            </div>
            <h3 style={{ fontSize: '17px', fontWeight: '800', color: 'var(--navy-900)', marginBottom: '8px' }}>
              1. Unified Financial Overview
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              Consolidate multi-currency bank feeds, payment gateways, and corporate credit cards into a single authoritative control room.
            </p>
          </div>

          {/* Pillar 2 */}
          <div className="panel" style={{ padding: '28px' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '8px', backgroundColor: 'var(--teal-50)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px' }}>
              <Sparkles size={20} color="var(--teal-600)" />
            </div>
            <h3 style={{ fontSize: '17px', fontWeight: '800', color: 'var(--navy-900)', marginBottom: '8px' }}>
              2. AI-Powered Transaction Handling
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              Automated double-entry classification with confidence ratings. Accept suggestions with one click or customize mapping rules.
            </p>
          </div>

          {/* Pillar 3 */}
          <div className="panel" style={{ padding: '28px' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '8px', backgroundColor: 'var(--teal-50)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px' }}>
              <RefreshCw size={20} color="var(--teal-600)" />
            </div>
            <h3 style={{ fontSize: '17px', fontWeight: '800', color: 'var(--navy-900)', marginBottom: '8px' }}>
              3. Split-Screen Reconciliation
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              Visual side-by-side statement matching. Eliminate manual Excel lookups with 98% automated confidence score alignments.
            </p>
          </div>

          {/* Pillar 4 */}
          <div className="panel" style={{ padding: '28px' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '8px', backgroundColor: 'var(--teal-50)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px' }}>
              <TrendingUp size={20} color="var(--teal-600)" />
            </div>
            <h3 style={{ fontSize: '17px', fontWeight: '800', color: 'var(--navy-900)', marginBottom: '8px' }}>
              4. Ledger Intelligence & Anomalies
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              Detect duplicate charges, SaaS seat inflation, working capital delays, and runway contraction before they impact quarterly EBITDA.
            </p>
          </div>

          {/* Pillar 5 */}
          <div className="panel" style={{ padding: '28px' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '8px', backgroundColor: 'var(--teal-50)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px' }}>
              <BarChart3 size={20} color="var(--teal-600)" />
            </div>
            <h3 style={{ fontSize: '17px', fontWeight: '800', color: 'var(--navy-900)', marginBottom: '8px' }}>
              5. Automated Reporting & Statements
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              Instant GAAP/IFRS compliant Profit & Loss, Balance Sheet, and Cash Flow telemetry with historical trailing period comparisons.
            </p>
          </div>

          {/* Pillar 6 */}
          <div className="panel" id="security" style={{ padding: '28px' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '8px', backgroundColor: 'var(--teal-50)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px' }}>
              <ShieldCheck size={20} color="var(--teal-600)" />
            </div>
            <h3 style={{ fontSize: '17px', fontWeight: '800', color: 'var(--navy-900)', marginBottom: '8px' }}>
              6. Institutional Security & Trust
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              Append-only immutable audit trail, SOC2 Type II compliance readiness, 256-bit AES encryption, and separation-of-duties access control.
            </p>
          </div>
        </div>
      </section>

      {/* Footer CTA */}
      <section
        style={{
          backgroundColor: 'var(--navy-900)',
          color: '#FFFFFF',
          padding: '70px 24px',
          textAlign: 'center'
        }}
      >
        <div style={{ maxWidth: '720px', margin: '0 auto' }}>
          <h2 style={{ fontSize: '32px', fontWeight: '800', letterSpacing: '-0.02em', marginBottom: '16px' }}>
            Ready to upgrade your accounting operations?
          </h2>
          <p style={{ fontSize: '16px', color: 'var(--text-light-muted)', marginBottom: '32px' }}>
            Experience real financial control with Ledger Ai. Launch the workspace now to explore the live control room.
          </p>

          <button
            onClick={onEnterApp}
            className="btn-teal"
            style={{ padding: '14px 28px', fontSize: '16px', borderRadius: 'var(--radius-md)' }}
          >
            <span>Launch Financial Control Room</span>
            <ArrowRight size={18} />
          </button>
        </div>
      </section>

      {/* Legal & Brand Footer */}
      <footer
        style={{
          backgroundColor: 'var(--navy-950)',
          color: 'var(--text-light-muted)',
          padding: '24px 36px',
          fontSize: '12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px'
        }}
      >
        <div>
          © 2026 Ledger Ai Inc. All rights reserved. Precision financial systems.
        </div>
        <div style={{ display: 'flex', gap: '20px' }}>
          <span>SOC2 Type II Certified</span>
          <span>Double-Entry Append Only</span>
          <span>Zero Credential Retention</span>
        </div>
      </footer>
    </div>
  );
}
