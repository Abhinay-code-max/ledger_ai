import { useState, useEffect } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  Activity,
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronRight,
  Eye,
  FileCheck2,
  FileSpreadsheet,
  FileText,
  FolderCheck,
  GitCompare,
  LayoutDashboard,
  Layers,
  LockKeyhole,
  Scale,
  ShieldCheck,
  Users,
} from 'lucide-react'
import Brand from '../components/Brand'
import { WorkspaceHeader } from '../components/workspace/WorkspaceHeader'
import { DocumentWorkflow } from '../components/workspace/DocumentWorkflow'
import { BankCsvWorkflow } from '../components/workspace/BankCsvWorkflow'
import { ReconciliationWorkflow } from '../components/workspace/ReconciliationWorkflow'
import { ReviewQueueWorkflow } from '../components/workspace/ReviewQueueWorkflow'
import { AccountingAndPostingWorkflow } from '../components/workspace/AccountingAndPostingWorkflow'
import { FinancialStatementsWorkflow } from '../components/workspace/FinancialStatementsWorkflow'
import { AuditAndProvenanceWorkflow } from '../components/workspace/AuditAndProvenanceWorkflow'
import { useAuth } from '../context/AuthContext'
import type {
  AccountingPeriodResponse,
  DocumentResponse,
  DocumentVersionResponse,
} from '../types/api'
import './workspaces.css'

type Role = 'admin' | 'manager' | 'employee'
type RecordItem = {
  id: string
  name: string
  company: string
  amount: string
  status: string
  type: string
  date: string
  owner: string
}

const roleNames: Record<Role, string> = {
  admin: 'Admin',
  manager: 'Manager',
  employee: 'Employee',
}

const fullRoleNames: Record<Role, string> = {
  admin: 'Administrator',
  manager: 'Finance Manager',
  employee: 'Finance Employee',
}

const roleDetails = {
  admin: {
    subtitle: 'THE BIG PICTURE',
    title: 'A clear view. Complete control.',
    description: 'Oversee your people, permissions, and financial operations from one central workspace.',
    icon: ShieldCheck,
    features: ['User & role management', 'Processing oversight', 'Audit trails & governance'],
  },
  manager: {
    subtitle: 'THE FINANCIAL WORKFLOW',
    title: 'Keep every close moving.',
    description: 'Guide your team from incoming documents to reviewed records and a confident close.',
    icon: FolderCheck,
    features: ['Review & approval queues', 'Reconciliation oversight', 'Team tasks & closing workflows'],
  },
  employee: {
    subtitle: 'THE EVERYDAY WORK',
    title: 'Less busywork. More progress.',
    description: 'Bring documents in, review extracted details, and move your assigned work forward.',
    icon: FileText,
    features: ['Document uploads', 'Extracted data review', 'Personal tasks & progress'],
  },
}

const validRole = (value: string | undefined): value is Role =>
  value === 'admin' || value === 'manager' || value === 'employee'

function TopPublicHeader() {
  return (
    <header className="ws-header">
      <Link to="/" aria-label="ledgar.ai home">
        <Brand />
      </Link>
      <Link to="/" className="ws-back">
        <ArrowLeft size={14} /> Back to website
      </Link>
    </header>
  )
}

export function RoleSelection() {
  return (
    <div className="workspace-entry">
      <TopPublicHeader />
      <main className="ws-selection">
        <div className="ws-entry-tag">
          <span /> A WORKSPACE FOR EVERY ROLE
        </div>
        <h1>
          Choose your ledgar.ai
          <br />
          <span>workspace.</span>
        </h1>
        <p className="ws-entry-description">
          The right tools. The right access. One connected financial workflow. <br />
          Select your role to continue to your secure workspace.
        </p>
        <div className="ws-role-grid">
          {(Object.keys(roleNames) as Role[]).map((role, index) => {
            const detail = roleDetails[role]
            const Icon = detail.icon
            return (
              <article className={`ws-role-card ws-role-${role}`} key={role}>
                <div className="ws-card-heading">
                  <span>0{index + 1}</span>
                  <Icon size={35} strokeWidth={1.3} />
                </div>
                <small>{detail.subtitle}</small>
                <h2>{fullRoleNames[role]}</h2>
                <p>{detail.description}</p>
                <ul>
                  {detail.features.map((feature) => (
                    <li key={feature}>
                      <Check size={13} />
                      {feature}
                    </li>
                  ))}
                </ul>
                <Link to={`/login/${role}`} className="ws-role-enter">
                  Enter {roleNames[role]} workspace <ArrowUpRight size={18} />
                </Link>
                <Link to={`/demo/${role}`} className="ws-demo-link">
                  Explore {roleNames[role].toLowerCase()} demo <ArrowRight size={12} />
                </Link>
              </article>
            )
          })}
        </div>
        <div className="ws-security-note">
          <LockKeyhole size={14} />
          <span>
            Secure access is verified by your organization. Role selection does not grant permissions.
          </span>
        </div>
      </main>
      <footer className="ws-entry-footer">
        <span>© {new Date().getFullYear()} ledgar.ai</span>
        <span>CLARITY AT EVERY LEVEL.</span>
        <Link to="/">
          Financial intelligence, connected <ArrowUpRight size={12} />
        </Link>
      </footer>
    </div>
  )
}

