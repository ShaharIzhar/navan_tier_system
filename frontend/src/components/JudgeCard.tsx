import { useState } from 'react'
import { api, type Judgement } from '../api'
import { Info } from './Section'
import { Icon, Spinner, useAsync } from './ui'

const SUPPORT: Record<string, { label: string; cls: string; hint: string }> = {
  strong: { label: 'Well supported', cls: 'st-found', hint: 'Solid evidence.' },
  partial: { label: 'Partly supported', cls: 'st-stale', hint: 'Some evidence, some gaps.' },
  weak: { label: 'Weakly supported', cls: 'st-conflicting', hint: 'Thin evidence. Check first.' },
}

/** One-sentence AI overview of why a proposal exists. Advisory only. */
export default function JudgeCard({ proposalId }: { proposalId: number }) {
  const [force, setForce] = useState(0)
  const { data: j, loading, error } = useAsync<Judgement>(() => api.judge(proposalId, force > 0), [proposalId, force])
  const s = j?.support ? SUPPORT[j.support] : null

  return (
    <div className="card judge">
      <div className="judge-head">
        <span className="judge-title"><span aria-hidden>✦</span> AI summary</span>
        <Info text="An AI read of this proposal. It can’t change anything; you decide." />
        {s && <span className={`badge ${s.cls}`} title={s.hint} style={{ marginLeft: 'auto' }}>{s.label}</span>}
        {j?.status === 'ok' && (
          <button className="icon-btn" title="Refresh summary" aria-label="Refresh summary" disabled={loading} onClick={() => setForce((f) => f + 1)}>
            {loading ? <Spinner /> : <Icon name="refresh" />}
          </button>
        )}
      </div>
      {loading && !j ? (
        <p className="judge-text muted"><Spinner /> Reading the proposal…</p>
      ) : error || j?.status === 'failed' ? (
        <p className="small muted">Summary unavailable right now.</p>
      ) : j ? (
        <>
          <p className="judge-text">{j.summary}</p>
          {j.main_doubt && <p className="judge-doubt"><span>Watch out:</span> {j.main_doubt}</p>}
          {j.grounded === false && <p className="judge-doubt"><span>Check:</span> mentions {j.ungrounded_numbers?.join(', ')}, which isn’t in the evidence.</p>}
        </>
      ) : null}
    </div>
  )
}
