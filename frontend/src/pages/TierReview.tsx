import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import EvidenceList from '../components/EvidenceList'
import { AttentionBadge, ErrorBox, FlagChip, Spinner, TierBadge, TRIGGER_LABELS, useAsync, useReviewer, when } from '../components/ui'

const ACTION_LABELS: Record<string, string> = {
  approve: 'approved',
  reject: 'rejected',
  request_info: 'requested more information',
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
  const missing = Object.entries(cur?.coverage ?? {}).filter(([, c]) => ['not_found', 'conflicting', 'stale', 'not_searched'].includes(c.status))

  return (
    <>
      <div className="crumb">
        <Link to="/reviews">Tier reviews</Link> / <Link to={`/companies/${prospect.id}`}>{prospect.company_name}</Link> / #{p.id}
      </div>
      <div className="page-head">
        <div>
          <h1>{p.title} <span className="muted">#{p.id}</span></h1>
          <p>
            <span className={`status-pill${p.status === 'open' ? ' awaiting' : ''}`}>{p.status_label}</span> · opened {when(p.created_at)} from{' '}
            {p.stage === 'day30' ? 'Day 30 activity' : 'signup-time evidence'} · {prospect.company_name} ({prospect.id})
          </p>
        </div>
      </div>
      <ErrorBox error={actionError} />

      <div className="detail-layout">
        <div className="stack">
          <div className="card card-pad stack">
            <div className="grid-3">
              <div>
                <div className="small muted">Current applied tier</div>
                <div className="tier-change" style={{ marginTop: 6 }}><TierBadge tier={p.from_tier} /></div>
              </div>
              <div>
                <div className="small muted">Standard-rule baseline</div>
                <div className="tier-change" style={{ marginTop: 6 }}>
                  <TierBadge tier={cur?.baseline.tier} provisional={cur?.baseline.provisional} />
                </div>
              </div>
              <div>
                <div className="small muted">Proposed tier</div>
                <div className="tier-change" style={{ marginTop: 6 }}><TierBadge tier={p.proposed_tier} /></div>
              </div>
            </div>
            <div className={`callout ${isOverride ? 'warn' : 'action'} small`}>
              {isOverride ? (
                <><strong>Evidence-based override.</strong> The standard GBV/headcount rules do not give Tier {p.proposed_tier}. Approving overrides policy for this account and is recorded as such.</>
              ) : (
                <><strong>Standard-rule correction.</strong> Applying Navan's GBV/headcount rules to the values below gives Tier {p.proposed_tier}.{p.basis && (p.basis as Record<string, unknown>).employee_source === 'research' ? ' Approving also accepts the research headcount as the value used for the rules.' : ''}</>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-head"><h2>Why this proposal exists</h2></div>
            <div className="card-pad">
              <ul className="reasons" style={{ marginTop: 0 }}>
                {p.rationale.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
              {cur && cur.flags.length > 0 && (
                <div className="row" style={{ marginTop: 10 }}>
                  {cur.flags.map((f, i) => <FlagChip key={i} label={f.label} severity={f.severity} />)}
                </div>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-head"><h2>Supporting evidence</h2><span className="card-sub">{data.evidence.length} item(s)</span></div>
            {data.evidence.length ? (
              <EvidenceList items={data.evidence} />
            ) : (
              <div className="card-pad small muted">
                {p.stage === 'day30'
                  ? 'Based on the post-signup activity summary (structured Navan data, not a web source). See the company page for details.'
                  : 'No cited evidence. Based on structured values shown above.'}
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-head"><h2>Conflicts and uncertainty</h2></div>
            <div className="card-pad stack">
              {p.uncertainties.length === 0 && conflicts.length === 0 && missing.length === 0 && <p className="muted small">None recorded.</p>}
              {p.uncertainties.length > 0 && (
                <ul className="reasons" style={{ marginTop: 0 }}>
                  {p.uncertainties.map((u, i) => <li key={i}>{u}</li>)}
                </ul>
              )}
              {conflicts.map((f, i) => (
                <div key={i} className="small"><FlagChip label={f.label} severity={f.severity} /> {f.reasons.join(' ')}</div>
              ))}
              {missing.length > 0 && (
                <p className="small muted">Missing or disputed research fields: {missing.map(([k, c]) => `${k.replace(/_/g, ' ')} (${c.status.replace('_', ' ')})`).join(', ')}.</p>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-head"><h2>Conversation</h2></div>
            <ul className="timeline">
              <li>
                <strong className="small">system</strong> <span className="muted small">opened this proposal · {when(p.created_at)}</span>
              </li>
              {data.decisions.map((d) => (
                <li key={d.id}>
                  <strong className="small">{d.reviewer}</strong>{' '}
                  <span className="muted small">{ACTION_LABELS[d.action] ?? d.action} · {when(d.created_at)}</span>
                  {d.action === 'approve' && <span className="small"> · Tier {d.tier_before} → Tier {d.tier_after}</span>}
                  {d.comment && <p style={{ marginTop: 4 }}>{d.comment}</p>}
                </li>
              ))}
            </ul>
            <div className="card-pad stack" style={{ borderTop: '1px solid var(--border)' }}>
              {!reviewer && <div className="callout warn small">Enter your name under “Acting as” in the sidebar to review.</div>}
              <textarea placeholder={unresolved ? 'Comment (required to reject or request info)' : 'Add a comment'} value={comment} onChange={(e) => setComment(e.target.value)} aria-label="Review comment" />
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
                  Waiting for more information. Add a value or run Deep Research on the <Link to={`/companies/${prospect.id}`}>company page</Link>; the
                  proposal updates automatically.
                </p>
              )}
            </div>
          </div>
        </div>

        <div className="stack">
          <div className="card card-pad stack">
            <h2>Company</h2>
            <dl className="kv">
              <dt>Original tier</dt><dd><TierBadge tier={prospect.original_tier} /></dd>
              <dt>Applied tier now</dt><dd><TierBadge tier={prospect.applied_tier} /></dd>
              <dt>Reported GBV</dt><dd>{prospect.entered_gbv_usd != null ? `$${prospect.entered_gbv_usd.toLocaleString()}` : '—'}</dd>
              <dt>Employees used</dt><dd>{cur?.accepted_values.employees?.toLocaleString() ?? 'unknown'}</dd>
              <dt>Attention</dt><dd>{cur && <AttentionBadge attention={cur.attention} label={cur.attention_label} />}</dd>
            </dl>
            <Link to={`/companies/${prospect.id}`}>Open company page →</Link>
          </div>
          <div className="card">
            <div className="card-head"><h2>Previous assessments</h2></div>
            <ul className="timeline">
              {data.history.map((h) => (
                <li key={h.id}>
                  <div className="spread">
                    <strong className="small">#{h.id} {TRIGGER_LABELS[h.trigger] ?? h.trigger}</strong>
                    <span className="small muted">{h.stage === 'day30' ? 'Day 30' : 'Day 0'}</span>
                  </div>
                  <div className="when">{when(h.created_at)} · baseline T{h.baseline_tier ?? '—'} · applied T{h.applied_tier ?? '—'}</div>
                  {p.linked_assessment_ids.includes(h.id) && <div className="small muted">supports this proposal</div>}
                </li>
              ))}
            </ul>
          </div>
          <div className="card">
            <div className="card-head"><h2>Audit history</h2></div>
            <ul className="timeline" style={{ maxHeight: 320, overflow: 'auto' }}>
              {data.audit.map((e) => (
                <li key={e.id}>
                  <strong className="small">{e.action.replace(/_/g, ' ')}</strong> <span className="muted small">by {e.actor}</span>
                  <div className="when">{when(e.created_at)}</div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </>
  )
}
