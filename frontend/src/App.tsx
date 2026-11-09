import { NavLink, Route, Routes } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api, type Meta } from './api'
import { useReviewer } from './components/ui'
import { Info } from './components/Section'
import ReviewQueue from './pages/ReviewQueue'
import Companies from './pages/Companies'
import CompanyDetail from './pages/CompanyDetail'
import TierReview from './pages/TierReview'
import Reviews from './pages/Reviews'
import Reports from './pages/Reports'
import Verified from './pages/Verified'

export default function App() {
  const [reviewer, setReviewer] = useReviewer()
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
        <NavLink to="/verified" className="navlink">Verified data</NavLink>
        <NavLink to="/reports" className="navlink">Reports</NavLink>
        <div className="sidebar-foot">
          <label style={{ color: '#8b93a7' }}>
            Acting as
            <input value={reviewer} placeholder="Your name" onChange={(e) => setReviewer(e.target.value)} />
          </label>
          <div>
            Research: {meta ? ({ live: `${meta.provider.model} + web search`, replay: 'recorded runs (demo)', off: 'not configured' } as Record<string, string>)[meta.provider.mode] : '…'}
          </div>
          <div>Scenario data is fictional. Company names are real.</div>
        </div>
      </nav>
      <main className="main">
        {meta?.provider.mode === 'replay' && (
          <div className="callout synthetic banner small row">
            <strong>Demo mode</strong> · no API key, so research shows <strong>recorded</strong> real Claude runs (8 Nov 2026).
            <Info text={`Recorded runs are replayed through the same validation and rules as live research. Recorded companies: ${meta.provider.recorded_companies.join(', ')}. Others show "Not researched". Add ANTHROPIC_API_KEY to backend/.env for live research.`} />
          </div>
        )}
        {meta?.provider.mode === 'off' && (
          <div className="callout warn banner small row">
            Live research is off (no API key).
            <Info text="Everything else works: rules, manual values, reviews, Day 30. No research results are simulated." />
          </div>
        )}
        <Routes>
          <Route path="/" element={<ReviewQueue />} />
          <Route path="/companies" element={<Companies />} />
          <Route path="/companies/:id" element={<CompanyDetail />} />
          <Route path="/reviews" element={<Reviews />} />
          <Route path="/reviews/:id" element={<TierReview />} />
          <Route path="/verified" element={<Verified />} />
          <Route path="/reports" element={<Reports />} />
        </Routes>
      </main>
    </div>
  )
}
