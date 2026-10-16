import { Component, lazy, Suspense, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { ArrowDown, ArrowDownRight, ArrowRight, ArrowUpRight, AudioLines, BookOpen, Check, CheckCheck, ChevronRight, CircleHelp, Command, Database, FileCheck2, FileText, Fingerprint, GitBranch, Layers3, LockKeyhole, Menu, Network, Play, ScanLine, ShieldCheck, UserRound, UsersRound, Waypoints, X } from 'lucide-react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import Brand from '../components/Brand'
import Workflow from '../components/Workflow'

gsap.registerPlugin(ScrollTrigger)
const IntelligenceScene = lazy(() => import('../components/IntelligenceScene'))

class SceneBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? <CoreFallback /> : this.props.children }
}

function CoreFallback() {
  return <div className="core-fallback" role="img" aria-label="LedgerAI intelligence engine with connected orbital data rings"><div /><div /><div /><span><Network size={58} /></span></div>
}

function Intro({ done }: { done: () => void }) {
  const reduced = useReducedMotion()
  useEffect(() => {
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const timer = window.setTimeout(done, reduced ? 350 : 3600)
    return () => { clearTimeout(timer); document.body.style.overflow = previous }
  }, [done, reduced])
  return <motion.div className="intro" initial={{ opacity: 1 }} exit={{ opacity: 0, transition: { duration: .45 } }} role="dialog" aria-label="Welcome to LedgerAI" aria-modal="true">
    <div className="intro-grid" />
    <svg className="intro-circuits" viewBox="0 0 1000 600" fill="none" aria-hidden="true"><path d="M210 180h110l60 60h55M790 180H680l-60 60h-55M210 420h110l60-60h55M790 420H680l-60-60h-55" stroke="currentColor" />{[[210, 180], [790, 180], [210, 420], [790, 420], [325, 300], [675, 300], [500, 130], [500, 470]].map(([cx, cy], i) => <circle key={i} cx={cx} cy={cy} r={i % 2 ? 2 : 3} fill="currentColor" style={{ animationDelay: `${.3 + i * .12}s` }} />)}</svg>
    <motion.div className="intro-identity" initial={{ opacity: 0, scale: .85 }} animate={reduced ? { opacity: 1 } : { opacity: [0, 1, 1, 0], scale: [.85, 1, 1, 13] }} transition={{ duration: 3.6, times: [0, .24, .72, 1], ease: [.7, 0, .2, 1] }}><div className="intro-ring" /><Brand /><span className="intro-caption">INTELLIGENCE, CONNECTED.</span></motion.div>
    <button className="intro-skip" autoFocus onClick={done}>Skip intro <ArrowRight size={15} /></button>
    <div className="intro-bottom"><span>FINANCE INTELLIGENCE / V.02</span><div className="intro-progress"><i /></div><span>INITIALIZING EXPERIENCE</span></div>
  </motion.div>
}

function Navigation() {
  const [open, setOpen] = useState(false)
  return <header className="site-header"><a href="#main" className="skip-link">Skip to content</a><div className="nav-shell"><div className="nav-brand-group"><Link to="/" aria-label="LedgerAI home"><Brand /></Link><span className="nav-divider" /><Link className="nav-login" to="/login">Log in <ArrowUpRight size={12} /></Link></div><nav className={open ? 'nav-links is-open' : 'nav-links'} aria-label="Main navigation">{[['Platform', '#platform'], ['How it works', '#workflow'], ['Intelligence', '#intelligence'], ['Workspaces', '#workspaces']].map(([label, href]) => <a key={href} href={href} onClick={() => setOpen(false)}>{label}</a>)}</nav><Link className="nav-cta" to="/login">Enter LedgerAI <ArrowUpRight size={16} /></Link><button className="menu-button" aria-label={open ? 'Close navigation' : 'Open navigation'} aria-expanded={open} onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button></div></header>
}

