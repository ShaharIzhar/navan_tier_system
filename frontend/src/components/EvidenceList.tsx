import { useState } from 'react'
import type { Evidence } from '../api'
import { CompanySiteBadge, ReliabilityChip, hostOf, isCompanySite, when } from './ui'

const TRUST: Record<string, number> = { primary: 0, manual_verified: 1, secondary: 2, manual_unverified: 3, aggregator: 4, synthetic: 5 }

export default function EvidenceList({ items, onWithdraw, companyDomain, highlightId }: { items: Evidence[]; onWithdraw?: (e: Evidence) => void; companyDomain?: string; highlightId?: number | null }) {
  const [showOlder, setShowOlder] = useState(false)
  if (!items.length) return <div className="empty small">No evidence recorded for this field.</div>
  const rank = (e: Evidence) => [
    e.superseded_by ? 1 : 0,
    e.origin === 'ai_research' && isCompanySite(e.source_url, companyDomain) ? 0 : 1,
    TRUST[e.reliability] ?? 6,
  ]
  const sorted = [...items].sort((x, y) => {
    const a = rank(x), b = rank(y)
    return a[0] - b[0] || a[1] - b[1] || a[2] - b[2]
  })
  const current = sorted.filter((e) => !e.superseded_by)
  const older = sorted.filter((e) => e.superseded_by)
  return (
    <div>
      {current.length === 0 && <div className="empty small">No current evidence for this field.</div>}
      {[...current, ...(showOlder ? older : [])].map((e) => {
        const superseded = !!e.superseded_by
        return (
          <div key={e.id} id={`ev-${e.id}`} className={`evidence-item${superseded ? ' superseded' : ''}${highlightId === e.id ? ' highlight' : ''}`}>
            <div className="spread">
              <div>{e.claim}</div>
              {onWithdraw && !superseded && (e.origin === 'human' || e.origin === 'synthetic_test') && (
                <button className="ghost small" onClick={() => onWithdraw(e)}>Withdraw</button>
              )}
            </div>
            <div className="evidence-meta">
              {e.origin === 'ai_research' && isCompanySite(e.source_url, companyDomain) ? (
                <span className="badge rel rel-primary">Company website</span>
              ) : (
                <ReliabilityChip reliability={e.reliability} />
              )}
              {e.signal_type === 'direct_travel' && (
                <span className="badge flag">
                  {e.travel_scope === 'local_field_travel' ? 'Local field travel (not counted)' : e.travel_scope === 'business_travel' ? 'Business travel' : 'Travel (type unclear)'}
                </span>
              )}
              {e.signal_type === 'indirect_growth' && <span className="badge flag">Growth signal</span>}
              {e.observation === 'inferred' && <span className="badge st-stale">Inferred, not stated</span>}
              {e.is_stale && <span className="badge st-stale">Stale</span>}
              {e.source_url ? (
                <span className="row" style={{ gap: 4 }}>
                  {e.origin === 'ai_research' && isCompanySite(e.source_url, companyDomain) && (
                    <CompanySiteBadge domain={hostOf(e.source_url) ?? ''} date={e.published_date} />
                  )}
                  <a href={e.source_url} target="_blank" rel="noreferrer">
                    {e.source_title || hostOf(e.source_url)}
                  </a>
                </span>
              ) : (
                <span>{e.origin === 'human' ? 'No source given' : e.publisher}</span>
              )}
              {e.publisher && e.source_url && <span>· {e.publisher}</span>}
              {e.published_date && <span>· published {e.published_date}</span>}
              <span>· {e.origin === 'human' ? `entered by ${e.entered_by} ${when(e.created_at)}` : `retrieved ${when(e.retrieved_at)}`}</span>
              {e.run_id && <span>· run #{e.run_id}</span>}
              {superseded && <span>· superseded ({e.superseded_by?.split(':')[0]})</span>}
              {e.origin === 'human' && !e.accepted_for_reassessment && <span>· explanatory only</span>}
            </div>
            {e.note && <div className="small muted" style={{ marginTop: 4 }}>{e.note}</div>}
          </div>
        )
      })}
      {older.length > 0 && (
        <div className="evidence-item">
          <button className="more" onClick={() => setShowOlder(!showOlder)}>
            {showOlder ? 'Hide older findings' : `Show ${older.length} older finding${older.length > 1 ? 's' : ''} (replaced by newer research)`}
          </button>
        </div>
      )}
    </div>
  )
}
