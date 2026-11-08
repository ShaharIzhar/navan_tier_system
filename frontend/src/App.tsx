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
        <NavLink to="/reports" className="navlink">Reports</NavLink>
        <div className="sidebar-foot">
          <label style={{ color: '#8b93a7' }}>
            Acting as
            <input value={reviewer} placeholder="Your name" onChange={(e) => setReviewer(e.target.value)} />
          </label>
          <div>
            Research: {meta ? (meta.provider.configured ? `${meta.provider.model} + web search` : 'not configured') : '…'}
          </div>
          <div>Scenario data is fictional. Company names are real.</div>
        </div>
      </nav>
      <main className="main">
        {meta && !meta.provider.configured && (
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
          <Route path="/reports" element={<Reports />} />
        </Routes>
      </main>
    </div>
  )
}
