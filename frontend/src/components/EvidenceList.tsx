import type { Evidence } from '../api'
import { ReliabilityChip, hostOf, when } from './ui'

export default function EvidenceList({ items, onWithdraw }: { items: Evidence[]; onWithdraw?: (e: Evidence) => void }) {
  if (!items.length) return <div className="empty small">No evidence recorded for this field.</div>
  return (
    <div>
      {items.map((e) => {
        const superseded = !!e.superseded_by
        return (
          <div key={e.id} className={`evidence-item${superseded ? ' superseded' : ''}`}>
            <div className="spread">
              <div>{e.claim}</div>
              {onWithdraw && !superseded && (e.origin === 'human' || e.origin === 'synthetic_test') && (
                <button className="ghost small" onClick={() => onWithdraw(e)}>Withdraw</button>
              )}
            </div>
            <div className="evidence-meta">
              <ReliabilityChip reliability={e.reliability} />
              {e.signal_type === 'direct_travel' && (
                <span className="badge flag">
                  {e.travel_scope === 'local_field_travel' ? 'Local field travel (not counted)' : e.travel_scope === 'business_travel' ? 'Business travel' : 'Travel (type unclear)'}
                </span>
              )}
              {e.signal_type === 'indirect_growth' && <span className="badge flag">Growth signal</span>}
              {e.observation === 'inferred' && <span className="badge st-stale">Inferred, not stated</span>}
              {e.is_stale && <span className="badge st-stale">Stale</span>}
              {e.source_url ? (
                <a href={e.source_url} target="_blank" rel="noreferrer">
                  {e.source_title || hostOf(e.source_url)}
                </a>
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
    </div>
  )
}
