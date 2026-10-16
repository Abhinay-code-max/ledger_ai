export default function Brand({ light = false }: { light?: boolean }) {
  const logo = import.meta.env.VITE_LOGO_URL
  if (logo) return <span className="brand"><img className="official-logo" src={logo} alt="LedgerAI" /></span>
  return <span className={`brand ${light ? 'brand-light' : ''}`}><svg className="brand-mark" width="32" height="35" viewBox="0 0 34 36" fill="none" aria-hidden="true"><path d="M4 5.5 15 2v27L4 32.5V5.5ZM18 2l9 3.5v27L18 29V2Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/><path d="M8 10.5l3-1m-3 7 3-1m-3 7 3-1M27 10h5m-5 8h5m-5 8h5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/><circle cx="32" cy="10" r="1.6" fill="var(--cyan)"/><circle cx="32" cy="18" r="1.6" fill="var(--cyan)"/><circle cx="32" cy="26" r="1.6" fill="var(--cyan)"/></svg><span>Ledger<span className="brand-ai">AI</span><span className="brand-dot">2.0</span></span></span>
}
