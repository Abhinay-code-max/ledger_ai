import { lazy, Suspense, useEffect } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import Home from './pages/Home'

const WorkspacePages = lazy(() => import('./pages/Workspaces'))

function WorkspaceRoute({ page }: { page: 'selection' | 'login' | 'dashboard' | 'demo' }) {
  return <Suspense fallback={<div className="route-loading"><span className="loading-orbit" />Preparing your workspace</div>}><WorkspacePages page={page} /></Suspense>
}

export default function App() {
  const location = useLocation()
  useEffect(() => { window.scrollTo({ top: 0, behavior: 'instant' }) }, [location.pathname])
  return <Routes>
    <Route path="/" element={<Home />} />
    <Route path="/login" element={<WorkspaceRoute page="selection" />} />
    <Route path="/login/:role" element={<WorkspaceRoute page="login" />} />
    <Route path="/dashboard/:role" element={<WorkspaceRoute page="dashboard" />} />
    <Route path="/demo/:role" element={<WorkspaceRoute page="demo" />} />
    <Route path="*" element={<div className="not-found"><div className="eyebrow">404 / OFF THE LEDGER</div><h1>This page is unaccounted for.</h1><a className="button primary" href="/">Return to LedgerAI ↗</a></div>} />
  </Routes>
}