function Hero({ ready }: { ready: boolean }) {
  const root = useRef<HTMLElement>(null)
  const [progress, setProgress] = useState(0)
  const [staticView, setStaticView] = useState(false)
  const reduced = useReducedMotion()
  useEffect(() => {
    if (reduced || !ready) return
    const context = gsap.context(() => {
      gsap.to('.hero-copy', { y: -60, opacity: .12, ease: 'none', scrollTrigger: { trigger: root.current, start: 'top top', end: 'bottom 15%', scrub: 1 } })
      ScrollTrigger.create({ trigger: root.current, start: 'top top', end: 'bottom top', onUpdate: self => setProgress(Math.round(self.progress * 100) / 100) })
      gsap.fromTo('.hero-copy > *', { y: 24, opacity: 0 }, { y: 0, opacity: 1, duration: .85, stagger: .09, delay: .15, ease: 'power3.out' })
    }, root)
    return () => context.revert()
  }, [reduced, ready])
  return <section className="hero" id="platform" ref={root} aria-labelledby="hero-title"><div className="hero-grid" /><div className="hero-orb-glow" /><div className="hero-inner"><div className="hero-copy"><a className="release-tag" href="#workflow"><span className="status-dot" />INTRODUCING LEDGERAI 2.0 <span className="release-tag-arrow"><ArrowUpRight size={12} /></span></a><h1 id="hero-title">Finance<br />Intelligence. <br /><span>Reimagined.</span></h1><p className="hero-description">From financial complexity to intelligent clarity. <br className="desktop-break" /> Documents, reconciliations, and approvals. <br className="desktop-break" /> One connected, evidence-driven workflow.</p><div className="hero-actions"><a className="button primary" href="#workflow">Explore LedgerAI <ArrowUpRight size={18} /></a><a className="text-button" href="#workflow"><span className="play-icon"><Play size={11} fill="currentColor" /></span>Discover how it works</a></div><div className="hero-assurance"><ShieldCheck size={14} /><span>Human controlled.</span><span className="small-dot" /><span>Evidence grounded.</span></div></div><div className="hero-visual"><div className="scene-corner top-left" /><div className="scene-corner bottom-right" /><div className="hero-scene"><SceneBoundary><Suspense fallback={<CoreFallback />}>{staticView ? <CoreFallback /> : <IntelligenceScene progress={progress} />}</Suspense></SceneBoundary></div><div className="core-label"><span className="status-dot" />LEDGER INTELLIGENCE ENGINE<span>Interactive 3D visualization</span></div><div className="float-label label-documents"><span className="float-icon"><FileText size={15} /></span><div><small>INPUT LAYER</small><strong>Financial documents</strong></div><span className="label-line" /></div><div className="float-label label-evidence"><span className="float-icon"><Fingerprint size={15} /></span><div><small>TRUST LAYER</small><strong>Connected evidence</strong></div></div><div className="engine-version"><span>LI.02</span><i />AI + RULES + HUMAN CONTROL</div><div className="drag-hint"><Command size={12} /> MOVE TO EXPLORE <span> / </span> DRAG TO ROTATE</div><button className="scene-view-toggle" aria-pressed={staticView} onClick={() => setStaticView(!staticView)}>{staticView ? 'Enable interactive 3D' : 'Use static view'}<Layers3 size={11} /></button></div></div><div className="hero-bottom"><a href="#workflow" className="scroll-cue"><span><ArrowDown size={15} /></span>SCROLL INTO INTELLIGENCE</a><div className="hero-bottom-note"><span>Built for the people behind the numbers.</span><div className="tiny-avatar"><UserRound size={11} /></div><div className="tiny-avatar"><UsersRound size={11} /></div><div className="tiny-avatar"><ShieldCheck size={11} /></div></div><span className="hero-index">01 <span>/ 08</span></span></div></section>
}

