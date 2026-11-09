import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type DeepPlan, type Flag, type ProspectDetail } from '../api'
import EnrichmentForm from '../components/EnrichmentForm'
import EvidenceList from '../components/EvidenceList'
import { Clamp, Hint, Info, Section } from '../components/Section'
import {
  AttentionBadge, ErrorBox, FIELD_LABELS, FlagChip, Modal, Spinner, StatusChip, TierBadge, TRIGGER_LABELS,
  TrendArrow, num, usd, useAsync, useReviewer, when,
} from '../components/ui'
import { g } from '../glossary'

const COMPARISON: Record<string, string> = {
  strengthens: 'Strengthens the signup signal',
  weakens: 'Weakens the signup signal',
  new_signal: 'New signal (not seen at signup)',
  consistent: 'Consistent with signup',
  neutral: 'No conclusion',
}

export default function CompanyDetail() {
  const { id = '' } = useParams()
  const { data, error, loading, reload } = useAsync(() => api.prospect(id), [id])
  const [reviewer] = useReviewer()
  const [busy, setBusy] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [modal, setModal] = useState<null | 'enrich' | 'deep' | 'synthetic'>(null)
  const [openField, setOpenField] = useState<string | null>(null)

  if (loading && !data) return <div className="empty"><Spinner /></div>
  if (error || !data) return <ErrorBox error={error ?? 'Not found'} />

  const run = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key)
    setActionError(null)
    try {
      await fn()
      reload()
    } catch (e) {
      setActionError(String((e as Error).message))
    } finally {
      setBusy(null)
    }
  }

  const { prospect: p, assessment: a } = data
  const lastRun = data.research_runs[0]
  const okRun = data.research_runs.find((r) => r.status === 'ok' || r.status === 'partial')
  const unresolved = data.proposals.filter((x) => x.status === 'open' || x.status === 'needs_info')
  const hasSynthetic = data.evidence.some((e) => e.origin === 'synthetic_test' && !e.superseded_by)
  const researchEmp = (a?.accepted_values.employee_sources ?? []).filter((s) => s.origin === 'ai_research' || s.origin === 'synthetic_test')
  const coverage = Object.values(a?.coverage ?? {})
  const covFound = coverage.filter((c) => c.status === 'found').length
  const covGaps = coverage.filter((c) => ['not_found', 'conflicting', 'stale'].includes(c.status)).length

  return (
    <>
      <div className="crumb"><Link to="/companies">All companies</Link> / {p.id}</div>
      <div className="page-head">
        <div>
          <h1>{p.company_name}</h1>
          <p className="small">
            <a href={`https://${p.domain}`} target="_blank" rel="noreferrer">{p.domain}</a> · {p.id} ·{' '}
            <Hint text={a?.stage === 'day30' ? g('day30') : 'Assessed with signup-time information only.'}>
              {a?.stage === 'day30' ? 'Day 30' : 'Signup (Day 0)'}
            </Hint>
          </p>
        </div>
        <div className="row">
          {a && <AttentionBadge attention={a.attention} label={a.attention_label} />}
          {a?.attention && (
            <Hint text={[g('priority'), ...a.priority_reasons].join(' ')} align="right">
              <span className="badge att-none">Priority: {a.priority}</span>
            </Hint>
          )}
        </div>
      </div>
      <ErrorBox error={actionError} />
      {hasSynthetic && (
        <div className="callout synthetic banner small">
          Contains a <strong>SYNTHETIC test observation</strong>, which is not real research. <Info text={g('synthetic')} />
        </div>
      )}

      <div className="detail-layout">
        <div className="stack">
          {/* At a glance */}
          <div className="card">
            <div className="hero">
              <div>
                <div className="label">Applied <Info text={g('applied_tier')} align="left" /></div>
                <TierBadge tier={p.applied_tier} />
              </div>
              <div>
                <div className="label">Rules say <Info text={a ? `${g('baseline_tier')} ${a.baseline.basis}` : g('baseline_tier')} /></div>
                <TierBadge tier={a?.baseline.tier} provisional={a?.baseline.provisional} />
              </div>
              <div>
                <div className="label">Reported GBV</div>
                <strong>{usd(p.entered_gbv_usd)}</strong>
              </div>
              <div>
                <div className="label">Employees used</div>
                <strong>{a?.accepted_values.employees == null ? '?' : num(a.accepted_values.employees)}</strong>
                {a?.accepted_values.near_threshold && <> <Info text={a.accepted_values.near_threshold} /></>}
              </div>
              <div />
            </div>
            {a && (
              <div style={{ padding: '0 16px 14px' }}>
                <div className="next-step">
                  <strong>Next step</strong>
                  <span>{a.recommended_action}</span>
                  {unresolved.map((x) => (
                    <Link key={x.id} to={`/reviews/${x.id}`} style={{ marginLeft: 'auto', whiteSpace: 'nowrap' }}>
                      Open review #{x.id} →
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Why flagged */}
          {a && (
            <Section
              id="flags"
              title="Why it was flagged"
              info="Each flag says why it fired. Hover a flag for its meaning; open a row for the evidence and the uncertainty."
              summary={a.flags.length ? `${a.flags.length} flag${a.flags.length > 1 ? 's' : ''}` : 'none'}
            >
              {a.flags.length === 0 ? (
                <p className="muted small">No flags.</p>
              ) : (
                a.flags.map((f, i) => <FlagRow key={i} f={f} />)
              )}
            </Section>
          )}

          {/* Reported vs found */}
          {a && (
            <Section id="reported" title="Reported vs. found" info={g('reported_vs_found')} flush>
              <table>
                <thead>
                  <tr><th></th><th>Reported</th><th>Research found</th><th>Used by rules</th></tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Annual GBV</td>
                    <td>{usd(p.entered_gbv_usd)}</td>
                    <td className="muted">— <Info text="Travel spend is not public, so GBV cannot be researched." /></td>
                    <td><strong>{usd(a.accepted_values.gbv_usd)}</strong></td>
                  </tr>
                  <tr>
                    <td>Employees</td>
                    <td>{p.zi_employees == null ? <span className="muted">missing</span> : num(p.zi_employees)}</td>
                    <td>
                      {researchEmp.length === 0 ? (
                        <span className="muted">{a.accepted_values.research_ran ? 'none found' : 'not researched'}</span>
                      ) : (
                        <span className="row" style={{ gap: 6 }}>
                          {researchEmp.map((s, i) => (
                            <Hint key={i} text={`${s.label}${s.as_of ? `, ${s.as_of}` : ''}. ${g(s.reliability)}${s.stale ? ' Stale.' : ''}`}>
                              <span className={`badge rel rel-${s.reliability}`}>{num(s.value)}</span>
                            </Hint>
                          ))}
                        </span>
                      )}
                    </td>
                    <td>
                      <Hint text={a.accepted_values.employee_source ?? 'No value available'}>
                        <strong>{a.accepted_values.employees == null ? 'unknown' : num(a.accepted_values.employees)}</strong>
                      </Hint>
                    </td>
                  </tr>
                  {a.accepted_values.headcount_history.length >= 2 && (
                    <tr>
                      <td>Headcount trend</td>
                      <td className="muted">—</td>
                      <td colSpan={2}><HeadcountTrend history={a.accepted_values.headcount_history} /></td>
                    </tr>
                  )}
                </tbody>
              </table>
            </Section>
          )}

          {/* Research */}
          <Section
            id="research"
            title="Public research"
            info="AI research with web search. Each field shows whether something was found. Click a field to see its sources."
            summary={
              okRun ? (
                <>
                  {covFound}/8 found · {covGaps} gaps
                  <Info text={`Last ${okRun.kind} run ${when(okRun.finished_at)} · ${okRun.web_search_requests} web searches · ≈$${okRun.approx_cost_usd.toFixed(3)} · prompt ${okRun.prompt_version}`} />
                </>
              ) : (
                'not researched yet'
              )
            }
            actions={
              <>
                <button
                  className={`small${okRun ? '' : ' primary'}`}
                  disabled={!!busy}
                  onClick={() => run('research', () => api.research(p.id, !!okRun, reviewer || 'user'))}
                  title={okRun ? 'Runs a fresh research pass (new API cost). Old evidence is kept.' : 'Runs standard research with web search'}
                >
                  {busy === 'research' && <Spinner />} {okRun ? 'Re-run' : 'Run research'}
                </button>
                <Hint text={g('deep_research')} align="right">
                  <button className="small" disabled={!!busy || !okRun} onClick={() => setModal('deep')}>Deep Research…</button>
                </Hint>
              </>
            }
            flush
          >
            {busy === 'research' && <div className="section-body small muted"><Spinner /> Searching the web… usually 20–90 seconds.</div>}
            {lastRun?.status === 'failed' && (
              <div className="section-body"><div className="callout error small"><strong>Research failed:</strong> {lastRun.error}</div></div>
            )}
            {a?.accepted_values.deep_research.suggested && (
              <div className="section-body" style={{ paddingBottom: 0 }}>
                <div className="callout warn small">
                  Deep Research suggested <Info text={a.accepted_values.deep_research.reason} />
                </div>
              </div>
            )}
            {okRun?.summary && <div className="section-body small text-2"><Clamp text={okRun.summary} /></div>}
            {a && (
              <div className="coverage-grid" style={{ borderTop: '1px solid var(--border)' }}>
                {Object.entries(a.coverage).map(([field, c]) => (
                  <div
                    key={field}
                    className={`coverage-item${openField === field ? ' open' : ''}`}
                    onClick={() => setOpenField(openField === field ? null : field)}
                    role="button"
                    aria-expanded={openField === field}
                  >
                    <span>
                      {FIELD_LABELS[field] ?? field}
                      {c.evidence_count > 0 && <span className="muted small"> · {c.evidence_count}</span>}
                      {c.manual && <span className="muted small"> · manual</span>}
                    </span>
                    <StatusChip status={c.status} explain={[g(c.status), c.summary].filter(Boolean).join(' ')} />
                  </div>
                ))}
              </div>
            )}
            {openField && a && (
              <div style={{ borderTop: '1px solid var(--border)' }}>
                <div className="section-body spread" style={{ paddingBottom: 6 }}>
                  <h3>{FIELD_LABELS[openField]}</h3>
                  <button className="more" onClick={() => setOpenField(null)}>Close</button>
                </div>
                <EvidenceList
                  items={data.evidence.filter((e) => e.field === openField)}
                  onWithdraw={(e) => run('withdraw', () => api.withdraw(e.id, reviewer || 'user', 'Withdrawn from company page'))}
                />
              </div>
            )}
            {okRun && (okRun.limitations.length > 0 || okRun.dropped_findings.length > 0) && (
              <div className="section-body small" style={{ borderTop: '1px solid var(--border)' }}>
                <details>
                  <summary>
                    Limitations ({okRun.limitations.length}){okRun.dropped_findings.length > 0 && ` · ${okRun.dropped_findings.length} finding(s) removed by validation`}
                  </summary>
                  <ul className="reasons">
                    {okRun.limitations.map((l, i) => <li key={i}>{l}</li>)}
                    {okRun.dropped_findings.map((d, i) => <li key={`d${i}`}>Removed: {d.claim} <span className="muted">({d.reason})</span></li>)}
                  </ul>
                </details>
              </div>
            )}
          </Section>

          {/* Day 30 */}
          <Day30Section data={data} busy={busy} onRelease={() => run('day30', () => api.releaseDay30(p.id))} />

          {/* Proposals */}
          {data.proposals.length > 0 && (
            <Section id="proposals" title="Tier proposals" info="Only a person can approve a tier change." summary={`${data.proposals.length}`} flush>
              <ul className="timeline">
                {data.proposals.map((x) => (
                  <li key={x.id} className="spread">
                    <span className="row">
                      <TierBadge tier={x.from_tier} /> → <TierBadge tier={x.proposed_tier} />
                      <Link to={`/reviews/${x.id}`}>#{x.id}</Link>
                      <Info text={`${x.title}. ${g(x.proposal_type)}`} />
                    </span>
                    <span className={`status-pill${x.status === 'open' ? ' awaiting' : ''}`}>{x.status_label}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}
        </div>

        {/* Right rail */}
        <div className="stack">
          <div className="card card-pad stack" style={{ gap: 10 }}>
            <h2>Actions</h2>
            <button onClick={() => setModal('enrich')}>Add or correct a value…</button>
            <Hint text={g('deep_research')}>
              <button style={{ width: '100%' }} disabled={!!busy || !okRun} onClick={() => setModal('deep')}>Run Deep Research…</button>
            </Hint>
            <details>
              <summary>Testing tools</summary>
              <button className="small" style={{ marginTop: 8 }} onClick={() => setModal('synthetic')}>Add synthetic test observation…</button>
            </details>
          </div>

          {data.evidence.some((e) => e.field === 'note') && (
            <Section id="notes" title="Notes" info="Free-text notes. Explanatory only; they do not change flags." flush>
              <EvidenceList items={data.evidence.filter((e) => e.field === 'note')} />
            </Section>
          )}

          <Section id="history" title="History" info="Every reassessment is a new row; older rows are never edited." summary={`${data.history.length}`} defaultOpen={false} flush>
            <ul className="timeline">
              {data.history.map((h) => (
                <li key={h.id}>
                  <div className="spread">
                    <strong className="small">{TRIGGER_LABELS[h.trigger] ?? h.trigger}</strong>
                    <AttentionBadge attention={h.attention} />
                  </div>
                  <div className="when">#{h.id} · {when(h.created_at)} · {h.stage === 'day30' ? 'Day 30' : 'Day 0'} · rules T{h.baseline_tier ?? '—'} · applied T{h.applied_tier ?? '—'}</div>
                </li>
              ))}
            </ul>
          </Section>

          <Section id="runs" title="Research runs" summary={`${data.research_runs.length}`} defaultOpen={false} flush>
            {data.research_runs.length === 0 ? (
              <div className="empty small">None yet</div>
            ) : (
              <ul className="timeline">
                {data.research_runs.map((r) => (
                  <li key={r.id} className="spread">
                    <span className="small">
                      <strong>{r.kind}</strong> · {r.prompt_version} · ≈${r.approx_cost_usd.toFixed(3)}
                      <Info text={`${when(r.started_at)} · ${r.model} · ${r.web_search_requests} searches · ${r.llm_calls} AI call(s)${r.error ? ` · ${r.error}` : ''}`} />
                    </span>
                    <span className={`badge ${r.status === 'failed' ? 'st-conflicting' : r.status === 'partial' ? 'st-stale' : 'st-found'}`}>{r.status}</span>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section id="audit" title="Audit trail" summary={`${data.audit.length}`} defaultOpen={false} flush>
            <ul className="timeline" style={{ maxHeight: 360, overflow: 'auto' }}>
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

      {modal === 'enrich' && (
        <Modal title="Add or correct a value" onClose={() => { setModal(null); reload() }}>
          <EnrichmentForm prospectId={p.id} reviewer={reviewer} onDone={() => { setModal(null); reload() }} />
        </Modal>
      )}
      {modal === 'deep' && (
        <DeepResearchModal
          prospectId={p.id}
          onClose={() => setModal(null)}
          onConfirm={(fields) => { setModal(null); run('deep', () => api.deepResearch(p.id, reviewer || 'user', fields)) }}
        />
      )}
      {modal === 'synthetic' && <SyntheticModal prospectId={p.id} reviewer={reviewer} onClose={() => { setModal(null); reload() }} />}
      {busy === 'deep' && (
        <div className="modal-backdrop"><div className="modal card-pad"><Spinner /> Running Deep Research… up to two minutes.</div></div>
      )}
    </>
  )
}

function FlagRow({ f }: { f: Flag }) {
  const [open, setOpen] = useState(false)
  const first = f.reasons[0] ?? ''
  const rest = f.reasons.slice(1)
  return (
    <div className="flag-row">
      <FlagChip label={f.label} severity={f.severity} />
      <div className="why small">
        {first}
        {f.stage === 'day30' && <span className="muted"> (Day 30)</span>}
        {open && (
          <>
            {rest.length > 0 && <ul className="reasons">{rest.map((r, j) => <li key={j}>{r}</li>)}</ul>}
            {f.uncertainty.length > 0 && <p className="muted" style={{ marginTop: 6 }}>Uncertainty: {f.uncertainty.join(' ')}</p>}
          </>
        )}
        {(rest.length > 0 || f.uncertainty.length > 0) && (
          <div>
            <button className="more" onClick={() => setOpen(!open)}>{open ? 'Less' : 'Details'}</button>
          </div>
        )}
      </div>
    </div>
  )
}

function HeadcountTrend({ history }: { history: { date: string; value: number; label: string }[] }) {
  const first = history[0]
  const last = history[history.length - 1]
  const pct = first.value ? ((last.value - first.value) / first.value) * 100 : null
  return (
    <span className="small">
      {num(first.value)} → {num(last.value)} <TrendArrow pct={pct} />
      <Info text={`${first.date} to ${last.date}, from dated public figures (may be different sources).`} />
    </span>
  )
}

function Day30Section({ data, busy, onRelease }: { data: ProspectDetail; busy: string | null; onRelease: () => void }) {
  const d = data.day30
  const day30 = data.assessment?.day30
  if (!d.received && !data.day30_pending) {
    return (
      <Section id="day30" title="Day 30 activity" info={g('day30')} summary="no data for this company" defaultOpen={false}>
        <p className="small muted">No 30-day summary exists. Missing activity is not treated as zero travel.</p>
      </Section>
    )
  }
  if (!d.received) {
    return (
      <Section
        id="day30"
        title="Day 30 activity"
        info={g('day30')}
        summary="not received yet"
        actions={
          <button className="small" disabled={!!busy} onClick={onRelease} title="Simulates the summary arriving and reruns the rules">
            {busy === 'day30' && <Spinner />} Receive Day 30 data
          </button>
        }
        defaultOpen={false}
      >
        <p className="small muted">The signup assessment uses no post-signup information.</p>
      </Section>
    )
  }
  return (
    <Section
      id="day30"
      title="Day 30 activity"
      info={`${g('day30')} The Day 0 assessment stays unchanged in History.`}
      summary={day30 ? COMPARISON[day30.comparison] ?? day30.comparison : undefined}
    >
      <div className="grid-3">
        <div className="stat" style={{ padding: 0 }}><div className="v">{num(d.travelers)}</div><div className="l">travelers</div></div>
        <div className="stat" style={{ padding: 0 }}><div className="v">{num(d.bookings)}</div><div className="l">bookings</div></div>
        <div className="stat" style={{ padding: 0 }}>
          <div className="v"><TrendArrow pct={d.trend_pct} /></div>
          <div className="l">
            booking trend <Info text="Bookings in days 16–30 compared with days 1–15." />
          </div>
        </div>
      </div>
      {day30?.notes.length ? <p className="small muted" style={{ marginTop: 10 }}>{day30.notes.join(' ')}</p> : null}
    </Section>
  )
}

function DeepResearchModal({ prospectId, onClose, onConfirm }: { prospectId: string; onClose: () => void; onConfirm: (fields: string[]) => void }) {
  const { data, error } = useAsync<DeepPlan>(() => api.deepPlan(prospectId), [prospectId])
  const [selected, setSelected] = useState<string[] | null>(null)
  const fields = selected ?? (data ? Object.keys(data.focus) : [])
  return (
    <Modal title="Run Deep Research?" onClose={onClose}>
      <ErrorBox error={error} />
      {!data ? (
        <Spinner />
      ) : (
        <div className="stack">
          <div className="callout warn small">{data.note}</div>
          <p className="small">
            Up to <strong>{data.max_searches} web searches</strong>, estimated at most <strong>≈${data.estimated_max_cost_usd.toFixed(2)}</strong>. Fields to investigate:
          </p>
          {Object.entries(data.focus).map(([f, why]) => (
            <label key={f} className="inline">
              <input
                type="checkbox"
                checked={fields.includes(f)}
                onChange={(e) => setSelected(e.target.checked ? [...fields, f] : fields.filter((x) => x !== f))}
              />
              <span><strong>{FIELD_LABELS[f] ?? f}</strong> <span className="muted">— {why}</span></span>
            </label>
          ))}
          <div className="row">
            <button className="primary" disabled={!fields.length} onClick={() => onConfirm(fields)}>Run Deep Research</button>
            <button onClick={onClose}>Cancel</button>
          </div>
        </div>
      )}
    </Modal>
  )
}

function SyntheticModal({ prospectId, reviewer, onClose }: { prospectId: string; reviewer: string; onClose: () => void }) {
  const [field, setField] = useState('employee_count')
  const [claim, setClaim] = useState('Alternative estimate: 90 employees')
  const [value, setValue] = useState('90')
  const [signal, setSignal] = useState('descriptive')
  const [err, setErr] = useState<string | null>(null)
  return (
    <Modal title="Add synthetic test observation" onClose={onClose}>
      <div className="stack">
        <div className="callout synthetic small">This creates a fake observation for testing. It is labelled SYNTHETIC everywhere and is never presented as public research.</div>
        <label>Field
          <select value={field} onChange={(e) => setField(e.target.value)}>
            {Object.entries(FIELD_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>Claim<input value={claim} onChange={(e) => setClaim(e.target.value)} /></label>
        {field === 'employee_count' && <label>Number<input value={value} onChange={(e) => setValue(e.target.value)} /></label>}
        <label>Signal type
          <select value={signal} onChange={(e) => setSignal(e.target.value)}>
            <option value="descriptive">Descriptive</option>
            <option value="direct_travel">Direct travel</option>
            <option value="indirect_growth">Growth</option>
          </select>
        </label>
        <ErrorBox error={err} />
        <div className="row">
          <button
            className="primary"
            onClick={async () => {
              try {
                await api.synthetic(prospectId, { field, claim, value_number: field === 'employee_count' ? Number(value) : null, signal_type: signal, entered_by: reviewer || 'tester' })
                onClose()
              } catch (e) {
                setErr(String((e as Error).message))
              }
            }}
          >
            Add synthetic observation
          </button>
        </div>
      </div>
    </Modal>
  )
}