export function RoleLogin() {
  const { role: rawRole } = useParams()
  const role: Role = validRole(rawRole) ? rawRole : 'employee'
  const navigate = useNavigate()
  const { login } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [token, setToken] = useState('')
  const [workspaceCode, setWorkspaceCode] = useState('nova')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!validRole(rawRole)) return <RoleSelection />
  const detail = roleDetails[role]
  const Icon = detail.icon

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')

    // If a bearer token is provided, verify directly with Role 4
    if (token.trim()) {
      setBusy(true)
      try {
        await login(token.trim(), workspaceCode.trim() || 'nova')
        navigate(`/dashboard/${role}`)
      } catch (cause) {
        setError(
          cause instanceof Error
            ? cause.message
            : 'Unable to verify session with Role 4 backend. Check network and credentials.',
        )
      } finally {
        setBusy(false)
      }
      return
    }

    // Work email / password submitted without configured enterprise identity provider
    setError('Secure sign-in is not connected for this workspace. Use your bearer token or explore the separate demo below.')
  }

  return (
    <div className="workspace-entry">
      <TopPublicHeader />
      <main className="ws-login-layout">
        <section className="ws-login-story">
          <div className="ws-entry-tag">
            <span /> {roleNames[role].toUpperCase()} WORKSPACE
          </div>
          <div className="ws-login-emblem">
            <Icon size={68} strokeWidth={1} />
            <i />
            <i />
            <i />
          </div>
          <h1>{detail.title}</h1>
          <p>{detail.description}</p>
          <div className="ws-login-benefits">
            {detail.features.map((feature) => (
              <span key={feature}>
                <CheckCircle2 size={15} />
                {feature}
              </span>
            ))}
          </div>
          <div className="ws-login-coordinate">
            LEDGAR.AI <span>HUMAN JUDGMENT. CONNECTED INTELLIGENCE.</span>
          </div>
        </section>

        <section className="ws-login-form">
          <Link to="/login" className="ws-back">
            <ArrowLeft size={13} /> Change workspace
          </Link>
          <small className="ws-overline">CONNECTED TO ROLE 4 PUBLIC API</small>
          <h2>Sign in as {roleNames[role]}</h2>
          <p>Provide your authenticated token or enterprise credentials.</p>

          <form onSubmit={submit}>
            <label htmlFor="ws-email">Work email</label>
            <input
              id="ws-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              placeholder="you@company.com"
              required={!token}
            />

            <label htmlFor="ws-password">Password</label>
            <input
              id="ws-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              placeholder="Enter your password"
              required={!token}
            />

            <label htmlFor="ws-token">Bearer Access Token (Role 4)</label>
            <input
              id="ws-token"
              type="text"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              autoComplete="off"
              placeholder="Enter your Bearer token or JWT"
            />

            <label htmlFor="ws-code">Workspace Code</label>
            <input
              id="ws-code"
              type="text"
              value={workspaceCode}
              onChange={(e) => setWorkspaceCode(e.target.value)}
              placeholder="nova"
            />

            <div className="ws-form-help">
              <LockKeyhole size={12} /> Your organization verifies your identity and role via Role 4.
            </div>

            {error && (
              <div className="ws-form-error" role="alert">
                <AlertCircle size={17} />
                <span>{error}</span>
              </div>
            )}

            <button className="button primary ws-submit" disabled={busy} type="submit">
              {busy ? 'Verifying your access…' : 'Sign in to workspace'}
              <ArrowRight size={16} />
            </button>
          </form>

          <div className="ws-demo-divider">
            <span /> PREVIEW WORKSPACE <span />
          </div>
          <Link to={`/demo/${role}`} className="ws-preview-button">
            <Eye size={15} /> Explore isolated browser-only demo <ArrowUpRight size={16} />
          </Link>
        </section>
      </main>
    </div>
  )
}

