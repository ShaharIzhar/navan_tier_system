import { useState } from 'react'
import type { Evidence } from '../api'
import { Hint } from './Section'
import { CompanySiteBadge, ReliabilityChip, SiteIcon, hostOf, isCompanySite } from './ui'

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
        const own = e.origin === 'ai_research' && isCompanySite(e.source_url, companyDomain)
        return (
          <div key={e.id} id={`ev-${e.id}`}
            className={`evidence-item${superseded ? ' superseded' : ''}${highlightId === e.id ? ' highlight' : ''}${e.source_url ? ' openable' : ''}`}
            role={e.source_url ? 'link' : undefined}
            tabIndex={e.source_url ? 0 : undefined}
            onClick={(ev) => {
              // Open the source when clicking anywhere in the row (not buttons/links, and not while selecting text).
              if (!e.source_url || (ev.target as HTMLElement).closest('a, button')) return
              if (window.getSelection()?.toString()) return
              window.open(e.source_url, '_blank', 'noopener,noreferrer')
            }}
            onKeyDown={(ev) => { if (ev.key === 'Enter' && e.source_url) window.open(e.source_url, '_blank', 'noopener,noreferrer') }}
          >
            <div className="spread" style={{ alignItems: 'flex-start' }}>
              <div className="claim-line">
                {own && (
                  <span className="own-badge">
                    <CompanySiteBadge domain={hostOf(e.source_url) ?? ''} date={e.published_date} plain /> Company website
                  </span>
                )}
                <span>{e.claim}</span>
              </div>
              {onWithdraw && !superseded && (e.origin === 'human' || e.origin === 'synthetic_test') && (
                <button className="ghost small" onClick={() => onWithdraw(e)}>Withdraw</button>
              )}
            </div>
            <div className="evidence-meta">
              {(e.origin === 'human' || e.origin === 'synthetic_test') && <ReliabilityChip reliability={e.reliability} />}
              {e.signal_type === 'direct_travel' && (
                <span className="badge flag">
                  {e.travel_scope === 'local_field_travel' ? 'Local travel (not counted)' : e.travel_scope === 'business_travel' ? 'Business travel' : 'Travel'}
                </span>
              )}
              {e.observation === 'inferred' && <span className="badge st-stale">Inferred</span>}
              {e.is_stale && <span className="badge st-stale">Old</span>}
              {e.source_url ? (
                <Hint text={[hostOf(e.source_url), e.source_title, e.published_date].filter(Boolean).join(' · ')}>
                  <a className="source-link" href={e.source_url} target="_blank" rel="noreferrer">
                    <SiteIcon url={e.source_url} />
                    <span>{e.source_title || hostOf(e.source_url)}</span>
                  </a>
                </Hint>
              ) : (
                <span>{e.origin === 'human' ? `Added by ${e.entered_by}` : e.publisher}</span>
              )}
              {e.published_date && <span>· {e.published_date}</span>}
              {superseded && <span>· replaced</span>}
              {e.origin === 'human' && !e.accepted_for_reassessment && <span>· note only</span>}
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