const capabilities = [
  { icon: ScanLine, title: 'Document understanding', short: 'Find the structure in every document.', text: 'Explore how invoices and statements become reviewable fields, with a source reference kept beside each value.', system: 'AI interpretation', evidence: 'Invoice → extracted fields → source reference' },
  { icon: GitBranch, title: 'Intelligent task routing', short: 'The next right task. The right person.', text: 'Task suggestions identify a likely workflow and responsible role. Company policy and backend permissions decide who can act.', system: 'AI suggestion + policy controls', evidence: 'Task description → suggested category → human review' },
  { icon: AudioLines, title: 'Transaction analysis', short: 'Turn rows of data into a clear picture.', text: 'Compare transaction records through explicit matching rules. Financial totals and matching tolerances stay deterministic.', system: 'Deterministic financial rules', evidence: 'Bank reference + amount + date → candidate match' },
  { icon: CircleHelp, title: 'Exception explanations', short: 'Understand what needs a closer look.', text: 'Surface conflicts with their supporting records so a reviewer can understand the difference before resolving it.', system: 'Evidence-grounded interpretation', evidence: 'Unmatched record → variance → source documents' },
  { icon: Fingerprint, title: 'Evidence retrieval', short: 'Every answer has a paper trail.', text: 'Keep the document, transaction, and review context connected. Inspect supporting evidence before making a financial decision.', system: 'Document and audit retrieval', evidence: 'Recommendation → record reference → review history' },
  { icon: Waypoints, title: 'Workflow assistance', short: 'Keep work moving. Keep people in control.', text: 'Prepare a next-step recommendation without posting an accounting decision. Authorized people review and approve each controlled action.', system: 'Assistance + human authorization', evidence: 'Suggested action → approval policy → authorized reviewer' },
]

function Intelligence() {
  const [active, setActive] = useState(0)
  const [expanded, setExpanded] = useState(false)
  const capability = capabilities[active]
  const Icon = capability.icon
  return <section className="intelligence section-pad" id="intelligence"><div className="section-topline"><span className="eyebrow"><span className="section-dash" />THE INTELLIGENCE LAYER</span><span className="section-number">03 / CONNECT</span></div><div className="intelligence-heading"><h2>Many moving parts. <br /><span>One connected mind.</span></h2><p>Purpose-built assistance at every step. <br />Explore the intelligence behind your workflow.</p></div><div className="intelligence-body"><div className="capability-network"><svg className="network-lines" viewBox="0 0 600 470" aria-hidden="true"><defs><radialGradient id="networkGlow"><stop offset="0" stopColor="#16d4d0" stopOpacity=".2" /><stop offset="1" stopColor="#16d4d0" stopOpacity="0" /></radialGradient></defs><circle cx="300" cy="235" r="215" fill="url(#networkGlow)" /><circle cx="300" cy="235" r="125" fill="none" stroke="#1d3b48" strokeDasharray="3 7" /><circle cx="300" cy="235" r="185" fill="none" stroke="#1a2e3a" />{[[110, 100], [490, 100], [70, 235], [530, 235], [110, 370], [490, 370]].map(([x, y], i) => <path key={i} d={`M300 235 Q${(x + 300) / 2} ${y} ${x} ${y}`} fill="none" stroke={active === i ? '#16d4d0' : '#26404d'} strokeWidth={active === i ? '1.5' : '1'} className={active === i ? 'active-path' : ''} />)}</svg><div className="network-center"><Network size={42} strokeWidth={1.1} /><span>LEDGER AI</span><small>CONNECTED INTELLIGENCE</small></div>{capabilities.map((item, i) => <button key={item.title} className={`capability-node node-${i} ${active === i ? 'selected' : ''}`} aria-pressed={active === i} onMouseEnter={() => setActive(i)} onFocus={() => setActive(i)} onClick={() => { setActive(i); setExpanded(true) }} aria-label={`Explore ${item.title}`}><item.icon size={21} strokeWidth={1.4} /><span>{item.title}</span></button>)}<span className="network-caption">SELECT A NODE TO EXPLORE</span></div><div className="capability-detail" key={active}><div className="detail-icon"><Icon size={23} strokeWidth={1.4} /></div><span className="mini-label">CAPABILITY 0{active + 1} / 06</span><h3>{capability.title}</h3><h4>{capability.short}</h4><p>{capability.text}</p><div className="system-label"><span className="status-dot" />{capability.system}</div><button className="text-button cyan" onClick={() => setExpanded(!expanded)} aria-expanded={expanded}>{expanded ? 'Close example' : 'Explore the connection'}<ArrowUpRight size={16} /></button><AnimatePresence>{expanded && <motion.div className="capability-example" initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}><small>ILLUSTRATIVE EVIDENCE PATH</small><p>{capability.evidence}</p><Link to="/demo/employee">Try the demo workspace <ArrowRight size={14} /></Link></motion.div>}</AnimatePresence></div></div><div className="intelligence-note"><InfoSymbol /><p>A visualization of the platform’s architecture. AI recommendations support decisions; policies and people authorize them.</p></div></section>
}