const seedRecords: RecordItem[] = [
  {
    id: 'DOC-1024',
    name: 'Invoice_October.pdf',
    company: 'Northstar Studios',
    amount: '₹48,500.00',
    status: 'Needs review',
    type: 'Invoice',
    date: 'Oct 16, 2026',
    owner: 'Priya Sharma',
  },
  {
    id: 'DOC-1023',
    name: 'Vendor_statement.pdf',
    company: 'Vertex Supplies',
    amount: '₹1,24,000.00',
    status: 'Ready to approve',
    type: 'Statement',
    date: 'Oct 15, 2026',
    owner: 'Arjun Mehta',
  },
  {
    id: 'DOC-1022',
    name: 'Travel_receipts.pdf',
    company: 'Team expenses',
    amount: '₹12,750.00',
    status: 'Reviewed',
    type: 'Expense',
    date: 'Oct 15, 2026',
    owner: 'Priya Sharma',
  },
  {
    id: 'DOC-1021',
    name: 'Office_invoice.pdf',
    company: 'Forma Workspace',
    amount: '₹32,400.00',
    status: 'Needs review',
    type: 'Invoice',
    date: 'Oct 14, 2026',
    owner: 'Riya Kapoor',
  },
]

type ConnectedTab =
  | 'documents'
  | 'transactions'
  | 'reconciliation'
  | 'reviews'
  | 'posting'
  | 'statements'
  | 'audit'

