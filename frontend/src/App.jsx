import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import DashboardView from './components/DashboardView';
import TransactionsView from './components/TransactionsView';
import AccountsView from './components/AccountsView';
import ReconciliationView from './components/ReconciliationView';
import ReportsView from './components/ReportsView';
import IntelligenceView from './components/IntelligenceView';
import InvoicesView from './components/InvoicesView';
import AiAgentPanel from './components/AiAgentPanel';
import LandingPageView from './components/LandingPageView';
import MobileNav from './components/MobileNav';

import {
  initialKpis,
  initialNeedsAttention,
  connectedAccounts,
  initialTransactions,
  reconciliationRecords,
  intelligenceInsights,
  sampleInvoices,
  financialStatements
} from './data/mockData';

export default function App() {
  const [viewMode, setViewMode] = useState('app'); // 'app' | 'landing'
  const [activeTab, setActiveTab] = useState('overview');
  const [currency, setCurrency] = useState('INR'); // 'INR' | 'USD'
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isAiOpen, setIsAiOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Core Financial State
  const [kpis, setKpis] = useState(initialKpis);
  const [needsAttention, setNeedsAttention] = useState(initialNeedsAttention);
  const [transactions, setTransactions] = useState(initialTransactions);
  const [accounts, setAccounts] = useState(connectedAccounts);
  const [reconciliationData, setReconciliationData] = useState(reconciliationRecords);
  const [invoices, setInvoices] = useState(sampleInvoices);

  // Global Keyboard Shortcut: Cmd/Ctrl + K opens AI Agent Panel
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsAiOpen((prev) => !prev);
      }
      if (e.key === 'Escape') {
        setIsAiOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // When clicking AI Agent in nav, open panel
  useEffect(() => {
    if (activeTab === 'ai-agent') {
      setIsAiOpen(true);
      setActiveTab('overview');
    }
  }, [activeTab]);

  const unresolvedNeedsAttentionCount = needsAttention.filter(i => !i.resolved).length;
  const uncategorizedTransactionsCount = transactions.filter(t => t.category === 'Uncategorized').length;

  // Render Marketing Landing Page if selected
  if (viewMode === 'landing') {
    return <LandingPageView onEnterApp={() => setViewMode('app')} />;
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--bg-canvas)', width: '100%', overflowX: 'hidden' }}>
      {/* Desktop Left Sidebar */}
      <div className="desktop-only">
        <Sidebar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          isCollapsed={isSidebarCollapsed}
          setIsCollapsed={setIsSidebarCollapsed}
          needsAttentionCount={unresolvedNeedsAttentionCount}
          uncategorizedCount={uncategorizedTransactionsCount}
        />
      </div>

      {/* Main Financial Workspace */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, paddingBottom: '64px' }}>
        <Header
          currency={currency}
          setCurrency={setCurrency}
          viewMode={viewMode}
          setViewMode={setViewMode}
          setIsAiOpen={setIsAiOpen}
          needsAttentionCount={unresolvedNeedsAttentionCount}
          onOpenNeedsAttention={() => setActiveTab('overview')}
          setIsMobileMenuOpen={setIsMobileMenuOpen}
        />

        {/* Tab Routed Content */}
        <main style={{ flex: 1 }}>
          {activeTab === 'overview' && (
            <DashboardView
              currency={currency}
              kpis={kpis}
              needsAttention={needsAttention}
              setNeedsAttention={setNeedsAttention}
              setActiveTab={setActiveTab}
              setIsAiOpen={setIsAiOpen}
              connectedAccounts={accounts}
            />
          )}

          {activeTab === 'transactions' && (
            <TransactionsView
              transactions={transactions}
              setTransactions={setTransactions}
              currency={currency}
            />
          )}

          {activeTab === 'accounts' && (
            <AccountsView
              connectedAccounts={accounts}
              currency={currency}
            />
          )}

          {activeTab === 'reconciliation' && (
            <ReconciliationView
              reconciliationData={reconciliationData}
              currency={currency}
            />
          )}

          {activeTab === 'reports' && (
            <ReportsView
              financialStatements={financialStatements}
              currency={currency}
            />
          )}

          {activeTab === 'intelligence' && (
            <IntelligenceView
              intelligenceInsights={intelligenceInsights}
            />
          )}

          {activeTab === 'invoices' && (
            <InvoicesView
              invoices={invoices}
              currency={currency}
            />
          )}

          {(activeTab === 'expenses' || activeTab === 'documents' || activeTab === 'integrations' || activeTab === 'team' || activeTab === 'settings') && (
            <div className="animate-fade-in" style={{ padding: '40px 28px', maxWidth: '800px' }}>
              <div className="panel" style={{ padding: '36px', textAlign: 'center' }}>
                <h2 style={{ fontSize: '18px', fontWeight: '800', color: 'var(--navy-900)', marginBottom: '8px' }}>
                  {activeTab.toUpperCase()} Workspace
                </h2>
                <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '20px' }}>
                  Active institutional controls configured for Acme Technologies.
                </p>
                <button onClick={() => setActiveTab('overview')} className="btn-secondary">
                  Return to Control Room Overview
                </button>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Persistent AI Agent Panel */}
      <AiAgentPanel
        isOpen={isAiOpen}
        onClose={() => setIsAiOpen(false)}
        setActiveTab={setActiveTab}
      />

      {/* Responsive Mobile Bottom Navigation */}
      <MobileNav
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        setIsAiOpen={setIsAiOpen}
        needsAttentionCount={unresolvedNeedsAttentionCount}
      />
    </div>
  );
}