function InfoSymbol() { return <span className="info-symbol">i</span> }

const demoRows = [
  { name: 'Figma, Inc.', initials: 'Fi', color: '#7960bd', ref: 'INV-2026-042', date: '14 Oct 2026', amount: '$144.00', status: 'Matched', detail: 'Invoice and bank entry share an exact reference and amount. Ready for an authorized reviewer.' },
  { name: 'Linear Orbit', initials: 'Li', color: '#526da8', ref: 'INV-2026-039', date: '13 Oct 2026', amount: '$320.00', status: 'In review', detail: 'The document reference needs confirmation. An assigned employee can review the extracted fields.' },
  { name: 'Acme Supplies', initials: 'Ac', color: '#ac835c', ref: 'INV-2026-037', date: '12 Oct 2026', amount: '$1,280.00', status: 'Exception', detail: 'Demo variance: the bank entry is $1,250.00 and the invoice is $1,280.00. A manager must review the $30.00 difference.' },
]

function ProductShowcase() {
  const [tab, setTab] = useState('Overview')
  const [selected, setSelected] = useState<typeof demoRows[number] | null>(null)
  const rows = tab === 'Exceptions' ? demoRows.filter(r => r.status === 'Exception') : tab === 'Approvals' ? demoRows.filter(r => r.status !== 'Exception') : demoRows
  return <section className="product-section section-pad" id="operations"><div className="section-topline"><span className="eyebrow"><span className="section-dash" />YOUR OPERATIONS, IN FOCUS</span><span className="section-number">04 / OPERATE</span></div><div className="product-heading"><div><h2>Less chasing numbers. <br /><span>More moving forward.</span></h2></div><div><p>A shared view of documents, exceptions, and decisions. <br />So everyone knows what happens next.</p><Link className="inline-link" to="/demo/manager">Explore the interactive demo <ArrowUpRight size={17} /></Link></div></div><div className="product-window"><div className="window-top"><span className="window-lights"><i /><i /><i /></span><span><LockKeyhole size={11} /> app.ledgerai / finance-workspace</span><span className="demo-tag">ILLUSTRATIVE DEMO</span></div><div className="product-app"><aside className="product-sidebar"><Brand light /><span className="sidebar-caption">FINANCE WORKSPACE</span>{[{ title: 'Overview', icon: Layers3 }, { title: 'Documents', icon: FileText }, { title: 'Reconciliation', icon: GitBranch }, { title: 'Exceptions', icon: CircleHelp }, { title: 'Approvals', icon: ShieldCheck }].map(item => <button className={tab === item.title ? 'active' : ''} onClick={() => setTab(item.title)} key={item.title}><item.icon size={15} />{item.title}{item.title === 'Exceptions' && <small>1</small>}</button>)}<div className="sidebar-bottom"><span className="workspace-avatar">JM</span><div>Jamie Morgan<small>Finance Manager · Demo</small></div></div></aside><div className="product-main"><div className="product-breadcrumb">Workspace <ChevronRight size={11} />{tab}<span>OCTOBER 2026 <ArrowDown size={10} /></span></div><div className="product-title"><div><h3>{tab === 'Overview' ? 'A clearer picture of your finances.' : tab === 'Exceptions' ? 'Every exception, explained.' : tab === 'Approvals' ? 'Your decisions make the difference.' : tab === 'Documents' ? 'Everything starts with a document.' : 'Bring every record into agreement.'}</h3><p>{tab === 'Exceptions' ? 'Review the source records before resolving the difference.' : 'Your finance operations, connected in one place.'}</p></div><Link to="/demo/manager" className="small-primary">Open workspace <ArrowUpRight size={12} /></Link></div><div className="demo-metrics"><div><span>Documents in this demo</span><strong>24 <small><FileText size={14} /></small></strong><p>Illustrative processing queue</p></div><div><span>Matched records</span><strong>18 <small className="metric-positive"><CheckCheck size={14} /></small></strong><p>Using reference & amount rules</p></div><div><span>Needs human review</span><strong>6 <small className="metric-warning"><UserRound size={14} /></small></strong><p>Review before any action</p></div></div><div className="product-table-heading"><h4>{tab === 'Exceptions' ? 'Exception queue' : tab === 'Approvals' ? 'Pending human review' : 'Recent financial activity'}</h4><span>SEEDED DEMO DATA</span></div><div className="demo-table-wrap"><table className="demo-table"><thead><tr><th>Document</th><th>Date</th><th>Amount</th><th>Status</th><th><span className="sr-only">Details</span></th></tr></thead><tbody>{rows.map(row => <tr key={row.ref} onClick={() => setSelected(row)}><td><span className="table-company" style={{ background: row.color }}>{row.initials}</span><span className="table-company-name">{row.name}<small>{row.ref}</small></span></td><td>{row.date}</td><td>{row.amount}</td><td><span className={`table-status ${row.status.toLowerCase().replace(' ', '-')}`}><i />{row.status}</span></td><td><button aria-label={`Inspect ${row.ref}`} onClick={() => setSelected(row)}><ArrowUpRight size={15} /></button></td></tr>)}</tbody></table></div><div className="product-evidence-note"><ShieldCheck size={14} /><span>Every record connected to its source. Every approval stays with your team.</span><Check size={13} /></div></div></div></div><div className="product-caption"><span className="status-dot" />A PRODUCT WALKTHROUGH WITH SEEDED DATA. NO LIVE FINANCIAL ACTIVITY.</div>{selected && <Modal title={selected.ref} onClose={() => setSelected(null)}><div className="record-detail"><span className="eyebrow">DEMO RECORD / {selected.status}</span><h3>{selected.name} <span>{selected.amount}</span></h3><p>{selected.detail}</p><div className="evidence-box"><FileCheck2 size={20} /><div>Source evidence<small>Sample invoice · {selected.ref}<br />Seeded bank reference · {selected.date}</small></div></div><Link className="button primary" to="/demo/manager">Continue in demo workspace <ArrowUpRight size={16} /></Link></div></Modal>}</section>
}