export function Dashboard({ demo = false }: { demo?: boolean }) {
  const { role: rawRole } = useParams()
  const role: Role = validRole(rawRole) ? rawRole : 'employee'
  const { token, principal, isLoading: isAuthLoading } = useAuth()

  // Connected full-stack cross-component state
  const [connectedTab, setConnectedTab] = useState<ConnectedTab>('documents')
  const [selectedDoc, setSelectedDoc] = useState<DocumentResponse | null>(null)
  const [selectedVersion, setSelectedVersion] = useState<DocumentVersionResponse | null>(null)
  const [selectedTxIds, setSelectedTxIds] = useState<string[]>([])
  const [approvedProposalId, setApprovedProposalId] = useState<string | null>(null)
  const [currentPeriod, setCurrentPeriod] = useState<AccountingPeriodResponse | null>(null)
  const [traceTarget, setTraceTarget] = useState<{ type: string; id: string } | null>(null)

  // Demo fallback states
  const [records] = useState<RecordItem[]>(seedRecords)
  const [demoTab, setDemoTab] = useState('Overview')

  if (!validRole(rawRole)) return <RoleSelection />

  // If not in demo mode and not authenticated, present login gate
  if (!demo && !isAuthLoading && (!token || !principal)) {
    return (
      <div className="workspace-entry">
        <TopPublicHeader />
        <main className="ws-auth-wall">
          <LockKeyhole size={43} />
          <h1>Your workspace is protected.</h1>
          <p>
            An authenticated session with Role 4 backend is required to access live financial data.
          </p>
          <div style={{ display: 'flex', gap: '12px' }}>
            <Link to={`/login/${role}`} className="button primary">
              Go to secure sign-in <ArrowRight size={16} />
            </Link>
            <Link to={`/demo/${role}`} className="button secondary">
              Explore Browser-Only Demo <ArrowRight size={14} />
            </Link>
          </div>
        </main>
      </div>
    )
  }

  // --- CONNECTED FULL-STACK WORKSPACE ---
  if (!demo) {
    return (
      <div className="ws-dashboard" style={{ flexDirection: 'column' }}>
        <WorkspaceHeader />

        {/* Full-Stack Tab Navigation */}
        <div className="ws-main-shell" style={{ margin: 0, width: '100%' }}>
          <div
            style={{
              background: '#0a2333',
              borderBottom: '1px solid #1c3e53',
              padding: '10px 28px 0',
              display: 'flex',
              gap: '6px',
              overflowX: 'auto',
            }}
          >
            {[
              { id: 'documents', label: '1. Documents & Ingestion', icon: FileText },
              { id: 'transactions', label: '2. Bank Statements & CSV', icon: FileSpreadsheet },
              { id: 'reconciliation', label: '3. Reconciliation & Exceptions', icon: GitCompare },
              { id: 'reviews', label: '4. Review Queue & Approvals', icon: Scale },
              { id: 'posting', label: '5. Ledger Posting & Periods', icon: Layers },
              { id: 'statements', label: '6. Financial Statements', icon: BookOpen },
              { id: 'audit', label: '7. Audit Log & Provenance', icon: Activity },
            ].map((tab) => {
              const Icon = tab.icon
              const isActive = connectedTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setConnectedTab(tab.id as ConnectedTab)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '11px 16px',
                    border: '1px solid transparent',
                    borderBottom: 'none',
                    borderTopLeftRadius: '6px',
                    borderTopRightRadius: '6px',
                    background: isActive ? '#f5f7f7' : 'transparent',
                    color: isActive ? '#143841' : '#8fa8b7',
                    fontWeight: isActive ? 600 : 400,
                    fontSize: '11px',
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                  }}
                >
                  <Icon size={14} />
                  <span>{tab.label}</span>
                </button>
              )
            })}
          </div>

          <main className="ws-dashboard-content" style={{ padding: '24px 28px 40px' }}>
            {connectedTab === 'documents' && (
              <DocumentWorkflow
                selectedDocId={selectedDoc?.id}
                onDocumentSelected={(doc, ver) => {
                  setSelectedDoc(doc)
                  setSelectedVersion(ver)
                }}
              />
            )}

            {connectedTab === 'transactions' && (
              <BankCsvWorkflow
                onSelectedTransactionsChange={(txIds) => {
                  setSelectedTxIds(txIds)
                }}
              />
            )}

            {connectedTab === 'reconciliation' && (
              <ReconciliationWorkflow
                selectedDoc={selectedDoc}
                selectedVersion={selectedVersion}
                selectedTxIds={selectedTxIds}
                onWorkflowCompleted={(res) => {
                  if (res.journal_proposal_id) {
                    setApprovedProposalId(res.journal_proposal_id)
                  }
                }}
              />
            )}

            {connectedTab === 'reviews' && (
              <ReviewQueueWorkflow
                onProposalApproved={(propId) => {
                  setApprovedProposalId(propId)
                }}
              />
            )}

            {connectedTab === 'posting' && (
              <AccountingAndPostingWorkflow
                approvedProposalId={approvedProposalId}
                onPeriodClosed={(period) => {
                  setCurrentPeriod(period)
                }}
              />
            )}

            {connectedTab === 'statements' && (
              <FinancialStatementsWorkflow
                currentPeriod={currentPeriod}
                onTraceLineSelected={(statementLineId) => {
                  setTraceTarget({ type: 'statement_line', id: statementLineId })
                  setConnectedTab('audit')
                }}
              />
            )}

            {connectedTab === 'audit' && (
              <AuditAndProvenanceWorkflow initialTraceTarget={traceTarget} />
            )}
          </main>
        </div>
      </div>
    )
  }

  // --- BROWSER-ONLY ISOLATED DEMO VIEW ---
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<RecordItem | null>(null)
  const [toast, setToast] = useState<string>('')

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSelected(null)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  useEffect(() => {
    if (!toast) return
    const timeout = setTimeout(() => setToast(''), 4000)
    return () => clearTimeout(timeout)
  }, [toast])

  const tabs = [
    { name: 'Overview', icon: LayoutDashboard },
    { name: 'AMD benchmarks', icon: Activity },
    ...(role === 'admin'
      ? [
          { name: 'Users & roles', icon: Users },
          { name: 'Audit trail', icon: ShieldCheck },
        ]
      : role === 'manager'
      ? [
          { name: 'Approvals', icon: FileCheck2 },
          { name: 'Close tasks', icon: FolderCheck },
        ]
      : [
          { name: 'My documents', icon: FileText },
          { name: 'My tasks', icon: FolderCheck },
        ]),
  ]

  const filteredRecords = records.filter(
    (r) =>
      r.name.toLowerCase().includes(search.toLowerCase()) ||
      r.company.toLowerCase().includes(search.toLowerCase()),
  )

  return (
    <div className="ws-dashboard">
      <aside className="ws-sidebar">
        <Link to="/">
          <Brand />
        </Link>
        <div className="ws-org-switch">
          <span className="ws-org-icon">N</span>
          <div>
            Northstar Finance<small>Demo Sandbox</small>
          </div>
        </div>
        <nav style={{ marginTop: '20px' }}>
          {tabs.map((item) => (
            <button
              key={item.name}
              className={demoTab === item.name ? 'active' : ''}
              onClick={() => setDemoTab(item.name)}
            >
              <item.icon size={17} />
              {item.name}
            </button>
          ))}
        </nav>
        <div style={{ marginTop: 'auto', paddingBottom: '20px' }}>
          <Link to={`/login/${role}`} className="ws-switch-role">
            <LockKeyhole size={15} /> Switch to Live Role 4 Workspace
          </Link>
        </div>
      </aside>

      <div className="ws-main-shell">
        <header className="ws-dashboard-header">
          <div className="ws-breadcrumb">
            Demo Sandbox <ChevronRight size={12} />
            <span>{demoTab}</span>
          </div>
          <span className="ws-demo-pill">DEMO WORKSPACE</span>
        </header>

        <main className="ws-dashboard-content">
          <div className="ws-page-title">
            <div>
              <div className="ws-overline">SIMULATED FINANCIAL WORKSPACE</div>
              <h1>Interactive Preview</h1>
              <p>Explore workflow features with illustrative data. No live backend connected.</p>
            </div>
            <Link to={`/login/${role}`} className="button primary">
              Open Live Stack <ArrowRight size={14} />
            </Link>
          </div>

          <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <label htmlFor="ws-file-upload" className="button secondary">
              Upload document
            </label>
            <input
              id="ws-file-upload"
              type="file"
              aria-label="Upload document"
              className="sr-only"
              style={{ display: 'none' }}
              onChange={() => {}}
            />
          </div>

          {demoTab === 'AMD benchmarks' ? (
            <div className="ws-panel" style={{ padding: '24px' }}>
              <h3>No verified measurements supplied</h3>
              <p>A benchmark needs the hardware model, runtime, dataset, and batch configuration to be verifiable.</p>
            </div>
          ) : (
            <div className="ws-panel">
              <div className="ws-panel-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3>Sample Documents</h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <label htmlFor="ws-search" style={{ fontSize: '12px' }}>Search documents</label>
                  <input
                    id="ws-search"
                    aria-label="Search documents"
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search documents…"
                    style={{ fontSize: '12px', padding: '4px 8px', borderRadius: '4px', border: '1px solid #334155', background: '#0f172a', color: '#fff' }}
                  />
                </div>
              </div>

              {filteredRecords.length === 0 ? (
                <div style={{ padding: '32px', textAlign: 'center' }}>
                  <p style={{ marginBottom: '12px', color: '#94a3b8' }}>No matching documents</p>
                  <button className="button secondary" onClick={() => setSearch('')}>
                    Clear filters
                  </button>
                </div>
              ) : (
                <div className="ws-table-overflow">
                  <table className="ws-record-table">
                    <thead>
                      <tr>
                        <th>DOCUMENT</th>
                        <th>AMOUNT</th>
                        <th>STATUS</th>
                        <th>ACTION</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredRecords.map((r) => (
                        <tr key={r.id}>
                          <td>
                            <strong>{r.name}</strong> ({r.company})
                          </td>
                          <td>{r.amount}</td>
                          <td>
                            <span className="ws-badge success">{r.status}</span>
                          </td>
                          <td>
                            <button
                              type="button"
                              aria-label={`Review ${r.name}`}
                              onClick={() => setSelected(r)}
                              className="button secondary small"
                              style={{ fontSize: '11px', padding: '4px 8px' }}
                            >
                              Review
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {selected && (
            <div
              role="dialog"
              aria-modal="true"
              aria-label="Document review"
              style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: 'rgba(0,0,0,0.6)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 9999,
              }}
            >
              <div style={{ background: '#1e293b', color: '#f8fafc', padding: '24px', borderRadius: '8px', maxWidth: '480px', width: '90%', border: '1px solid #334155' }}>
                <h2 style={{ fontSize: '18px', marginBottom: '8px' }}>Document review: {selected.name}</h2>
                <p style={{ color: '#94a3b8', fontSize: '13px', marginBottom: '20px' }}>
                  Company: {selected.company} | Amount: {selected.amount}
                </p>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    className="button primary"
                    onClick={() => {
                      setSelected(null)
                      setToast('Demo approval recorded after your review')
                    }}
                  >
                    Record demo approval
                  </button>
                  <button
                    type="button"
                    aria-label="Close document review"
                    className="button secondary"
                    onClick={() => setSelected(null)}
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          )}

          {toast && (
            <div
              role="status"
              aria-live="polite"
              style={{
                position: 'fixed',
                bottom: '24px',
                right: '24px',
                background: '#059669',
                color: '#fff',
                padding: '12px 20px',
                borderRadius: '6px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                zIndex: 10000,
                fontSize: '13px',
              }}
            >
              {toast}
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

export default function WorkspacePages({
  page,
}: {
  page: 'selection' | 'login' | 'dashboard' | 'demo'
}) {
  if (page === 'selection') return <RoleSelection />
  if (page === 'login') return <RoleLogin />
  return <Dashboard demo={page === 'demo'} />
}
