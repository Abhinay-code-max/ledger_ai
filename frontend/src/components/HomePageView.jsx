import React, { useState } from 'react';
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
  ChevronRight,
  TrendingUp,
  TrendingDown,
  UserCheck,
  Sliders,
  Shield,
  Zap,
  DollarSign,
  Activity,
  LogOut,
  KeyRound,
  Users,
  Eye
} from 'lucide-react';
import { DEMO_USERS } from '../data/authUsers';

export default function HomePageView({
  onEnterApp,
  onOpenAuth,
  currentUser,
  onLogout,
  onQuickRoleLogin
}) {
  const [activeSandboxTab, setActiveSandboxTab] = useState('categorization'); // 'categorization' | 'reconciliation' | 'rbac'
  const [sandboxClassified, setSandboxClassified] = useState(false);
  const [sandboxMatched, setSandboxMatched] = useState(false);
  const [activeRoleFilter, setActiveRoleFilter] = useState('cfo');

  return (
    <div className="animate-fade-in" style={{ backgroundColor: 'var(--bg-canvas)', color: 'var(--navy-900)', minHeight: '100vh' }}>
      {/* Top Navigation */}
      <nav
        style={{
          borderBottom: '1px solid var(--border-light)',
          backgroundColor: '#FFFFFF',
          padding: '14px 36px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          position: 'sticky',
          top: 0,
          zIndex: 50,
          boxShadow: 'var(--shadow-xs)'
        }}
      >
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }} onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
          <div
            style={{
              width: '34px',
              height: '34px',
              borderRadius: '8px',
              backgroundColor: 'var(--navy-900)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: 'var(--shadow-xs)'
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M4 6H18M4 12H14M4 18H18" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" />
              <circle cx="19" cy="12" r="2.5" fill="#23C7B8" />
            </svg>
          </div>
          <span style={{ fontSize: '19px', fontWeight: '800', letterSpacing: '-0.02em', color: 'var(--navy-900)' }}>
            Ledger <span style={{ color: 'var(--teal-500)' }}>Ai</span>
          </span>
          <span className="badge badge-teal desktop-only" style={{ fontSize: '10px', marginLeft: '6px' }}>
            Enterprise FOS
          </span>
        </div>

        {/* Navigation Links */}
        <div className="desktop-only" style={{ display: 'flex', alignItems: 'center', gap: '26px', fontSize: '13px', fontWeight: '600', color: 'var(--text-secondary)' }}>
          <a href="#overview" style={{ textDecoration: 'none', color: 'inherit' }}>Overview</a>
          <a href="#sandbox" style={{ textDecoration: 'none', color: 'inherit' }}>Interactive Sandbox</a>
          <a href="#authorization" style={{ textDecoration: 'none', color: 'inherit' }}>Role Security (RBAC)</a>
          <a href="#features" style={{ textDecoration: 'none', color: 'inherit' }}>Core Capabilities</a>
          <a href="#pricing" style={{ textDecoration: 'none', color: 'inherit' }}>Pricing</a>
          <a href="#security" style={{ textDecoration: 'none', color: 'inherit' }}>Compliance & Trust</a>
        </div>

        {/* Right Auth Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {currentUser ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '5px 10px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--bg-canvas)',
                  border: '1px solid var(--border-light)',
                  fontSize: '12px'
                }}
              >
                <div
                  style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    backgroundColor: currentUser.role === 'cfo' ? 'var(--navy-900)' : currentUser.role === 'accountant' ? 'var(--teal-600)' : 'var(--alert-amber-badge)',
                    color: '#FFFFFF',
                    fontSize: '10px',
                    fontWeight: '700',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}
                >
                  {currentUser.avatar || 'US'}
                </div>
                <div className="desktop-only">
                  <div style={{ fontWeight: '700', color: 'var(--navy-900)' }}>{currentUser.name}</div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{currentUser.roleBadge}</div>
                </div>
              </div>

              <button
                onClick={onEnterApp}
                className="btn-primary"
                style={{ fontSize: '13px', padding: '8px 16px', backgroundColor: 'var(--navy-900)' }}
              >
                <span>Launch Workspace</span>
                <ArrowRight size={14} />
              </button>

              <button
                onClick={onLogout}
                className="btn-secondary"
                style={{ padding: '8px', fontSize: '12px' }}
                title="Sign Out"
              >
                <LogOut size={15} />
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button
                onClick={() => onOpenAuth('signin')}
                className="btn-secondary"
                style={{ fontSize: '13px', padding: '8px 16px' }}
              >
                Sign In
              </button>

              <button
                onClick={() => onOpenAuth('signup')}
                className="btn-teal"
                style={{ fontSize: '13px', padding: '8px 16px' }}
              >
                Create Account
              </button>

              <button
                onClick={onEnterApp}
                className="btn-primary desktop-only"
                style={{ fontSize: '13px', padding: '8px 16px', backgroundColor: 'var(--navy-900)' }}
              >
                <span>Live Demo</span>
                <ArrowRight size={14} />
              </button>
            </div>
          )}
        </div>
      </nav>

      {/* Hero Section */}
      <header
        className="ledger-grid-bg"
        style={{
          padding: '76px 24px 50px',
          textAlign: 'center',
          maxWidth: '1240px',
          margin: '0 auto',
          position: 'relative'
        }}
      >
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '6px 14px', borderRadius: '20px', backgroundColor: 'var(--teal-50)', border: '1px solid rgba(14, 170, 165, 0.3)', fontSize: '12px', fontWeight: '700', color: 'var(--teal-700)', marginBottom: '22px' }}>
          <Sparkles size={14} />
          <span>Institutional Financial Intelligence • SOC2 Type II Certified</span>
        </div>

        <h1
          style={{
            fontSize: '52px',
            lineHeight: 1.12,
            fontWeight: '800',
            letterSpacing: '-0.03em',
            color: 'var(--navy-900)',
            maxWidth: '920px',
            margin: '0 auto 20px'
          }}
        >
          Autonomous Accounting With Separation-of-Duties Precision.
        </h1>

        <p
          style={{
            fontSize: '18px',
            lineHeight: 1.6,
            color: 'var(--text-secondary)',
            maxWidth: '720px',
            margin: '0 auto 36px'
          }}
        >
          Ledger Ai automatically classifies transactions, executes split-screen bank reconciliation, and generates audit-ready GAAP statements—with strict role-based authorization for CFOs, Accountants, and Auditors.
        </p>

        {/* Primary CTA Row */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '14px', flexWrap: 'wrap', marginBottom: '44px' }}>
          <button
            onClick={onEnterApp}
            className="btn-teal"
            style={{ padding: '13px 28px', fontSize: '15px', borderRadius: 'var(--radius-md)', boxShadow: '0 4px 14px rgba(14, 170, 165, 0.3)' }}
          >
            <span>Launch Live Workspace</span>
            <ArrowRight size={16} />
          </button>

          <button
            onClick={() => {
              const el = document.getElementById('authorization');
              if (el) el.scrollIntoView({ behavior: 'smooth' });
            }}
            className="btn-secondary"
            style={{ padding: '13px 24px', fontSize: '15px', borderRadius: 'var(--radius-md)' }}
          >
            <ShieldCheck size={16} color="var(--teal-600)" />
            <span>Explore RBAC Security</span>
          </button>

          {!currentUser && (
            <button
              onClick={() => onOpenAuth('signin')}
              className="btn-secondary"
              style={{ padding: '13px 22px', fontSize: '15px', borderRadius: 'var(--radius-md)' }}
            >
              <KeyRound size={16} />
              <span>Sign In with Demo Role</span>
            </button>
          )}
        </div>

        {/* Key Real-Time Metrics Strip */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '12px',
            maxWidth: '1040px',
            margin: '0 auto 40px',
            textAlign: 'left'
          }}
        >
          <div style={{ padding: '16px 20px', backgroundColor: '#FFFFFF', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-light)', boxShadow: 'var(--shadow-xs)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: '700', textTransform: 'uppercase' }}>Cash Monitored</div>
            <div className="mono-num" style={{ fontSize: '22px', fontWeight: '800', color: 'var(--navy-900)', marginTop: '4px' }}>₹1,42,85,600</div>
            <div style={{ fontSize: '11px', color: '#047857', fontWeight: '600', marginTop: '2px' }}>Across 5 Institutional Accounts</div>
          </div>

          <div style={{ padding: '16px 20px', backgroundColor: '#FFFFFF', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-light)', boxShadow: 'var(--shadow-xs)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: '700', textTransform: 'uppercase' }}>Auto-Match Accuracy</div>
            <div className="mono-num" style={{ fontSize: '22px', fontWeight: '800', color: 'var(--teal-600)', marginTop: '4px' }}>99.4%</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: '600', marginTop: '2px' }}>AI High-Confidence Alignment</div>
          </div>

          <div style={{ padding: '16px 20px', backgroundColor: '#FFFFFF', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-light)', boxShadow: 'var(--shadow-xs)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: '700', textTransform: 'uppercase' }}>Restatements / Errors</div>
            <div className="mono-num" style={{ fontSize: '22px', fontWeight: '800', color: '#047857', marginTop: '4px' }}>0.00%</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: '600', marginTop: '2px' }}>Double-Entry Invariant Guard</div>
          </div>

          <div style={{ padding: '16px 20px', backgroundColor: '#FFFFFF', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-light)', boxShadow: 'var(--shadow-xs)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: '700', textTransform: 'uppercase' }}>Role Authorization</div>
            <div className="mono-num" style={{ fontSize: '22px', fontWeight: '800', color: 'var(--navy-800)', marginTop: '4px' }}>3 Enforced Roles</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: '600', marginTop: '2px' }}>CFO, Accountant, Auditor</div>
          </div>
        </div>
      </header>

      {/* Interactive Sandbox Section (Try Ledger AI Live Right on the Home Page) */}
      <section
        id="sandbox"
        style={{
          padding: '60px 24px',
          maxWidth: '1160px',
          margin: '0 auto'
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: '700', color: 'var(--teal-700)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
            <Zap size={14} />
            <span>Interactive Demo Console</span>
          </div>
          <h2 style={{ fontSize: '32px', fontWeight: '800', color: 'var(--navy-900)', letterSpacing: '-0.02em' }}>
            Experience Ledger Ai In Action
          </h2>
          <p style={{ fontSize: '15px', color: 'var(--text-secondary)', maxWidth: '600px', margin: '0 auto' }}>
            Test transaction classification, reconciliation matching, and role authorization right here before opening the full workspace.
          </p>
        </div>

        {/* Sandbox Container */}
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: 'var(--radius-xl)',
            border: '1px solid var(--border-light)',
            boxShadow: 'var(--shadow-md)',
            overflow: 'hidden'
          }}
        >
          {/* Sandbox Tabs */}
          <div
            style={{
              display: 'flex',
              borderBottom: '1px solid var(--border-light)',
              backgroundColor: 'var(--bg-canvas)',
              padding: '8px 12px',
              gap: '8px'
            }}
          >
            <button
              onClick={() => setActiveSandboxTab('categorization')}
              style={{
                padding: '9px 18px',
                borderRadius: 'var(--radius-md)',
                border: 'none',
                fontSize: '13px',
                fontWeight: '700',
                cursor: 'pointer',
                backgroundColor: activeSandboxTab === 'categorization' ? '#FFFFFF' : 'transparent',
                color: activeSandboxTab === 'categorization' ? 'var(--navy-900)' : 'var(--text-muted)',
                boxShadow: activeSandboxTab === 'categorization' ? 'var(--shadow-xs)' : 'none',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              <Sparkles size={15} color="var(--teal-500)" />
              <span>1. AI Double-Entry Classification</span>
            </button>

            <button
              onClick={() => setActiveSandboxTab('reconciliation')}
              style={{
                padding: '9px 18px',
                borderRadius: 'var(--radius-md)',
                border: 'none',
                fontSize: '13px',
                fontWeight: '700',
                cursor: 'pointer',
                backgroundColor: activeSandboxTab === 'reconciliation' ? '#FFFFFF' : 'transparent',
                color: activeSandboxTab === 'reconciliation' ? 'var(--navy-900)' : 'var(--text-muted)',
                boxShadow: activeSandboxTab === 'reconciliation' ? 'var(--shadow-xs)' : 'none',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              <RefreshCw size={15} color="var(--teal-500)" />
              <span>2. Split-Screen Reconciliation</span>
            </button>

            <button
              onClick={() => setActiveSandboxTab('rbac')}
              style={{
                padding: '9px 18px',
                borderRadius: 'var(--radius-md)',
                border: 'none',
                fontSize: '13px',
                fontWeight: '700',
                cursor: 'pointer',
                backgroundColor: activeSandboxTab === 'rbac' ? '#FFFFFF' : 'transparent',
                color: activeSandboxTab === 'rbac' ? 'var(--navy-900)' : 'var(--text-muted)',
                boxShadow: activeSandboxTab === 'rbac' ? 'var(--shadow-xs)' : 'none',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              <ShieldCheck size={15} color="var(--teal-500)" />
              <span>3. Role-Based Access Control</span>
            </button>
          </div>

          {/* Sandbox Body */}
          <div style={{ padding: '28px' }}>
            {/* Tab 1: AI Categorization */}
            {activeSandboxTab === 'categorization' && (
              <div className="animate-fade-in">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px', flexWrap: 'wrap', gap: '10px' }}>
                  <div>
                    <h3 style={{ fontSize: '17px', fontWeight: '800', color: 'var(--navy-900)' }}>
                      Live Merchant Ingestion & Tax Code Prediction
                    </h3>
                    <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                      Unmapped debit feed arrives from HDFC Corporate Card. Watch AI formulate GAAP entries.
                    </p>
                  </div>
                  <button
                    onClick={() => setSandboxClassified(prev => !prev)}
                    className="btn-teal"
                    style={{ fontSize: '12px', padding: '8px 16px' }}
                  >
                    <Sparkles size={14} />
                    <span>{sandboxClassified ? 'Reset Transaction' : 'Trigger AI Auto-Classify'}</span>
                  </button>
                </div>

                <div
                  style={{
                    border: '1px solid var(--border-light)',
                    borderRadius: 'var(--radius-md)',
                    overflow: 'hidden'
                  }}
                >
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                    <thead>
                      <tr style={{ backgroundColor: 'var(--bg-canvas)', borderBottom: '1px solid var(--border-light)' }}>
                        <th style={{ padding: '10px 16px', fontWeight: '700', color: 'var(--navy-900)' }}>Date & Source</th>
                        <th style={{ padding: '10px 16px', fontWeight: '700', color: 'var(--navy-900)' }}>Raw Bank Feed Merchant</th>
                        <th style={{ padding: '10px 16px', fontWeight: '700', color: 'var(--navy-900)' }}>Amount</th>
                        <th style={{ padding: '10px 16px', fontWeight: '700', color: 'var(--navy-900)' }}>AI Predicted Classification</th>
                        <th style={{ padding: '10px 16px', fontWeight: '700', color: 'var(--navy-900)' }}>Confidence</th>
                        <th style={{ padding: '10px 16px', fontWeight: '700', color: 'var(--navy-900)' }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
                          <div style={{ fontWeight: '600' }}>07 Oct 2026</div>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>HDFC Card • 8821</div>
                        </td>
                        <td style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
                          <div style={{ fontWeight: '700', color: 'var(--navy-900)' }}>AMZN WEB SERVICES WA #89102</div>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>MCC: 7372 Computer Programming</div>
                        </td>
                        <td className="mono-num" style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-subtle)', fontWeight: '700', color: '#B91C1C' }}>
                          -₹84,200.00
                        </td>
                        <td style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
                          {sandboxClassified ? (
                            <div>
                              <span style={{ fontWeight: '700', color: 'var(--navy-900)' }}>SaaS & Cloud Infrastructure</span>
                              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>GL 6020 • Debit OpEx / Credit HDFC</div>
                            </div>
                          ) : (
                            <span className="badge badge-amber">Unassigned Debit</span>
                          )}
                        </td>
                        <td style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
                          {sandboxClassified ? (
                            <span className="badge badge-teal" style={{ fontWeight: '700' }}>98.8% Match</span>
                          ) : (
                            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Pending AI run</span>
                          )}
                        </td>
                        <td style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
                          {sandboxClassified ? (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#047857', fontWeight: '700', fontSize: '12px' }}>
                              <CheckCircle2 size={16} />
                              <span>Classification Ready</span>
                            </div>
                          ) : (
                            <span style={{ fontSize: '12px', color: 'var(--alert-amber-badge)', fontWeight: '600' }}>Needs Review</span>
                          )}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {sandboxClassified && (
                  <div className="animate-fade-in" style={{ marginTop: '16px', padding: '14px', backgroundColor: 'var(--teal-50)', borderRadius: 'var(--radius-md)', border: '1px solid rgba(14, 170, 165, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <CheckCircle2 size={18} color="var(--teal-700)" />
                      <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--teal-900)' }}>
                        Double-entry balanced: ₹84,200 assigned to Cloud Hosting (Dept: Engineering). Ready for CFO ledger posting!
                      </span>
                    </div>
                    <button onClick={onEnterApp} className="btn-primary btn-sm" style={{ backgroundColor: 'var(--navy-900)' }}>
                      <span>View in Workspace</span>
                      <ArrowRight size={13} />
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Tab 2: Split Screen Reconciliation */}
            {activeSandboxTab === 'reconciliation' && (
              <div className="animate-fade-in">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px', flexWrap: 'wrap', gap: '10px' }}>
                  <div>
                    <h3 style={{ fontSize: '17px', fontWeight: '800', color: 'var(--navy-900)' }}>
                      Real-Time Split-Screen Bank Statement Matching
                    </h3>
                    <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                      Eliminate manual spreadsheets. Auto-match bank feed rows against ERP invoices and vendor payments.
                    </p>
                  </div>
                  <button
                    onClick={() => setSandboxMatched(prev => !prev)}
                    className="btn-teal"
                    style={{ fontSize: '12px', padding: '8px 16px' }}
                  >
                    <RefreshCw size={14} />
                    <span>{sandboxMatched ? 'Reset Match' : 'Simulate Auto-Match'}</span>
                  </button>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
                  {/* Left: Bank Statement Line */}
                  <div style={{ border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', padding: '16px', backgroundColor: 'var(--bg-canvas)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                      <span style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Bank Statement Feed (ICICI)</span>
                      <span className="badge badge-teal">Bank Record</span>
                    </div>
                    <div style={{ fontSize: '14px', fontWeight: '700', color: 'var(--navy-900)' }}>RTGS Credit: Bharat SaaS Labs</div>
                    <div className="mono-num" style={{ fontSize: '20px', fontWeight: '800', color: '#047857', margin: '6px 0' }}>+₹6,20,000.00</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Ref: CMS892301994 • Value Date: 05 Oct 2026</div>
                  </div>

                  {/* Right: Internal Invoice Record */}
                  <div style={{ border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', padding: '16px', backgroundColor: sandboxMatched ? 'var(--teal-50)' : 'var(--bg-canvas)', borderColor: sandboxMatched ? 'var(--teal-500)' : 'var(--border-light)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                      <span style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Internal General Ledger Invoice</span>
                      <span className={sandboxMatched ? 'badge badge-teal' : 'badge badge-amber'}>{sandboxMatched ? '99.2% Matched' : 'Awaiting Match'}</span>
                    </div>
                    <div style={{ fontSize: '14px', fontWeight: '700', color: 'var(--navy-900)' }}>INV-2026-089 (Bharat SaaS Labs)</div>
                    <div className="mono-num" style={{ fontSize: '20px', fontWeight: '800', color: 'var(--navy-900)', margin: '6px 0' }}>₹6,20,000.00</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Annual Platform Enterprise Tier • Billed 01 Oct 2026</div>
                  </div>
                </div>

                {sandboxMatched && (
                  <div className="animate-fade-in" style={{ marginTop: '16px', padding: '14px', backgroundColor: '#ECFDF5', borderRadius: 'var(--radius-md)', border: '1px solid #A7F3D0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <CheckCircle2 size={18} color="#047857" />
                      <span style={{ fontSize: '13px', fontWeight: '600', color: '#065F46' }}>
                        Zero-variance match verified! Clears Accounts Receivable by ₹6,20,000.
                      </span>
                    </div>
                    <button onClick={onEnterApp} className="btn-primary btn-sm" style={{ backgroundColor: 'var(--navy-900)' }}>
                      <span>Reconcile in App</span>
                      <ArrowRight size={13} />
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Tab 3: RBAC Simulator */}
            {activeSandboxTab === 'rbac' && (
              <div className="animate-fade-in">
                <div style={{ marginBottom: '18px' }}>
                  <h3 style={{ fontSize: '17px', fontWeight: '800', color: 'var(--navy-900)' }}>
                    Institutional Separation-of-Duties (RBAC Matrix)
                  </h3>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                    Select a role to inspect permissions. Test how controls adapt across organizational boundaries.
                  </p>
                </div>

                {/* Role Selector Pills */}
                <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
                  {Object.keys(DEMO_USERS).map((roleKey) => {
                    const u = DEMO_USERS[roleKey];
                    const isSel = activeRoleFilter === roleKey;
                    return (
                      <button
                        key={roleKey}
                        onClick={() => setActiveRoleFilter(roleKey)}
                        style={{
                          padding: '10px 16px',
                          borderRadius: 'var(--radius-md)',
                          border: isSel ? '2px solid var(--navy-900)' : '1px solid var(--border-light)',
                          backgroundColor: isSel ? '#FFFFFF' : 'var(--bg-canvas)',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '10px',
                          boxShadow: isSel ? 'var(--shadow-sm)' : 'none'
                        }}
                      >
                        <div
                          style={{
                            width: '26px',
                            height: '26px',
                            borderRadius: '50%',
                            backgroundColor: roleKey === 'cfo' ? 'var(--navy-900)' : roleKey === 'accountant' ? 'var(--teal-600)' : 'var(--alert-amber-badge)',
                            color: '#FFFFFF',
                            fontSize: '11px',
                            fontWeight: '700',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                          }}
                        >
                          {u.avatar}
                        </div>
                        <div style={{ textAlign: 'left' }}>
                          <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--navy-900)' }}>{u.name}</div>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{u.roleTitle}</div>
                        </div>
                      </button>
                    );
                  })}
                </div>

                {/* Role Details & Permissions Grid */}
                {(() => {
                  const roleObj = DEMO_USERS[activeRoleFilter];
                  return (
                    <div style={{ border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', padding: '20px', backgroundColor: 'var(--bg-canvas)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
                        <div>
                          <span className={`badge badge-${roleObj.badgeColor}`} style={{ fontSize: '12px' }}>
                            {roleObj.roleBadge}
                          </span>
                          <span style={{ fontSize: '13px', color: 'var(--text-secondary)', marginLeft: '10px' }}>
                            {roleObj.description}
                          </span>
                        </div>

                        <button
                          onClick={() => onQuickRoleLogin(activeRoleFilter)}
                          className="btn-primary btn-sm"
                          style={{ backgroundColor: 'var(--navy-900)' }}
                        >
                          <span>Log in as {roleObj.name}</span>
                          <ArrowRight size={13} />
                        </button>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
                        {[
                          { name: 'Approve & Post Journals', allowed: roleObj.permissions.canApprove },
                          { name: 'Categorize Bank Feeds', allowed: roleObj.permissions.canEdit },
                          { name: 'Execute Irrevocable Period Close', allowed: roleObj.permissions.canClosePeriod },
                          { name: 'Run Reconciliation Auto-Match', allowed: roleObj.permissions.canReconcile },
                          { name: 'View Audit Logs & Statements', allowed: true },
                          { name: 'Configure Security & Bank Settings', allowed: roleObj.permissions.canManageSettings },
                        ].map((perm, idx) => (
                          <div
                            key={idx}
                            style={{
                              padding: '10px 14px',
                              borderRadius: 'var(--radius-sm)',
                              backgroundColor: '#FFFFFF',
                              border: '1px solid var(--border-subtle)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between'
                            }}
                          >
                            <span style={{ fontSize: '12px', fontWeight: '600', color: 'var(--navy-900)' }}>{perm.name}</span>
                            {perm.allowed ? (
                              <span style={{ color: '#047857', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontWeight: '700' }}>
                                <Check size={14} /> Allowed
                              </span>
                            ) : (
                              <span style={{ color: '#B91C1C', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontWeight: '700' }}>
                                <Lock size={13} /> Locked
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })()}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Role-Based Access Control Section */}
      <section
        id="authorization"
        style={{
          padding: '80px 24px',
          maxWidth: '1200px',
          margin: '0 auto'
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '50px' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: '700', color: 'var(--teal-700)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
            <ShieldCheck size={16} />
            <span>Cryptographic Separation of Duties</span>
          </div>
          <h2 style={{ fontSize: '36px', fontWeight: '800', letterSpacing: '-0.02em', color: 'var(--navy-900)', marginBottom: '12px' }}>
            Enterprise Roles Designed For Accounting Integrity
          </h2>
          <p style={{ fontSize: '16px', color: 'var(--text-secondary)', maxWidth: '640px', margin: '0 auto' }}>
            Accounting errors happen when everyone has write access. Ledger Ai enforces role-bounded operational guardrails.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px' }}>
          {/* Card 1: CFO / Administrator */}
          <div
            className="panel"
            style={{
              padding: '30px',
              borderTop: '4px solid var(--navy-900)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between'
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <span className="badge badge-navy" style={{ fontSize: '11px' }}>Full Authority</span>
                <span className="mono-num" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>TIER 1 (EXEC)</span>
              </div>
              <h3 style={{ fontSize: '20px', fontWeight: '800', color: 'var(--navy-900)', marginBottom: '8px' }}>
                Chief Financial Officer
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '20px' }}>
                Executive control over all financial modules. Authorizes ledger postings, seals accounting periods, configures bank credentials, and sets compliance rules.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '24px' }}>
                {['Approve & seal accounting period locks', 'Post journal proposals to General Ledger', 'Manage banking API tokens & institutional settings', 'Full access to confidential burn & runway telemetry'].map((item, idx) => (
                  <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '12px', color: 'var(--text-primary)' }}>
                    <CheckCircle2 size={15} color="var(--teal-600)" style={{ flexShrink: 0, marginTop: '1px' }} />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>

            <button
              onClick={() => onQuickRoleLogin('cfo')}
              className="btn-primary"
              style={{ width: '100%', padding: '10px', backgroundColor: 'var(--navy-900)', fontSize: '13px', justifyContent: 'center' }}
            >
              <span>Test as CFO (Alex Vance)</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 2: Senior Accountant */}
          <div
            className="panel"
            style={{
              padding: '30px',
              borderTop: '4px solid var(--teal-500)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between'
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <span className="badge badge-teal" style={{ fontSize: '11px' }}>Operational Lead</span>
                <span className="mono-num" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>TIER 2 (EDITOR)</span>
              </div>
              <h3 style={{ fontSize: '20px', fontWeight: '800', color: 'var(--navy-900)', marginBottom: '8px' }}>
                Senior Staff Accountant
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '20px' }}>
                Hands-on day-to-day operations. Classifies transactions, prepares reconciliation proposals, drafts invoices, and runs financial reports.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '24px' }}>
                {['Classify and batch accept transactions', 'Generate split-screen reconciliation proposals', 'Issue client invoices and dispatch reminders', 'Period close lock restricted to CFO approval'].map((item, idx) => (
                  <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '12px', color: 'var(--text-primary)' }}>
                    <CheckCircle2 size={15} color="var(--teal-600)" style={{ flexShrink: 0, marginTop: '1px' }} />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>

            <button
              onClick={() => onQuickRoleLogin('accountant')}
              className="btn-teal"
              style={{ width: '100%', padding: '10px', fontSize: '13px', justifyContent: 'center' }}
            >
              <span>Test as Accountant (Sarah Chen)</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 3: External Auditor */}
          <div
            className="panel"
            style={{
              padding: '30px',
              borderTop: '4px solid var(--alert-amber-badge)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between'
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <span className="badge badge-amber" style={{ fontSize: '11px' }}>Read-Only Inspection</span>
                <span className="mono-num" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>TIER 3 (AUDIT)</span>
              </div>
              <h3 style={{ fontSize: '20px', fontWeight: '800', color: 'var(--navy-900)', marginBottom: '8px' }}>
                Independent Auditor
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '20px' }}>
                Forensic non-repudiation view. Certified read-only access to immutable ledgers, journal balance proofs, and historical audit logs without edit risk.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '24px' }}>
                {['Full inspection of GAAP/IFRS trial balance', 'Review append-only audit trail logs', 'Inspect invoice documents & transaction matches', 'Zero write / delete capability to prevent tampering'].map((item, idx) => (
                  <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '12px', color: 'var(--text-primary)' }}>
                    <CheckCircle2 size={15} color="var(--alert-amber-badge)" style={{ flexShrink: 0, marginTop: '1px' }} />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>

            <button
              onClick={() => onQuickRoleLogin('auditor')}
              className="btn-secondary"
              style={{ width: '100%', padding: '10px', fontSize: '13px', justifyContent: 'center', borderColor: 'var(--alert-amber-badge)', color: 'var(--alert-amber-text)' }}
            >
              <span>Test as Auditor (Marcus Reed)</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </section>

      {/* 6 Core Capability Pillars */}
      <section id="features" style={{ padding: '80px 24px', maxWidth: '1200px', margin: '0 auto' }}>
        <div style={{ textAlign: 'center', marginBottom: '54px' }}>
          <h2 style={{ fontSize: '32px', fontWeight: '800', letterSpacing: '-0.02em', color: 'var(--navy-900)', marginBottom: '12px' }}>
            Built for precision, clarity, and institutional control.
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

      {/* Pricing / Deployment Options */}
      <section id="pricing" style={{ padding: '70px 24px', maxWidth: '1160px', margin: '0 auto', backgroundColor: '#FFFFFF', borderRadius: 'var(--radius-xl)', border: '1px solid var(--border-light)', marginBottom: '60px' }}>
        <div style={{ textAlign: 'center', marginBottom: '44px' }}>
          <span style={{ fontSize: '12px', fontWeight: '700', color: 'var(--teal-700)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Transparent Deployment
          </span>
          <h2 style={{ fontSize: '32px', fontWeight: '800', color: 'var(--navy-900)', marginTop: '6px' }}>
            Calibrated for Growing Enterprises
          </h2>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
          <div style={{ padding: '28px', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-light)', backgroundColor: 'var(--bg-canvas)' }}>
            <h4 style={{ fontSize: '18px', fontWeight: '800', color: 'var(--navy-900)' }}>Starter</h4>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '14px' }}>For early-stage startups</div>
            <div className="mono-num" style={{ fontSize: '32px', fontWeight: '800', color: 'var(--navy-900)' }}>₹14,999<span style={{ fontSize: '13px', fontWeight: '500', color: 'var(--text-muted)' }}>/mo</span></div>
            <ul style={{ listStyle: 'none', margin: '20px 0', display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
              <li>✓ Up to 3 bank accounts</li>
              <li>✓ Basic AI categorization</li>
              <li>✓ Standard P&L & Balance Sheet</li>
              <li>✓ 1 Admin Seat</li>
            </ul>
            <button onClick={onEnterApp} className="btn-secondary" style={{ width: '100%', justifyContent: 'center' }}>Launch Starter</button>
          </div>

          <div style={{ padding: '28px', borderRadius: 'var(--radius-lg)', border: '2px solid var(--teal-500)', backgroundColor: '#FFFFFF', boxShadow: 'var(--shadow-md)', position: 'relative' }}>
            <span style={{ position: 'absolute', top: '-11px', right: '20px', backgroundColor: 'var(--teal-500)', color: '#FFFFFF', fontSize: '10px', fontWeight: '800', padding: '2px 8px', borderRadius: '10px', textTransform: 'uppercase' }}>Most Popular</span>
            <h4 style={{ fontSize: '18px', fontWeight: '800', color: 'var(--navy-900)' }}>Growth Scale</h4>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '14px' }}>For high-velocity companies</div>
            <div className="mono-num" style={{ fontSize: '32px', fontWeight: '800', color: 'var(--teal-700)' }}>₹39,999<span style={{ fontSize: '13px', fontWeight: '500', color: 'var(--text-muted)' }}>/mo</span></div>
            <ul style={{ listStyle: 'none', margin: '20px 0', display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
              <li>✓ Unlimited bank & gateway connections</li>
              <li>✓ Real-time Split-Screen Reconciliation</li>
              <li>✓ Full 3-Tier RBAC (CFO + Accountants + Auditor)</li>
              <li>✓ Runway & Anomaly Intelligence</li>
            </ul>
            <button onClick={onEnterApp} className="btn-teal" style={{ width: '100%', justifyContent: 'center' }}>Launch Growth</button>
          </div>

          <div style={{ padding: '28px', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-light)', backgroundColor: 'var(--bg-canvas)' }}>
            <h4 style={{ fontSize: '18px', fontWeight: '800', color: 'var(--navy-900)' }}>Institutional</h4>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '14px' }}>For multi-entity holding orgs</div>
            <div className="mono-num" style={{ fontSize: '32px', fontWeight: '800', color: 'var(--navy-900)' }}>Custom</div>
            <ul style={{ listStyle: 'none', margin: '20px 0', display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
              <li>✓ Multi-entity consolidated reporting</li>
              <li>✓ Dedicated tenant cryptographic isolation</li>
              <li>✓ Custom external auditor guest portals</li>
              <li>✓ 24/7 dedicated finance engineering SLA</li>
            </ul>
            <button onClick={() => onOpenAuth('signup')} className="btn-secondary" style={{ width: '100%', justifyContent: 'center' }}>Contact Institutional Desk</button>
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
          © 2026 Ledger Ai Inc. All rights reserved. Precision financial operating systems.
        </div>
        <div style={{ display: 'flex', gap: '20px' }}>
          <span>SOC2 Type II Certified</span>
          <span>Double-Entry Append Only</span>
          <span>Role-Based Access Guard</span>
          <span>Zero Credential Retention</span>
        </div>
      </footer>
    </div>
  );
}