function DataTransformation() {
  return <section className="data-section section-pad"><div className="data-intro"><span className="eyebrow"><span className="section-dash" />FROM INFORMATION TO ACTION</span><h2>Complexity comes in. <br /><span>Clarity comes out.</span></h2><p>Every record follows a visible path. <br />Every decision has a responsible person.</p></div><div className="data-diagram" aria-label="Documents and bank records become structured data and matched records, then pass through a human approval gate before reporting."><div className="data-input"><div><FileText size={17} /><span>Documents<small>Invoices & statements</small></span></div><div><Database size={17} /><span>Transactions<small>Bank & ledger records</small></span></div></div><div className="data-connect"><i /><i /><i /></div><div className="data-core"><Network size={36} /><span>LEDGER AI</span><small>INTERPRET + RECONCILE</small></div><div className="data-connect after"><i /><i /><i /></div><div className="data-output"><span><Check size={12} />Structured data</span><span><Check size={12} />Matched transactions</span><span className="needs-review"><UserRound size={12} />Exceptions to review</span><span><Fingerprint size={12} />Source evidence</span></div><div className="data-approval"><ShieldCheck size={17} /><span>HUMAN APPROVAL GATE</span><ArrowRight size={15} /><span>Approved records & reporting</span></div></div></section>
}

