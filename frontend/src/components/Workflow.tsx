import { useEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { ArrowDownToLine, ArrowUpRight, Check, CheckCheck, ChevronRight, FileCheck2, FileText, Fingerprint, GitCompareArrows, Layers3, LockKeyhole, ScanLine, ShieldCheck, Sparkles, TriangleAlert, Upload, UserRoundCheck } from 'lucide-react'
import './workflow.css'

const stages = [
  {
    label: 'Upload documents',
    description: 'Give every record a home. Bring invoices, receipts and statements into one connected workspace.',
    mode: 'SOURCE DOCUMENTS',
    icon: Upload,
    title: 'A single starting point.',
    subtitle: 'Original files stay connected to every result.',
    status: '3 sources received',
    panel: 'Your source documents',
    rows: [['invoice-014.pdf', 'Invoice · 1 page'], ['bank-statement.csv', 'Statement · 42 entries'], ['receipt-008.jpg', 'Receipt · 1 image']],
    note: 'Original documents retained',
    count: '03',
  },
  {
    label: 'Extract the essentials',
    description: 'AI interprets your documents and suggests structured fields, with the original evidence just a click away.',
    mode: 'AI INTERPRETATION',
    icon: ScanLine,
    title: 'The details, made useful.',
    subtitle: 'Suggested fields. Traceable back to the source.',
    status: 'Fields ready to review',
    panel: 'Extracted invoice fields',
    rows: [['Supplier', 'Acme Studio'], ['Invoice number', 'INV-2026-014'], ['Invoice total', '₹ 24,000.00']],
    note: 'AI suggestions require verification',
    count: '12',
  },
  {
    label: 'Reconcile transactions',
    description: 'Compare records using explicit rules for amounts, dates and references. Every match has a reason.',
    mode: 'DETERMINISTIC RULES',
    icon: GitCompareArrows,
    title: 'Every match has a why.',
    subtitle: 'Compare the evidence. Follow the matching logic.',
    status: 'Matching rules applied',
    panel: 'Transaction comparison',
    rows: [['Invoice total', '₹ 24,000.00'], ['Bank transaction', '₹ 24,000.00'], ['Reference check', 'INV-2026-014 · exact']],
    note: 'Amount + reference match',
    count: '02',
  },
  {
    label: 'Surface exceptions',
    description: 'See missing fields, unmatched entries and potential duplicates together, with context for the next decision.',
    mode: 'EXCEPTION DETECTION',
    icon: TriangleAlert,
    title: 'Clarity where it counts.',
    subtitle: 'A focused queue of items that need your attention.',
    status: '1 item needs attention',
    panel: 'Exception evidence',
    rows: [['Record', 'Receipt #008'], ['Issue detected', 'Tax number missing'], ['Suggested action', 'Verify source document']],
    note: 'Flagged for review · no automatic posting',
    count: '01',
  },
  {
    label: 'Review & approve',
    description: 'Your team makes the final call. Inspect the evidence, correct a suggestion and record an accountable approval.',
    mode: 'HUMAN APPROVAL',
    icon: UserRoundCheck,
    title: 'You stay in control.',
    subtitle: 'A clear decision, with an auditable trail.',
    status: 'Approval recorded',
    panel: 'Review activity',
    rows: [['Reviewer', 'Alex Morgan · demo'], ['Source verification', 'Completed'], ['Decision', 'Approved for reporting']],
    note: 'Reviewer and decision recorded',
    count: '01',
  },
  {
    label: 'Report with confidence',
    description: 'Move from reviewed records to a clear financial picture, with supporting detail ready when you need it.',
    mode: 'CONNECTED REPORTING',
    icon: FileCheck2,
    title: 'A clear way forward.',
    subtitle: 'Reviewed data. Connected evidence. Ready to share.',
    status: 'Report ready',
    panel: 'Reporting package',
    rows: [['Period', 'October 2026 · demo'], ['Reconciled record', 'INV-2026-014'], ['Included evidence', 'Source + match + approval']],
    note: 'Ready for your final reporting review',
    count: '01',
  },
]

export default function Workflow() {
  const [active, setActive] = useState(0)
  const [reducedMotion, setReducedMotion] = useState(false)
  const sectionRef = useRef<HTMLElement>(null)
  const manualPosition = useRef<number | null>(null)
  const stage = stages[active]
  const ActiveIcon = stage.icon

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const updateMotion = () => setReducedMotion(media.matches)
    updateMotion()
    media.addEventListener('change', updateMotion)
    let ticking = false
    let animationFrame = 0
    const onScroll = () => {
      if (ticking || media.matches) return
      ticking = true
      animationFrame = window.requestAnimationFrame(() => {
        ticking = false
        const section = sectionRef.current
        if (!section || section.contains(document.activeElement)) return
        if (manualPosition.current !== null) {
          if (Math.abs(window.scrollY - manualPosition.current) < 110) return
          manualPosition.current = null
        }
        const bounds = section.getBoundingClientRect()
        const start = window.innerHeight * 0.52
        if (bounds.top > start || bounds.bottom < window.innerHeight * 0.35) return
        const travel = Math.max(520, bounds.height * 0.62)
        const progress = Math.min(0.999, Math.max(0, (start - bounds.top) / travel))
        setActive(Math.floor(progress * stages.length))
      })
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      window.cancelAnimationFrame(animationFrame)
      window.removeEventListener('scroll', onScroll)
      media.removeEventListener('change', updateMotion)
    }
  }, [])

  const selectStage = (index: number) => {
    manualPosition.current = window.scrollY
    setActive(index)
  }

  const stageStyle = { '--wf-stage': active } as CSSProperties

  return (
    <section className="wf-section" id="workflow" ref={sectionRef} style={stageStyle} aria-labelledby="wf-heading">
      <div className="wf-inner">
        <div className="wf-eyebrow"><span><i /> HOW IT WORKS</span><span>ONE CONNECTED WORKFLOW <span className="wf-eyebrow-line" /> 01—06</span></div>
        <div className="wf-heading-row">
          <h2 id="wf-heading">From scattered records. <br /><span>To a clear way forward.</span></h2>
          <p>Less chasing the details. <br />More seeing the whole picture.</p>
        </div>
        <div className="wf-layout">
          <div className="wf-navigation" role="group" aria-label="Workflow stages">
            <div className="wf-stage-list">
              {stages.map((item, index) => {
                const Icon = item.icon
                return <button className={`wf-stage-button${active === index ? ' is-active' : ''}`} key={item.label} onClick={() => selectStage(index)} aria-pressed={active === index} aria-controls="wf-stage-detail">
                  <span className="wf-stage-number">0{index + 1}</span>
                  <span className="wf-stage-label"><Icon size={18} strokeWidth={1.6} /><span>{item.label}</span></span>
                  <ChevronRight className="wf-stage-chevron" size={17} />
                </button>
              })}
            </div>
            <div className="wf-context" id="wf-stage-detail" aria-live="polite" aria-atomic="true">
              <span className="wf-mode"><span />{stage.mode}</span>
              <p>{stage.description}</p>
            </div>
            <div className="wf-nav-footer"><ShieldCheck size={17} /><span>Evidence at every step. You in control.</span></div>
          </div>

          <div className={`wf-product wf-product-stage-${active}`} role="group" aria-label={`${stage.label}: ${stage.title}`}>
            <div className="wf-product-top"><span className="wf-product-brand"><Layers3 size={17} /> ledgar<span>.ai</span></span><span className="wf-workspace"><span />DEMO WORKSPACE</span><span className="wf-product-menu">•••</span></div>
            <div className="wf-product-title" key={`title-${active}`}><span>0{active + 1} / THE PROCESS</span><h3>{stage.title}</h3><p>{stage.subtitle}</p></div>
            <div className="wf-visual-stage" aria-hidden="true">
              <div className="wf-orbit wf-orbit-one" /><div className="wf-orbit wf-orbit-two" />
              <svg className="wf-connectors" viewBox="0 0 650 340" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="wf-line-gradient"><stop stopColor="#16d4d0" stopOpacity=".08" /><stop offset=".5" stopColor="#16d4d0" /><stop offset="1" stopColor="#16d4d0" stopOpacity=".2" /></linearGradient></defs><path d="M175 167 H260 Q280 167 280 187 V202 Q280 220 304 220 H356 Q380 220 380 200 V137 Q380 120 405 120 H492" /><path className="wf-path-lower" d="M325 238 V290 Q325 308 350 308 H460" /><circle cx="175" cy="167" r="4" /><circle cx="492" cy="120" r="4" /></svg>
              <div className="wf-document" style={{ transform: reducedMotion ? 'none' : `perspective(900px) rotateY(${10 - active * 2}deg) rotateZ(${-7 + active * 1.1}deg)` }}>
                <div className="wf-doc-top"><span className="wf-doc-logo">a<span>c</span></span><span>ACME<br />STUDIO</span><FileText size={17} /></div>
                <div className="wf-doc-invoice">INVOICE <span>014</span></div>
                <div className="wf-doc-meta"><span>Invoice to<br /><b>ledgar.ai Demo</b></span><span>Issued<br /><b>01 Oct 2026</b></span></div>
                <div className="wf-doc-rule" /><div className="wf-doc-line"><span>Design services</span><b>₹ 20,000</b></div><div className="wf-doc-line"><span>Project support</span><b>₹ 4,000</b></div><div className="wf-doc-rule" />
                <div className="wf-doc-total"><span>TOTAL DUE</span><b>₹ 24,000<span>.00</span></b></div>
                <div className="wf-doc-bottom"><span>INV-2026-014</span><span>DEMO DOCUMENT</span></div>
                {active === 1 && <div className="wf-scan-line" />}
                {active >= 2 && <span className={`wf-doc-stamp${active === 3 ? ' wf-doc-stamp-warning' : ''}`}>{active === 3 ? <TriangleAlert size={12} /> : <Check size={12} />}{active === 3 ? 'REVIEW' : active >= 4 ? 'VERIFIED' : 'MATCHED'}</span>}
              </div>

              <div className="wf-processing-core"><div className="wf-core-glow" /><span><ActiveIcon size={28} strokeWidth={1.5} /></span><b>{active === 0 ? 'INGEST' : active === 1 ? 'EXTRACT' : active === 2 ? 'MATCH' : active === 3 ? 'DETECT' : active === 4 ? 'APPROVE' : 'REPORT'}</b></div>

              <div className="wf-extraction-card">
                <div className="wf-extraction-heading"><span><Sparkles size={13} />{active === 4 ? 'REVIEW RECORD' : active === 5 ? 'REPORT SUMMARY' : 'STRUCTURED DATA'}</span><span className="wf-small-dot" /></div>
                <div className="wf-extraction-field"><span>SUPPLIER</span><strong>Acme Studio</strong><Check size={12} /></div>
                <div className="wf-extraction-field"><span>REFERENCE</span><strong>INV-2026-014</strong><Check size={12} /></div>
                <div className="wf-extraction-field wf-extraction-total"><span>INVOICE TOTAL</span><strong>₹ 24,000.00</strong><Check size={12} /></div>
                <div className={`wf-extraction-footer${active === 3 ? ' wf-is-warning' : ''}`}>{active === 3 ? <TriangleAlert size={12} /> : active >= 4 ? <ShieldCheck size={12} /> : <Fingerprint size={12} />}<span>{active === 0 ? 'Source connected' : active === 1 ? 'AI suggested · verify fields' : active === 2 ? 'Rule-based match' : active === 3 ? 'Related receipt needs review' : active === 4 ? 'Human approval recorded' : 'Evidence attached'}</span></div>
              </div>
              <div className="wf-floating-badge"><span>{active === 3 ? <TriangleAlert size={13} /> : <CheckCheck size={14} />}</span>{stage.status}<ArrowUpRight size={13} /></div>
            </div>

            <div className="wf-evidence-panel" key={`evidence-${active}`}>
              <div className="wf-evidence-top"><h4><ActiveIcon size={15} />{stage.panel}</h4><span>{stage.count} {active === 1 ? 'FIELDS' : active === 0 ? 'FILES' : active === 2 ? 'RULES' : 'RECORD'}</span></div>
              <div className="wf-evidence-rows">{stage.rows.map(([label, value]) => <div className="wf-evidence-row" key={label}><span>{label}</span><strong>{value}</strong>{active === 3 ? <span className="wf-evidence-warning" /> : <Check size={12} />}</div>)}</div>
              <div className="wf-evidence-bottom"><span><LockKeyhole size={11} />{stage.note}</span>{active === 5 ? <span><ArrowDownToLine size={12} />EXPORT READY</span> : <span>SOURCE LINKED <ArrowUpRight size={11} /></span>}</div>
            </div>
            <div className="wf-product-bottom"><span className="wf-demo-dot" />Illustrative workflow · demo data<span className="wf-product-pagination">{stages.map((item, index) => <button key={item.label} onClick={() => selectStage(index)} aria-label={`Show ${item.label}`} aria-pressed={active === index} className={active === index ? 'is-active' : ''} />)}</span></div>
          </div>
        </div>
        <div className="wf-section-footer"><span>BUILT FOR THE WAY FINANCE REALLY WORKS.</span><span>Bring order to every record.<ArrowUpRight size={17} /></span></div>
      </div>
    </section>
  )
}
