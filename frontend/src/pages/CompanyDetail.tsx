import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type DeepPlan, type ProspectDetail } from '../api'
import EnrichmentForm from '../components/EnrichmentForm'
import EvidenceList from '../components/EvidenceList'
import {
  AttentionBadge, ErrorBox, FIELD_LABELS, FlagChip, Modal, Spinner, StatusChip, TierBadge, TRIGGER_LABELS,
  TrendArrow, num, usd, useAsync, useReviewer, when,
} from '../components/ui'

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

  return (
    <>
      <div className="crumb"><Link to="/companies">All companies</Link> / {p.id}</div>
      <div className="page-head">
        <div>
          <h1>{p.company_name}</h1>
          <p>
            <a href={`https://${p.domain}`} target="_blank" rel="noreferrer">{p.domain}</a> · {p.id}
            {a && <> · {a.stage === 'day30' ? 'Day 30 reassessment' : 'Signup (Day 0) assessment'}</>}
          </p>
        </div>
        <div className="row">
          {a && <AttentionBadge attention={a.attention} label={a.attention_label} />}
          {a?.attention && <span className="badge att-none">Priority: {a.priority}</span>}
        </div>
      </div>
      <ErrorBox error={actionError} />
      {hasSynthetic && (
        <div className="callout synthetic banner small">
          This company has a <strong>SYNTHETIC test observation</strong> added for a controlled test. It is not public research and
          is not a claim about the real company.
        </div>
      )}

      <div className="detail-layout">
        <div className="stack">
          {/* What happened / why it matters / what to do */}
          <div className="card">
            <div className="card-pad stack">
              {a && (
                <div className="callout action">
                  <h3>Recommended next step</h3>
                  <p>{a.recommended_action}</p>
                  {unresolved.map((x) => (
                    <p key={x.id} style={{ marginTop: 6 }}>
                      <Link to={`/reviews/${x.id}`}>Open review #{x.id}: Tier {x.from_tier} → Tier {x.proposed_tier} →</Link>
                    </p>
                  ))}
                </div>
              )}
              <div className="grid-3">
                <div>
                  <div className="small muted">Applied tier</div>
                  <div className="row" style={{ marginTop: 4 }}>
                    <TierBadge tier={p.applied_tier} />
                    {p.applied_tier !== p.original_tier && <span className="small muted">changed from T{p.original_tier} by review</span>}
                  </div>
                </div>
                <div>
                  <div className="small muted">Standard-rule baseline</div>
                  <div className="row" style={{ marginTop: 4 }}>
                    <TierBadge tier={a?.baseline.tier} provisional={a?.baseline.provisional} />
                    {a?.baseline.provisional && <span className="small muted">provisional</span>}
                  </div>
                </div>
                <div>
                  <div className="small muted">Original (dataset) tier</div>
                  <div style={{ marginTop: 4 }}><TierBadge tier={p.original_tier} /></div>
                </div>
              </div>
              {a && <p className="small text-2">{a.baseline.basis}</p>}
              {a?.accepted_values.near_threshold && <p className="small text-2">⚠ {a.accepted_values.near_threshold}</p>}
            </div>
          </div>

          {/* Reported vs found */}
          {a && (
            <div className="card">
              <div className="card-head">
                <h2>Reported vs. found</h2>
                <span className="card-sub">Reported values are the company's own / enrichment inputs</span>
              </div>
              <table>
                <thead>
                  <tr><th>Signal</th><th>Reported at signup</th><th>Independent research</th><th>Used for tier rules</th></tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Annual GBV</td>
                    <td>{usd(p.entered_gbv_usd)}</td>
                    <td className="muted">Not researchable (no public source for travel spend)</td>
                    <td>{usd(a.accepted_values.gbv_usd)}</td>
                  </tr>
                  <tr>
                    <td>Employees</td>
                    <td>{p.zi_employees == null ? <span className="muted">missing</span> : num(p.zi_employees)}</td>
                    <td>
                      {a.accepted_values.employee_sources.filter((s) => s.origin === 'ai_research' || s.origin === 'synthetic_test').length === 0 ? (
                        <span className="muted">{a.accepted_values.research_ran ? 'none found' : 'not researched'}</span>
                      ) : (
                        a.accepted_values.employee_sources
                          .filter((s) => s.origin === 'ai_research' || s.origin === 'synthetic_test')
                          .map((s, i) => (
                            <div key={i} className="small">
                              <strong>{num(s.value)}</strong> <span className="muted">— {s.label}{s.as_of ? `, ${s.as_of}` : ''}{s.stale ? ' (stale)' : ''}</span>
                            </div>
                          ))
                      )}
                    </td>
                    <td>
                      {a.accepted_values.employees == null ? <span className="muted">unknown</span> : <strong>{num(a.accepted_values.employees)}</strong>}
                      {a.accepted_values.employee_source && <div className="small muted">{a.accepted_values.employee_source}</div>}
                    </td>
                  </tr>
                  {a.accepted_values.headcount_history.length >= 2 && (
                    <tr>
                      <td>Headcount trend</td>
                      <td className="muted">—</td>
                      <td colSpan={2}>
                        <HeadcountTrend history={a.accepted_values.headcount_history} />
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* Flags */}
          {a && (
            <div className="card">
              <div className="card-head">
                <h2>Why this company was flagged</h2>
                <span className="card-sub">Each flag lists its evidence and open uncertainty</span>
              </div>
              <div className="card-pad">
                {a.flags.length === 0 ? (
                  <p className="muted">No reason flags. {a.recommended_action}</p>
                ) : (
                  a.flags.map((f, i) => (
                    <div className="flag-card" key={i}>
                      <div className="row">
                        <FlagChip label={f.label} severity={f.severity} />
                        <span className="small muted">{f.severity} · {f.stage === 'day30' ? 'from Day 30 activity' : 'signup-time evidence'}</span>
                      </div>
                      <ul className="reasons">
                        {f.reasons.map((r, j) => <li key={j}>{r}</li>)}
                      </ul>
                      {f.uncertainty.length > 0 && (
                        <div className="small muted" style={{ marginTop: 6 }}>Uncertainty: {f.uncertainty.join(' ')}</div>
                      )}
                    </div>
                  ))
                )}
                {a.accepted_values.suppressed_proposals.map((s, i) => (
                  <p key={i} className="small muted" style={{ marginTop: 8 }}>Not re-proposed: {s.title}. {s.reason}</p>
                ))}
              </div>
            </div>
          )}

          {/* Research */}
          <div className="card">
            <div className="card-head">
              <div>
                <h2>Public research</h2>
                <div className="card-sub">
                  {okRun
                    ? `Last ${okRun.kind} research ${when(okRun.finished_at)} · ${okRun.web_search_requests} web searches · ≈$${okRun.approx_cost_usd.toFixed(3)}`
                    : 'No research yet. Fields show “Not searched”.'}
                </div>
              </div>
              <div className="row">
                <button
                  className={okRun ? '' : 'primary'}
                  disabled={!!busy}
                  onClick={() => run('research', () => api.research(p.id, !!okRun, reviewer || 'user'))}
                  title={okRun ? 'Runs a fresh standard research pass (new API usage). Older evidence is kept.' : 'Runs standard research with web search'}
                >
                  {busy === 'research' && <Spinner />} {okRun ? 'Re-run standard research' : 'Run standard research'}
                </button>
                <button disabled={!!busy || !okRun} onClick={() => setModal('deep')} title="Additional, targeted research. Asks for confirmation first.">
                  Run Deep Research…
                </button>
              </div>
            </div>
            {busy === 'research' && <div className="card-pad small muted"><Spinner /> Searching the web and extracting findings. This usually takes 20–90 seconds.</div>}
            {lastRun?.status === 'failed' && (
              <div className="card-pad"><div className="callout error small"><strong>Research failed:</strong> {lastRun.error} No research findings were stored or simulated.</div></div>
            )}
            {a?.accepted_values.deep_research.suggested && (
              <div className="card-pad" style={{ paddingBottom: 0 }}>
                <div className="callout warn small">Deep Research suggested: {a.accepted_values.deep_research.reason}</div>
              </div>
            )}
            {okRun?.summary && <div className="card-pad"><p>{okRun.summary}</p></div>}
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
                    <StatusChip status={c.status} />
                  </div>
                ))}
              </div>
            )}
            {openField && a && (
              <div style={{ borderTop: '1px solid var(--border)' }}>
                <div className="card-pad" style={{ paddingBottom: 4 }}>
                  <h3>{FIELD_LABELS[openField]}</h3>
                  {a.coverage[openField]?.summary && <p className="small text-2" style={{ marginTop: 4 }}>{a.coverage[openField].summary}</p>}
                </div>
                <EvidenceList
                  items={data.evidence.filter((e) => e.field === openField)}
                  onWithdraw={(e) => run('withdraw', () => api.withdraw(e.id, reviewer || 'user', 'Withdrawn from company page'))}
                />
              </div>
            )}
            {okRun && (okRun.limitations.length > 0 || okRun.dropped_findings.length > 0) && (
              <div className="card-pad small" style={{ borderTop: '1px solid var(--border)' }}>
                {okRun.limitations.length > 0 && (
                  <>
                    <strong>Research limitations</strong>
                    <ul className="reasons">{okRun.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>
                  </>
                )}
                {okRun.dropped_findings.length > 0 && (
                  <details>
                    <summary>{okRun.dropped_findings.length} finding(s) removed by validation</summary>
                    <ul className="reasons">
                      {okRun.dropped_findings.map((d, i) => <li key={i}>{d.claim} — <span className="muted">{d.reason}</span></li>)}
                    </ul>
                  </details>
                )}
              </div>
            )}
          </div>

          {/* Day 30 */}
          <Day30Card data={data} busy={busy} onRelease={() => run('day30', () => api.releaseDay30(p.id))} />

          {/* Proposals */}
          {data.proposals.length > 0 && (
            <div className="card">
              <div className="card-head"><h2>Tier proposals</h2></div>
              <ul className="timeline">
                {data.proposals.map((x) => (
                  <li key={x.id} className="spread">
                    <span>
                      <Link to={`/reviews/${x.id}`}>#{x.id} {x.title}</Link>
                      <div className="when">{x.proposal_type === 'standard_rule_correction' ? 'Standard-rule correction' : 'Evidence-based override'} · {x.stage === 'day30' ? 'Day 30' : 'Day 0'}</div>
                    </span>
                    <span className={`status-pill${x.status === 'open' ? ' awaiting' : ''}`}>{x.status_label}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Right rail */}
        <div className="stack">
          <div className="card card-pad stack">
            <h2>Actions</h2>
            <button onClick={() => setModal('enrich')}>Add or correct a value…</button>
            <button disabled={!!busy || !okRun} onClick={() => setModal('deep')}>Run Deep Research…</button>
            <details>
              <summary>Testing tools</summary>
              <p className="small muted" style={{ margin: '6px 0' }}>Adds a clearly labelled synthetic observation to test conflict handling. Never shown as public research.</p>
              <button className="small" onClick={() => setModal('synthetic')}>Add synthetic test observation…</button>
            </details>
          </div>

          {data.evidence.some((e) => e.field === 'note') && (
            <div className="card">
              <div className="card-head"><h2>Notes</h2><span className="card-sub">Explanatory only</span></div>
              <EvidenceList items={data.evidence.filter((e) => e.field === 'note')} />
            </div>
          )}

          <div className="card">
            <div className="card-head"><h2>Assessment history</h2><span className="card-sub">Earlier rows are never edited</span></div>
            <ul className="timeline">
              {data.history.map((h) => (
                <li key={h.id}>
                  <div className="spread">
                    <strong className="small">#{h.id} {TRIGGER_LABELS[h.trigger] ?? h.trigger}</strong>
                    <span className="badge att-none">{h.stage === 'day30' ? 'Day 30' : 'Day 0'}</span>
                  </div>
                  <div className="when">{when(h.created_at)}</div>
                  <div className="row small" style={{ marginTop: 4 }}>
                    Baseline <TierBadge tier={h.baseline_tier} /> Applied <TierBadge tier={h.applied_tier} />
                    <AttentionBadge attention={h.attention} />
                  </div>
                  {h.flags.length > 0 && <div className="small muted" style={{ marginTop: 4 }}>{h.flags.map((f) => f.replace('_', ' ')).join(', ')}</div>}
                </li>
              ))}
            </ul>
          </div>

          <div className="card">
            <div className="card-head"><h2>Research runs</h2></div>
            {data.research_runs.length === 0 ? (
              <div className="empty small">None yet</div>
            ) : (
              <ul className="timeline">
                {data.research_runs.map((r) => (
                  <li key={r.id}>
                    <div className="spread">
                      <strong className="small">#{r.id} {r.kind} · {r.prompt_version}</strong>
                      <span className={`badge ${r.status === 'failed' ? 'st-conflicting' : r.status === 'partial' ? 'st-stale' : 'st-found'}`}>{r.status}</span>
                    </div>
                    <div className="when">
                      {when(r.started_at)} · {r.model} · {r.web_search_requests} searches · {r.llm_calls} LLM call(s) · ≈${r.approx_cost_usd.toFixed(3)}
                    </div>
                    {r.error && <div className="small muted">{r.error}</div>}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="card">
            <div className="card-head"><h2>Audit trail</h2></div>
            <ul className="timeline" style={{ maxHeight: 360, overflow: 'auto' }}>
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
      {modal === 'synthetic' && (
        <SyntheticModal prospectId={p.id} reviewer={reviewer} onClose={() => { setModal(null); reload() }} />
      )}
      {busy === 'deep' && (
        <div className="modal-backdrop"><div className="modal card-pad"><Spinner /> Running Deep Research… this can take up to two minutes.</div></div>
      )}
    </>
  )
}

function HeadcountTrend({ history }: { history: { date: string; value: number; label: string }[] }) {
  const first = history[0]
  const last = history[history.length - 1]
  const pct = first.value ? ((last.value - first.value) / first.value) * 100 : null
  return (
    <span className="small">
      {num(first.value)} ({first.date}) → {num(last.value)} ({last.date}) <TrendArrow pct={pct} label="Change between two dated public figures" />
      <span className="muted"> · from dated public figures, may come from different sources</span>
    </span>
  )
}

function Day30Card({ data, busy, onRelease }: { data: ProspectDetail; busy: string | null; onRelease: () => void }) {
  const d = data.day30
  const a = data.assessment
  if (!d.received && !data.day30_pending) {
    return (
      <div className="card card-pad">
        <h2>Post-signup activity (Day 30)</h2>
        <p className="small muted" style={{ marginTop: 4 }}>No 30-day activity summary exists for this company in the dataset. Missing activity is not treated as zero travel.</p>
      </div>
    )
  }
  if (!d.received) {
    return (
      <div className="card card-pad spread">
        <div>
          <h2>Post-signup activity (Day 30)</h2>
          <p className="small muted" style={{ marginTop: 4 }}>Not received yet. The signup assessment uses no post-signup information.</p>
        </div>
        <button disabled={!!busy} onClick={onRelease} title="Simulates the 30-day summary arriving and runs a rules-only reassessment">
          {busy === 'day30' && <Spinner />} Receive Day 30 activity
        </button>
      </div>
    )
  }
  const day30 = a?.day30
  return (
    <div className="card">
      <div className="card-head">
        <h2>Post-signup activity (Day 30)</h2>
        <span className="card-sub">Received {when(d.released_at)} · compared with Day 0 assessment #{day30?.compared_with_assessment_id}</span>
      </div>
      <div className="card-pad stack">
        <div className="grid-3">
          <div className="stat" style={{ padding: 0 }}><div className="v">{num(d.travelers)}</div><div className="l">travelers</div></div>
          <div className="stat" style={{ padding: 0 }}><div className="v">{num(d.bookings)}</div><div className="l">bookings in 30 days</div></div>
          <div className="stat" style={{ padding: 0 }}>
            <div className="v"><TrendArrow pct={d.trend_pct} label="Bookings in days 16–30 vs days 1–15" /></div>
            <div className="l">bookings, days 16–30 vs 1–15</div>
          </div>
        </div>
        {day30 && (
          <p className="small">
            Compared with signup: <strong>{({ strengthens: 'strengthens the earlier signal', weakens: 'weakens the earlier signal', new_signal: 'new signal not seen at signup', consistent: 'consistent with the earlier assessment', neutral: 'no conclusion' } as Record<string, string>)[day30.comparison] ?? day30.comparison}</strong>.
            {day30.notes.map((n, i) => <span key={i}> {n}</span>)}
          </p>
        )}
        <p className="small muted">Booking counts are not dollar GBV, and 30 days may not represent a full year. The Day 0 assessment is kept unchanged in the history.</p>
      </div>
    </div>
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

