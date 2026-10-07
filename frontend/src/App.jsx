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
import HomePageView from './components/HomePageView';
import AuthModal from './components/AuthModal';
import AuthGuardModal from './components/AuthGuardModal';
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

import {
  DEMO_USERS,
  getStoredUser,
  setStoredUser
} from './data/authUsers';

import { Lock, ShieldAlert, CheckCircle2, UserCheck, X } from 'lucide-react';

export default function App() {
  const [viewMode, setViewMode] = useState('home'); // 'home' | 'app'
  const [activeTab, setActiveTab] = useState('overview');
  const [currency, setCurrency] = useState('INR'); // 'INR' | 'USD'
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isAiOpen, setIsAiOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Authentication & Authorization (RBAC) State
  const [currentUser, setCurrentUser] = useState(() => getStoredUser());
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState('signin'); // 'signin' | 'signup'
  const [isGuardModalOpen, setIsGuardModalOpen] = useState(false);
  const [guardDetails, setGuardDetails] = useState(null); // { actionName, requiredRole, reason }
  const [systemNotification, setSystemNotification] = useState(null);

  // Core Financial State
  const [kpis, setKpis] = useState(initialKpis);
  const [needsAttention, setNeedsAttention] = useState(initialNeedsAttention);
  const [transactions, setTransactions] = useState(initialTransactions);
  const [accounts, setAccounts] = useState(connectedAccounts);
  const [reconciliationData, setReconciliationData] = useState(reconciliationRecords);
  const [invoices, setInvoices] = useState(sampleInvoices);

  const showSystemNotification = (msg) => {
    setSystemNotification(msg);
    setTimeout(() => setSystemNotification(null), 4000);
  };

  // Switch role handler
  const handleSwitchRole = (roleKey) => {
    const targetUser = DEMO_USERS[roleKey];
    if (targetUser) {
      setCurrentUser(targetUser);
      setStoredUser(targetUser);
      showSystemNotification(`Switched role to ${targetUser.name} • ${targetUser.roleBadge}`);
    }
  };

  // Successful login
  const handleSuccessLogin = (user) => {
    setCurrentUser(user);
    setStoredUser(user);
    setViewMode('app');
    showSystemNotification(`Welcome back, ${user.name} (${user.roleBadge})`);
  };

  // Logout
  const handleLogout = () => {
    setCurrentUser(null);
    setStoredUser(null);
    setViewMode('home');
    showSystemNotification('Signed out of Ledger Ai workspace.');
  };

  // Institutional Authorization Guard
  const requirePermission = (permissionKey, actionName, requiredRole = 'cfo', reason) => {
    if (!currentUser) {
      setAuthModalMode('signin');
      setIsAuthModalOpen(true);
      return false;
    }

    if (currentUser.permissions && currentUser.permissions[permissionKey]) {
      return true;
    }

    // Permission denied: Trigger Institutional Auth Guard Modal
    setGuardDetails({
      actionName,
      requiredRole,
      reason: reason || `This operation requires elevated ${requiredRole.toUpperCase()} credentials. Your account is logged in as ${currentUser.roleTitle || currentUser.name}.`
    });
    setIsGuardModalOpen(true);
    return false;
  };

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

  return (
    <>
      {/* Toast Notification Banner */}
      {systemNotification && (
        <div
          className="animate-fade-in"
          style={{
            position: 'fixed',
            top: '20px',
            right: '24px',
            backgroundColor: 'var(--navy-900)',
            color: '#FFFFFF',
            padding: '12px 20px',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-panel)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            zIndex: 150,
            fontSize: '13px',
            border: '1px solid var(--teal-500)',
          }}
        >
          <CheckCircle2 size={18} color="var(--teal-400)" />
          <span style={{ fontWeight: '600' }}>{systemNotification}</span>
          <button
            onClick={() => setSystemNotification(null)}
            style={{ background: 'none', border: 'none', color: 'var(--text-light-muted)', cursor: 'pointer', marginLeft: '6px' }}
          >
            <X size={15} />
          </button>
        </div>
      )}

      {/* Render Public Home Page */}
      {viewMode === 'home' ? (
        <HomePageView
          onEnterApp={() => setViewMode('app')}
          onOpenAuth={(mode) => {
            setAuthModalMode(mode);
            setIsAuthModalOpen(true);
          }}
          currentUser={currentUser}
          onLogout={handleLogout}
          onQuickRoleLogin={(roleKey) => {
            handleSwitchRole(roleKey);
            setViewMode('app');
          }}
        />
      ) : (
        /* Render Authenticated Financial Workspace */
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
              onNavigateHome={() => setViewMode('home')}
              currentUser={currentUser}
              onSwitchRole={handleSwitchRole}
              onLogout={handleLogout}
            />
          </div>

          {/* Main Financial Workspace */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, paddingBottom: '64px' }}>
            {/* Auditor Read-Only Banner */}
            {currentUser?.permissions?.isReadOnly && (
              <div
                style={{
                  backgroundColor: '#FEF3C7',
                  borderBottom: '1px solid #FDE68A',
                  color: '#92400E',
                  padding: '8px 24px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '12px',
                  fontWeight: '600'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Lock size={14} color="#D97706" />
                  <span>
                    <strong>Auditor Inspection Mode:</strong> You are browsing as Marcus Reed (Independent Auditor) with read-only privileges. Ledger modifications and journal approvals are locked.
                  </span>
                </div>
                <button
                  onClick={() => handleSwitchRole('cfo')}
                  style={{
                    backgroundColor: '#FFFFFF',
                    border: '1px solid #D97706',
                    color: '#92400E',
                    padding: '3px 10px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    fontWeight: '700',
                    cursor: 'pointer'
                  }}
                >
                  Switch to CFO (Alex Vance)
                </button>
              </div>
            )}

            <Header
              currency={currency}
              setCurrency={setCurrency}
              viewMode={viewMode}
              setViewMode={setViewMode}
              setIsAiOpen={setIsAiOpen}
              needsAttentionCount={unresolvedNeedsAttentionCount}
              onOpenNeedsAttention={() => setActiveTab('overview')}
              setIsMobileMenuOpen={setIsMobileMenuOpen}
              currentUser={currentUser}
              onSwitchRole={handleSwitchRole}
              onOpenAuth={(mode) => {
                setAuthModalMode(mode);
                setIsAuthModalOpen(true);
              }}
              onLogout={handleLogout}
              onNavigateHome={() => setViewMode('home')}
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
                  currentUser={currentUser}
                  requirePermission={requirePermission}
                />
              )}

              {activeTab === 'transactions' && (
                <TransactionsView
                  transactions={transactions}
                  setTransactions={setTransactions}
                  currency={currency}
                  currentUser={currentUser}
                  requirePermission={requirePermission}
                />
              )}

              {activeTab === 'accounts' && (
                <AccountsView
                  connectedAccounts={accounts}
                  currency={currency}
                  currentUser={currentUser}
                  requirePermission={requirePermission}
                />
              )}

              {activeTab === 'reconciliation' && (
                <ReconciliationView
                  reconciliationData={reconciliationData}
                  currency={currency}
                  currentUser={currentUser}
                  requirePermission={requirePermission}
                />
              )}

              {activeTab === 'reports' && (
                <ReportsView
                  financialStatements={financialStatements}
                  currency={currency}
                  currentUser={currentUser}
                />
              )}

              {activeTab === 'intelligence' && (
                <IntelligenceView
                  intelligenceInsights={intelligenceInsights}
                  currentUser={currentUser}
                />
              )}

              {activeTab === 'invoices' && (
                <InvoicesView
                  invoices={invoices}
                  currency={currency}
                  currentUser={currentUser}
                  requirePermission={requirePermission}
                />
              )}

              {(activeTab === 'expenses' || activeTab === 'documents' || activeTab === 'integrations' || activeTab === 'team' || activeTab === 'settings') && (
                <div className="animate-fade-in" style={{ padding: '40px 28px', maxWidth: '800px' }}>
                  <div className="panel" style={{ padding: '36px', textAlign: 'center' }}>
                    <div style={{ display: 'inline-flex', padding: '12px', borderRadius: '50%', backgroundColor: 'var(--teal-50)', marginBottom: '14px' }}>
                      <ShieldAlert size={28} color="var(--teal-600)" />
                    </div>
                    <h2 style={{ fontSize: '18px', fontWeight: '800', color: 'var(--navy-900)', marginBottom: '8px' }}>
                      {activeTab.toUpperCase()} Workspace
                    </h2>
                    <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '12px' }}>
                      Active institutional controls configured for Acme Technologies Inc.
                    </p>
                    <div style={{ display: 'inline-block', padding: '6px 14px', borderRadius: '16px', backgroundColor: 'var(--bg-canvas)', border: '1px solid var(--border-light)', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '20px' }}>
                      Active Role: <strong>{currentUser?.roleTitle || 'User'}</strong> ({currentUser?.roleBadge || 'Admin'})
                    </div>
                    <div>
                      <button onClick={() => setActiveTab('overview')} className="btn-secondary">
                        Return to Control Room Overview
                      </button>
                    </div>
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
      )}

      {/* Authentication Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        initialMode={authModalMode}
        onSuccessLogin={handleSuccessLogin}
      />

      {/* Authorization Guard Modal */}
      <AuthGuardModal
        isOpen={isGuardModalOpen}
        onClose={() => setIsGuardModalOpen(false)}
        guardDetails={guardDetails}
        currentUser={currentUser}
        onSwitchRole={handleSwitchRole}
      />
    </>
  );
}
