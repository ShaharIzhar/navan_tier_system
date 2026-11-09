import { NavLink, Route, Routes } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api, type Meta } from './api'
import UserMenu from './components/UserMenu'
import { Info } from './components/Section'
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
        <NavLink to="/" end className="navlink">Review queue</NavLink>
        <NavLink to="/companies" className="navlink">All companies</NavLink>
        <NavLink to="/reviews" className="navlink">Tier reviews</NavLink>
      </nav>
      <main className="main">
        <div className="topbar"><UserMenu /></div>
        {meta?.provider.mode === 'replay' && (
          <div className="callout synthetic banner small row">
            <strong>Demo mode</strong> · no API key, so research shows <strong>recorded</strong> real Claude runs (8 Nov 2026).
            <Info text="Shows saved research from 8 Nov. Add an API key for live research." />
          </div>
        )}
        {meta?.provider.mode === 'off' && (
          <div className="callout warn banner small row">
            Live research is off (no API key).
            <Info text="Everything else still works." />
          </div>
        )}
        <Routes>
          <Route path="/" element={<ReviewQueue />} />
          <Route path="/companies" element={<Companies />} />
          <Route path="/companies/:id" element={<CompanyDetail />} />
          <Route path="/reviews" element={<Reviews />} />
          <Route path="/reviews/:id" element={<TierReview />} />
        </Routes>
      </main>
    </div>
  )
}
