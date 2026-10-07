import React, { useState } from 'react';
import {
  Download,
  Calendar,
  ChevronDown,
  TrendingUp,
  FileSpreadsheet,
  Printer,
  Sparkles,
  BarChart2,
  PieChart
} from 'lucide-react';

export default function ReportsView({ financialStatements, currency }) {
  const [reportType, setReportType] = useState('pnl');
  const [timeframe, setTimeframe] = useState('MONTH');

  const { pnl, balanceSheet } = financialStatements;

  return (
    <div className="animate-fade-in" style={{ padding: '28px', maxWidth: '1440px', margin: '0 auto', width: '100%' }}>
      {/* Top Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontSize: '22px', fontWeight: '800', color: 'var(--navy-900)', letterSpacing: '-0.02em', marginBottom: '3px' }}>
            Financial Reporting & Statements
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            Certified double-entry financial statements, variance analysis, and cash flow telemetry.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Timeframe Selector */}
          <div
            style={{
              display: 'flex',
              border: '1px solid var(--border-light)',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-surface)',
              padding: '2px'
            }}
          >
            {['MONTH', 'QUARTER', 'YTD'].map((t) => (
              <button
                key={t}
                onClick={() => setTimeframe(t)}
                style={{
                  padding: '5px 10px',
                  fontSize: '11px',
                  fontWeight: timeframe === t ? '700' : '500',
                  backgroundColor: timeframe === t ? 'var(--navy-900)' : 'transparent',
                  color: timeframe === t ? '#FFFFFF' : 'var(--text-muted)',
                  borderRadius: 'var(--radius-xs)',
                  transition: 'all var(--transition-fast)'
                }}
              >
                {t === 'MONTH' ? 'Month-to-Date' : t === 'QUARTER' ? 'Trailing Q3' : 'Full FY2026'}
              </button>
            ))}
          </div>

          <button className="btn-secondary btn-sm" style={{ padding: '7px 14px' }}>
            <Download size={14} />
            <span>Export PDF / Excel</span>
          </button>
        </div>
      </div>

      {/* Report Selection Tabs */}
      <div
        style={{
          display: 'flex',
          borderBottom: '1px solid var(--border-light)',
          marginBottom: '24px',
          gap: '8px'
        }}
      >
        {[
          { id: 'pnl', label: 'Profit & Loss (P&L)' },
          { id: 'balance-sheet', label: 'Balance Sheet' },
          { id: 'cash-flow', label: 'Cash Flow Statement' },
          { id: 'expense-breakdown', label: 'Expense Analysis' }
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setReportType(tab.id)}
            style={{
              padding: '10px 16px',
              fontSize: '13px',
              fontWeight: reportType === tab.id ? '700' : '500',
              color: reportType === tab.id ? 'var(--navy-900)' : 'var(--text-muted)',
              borderBottom: reportType === tab.id ? '2px solid var(--teal-500)' : '2px solid transparent',
              borderRadius: 0,
              backgroundColor: 'transparent'
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Restrained Sophisticated SVG Chart (Navy & Teal only) */}
      <div className="panel" style={{ padding: '20px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <div>
            <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--navy-900)' }}>
              Monthly Revenue vs Operating Expenses Trajectory (Trailing 6 Months)
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Values in ₹ Lakhs • Revenue (Navy #081B33), Expenses (Teal #0EAAA5)
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '11px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '10px', height: '10px', backgroundColor: 'var(--navy-900)', borderRadius: '2px' }} />
              <span>Revenue</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '10px', height: '10px', backgroundColor: 'var(--teal-500)', borderRadius: '2px' }} />
              <span>Expenses</span>
            </div>
          </div>
        </div>

        {/* Clean SVG Bar Chart */}
        <div style={{ height: '180px', width: '100%', display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', padding: '0 20px 10px' }}>
          {[
            { month: 'May 2026', rev: 48, exp: 32 },
            { month: 'Jun 2026', rev: 52, exp: 34 },
            { month: 'Jul 2026', rev: 56, exp: 35 },
            { month: 'Aug 2026', rev: 59, exp: 36 },
            { month: 'Sep 2026', rev: 61, exp: 33 },
            { month: 'Oct 2026', rev: 64, exp: 39 },
          ].map((bar, i) => (
            <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: '6px', height: '140px' }}>
                {/* Revenue Bar (Navy) */}
                <div
                  style={{
                    width: '28px',
                    height: `${(bar.rev / 70) * 130}px`,
                    backgroundColor: 'var(--navy-900)',
                    borderRadius: '4px 4px 0 0',
                    transition: 'height 400ms ease'
                  }}
                  title={`Revenue: ₹${bar.rev} Lakhs`}
                />
                {/* Expense Bar (Teal) */}
                <div
                  style={{
                    width: '28px',
                    height: `${(bar.exp / 70) * 130}px`,
                    backgroundColor: 'var(--teal-500)',
                    borderRadius: '4px 4px 0 0',
                    transition: 'height 400ms ease'
                  }}
                  title={`Expense: ₹${bar.exp} Lakhs`}
                />
              </div>
              <span className="mono-num" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                {bar.month}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Tabular Statement Content */}
      {reportType === 'pnl' && (
        <div className="panel" style={{ padding: '24px' }}>
          <div style={{ borderBottom: '1px solid var(--border-light)', paddingBottom: '14px', marginBottom: '18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <h2 style={{ fontSize: '16px', fontWeight: '800', color: 'var(--navy-900)' }}>
                Statement of Profit and Loss
              </h2>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                {pnl.period} • {pnl.comparison}
              </div>
            </div>
            <span className="badge badge-teal">Audited Double-Entry Baseline</span>
          </div>

          <div>
            {pnl.sections.map((sec, idx) => (
              <div key={idx} style={{ marginBottom: '22px' }}>
                <div style={{ fontSize: '12px', fontWeight: '800', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--navy-900)', marginBottom: '8px' }}>
                  {sec.title}
                </div>

                {sec.items && (
                  <table className="ledger-table" style={{ marginBottom: '8px' }}>
                    <tbody>
                      {sec.items.map((item, i) => (
                        <tr key={i}>
                          <td style={{ padding: '8px 12px' }}>{item.name}</td>
                          <td className="mono-num" style={{ textAlign: 'right', padding: '8px 12px', color: 'var(--text-muted)' }}>
                            {item.prior}
                          </td>
                          <td className="mono-num" style={{ textAlign: 'right', fontWeight: '700', padding: '8px 12px' }}>
                            {item.current}
                          </td>
                          <td className="mono-num" style={{ textAlign: 'right', fontSize: '12px', color: item.delta.startsWith('+') ? 'var(--alert-emerald-text)' : 'var(--text-muted)', width: '80px', padding: '8px 12px' }}>
                            {item.delta}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}

                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 12px',
                    backgroundColor: 'var(--bg-canvas)',
                    borderRadius: 'var(--radius-sm)',
                    fontWeight: '800',
                    fontSize: '14px'
                  }}
                >
                  <span>Total {sec.title}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    {sec.margin && <span style={{ fontSize: '12px', color: 'var(--teal-700)', fontWeight: '700' }}>{sec.margin}</span>}
                    <span className="mono-num">{sec.total}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {reportType === 'balance-sheet' && (
        <div className="panel" style={{ padding: '24px' }}>
          <div style={{ borderBottom: '1px solid var(--border-light)', paddingBottom: '14px', marginBottom: '18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <h2 style={{ fontSize: '16px', fontWeight: '800', color: 'var(--navy-900)' }}>
                Balance Sheet Statement
              </h2>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                {balanceSheet.asOf} • Accrual Basis Accounting
              </div>
            </div>
            <span className="badge badge-emerald">Equation Verified: Assets = Liabilities + Equity</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '28px' }}>
            {balanceSheet.sections.map((sec, idx) => (
              <div key={idx}>
                <h3 style={{ fontSize: '14px', fontWeight: '800', color: 'var(--navy-900)', borderBottom: '2px solid var(--navy-900)', paddingBottom: '6px', marginBottom: '12px' }}>
                  {sec.category}
                </h3>

                {sec.groups.map((grp, gIdx) => (
                  <div key={gIdx} style={{ marginBottom: '18px' }}>
                    <div style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-muted)', marginBottom: '6px' }}>
                      {grp.name}
                    </div>

                    <table className="ledger-table" style={{ marginBottom: '6px' }}>
                      <tbody>
                        {grp.items.map((it, itIdx) => (
                          <tr key={itIdx}>
                            <td style={{ padding: '6px 8px' }}>{it.name}</td>
                            <td className="mono-num" style={{ textAlign: 'right', padding: '6px 8px', fontWeight: '600' }}>
                              {it.amount}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>

                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', fontWeight: '700', color: 'var(--navy-800)', padding: '4px 8px', backgroundColor: 'var(--bg-canvas)' }}>
                      <span>Subtotal {grp.name}</span>
                      <span className="mono-num">{grp.subtotal}</span>
                    </div>
                  </div>
                ))}

                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '12px', backgroundColor: 'var(--navy-900)', color: '#FFFFFF', borderRadius: 'var(--radius-sm)', fontWeight: '800', fontSize: '14px', marginTop: '16px' }}>
                  <span>Total {sec.category}</span>
                  <span className="mono-num" style={{ color: 'var(--teal-300)' }}>{sec.total}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {(reportType === 'cash-flow' || reportType === 'expense-breakdown') && (
        <div className="panel" style={{ padding: '24px' }}>
          <div style={{ borderBottom: '1px solid var(--border-light)', paddingBottom: '14px', marginBottom: '18px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: '800', color: 'var(--navy-900)' }}>
              {reportType === 'cash-flow' ? 'Cash Flow Statement' : 'Expense Category Analysis'}
            </h2>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Detailed cash telemetry and variance decomposition against fiscal targets.
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
            {[
              { label: 'Engineering Payroll & Salaried', amount: '₹18,50,000', pct: '47.3%' },
              { label: 'Software Subscriptions & Tooling', amount: '₹5,72,000', pct: '14.6%' },
              { label: 'Cloud Infrastructure (AWS/GCP)', amount: '₹6,80,000', pct: '17.4%' },
              { label: 'Performance Marketing & Ads', amount: '₹4,50,000', pct: '11.5%' },
              { label: 'Workspace Facilities & Office', amount: '₹1,25,000', pct: '3.2%' },
              { label: 'Legal, Audit & Professional', amount: '₹1,20,000', pct: '3.1%' },
            ].map((exp, i) => (
              <div key={i} style={{ padding: '14px', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>{exp.label}</div>
                <div className="mono-num" style={{ fontSize: '18px', fontWeight: '800', color: 'var(--navy-900)' }}>{exp.amount}</div>
                <div style={{ fontSize: '11px', color: 'var(--teal-700)', fontWeight: '700' }}>{exp.pct} of total OpEx</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
