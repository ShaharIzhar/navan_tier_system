import { useState } from 'react'
import { api, type Judgement } from '../api'
import { Info } from './Section'
import { Spinner, useAsync, when } from './ui'

const SUPPORT: Record<string, { label: string; cls: string; hint: string }> = {
  strong: { label: 'Well supported', cls: 'st-found', hint: 'Several independent, reliable sources back the change.' },
  partial: { label: 'Partly supported', cls: 'st-stale', hint: 'Some evidence backs it, but there are real gaps or weak sources.' },
  weak: { label: 'Weakly supported', cls: 'st-conflicting', hint: 'Evidence is thin, unreliable or conflicting. Check before approving.' },
}

/** One-sentence AI overview of why a proposal exists. Advisory only. */
export default function JudgeCard({ proposalId }: { proposalId: number }) {
  const [force, setForce] = useState(0)
  const { data: j, loading, error } = useAsync<Judgement>(() => api.judge(proposalId, force > 0), [proposalId, force])
  const s = j?.support ? SUPPORT[j.support] : null

  return (
    <div className="card judge">
      <div className="judge-head">
        <span className="judge-mark" aria-hidden>✦</span>
        <span className="judge-title">AI judge</span>
        <Info text="Claude Haiku reads only this proposal's reasons, evidence and doubts, and sums up why it exists. It cannot change anything; you decide. Numbers it uses are checked against the evidence." />
        {s && (
          <span className={`badge ${s.cls}`} title={s.hint} style={{ marginLeft: 'auto' }}>{s.label}</span>
        )}
      </div>
      {loading && !j ? (
        <p className="judge-text muted"><Spinner /> Reading the proposal…</p>
      ) : error || j?.status === 'failed' ? (
        <p className="small muted">AI summary unavailable: {error ?? j?.error}. The evidence below is unaffected.</p>
      ) : j ? (
        <>
          <p className="judge-text">{j.summary}</p>
          {j.main_doubt && (
            <p className="judge-doubt"><span>Main doubt:</span> {j.main_doubt}</p>
          )}
          {j.grounded === false && (
            <p className="callout warn small" style={{ marginTop: 8 }}>
              Check this summary: it mentions {j.ungrounded_numbers?.join(', ')}, which is not in the evidence.
            </p>
          )}
          <div className="judge-foot">
            {j.model} · {when(j.created_at)}
            <button className="more" disabled={loading} onClick={() => setForce((f) => f + 1)}>{loading ? 'Refreshing…' : 'Refresh'}</button>
          </div>
        </>
      ) : null}
    </div>
  )
}