const roles = [
  { id: 'admin', name: 'Administrator', caption: 'THE BIG PICTURE', icon: ShieldCheck, description: 'The right access. The complete picture. Keep your financial ecosystem running with confidence.', tasks: ['Users & access controls', 'AI processing & audit history', 'System operations'], accent: 'navy' },
  { id: 'manager', name: 'Finance Manager', caption: 'THE DECISION MAKER', icon: Layers3, description: 'Bring clarity to every close. Give your team direction and every decision a traceable foundation.', tasks: ['Reconciliations & exceptions', 'Approvals & month-end close', 'Financial statements'], accent: 'blue' },
  { id: 'employee', name: 'Finance Employee', caption: 'THE EVERYDAY EXPERT', icon: FileCheck2, description: 'Less repetitive work. More meaningful progress. Turn daily documents into review-ready records.', tasks: ['Document uploads & corrections', 'Assigned tasks & transactions', 'Permitted AI assistance'], accent: 'teal' },
]

function RoleShowcase() {
  const reduced = useReducedMotion()
  return <section className="roles-section section-pad" id="workspaces"><div className="section-topline"><span className="eyebrow"><span className="section-dash" />BUILT AROUND YOUR TEAM</span><span className="section-number">06 / COLLABORATE</span></div><div className="roles-heading"><h2>Different responsibilities. <br /><span>Shared intelligence.</span></h2><p>A focused workspace for every role. <br />Connected by one transparent workflow.</p></div><div className="role-cards">{roles.map((role, i) => <motion.article key={role.id} className={`role-card role-${role.accent}`} initial={reduced ? false : { opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true, amount: .2 }} transition={{ duration: .5, delay: i * .1 }} onPointerMove={e => { if (reduced || e.pointerType === 'touch') return; const r = e.currentTarget.getBoundingClientRect(); e.currentTarget.style.setProperty('--rx', `${-(e.clientY - r.top - r.height / 2) / 80}deg`); e.currentTarget.style.setProperty('--ry', `${(e.clientX - r.left - r.width / 2) / 80}deg`) }} onPointerLeave={e => { e.currentTarget.style.setProperty('--rx', '0deg'); e.currentTarget.style.setProperty('--ry', '0deg') }}><div className="role-card-top"><span>0{i + 1}</span><span className="role-symbol"><role.icon size={35} strokeWidth={1.2} /></span><ArrowUpRight size={17} /></div><span className="mini-label">{role.caption}</span><h3>{role.name}</h3><p>{role.description}</p><ul>{role.tasks.map(task => <li key={task}><Check size={13} />{task}</li>)}</ul><Link to={`/login/${role.id}`}>Explore workspace <ArrowUpRight size={16} /></Link></motion.article>)}</div><p className="roles-note"><LockKeyhole size={13} />Role selection personalizes your sign-in. Your identity and permissions are verified by the backend.</p></section>
}

