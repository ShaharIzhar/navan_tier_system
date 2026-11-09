import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type ProspectDetail } from '../api'
import { Info } from './Section'
import { Diff, proposalDiff } from './Diff'
import { ReliabilityChip, Spinner, TierBadge, num } from './ui'
import { g } from '../glossary'

type Choice = { key: string; value: number; label: string; detail?: string; reliability?: string; url?: string | null; kind: 'keep_current' | 'use_source' }

/** Top-of-page "Decision needed" box: settle a disputed headcount and/or decide a tier proposal. */
export default function DecisionPanel({ data, reviewer, onDone }: { data: ProspectDetail; reviewer: string; onDone: () => void }) {
  const a = data.assessment
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [comment, setComment] = useState('')
  const [custom, setCustom] = useState('')
  const [showCustom, setShowCustom] = useState(false)
  if (!a) return null

  const proposals = data.proposals.filter((p) => p.status === 'open' || p.status === 'needs_info')
  const conflict = a.flags.find((f) => f.type === 'data_conflict' && f.severity !== 'low' && f.reasons[0]?.startsWith('Employee counts disagree'))
  if (!proposals.length && !conflict) return null

  // Competing headcounts: the value in use now, then each distinct research value.
  const choices: Choice[] = []
  if (conflict) {
    if (a.accepted_values.employees != null) {
      choices.push({ key: 'current', value: a.accepted_values.employees, label: 'Keep current', detail: a.accepted_values.employee_source ?? undefined, kind: 'keep_current' })
    }
    const seen = new Set(choices.map((c) => c.value))
    for (const s of a.accepted_values.employee_sources) {
      if (s.origin === 'dataset' || s.origin === 'human' || seen.has(s.value)) continue
      seen.add(s.value)
      const ev = data.evidence.find((e) => e.id === s.evidence_id)
      choices.push({ key: `s${s.evidence_id}`, value: s.value, label: `Use ${s.label}`, detail: s.as_of ?? undefined, reliability: s.reliability, url: ev?.source_url ?? null, kind: 'use_source' })
    }
  }

  const run = async (key: string, fn: () => Promise<unknown>) => {
    if (!reviewer) {
      setError('Enter your name under “Acting as” in the sidebar first.')
      return
    }
    setBusy(key)
    setError(null)
    try {
      await fn()
      setComment('')
      setCustom('')
      setShowCustom(false)
      onDone()
    } catch (e) {
      setError(String((e as Error).message))
    } finally {
      setBusy(null)
    }
  }

  const resolve = (c: Choice) =>
    run(c.key, () =>
      api.resolveConflict(data.prospect.id, {
        value: c.value, reviewer, choice: c.kind, source_url: c.url, source_label: c.kind === 'keep_current' ? c.detail : c.label.replace(/^Use /, ''),
        note: comment || undefined,
      }),
    )

  return (
    <div className="card decision banner">
      <div className="decision-head">
        <span className="decision-dot" />
        <h2>Decision needed</h2>
        <span className="muted small">Nothing changes until you choose.</span>
      </div>

      {conflict && (
        <div className="decision-block">
          <div className="row" style={{ marginBottom: 8 }}>
            <strong>Which employee count is right?</strong>
            <Info text={`${conflict.reasons.join(' ')} Your choice is recorded as a verified decision; the other sources are kept as evidence.`} />
          </div>
          <Diff
            title="employee_count · used by the tier rules"
            lines={[
              ...choices.map((c) => ({
                sign: (c.kind === 'keep_current' ? '-' : '+') as '-' | '+',
                field: c.kind === 'keep_current' ? 'In use now' : 'Found',
                value: num(c.value),
                note: (
                  <>
                    <span>{c.kind === 'keep_current' ? c.detail : c.label.replace(/^Use /, '')}</span>
                    {c.reliability && <ReliabilityChip reliability={c.reliability} />}
                    {c.kind !== 'keep_current' && c.detail && <span className="muted">{c.detail}</span>}
                  </>
                ),
                action: (
                  <>
                    <span className="small muted">→</span>
                    <TierBadge tier={tierFor(a.accepted_values.gbv_usd, c.value)} />
                    <button className={`small${c.kind === 'keep_current' ? ' primary' : ''}`} disabled={!!busy} onClick={() => resolve(c)}>
                      {busy === c.key && <Spinner />} {c.kind === 'keep_current' ? 'Keep current' : 'Use this'}
                    </button>
                  </>
                ),
              })),
              {
                sign: ' ' as const,
                field: 'Other',
                value: showCustom ? (
                  <input autoFocus inputMode="numeric" placeholder="e.g. 120" value={custom} onChange={(e) => setCustom(e.target.value)}
                    aria-label="Other employee count" style={{ width: 100 }} />
                ) : '—',
                note: showCustom ? 'Enter the correct number' : '',
                action: showCustom ? (
                  <button className="small primary" disabled={!!busy || !/^\d+$/.test(custom.trim())}
                    onClick={() => resolve({ key: 'custom', value: Number(custom), label: 'Use Reviewer value', kind: 'use_source' })}>
                    Save
                  </button>
                ) : (
                  <button className="small" disabled={!!busy} onClick={() => setShowCustom(true)}>Enter another number</button>
                ),
              },
            ]}
          />
          <p className="small muted" style={{ marginTop: 6 }}>
            → shows the tier the standard rules would give with that number. If it differs from the current tier, a proposal opens for approval.
          </p>
        </div>
      )}

      {proposals.map((p) => (
        <div className="decision-block" key={p.id}>
          <div className="row" style={{ marginBottom: 8 }}>
            <strong>Change tier?</strong>
            <TierBadge tier={p.from_tier} /> → <TierBadge tier={p.proposed_tier} />
            <span className="small muted">{p.proposal_type === 'evidence_override' ? 'Evidence-based override' : 'Standard-rule correction'}</span>
            <Info text={`${p.rationale.join(' ')} ${g(p.proposal_type)}`} />
            {p.status === 'needs_info' && <span className="badge att-review_suggested">Waiting for info</span>}
            <Link to={`/reviews/${p.id}`} className="small" style={{ marginLeft: 'auto' }}>Full review #{p.id} →</Link>
          </div>
          <div style={{ marginBottom: 10 }}><Diff title="Changes if approved" lines={proposalDiff(p, a)} /></div>
          <div className="row">
            <button className="approve" disabled={!!busy} onClick={() => run(`a${p.id}`, () => api.decide(p.id, 'approve', reviewer, comment || undefined))}>
              {busy === `a${p.id}` && <Spinner />} Approve: move to Tier {p.proposed_tier}
            </button>
            <button className="danger" disabled={!!busy || !comment.trim()} title={comment.trim() ? '' : 'Add a short reason below first'}
              onClick={() => run(`r${p.id}`, () => api.decide(p.id, 'reject', reviewer, comment))}>
              {busy === `r${p.id}` && <Spinner />} Reject: keep Tier {p.from_tier}
            </button>
            <button disabled={!!busy || !comment.trim()} title={comment.trim() ? '' : 'Say what is missing below first'}
              onClick={() => run(`i${p.id}`, () => api.decide(p.id, 'request_info', reviewer, comment))}>
              Ask for more info
            </button>
          </div>
        </div>
      ))}

      <div className="decision-block" style={{ paddingTop: 0 }}>
        <input className="decision-comment" placeholder="Reason (optional; required to reject or ask for info)" value={comment}
          onChange={(e) => setComment(e.target.value)} aria-label="Decision reason" />
        {error && <div className="callout error small" style={{ marginTop: 8 }}>{error}</div>}
      </div>
    </div>
  )
}

function tierFor(gbv: number | null, employees: number): number | null {
  if (gbv == null || gbv < 0) return null
  if (gbv >= 500_000) return 1
  if (gbv >= 100_000 || employees >= 150) return 2
  return 3
}
