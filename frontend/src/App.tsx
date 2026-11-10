import { Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api, type Meta } from './api'
import UserMenu from './components/UserMenu'
import ReviewQueue from './pages/ReviewQueue'
import Companies from './pages/Companies'
import CompanyDetail from './pages/CompanyDetail'
import TierReview from './pages/TierReview'
import Reviews from './pages/Reviews'

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null)
  useEffect(() => {
    api.meta().then(setMeta).catch(() => setMeta(null))
  }, [])

  return (
    <div className="shell">
      <nav className="sidebar">
        <div className="brand">
          Navan Growth Intelligence
          <small>Prospect tier review · prototype</small>
        </div>
        <NavLink to="/companies" className="navlink">All companies</NavLink>
        <NavLink to="/queue" className="navlink">Review queue</NavLink>
        <NavLink to="/reviews" className="navlink">Tier reviews</NavLink>
        {meta?.provider.mode === 'replay' && (
          <div className="sidebar-mode demo small" role="status">
            <strong>Demo mode</strong>
            <span>No API key. Research shows recorded real runs for {meta.provider.recorded_companies?.length ?? 0} companies.</span>
          </div>
        )}
        {meta?.provider.mode === 'off' && (
          <div className="sidebar-mode off small" role="status">
            <strong>Live research off</strong>
            <span>No API key. Everything else still works.</span>
          </div>
        )}
      </nav>
      <main className="main">
        <div className="topbar"><UserMenu /></div>
        <Routes>
          <Route path="/" element={<Navigate to="/companies" replace />} />
          <Route path="/queue" element={<ReviewQueue />} />
          <Route path="/companies" element={<Companies />} />
          <Route path="/companies/:id" element={<CompanyDetail />} />
          <Route path="/reviews" element={<Reviews />} />
          <Route path="/reviews/:id" element={<TierReview />} />
        </Routes>
      </main>
    </div>
  )
}