function Trust() {
  const [active, setActive] = useState(0)
  const entries = [{ title: 'Intelligence you can question.', text: 'Keep recommendations grounded in the documents and transaction records behind them. Inspect the evidence and understand the proposed next step.', icon: Fingerprint, label: 'EVIDENCE OVER ASSUMPTION', tags: ['Source references', 'Transparent explanations'] }, { title: 'People stay in control.', text: 'AI assists with interpretation. Financial rules calculate and reconcile. Authorized reviewers make the final call on controlled actions.', icon: UserRound, label: 'HUMAN AUTHORIZATION', tags: ['Review before posting', 'Policy-controlled actions'] }, { title: 'A trail worth following.', text: 'Connect documents, corrections, approvals, and reporting in a traceable workflow. Give each role visibility into the work they are allowed to perform.', icon: GitBranch, label: 'TRACEABILITY BY DESIGN', tags: ['Role-based collaboration', 'Connected audit evidence'] }]
  const entry = entries[active]
  return <section className="trust-section section-pad" id="controls"><div className="trust-intro"><span className="eyebrow"><span className="section-dash" />INTELLIGENT BY DESIGN. ACCOUNTABLE BY DEFAULT.</span><h2>Confidence isn’t a feature. <br /><span>It’s the foundation.</span></h2><p>More intelligence should mean more clarity. <br />Built around evidence, visibility, and human judgment.</p></div><div className="trust-content"><div className="trust-accordions">{entries.map((item, i) => <div className={`trust-item ${active === i ? 'active' : ''}`} key={item.title}><button onClick={() => setActive(i)} aria-expanded={active === i}><span>0{i + 1}</span>{item.title}<ArrowUpRight size={18} /></button>{active === i && <motion.p initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }}>{item.text}</motion.p>}</div>)}</div><div className="trust-visual"><div className="trust-lines" /><div className="trust-emblem"><entry.icon size={54} strokeWidth={.9} /></div><span className="mini-label">{entry.label}</span><div className="trust-tags">{entry.tags.map(tag => <span key={tag}><Check size={12} />{tag}</span>)}</div><small>CONTROL IS PART OF THE WORKFLOW.</small></div></div></section>
}

function FinalCTA() {
  const section = useRef<HTMLElement>(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => { if (entry.isIntersecting) { setVisible(true); observer.disconnect() } }, { rootMargin: '200px' })
    if (section.current) observer.observe(section.current)
    return () => observer.disconnect()
  }, [])
  return <section className="final-cta section-pad" ref={section}><div className="final-stars" /><div className="final-core">{visible && <SceneBoundary><Suspense fallback={<CoreFallback />}><IntelligenceScene variant="compact" /></Suspense></SceneBoundary>}</div><div className="final-copy"><span className="eyebrow"><span className="status-dot" />YOUR NEXT CHAPTER STARTS HERE</span><h2>The future of finance<br />operations <span>starts here.</span></h2><p>Intelligent financial workflows. <br />Transparency, control, and confidence.</p><Link className="button primary" to="/login">Enter LedgerAI <ArrowUpRight size={18} /></Link><a className="back-top" href="#platform">Back to top <ArrowUpRight size={13} /></a></div><div className="final-coordinates">LEDGER INTELLIGENCE / V.02<span>HUMAN + INTELLIGENCE</span></div></section>
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const panel = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const old = document.body.style.overflow
    const previous = document.activeElement as HTMLElement | null
    document.body.style.overflow = 'hidden'
    panel.current?.querySelector<HTMLElement>('button, a[href], input, [tabindex="0"]')?.focus()
    const handle = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
      if (event.key === 'Tab') {
        const elements = panel.current?.querySelectorAll<HTMLElement>('button, a[href], input, [tabindex="0"]')
        if (!elements?.length) return
        const first = elements[0], last = elements[elements.length - 1]
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
      }
    }
    window.addEventListener('keydown', handle)
    return () => { document.body.style.overflow = old; window.removeEventListener('keydown', handle); previous?.focus() }
  }, [onClose])
  return <div className="modal-overlay" onClick={onClose}><div className="modal-panel" ref={panel} role="dialog" aria-modal="true" aria-labelledby="modal-title" tabIndex={-1} onClick={e => e.stopPropagation()}><div className="modal-header"><h2 id="modal-title">{title}</h2><button onClick={onClose} aria-label="Close dialog"><X size={21} /></button></div>{children}</div></div>
}

