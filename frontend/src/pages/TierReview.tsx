import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import EvidenceList from '../components/EvidenceList'
import { Hint, Info, Section } from '../components/Section'
import { AttentionBadge, ErrorBox, FlagChip, Spinner, TierBadge, TRIGGER_LABELS, useAsync, useReviewer, when } from '../components/ui'
import { g } from '../glossary'

const ACTION_LABELS: Record<string, string> = {
  approve: 'approved',
  reject: 'rejected',
  request_info: 'asked for more information',
  comment: 'commented',
}

export default function TierReview() {
  const { id = '' } = useParams()
  const { data, error, loading, reload } = useAsync(() => api.proposal(Number(id)), [id])
  const [reviewer] = useReviewer()
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  if (loading && !data) return <div className="empty"><Spinner /></div>
  if (error || !data) return <ErrorBox error={error ?? 'Not found'} />

  const { proposal: p, prospect, current_assessment: cur } = data
  const unresolved = p.status === 'open' || p.status === 'needs_info'
  const isOverride = p.proposal_type === 'evidence_override'
  const typeLabel = isOverride ? 'Evidence-based override' : 'Standard-rule correction'

  const act = async (action: string) => {
    setBusy(action)
    setActionError(null)
    try {
      await api.decide(p.id, action, reviewer, comment)
      setComment('')
      reload()
    } catch (e) {
      setActionError(String((e as Error).message))
    } finally {
      setBusy(null)
    }
  }

  const conflicts = (cur?.flags ?? []).filter((f) => f.type === 'data_conflict' || f.type === 'insufficient_evidence')
  const missing = Object.entries(cur?.coverage ?? {}).filter(([, c]) => ['not_found', 'conflicting', 'stale'].includes(c.status))
  const uncertaintyCount = p.uncertainties.length + conflicts.length + (missing.length ? 1 : 0)

  return (
    <>
      <div className="crumb">
        <Link to="/reviews">Tier reviews</Link> / <Link to={`/companies/${prospect.id}`}>{prospect.company_name}</Link> / #{p.id}
      </div>
      <div className="page-head">
        <div>
          <h1 className="row" style={{ gap: 10 }}>
            {prospect.company_name}
            <span className="tier-change"><TierBadge tier={p.from_tier} /> → <TierBadge tier={p.proposed_tier} /></span>
          </h1>
          <p className="row small" style={{ marginTop: 6 }}>
            <span className={`status-pill${p.status === 'open' ? ' awaiting' : ''}`}>{p.status_label}</span>
            <span className="muted">·</span>
            <Hint text={g(p.proposal_type)}>
              <span className={`badge ${isOverride ? 'att-review_suggested' : 'att-none'}`}>{typeLabel}</span>
            </Hint>
            <span className="muted">· from {p.stage === 'day30' ? 'Day 30 activity' : 'signup evidence'} · #{p.id}</span>
          </p>
        </div>
      </div>
      <ErrorBox error={actionError} />

      <div className="detail-layout">
        <div className="stack">
          <Section id="rv-why" title="Why" info="The reasons this proposal was created." summary={p.title}>
            <ul className="reasons" style={{ marginTop: 0 }}>
              {p.rationale.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
            {cur && cur.flags.length > 0 && (
              <div className="row" style={{ marginTop: 10 }}>
                {cur.flags.map((f, i) => <FlagChip key={i} label={f.label} severity={f.severity} />)}
              </div>
            )}
          </Section>

          <Section
            id="rv-evidence"
            title="Evidence"
            info="Sources behind the proposal. Hover a source badge for how reliable it is."
            summary={data.evidence.length ? `${data.evidence.length} item(s)` : p.stage === 'day30' ? 'Day 30 activity' : 'structured values'}
            flush
          >
            {data.evidence.length ? (
              <EvidenceList items={data.evidence} />
            ) : (
              <div className="section-body small muted">
                {p.stage === 'day30' ? 'Based on the Day 30 activity summary (Navan data, not a web source).' : 'Based on the structured values shown on the company page.'}
              </div>
            )}
          </Section>

          <Section
            id="rv-uncertainty"
            title="Uncertainty"
            info="What could make this proposal wrong."
            summary={uncertaintyCount ? `${uncertaintyCount} item(s)` : 'none'}
          >
            {uncertaintyCount === 0 && <p className="muted small">None recorded.</p>}
            <ul className="reasons" style={{ marginTop: 0 }}>
              {p.uncertainties.map((u, i) => <li key={i}>{u}</li>)}
              {conflicts.map((f, i) => (
                <li key={`c${i}`}>
                  <FlagChip label={f.label} severity={f.severity} explain={f.reasons.slice(1).join(' ') || undefined} /> {f.reasons[0]}
                </li>
              ))}
              {missing.length > 0 && <li className="muted">Gaps: {missing.map(([k]) => k.replace(/_/g, ' ')).join(', ')}</li>}
            </ul>
          </Section>

          <div className="card">
            <div className="section-head"><h2>Decision</h2><Info text="Approve changes the tier inside the prototype. Reject keeps it. Request more information keeps the proposal open. A comment is required to reject or ask for info." /></div>
            {data.decisions.length > 0 && (
              <ul className="timeline">
                {data.decisions.map((d) => (
                  <li key={d.id}>
                    <strong className="small">{d.reviewer}</strong>{' '}
                    <span className="muted small">{ACTION_LABELS[d.action] ?? d.action} · {when(d.created_at)}</span>
                    {d.action === 'approve' && <span className="small"> · T{d.tier_before} → T{d.tier_after}</span>}
                    {d.comment && <p style={{ marginTop: 4 }}>{d.comment}</p>}
                  </li>
                ))}
              </ul>
            )}
            <div className="section-body stack" style={{ borderTop: data.decisions.length ? '1px solid var(--border)' : undefined }}>
              {!reviewer && <div className="callout warn small">Enter your name under “Acting as” in the sidebar.</div>}
              <textarea placeholder={unresolved ? 'Comment' : 'Add a comment'} value={comment} onChange={(e) => setComment(e.target.value)} aria-label="Review comment" />
              <div className="row">
                {unresolved && (
                  <>
                    <button className="approve" disabled={!!busy || !reviewer} onClick={() => act('approve')}>
                      {busy === 'approve' && <Spinner />} Approve Tier {p.proposed_tier}
                    </button>
                    <button className="danger" disabled={!!busy || !reviewer || !comment.trim()} onClick={() => act('reject')}>
                      {busy === 'reject' && <Spinner />} Reject
                    </button>
                    <button disabled={!!busy || !reviewer || !comment.trim()} onClick={() => act('request_info')}>
                      {busy === 'request_info' && <Spinner />} Request more information
                    </button>
                  </>
                )}
                <button className="ghost" disabled={!!busy || !reviewer || !comment.trim()} onClick={() => act('comment')}>Comment only</button>
              </div>
              {p.status === 'needs_info' && (
                <p className="small muted">
                  Waiting for more information. Add it on the <Link to={`/companies/${prospect.id}`}>company page</Link>.
                </p>
              )}
            </div>
          </div>
        </div>

        <div className="stack">
          <div className="card card-pad">
            <dl className="kv">
              <dt className="row">Original <Info text={g('original_tier')} align="left" /></dt><dd><TierBadge tier={prospect.original_tier} /></dd>
              <dt className="row">Applied now <Info text={g('applied_tier')} align="left" /></dt><dd><TierBadge tier={prospect.applied_tier} /></dd>
              <dt className="row">Rules say <Info text={cur ? `${g('baseline_tier')} ${cur.baseline.basis}` : g('baseline_tier')} align="left" /></dt>
              <dd><TierBadge tier={cur?.baseline.tier} provisional={cur?.baseline.provisional} /></dd>
              <dt>Reported GBV</dt><dd>{prospect.entered_gbv_usd != null ? `$${prospect.entered_gbv_usd.toLocaleString()}` : '—'}</dd>
              <dt>Employees used</dt><dd>{cur?.accepted_values.employees?.toLocaleString() ?? 'unknown'}</dd>
              <dt>Attention</dt><dd>{cur && <AttentionBadge attention={cur.attention} label={cur.attention_label} />}</dd>
            </dl>
            <div style={{ marginTop: 10 }}><Link to={`/companies/${prospect.id}`}>Company page →</Link></div>
          </div>

          <Section id="rv-history" title="Previous assessments" summary={`${data.history.length}`} defaultOpen={false} flush>
            <ul className="timeline">
              {data.history.map((h) => (
                <li key={h.id}>
                  <strong className="small">{TRIGGER_LABELS[h.trigger] ?? h.trigger}</strong>
                  {p.linked_assessment_ids.includes(h.id) && <span className="small muted"> · supports this</span>}
                  <div className="when">{when(h.created_at)} · {h.stage === 'day30' ? 'Day 30' : 'Day 0'} · rules T{h.baseline_tier ?? '—'} · applied T{h.applied_tier ?? '—'}</div>
                </li>
              ))}
            </ul>
          </Section>

          <Section id="rv-audit" title="Audit trail" summary={`${data.audit.length}`} defaultOpen={false} flush>
            <ul className="timeline" style={{ maxHeight: 320, overflow: 'auto' }}>
              {data.audit.map((e) => (
                <li key={e.id}>
                  <strong className="small">{e.action.replace(/_/g, ' ')}</strong> <span className="muted small">by {e.actor}</span>
                  <div className="when">{when(e.created_at)}</div>
                </li>
              ))}
            </ul>
          </Section>
        </div>
      </div>
    </>
  )
}
