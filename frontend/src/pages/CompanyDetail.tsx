import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type Assessment, type DeepPlan, type Flag, type ProspectDetail } from '../api'
import EvidenceList from '../components/EvidenceList'
import { Clamp, Hint, Info, Section } from '../components/Section'
import {
  AttentionBadge, CompanySiteBadge, ErrorBox, FIELD_LABELS, FlagChip, Modal, Spinner, StatusChip, TierBadge, hostOf, sourceText,
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

// Research fields a salesperson can add their own finding to (maps to the enrichment API).
const ADDABLE: Record<string, { param: string; placeholder: string }> = {
  travel_indicators: { param: 'travel_requirement', placeholder: 'e.g. Sales team travels to clients across Europe monthly' },
  funding_financial: { param: 'funding', placeholder: 'e.g. Raised a $20M Series B in 2026' },
  recent_expansion: { param: 'expansion', placeholder: 'e.g. Opened a New York office' },
  geographic_footprint: { param: 'geographic_footprint', placeholder: 'e.g. Offices in UK, US and Germany' },
}

export default function CompanyDetail() {
  const { id = '' } = useParams()
  const { data, error, loading, reload } = useAsync(() => api.prospect(id), [id])
  const [reviewer] = useReviewer()
  const [busy, setBusy] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [deepOpen, setDeepOpen] = useState(false)
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

  const saved = (before: Assessment | null, after: Assessment) => {
    const changed = before?.baseline.tier !== after.baseline.tier || before?.attention !== after.attention
    setNotice(`Saved. Rules rerun with no AI call${changed ? `: rules now say Tier ${after.baseline.tier}, attention ${after.attention_label}.` : '. Nothing else changed.'}`)
    reload()
  }

  const { prospect: p, assessment: a } = data
  const lastRun = data.research_runs[0]
  const okRun = data.research_runs.find((r) => r.status === 'ok' || r.status === 'partial')
  const unresolved = data.proposals.filter((x) => x.status === 'open' || x.status === 'needs_info')
  const hasSynthetic = data.evidence.some((e) => e.origin === 'synthetic_test' && !e.superseded_by)
  const coverage = Object.values(a?.coverage ?? {})
  const covFound = coverage.filter((c) => c.status === 'found').length
  const covGaps = coverage.filter((c) => ['not_found', 'conflicting', 'stale'].includes(c.status)).length

  return (
    <div className="single">
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
      {notice && (
        <div className="callout action banner small spread">
          <span>{notice}</span>
          <button className="more" onClick={() => setNotice(null)}>Dismiss</button>
        </div>
      )}
      {hasSynthetic && (
        <div className="callout synthetic banner small">
          Contains a <strong>SYNTHETIC test observation</strong>, which is not real research. <Info text={g('synthetic')} />
        </div>
      )}

      <div className="stack">
        {/* Tiers + next step */}
        <div className="card">
          <div className="hero hero-tight">
            <div>
              <div className="label">Applied tier <Info text={g('applied_tier')} align="left" /></div>
              <TierBadge tier={p.applied_tier} />
            </div>
            <div>
              <div className="label">Rules say <Info text={a ? `${g('baseline_tier')} ${a.baseline.basis}` : g('baseline_tier')} /></div>
              <TierBadge tier={a?.baseline.tier} provisional={a?.baseline.provisional} />
            </div>
            {a && (
              <div className="next-step">
                <strong>Next step</strong>
                <span>{a.recommended_action}</span>
                {unresolved.map((x) => (
                  <Link key={x.id} to={`/reviews/${x.id}`} style={{ marginLeft: 'auto', whiteSpace: 'nowrap' }}>
                    Open review #{x.id} →
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Values */}
        {a && (
          <Section id="values" title="Values" info="The numbers the tier rules use, next to what public research found. Click Edit to correct a value; the rules rerun instantly with no AI call." flush>
            <table className="values">
              <thead>
                <tr><th></th><th>Used by the tier rules</th><th>Research found</th><th></th></tr>
              </thead>
              <tbody>
                <tr>
                  <td className="vlabel">Annual GBV</td>
                  <td>
                    <Hint text="Reported by the company at signup (fictional scenario value). Used as-is by the tier rules.">
                      <strong className="vbig">{usd(a.accepted_values.gbv_usd)}</strong>
                    </Hint>{' '}
                    <span className="muted small">reported by the company</span>
                  </td>
                  <td className="muted small">— <Info text="Travel spend is not public, so GBV cannot be researched." /></td>
                  <td></td>
                </tr>
                <EmployeeRow data={data} reviewer={reviewer} onSaved={saved} />
                {a.accepted_values.headcount_history.length >= 2 && (
                  <tr>
                    <td className="vlabel">Headcount trend</td>
                    <td colSpan={3}><HeadcountTrend history={a.accepted_values.headcount_history} /></td>
                  </tr>
                )}
              </tbody>
            </table>
          </Section>
        )}

        {/* Why flagged */}
        {a && (
          <Section
            id="flags"
            title="Why it was flagged"
            info="Each flag says why it fired. Hover a flag for its meaning; open a row for the evidence and the uncertainty."
            summary={a.flags.length ? `${a.flags.length} flag${a.flags.length > 1 ? 's' : ''}` : 'none'}
          >
            {a.flags.length === 0 ? <p className="muted small">No flags.</p> : a.flags.map((f, i) => <FlagRow key={i} f={f} />)}
          </Section>
        )}

        {/* Research */}
        <Section
          id="research"
          title="Public research"
          info="AI research with web search. Each field shows whether something was found. Click a field to see its sources or add your own finding."
          summary={
            okRun ? (
              <>
                {okRun.replayed && (
                  <span className="badge rel rel-synthetic" style={{ fontWeight: 600 }} title="Recorded real Claude run replayed in demo mode (no API key)">Recorded</span>
                )}
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
                <button className="small" disabled={!!busy || !okRun} onClick={() => setDeepOpen(true)}>Deep Research…</button>
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
                companyDomain={p.domain}
                items={data.evidence.filter((e) => e.field === openField)}
                onWithdraw={(e) => run('withdraw', () => api.withdraw(e.id, reviewer || 'user', 'Withdrawn from company page'))}
              />
              {ADDABLE[openField] && (
                <AddFinding prospectId={p.id} field={openField} reviewer={reviewer} onSaved={saved} />
              )}
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

        <Day30Section data={data} busy={busy} onRelease={() => run('day30', () => api.releaseDay30(p.id))} />

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

      {deepOpen && (
        <DeepResearchModal
          prospectId={p.id}
          onClose={() => setDeepOpen(false)}
          onConfirm={(fields) => { setDeepOpen(false); run('deep', () => api.deepResearch(p.id, reviewer || 'user', fields)) }}
        />
      )}
      {busy === 'deep' && (
        <div className="modal-backdrop"><div className="modal card-pad"><Spinner /> Running Deep Research… up to two minutes.</div></div>
      )}
    </div>
  )
}

/** Employee row with inline correction. */
function EmployeeRow({ data, reviewer, onSaved }: { data: ProspectDetail; reviewer: string; onSaved: (b: Assessment | null, a: Assessment) => void }) {
  const a = data.assessment!
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState('')
  const [url, setUrl] = useState('')
  const [verified, setVerified] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const found = a.accepted_values.employee_sources.filter((s) => s.origin === 'ai_research' || s.origin === 'synthetic_test')
  const usedSource = a.accepted_values.employee_sources.find((s) => s.label === a.accepted_values.employee_source)

  const save = async () => {
    setBusy(true)
    setErr(null)
    try {
      const r = await api.enrich(data.prospect.id, {
        param: 'employee_count', value, entered_by: reviewer, source_url: url || undefined, verified: verified && !!url, accepted: true,
      })
      setEditing(false)
      setValue('')
      setUrl('')
      setVerified(false)
      onSaved(r.before, r.after)
    } catch (e) {
      setErr(String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <tr>
        <td className="vlabel">Employees</td>
        <td>
          <Hint text={usedSource ? sourceText(usedSource) : 'No employee count from any source yet.'}>
            <strong className="vbig">{a.accepted_values.employees == null ? 'unknown' : num(a.accepted_values.employees)}</strong>
          </Hint>{' '}
          <span className="muted small">{a.accepted_values.employee_source ?? 'no estimate'}</span>
        </td>
        <td>
          {found.length === 0 ? (
            <span className="muted small">{a.accepted_values.research_ran ? 'none found' : 'not researched'}</span>
          ) : (
            <span className="row" style={{ gap: 6 }}>
              {found.map((s, i) => (
                <Hint key={i} text={sourceText(s)}>
                  <span className={`badge rel rel-${s.company_site ? 'primary own-site' : s.reliability}`}>
                    {num(s.value)}
                    {s.company_site && <CompanySiteBadge domain={hostOf(s.url) ?? data.prospect.domain} date={s.as_of} plain />}
                  </span>
                </Hint>
              ))}
            </span>
          )}
        </td>
        <td className="vedit">
          {!editing && <button className="small" onClick={() => setEditing(true)} aria-label="Edit employees">✎ Edit</button>}
        </td>
      </tr>
      {editing && (
        <tr className="edit-row">
          <td></td>
          <td colSpan={3}>
            <div className="row">
              <input autoFocus inputMode="numeric" placeholder="Correct number" value={value} onChange={(e) => setValue(e.target.value)}
                aria-label="Correct employee count" style={{ width: 140 }} />
              <input type="url" placeholder="Source URL (optional)" value={url} onChange={(e) => setUrl(e.target.value)} style={{ flex: 1, minWidth: 200 }} />
              <label className="inline small">
                <input type="checkbox" checked={verified} disabled={!url} onChange={(e) => setVerified(e.target.checked)} />
                I checked the source
                <Info text="Checked against a source = verified: it settles conflicts. Without a source the value is used but marked unverified." />
              </label>
              <button className="primary small" disabled={busy || !reviewer || !/^\d[\d,]*$/.test(value.trim())} onClick={save}>
                {busy && <Spinner />} Save
              </button>
              <button className="small" onClick={() => { setEditing(false); setErr(null) }}>Cancel</button>
            </div>
            {!reviewer && <p className="small muted" style={{ marginTop: 6 }}>Enter your name under “Acting as” in the sidebar to save.</p>}
            {err && <div className="callout error small" style={{ marginTop: 6 }}>{err}</div>}
          </td>
        </tr>
      )}
    </>
  )
}

/** Inline "add your own finding" inside an opened research field. */
function AddFinding({ prospectId, field, reviewer, onSaved }: { prospectId: string; field: string; reviewer: string; onSaved: (b: Assessment | null, a: Assessment) => void }) {
  const spec = ADDABLE[field]
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState('')
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  if (!open) {
    return (
      <div className="section-body" style={{ paddingTop: 6 }}>
        <button className="more" onClick={() => setOpen(true)}>+ Add what you know</button>
      </div>
    )
  }
  return (
    <div className="section-body stack" style={{ gap: 8, borderTop: '1px solid var(--border)' }}>
      <input autoFocus placeholder={spec.placeholder} value={value} onChange={(e) => setValue(e.target.value)} aria-label="Your finding" />
      <div className="row">
        <input type="url" placeholder="Source URL (optional)" value={url} onChange={(e) => setUrl(e.target.value)} style={{ flex: 1 }} />
        <button className="primary small" disabled={busy || !reviewer || !value.trim()} onClick={async () => {
          setBusy(true)
          setErr(null)
          try {
            const r = await api.enrich(prospectId, { param: spec.param, value, entered_by: reviewer, source_url: url || undefined, verified: !!url, accepted: true })
            setOpen(false)
            setValue('')
            setUrl('')
            onSaved(r.before, r.after)
          } catch (e) {
            setErr(String((e as Error).message))
          } finally {
            setBusy(false)
          }
        }}>
          {busy && <Spinner />} Save
        </button>
        <button className="small" onClick={() => setOpen(false)}>Cancel</button>
      </div>
      {!reviewer && <p className="small muted">Enter your name under “Acting as” in the sidebar to save.</p>}
      {err && <div className="callout error small">{err}</div>}
    </div>
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