function Footer() {
  const [info, setInfo] = useState<'docs' | 'controls' | null>(null)
  return <><footer className="site-footer"><div className="footer-main"><Link to="/" aria-label="LedgerAI home"><Brand /></Link><p>Clarity in every record. <br />Confidence in every decision.</p><div><span>EXPLORE</span><a href="#workflow">How it works</a><a href="#intelligence">Intelligence</a><Link to="/login">Workspaces</Link></div><div><span>TAKE A CLOSER LOOK</span><Link to="/demo/manager">Interactive demo <ArrowUpRight size={12} /></Link><button onClick={() => setInfo('docs')}>Experience guide <ArrowUpRight size={12} /></button><button onClick={() => setInfo('controls')}>Privacy & controls <ArrowUpRight size={12} /></button></div></div><div className="footer-bottom"><span>© {new Date().getFullYear()} LedgerAI. Designed for clarity.</span><span><span className="status-dot" />AI ASSISTS. PEOPLE DECIDE.</span><a href="#platform">BACK TO TOP ↑</a></div></footer>{info && <Modal title={info === 'docs' ? 'Your LedgerAI experience guide' : 'Privacy & human controls'} onClose={() => setInfo(null)}><div className="guide-content">{info === 'docs' ? <><BookOpen size={30} /><p>Follow the six-stage pipeline to explore document intake, extraction, deterministic reconciliation, exception review, human approval, and reporting.</p><p>Try an interactive workspace for each role. These previews use seeded data in your browser; changes are illustrative and reset when you reload.</p><Link className="button primary" to="/demo/manager">Open the manager demo <ArrowRight size={16} /></Link></> : <><ShieldCheck size={30} /><p>This frontend demo does not post financial records or upload files to a server. Selected files are inspected locally for the illustrative upload experience.</p><p>Production sign-in requires a configured identity backend. Role choice alone never grants access. AI suggestions cannot grant permissions or bypass approvals.</p><p>Do not enter production credentials until your own backend is connected and its controls have been verified.</p></>}</div></Modal>}</>
}

export default function Home() {
  const [intro, setIntro] = useState(() => { try { return !sessionStorage.getItem('ledgerai-intro-seen') } catch { return true } })
  const completeIntro = useRef(() => { try { sessionStorage.setItem('ledgerai-intro-seen', 'true') } catch { } setIntro(false) }).current
  const content = useRef<HTMLDivElement>(null)
  const reduced = useReducedMotion()
  useEffect(() => {
    if (intro || reduced) return
    const context = gsap.context(() => {
      gsap.utils.toArray<HTMLElement>('.section-topline, .intelligence-heading, .product-heading, .data-intro, .roles-heading, .trust-intro').forEach(item => {
        gsap.fromTo(item, { opacity: 0, y: 25 }, { opacity: 1, y: 0, duration: .75, ease: 'power2.out', scrollTrigger: { trigger: item, start: 'top 90%', once: true } })
      })
      ScrollTrigger.refresh()
    }, content)
    return () => context.revert()
  }, [intro, reduced])
  return <><AnimatePresence>{intro && <Intro done={completeIntro} />}</AnimatePresence><div ref={content} className="homepage" inert={intro} aria-hidden={intro || undefined}><Navigation /><main id="main"><Hero ready={!intro} /><div className="value-strip"><span>BUILT FOR FINANCIAL OPERATIONS</span><div><FileText size={16} />Document intelligence</div><div><GitBranch size={16} />Connected reconciliation</div><div><ShieldCheck size={16} />Human-led approvals</div><span className="strip-end">ONE INTELLIGENT WORKFLOW <ArrowDownRight size={17} /></span></div><Workflow /><Intelligence /><ProductShowcase /><DataTransformation /><RoleShowcase /><Trust /><FinalCTA /></main><Footer /></div></>
}
