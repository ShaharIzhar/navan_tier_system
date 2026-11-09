import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type Assessment, type Flag, type ProspectDetail } from '../api'
import EvidenceList from '../components/EvidenceList'
import { Suggestion, TierArrow } from '../components/ProspectTable'
import { useConfirm } from '../components/confirm'
import { Clamp, Hint, Info, Section } from '../components/Section'
import {
  AttentionBadge, CompanySiteBadge, ErrorBox, FIELD_LABELS, FlagChip, Spinner, StatusChip, TierBadge, hostOf, sourceText,
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
  const confirm = useConfirm()
  const [openField, setOpenField] = useState<string | null>(null)
  const [highlight, setHighlight] = useState<{ id: number; at: number } | null>(null)
  useEffect(() => {
    if (!highlight) return
    const t = setTimeout(() => document.getElementById(`ev-${highlight.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 60)
    return () => clearTimeout(t)
  }, [highlight])
  const showEvidence = (field: string, evidenceId: number) => {
    setOpenField(field)
    setHighlight({ id: evidenceId, at: Date.now() })
  }

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

  const runDeep = async () => {
    const ok = await confirm({
      title: `Run Deep Research for ${data.prospect.company_name}?`,
      confirmLabel: 'Run Deep Research',
      body: <p>A more thorough search of all areas, including travel requirements and expansion. Takes up to two minutes. Current findings are kept.</p>,
    })
    if (ok) run('deep', () => api.deepResearch(data.prospect.id, reviewer || 'user'))
  }

  const saved = (before: Assessment | null, after: Assessment) => {
    const changed = before?.baseline.tier !== after.baseline.tier || before?.attention !== after.attention
    setNotice(`Saved. Rules rerun with no AI call${changed ? `: rules now say Tier ${after.baseline.tier}, attention ${after.attention_label}.` : '. Nothing else changed.'}`)
    reload()
  }

  const { prospect: p, assessment: a } = data
  const lastRun = data.research_runs[0]
  const okRun = data.research_runs.find((r) => r.status === 'ok' || r.status === 'partial')
  const hasSynthetic = data.evidence.some((e) => e.origin === 'synthetic_test' && !e.superseded_by)
  const coverage = Object.values(a?.coverage ?? {})
  const covFound = coverage.filter((c) => c.status === 'found').length
  const covGaps = coverage.filter((c) => ['not_found', 'conflicting', 'stale'].includes(c.status)).length

  return (
    <div className="single">
      <div className="crumb"><Link to="/companies">All companies</Link> / {p.id}</div>
      <div className="page-head">
        <div>
          <h1 className="row" style={{ gap: 10 }}>
            {p.company_name}
            <span className="tier-change">
              <TierBadge tier={p.applied_tier} />
              {p.suggestion && <Suggestion s={p.suggestion} />}
            </span>
          </h1>
          <p className="small">
            <a href={`https://${p.domain}`} target="_blank" rel="noreferrer">{p.domain}</a> · {p.id} ·{' '}
            <Hint text={a?.stage === 'day30' ? 'Includes the first 30 days on Navan.' : 'Based on signup information only.'}>
              {a?.stage === 'day30' ? 'Day 30' : 'Signup (Day 0)'}
            </Hint>
          </p>
        </div>
        <div className="row">
          {a && <AttentionBadge attention={a.attention} label={a.attention_label} />}
          {a?.attention && (
            <Hint text={g('priority')} align="right">
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
          Contains <strong>test data</strong>, not real research.
        </div>
      )}

      <div className="stack">
        {/* Values */}
        {a && (
          <Section id="values" title="Values" info="What we use vs. what research found. Click Edit to correct." flush>
            <table className="values">
              <thead>
                <tr><th></th><th>Used by the tier rules</th><th>Research found</th><th></th></tr>
              </thead>
              <tbody>
                <tr>
                  <td className="vlabel">Annual GBV</td>
                  <td>
                    <Hint text="Reported by the company at signup.">
                      <strong className="vbig">{usd(a.accepted_values.gbv_usd)}</strong>
                    </Hint>{' '}
                    <span className="muted small">reported by the company</span>
                  </td>
                  <td className="muted small">— <Info text="Travel spend isn’t public." /></td>
                  <td></td>
                </tr>
                <EmployeeRow data={data} reviewer={reviewer} onSaved={saved} onShowEvidence={(id) => showEvidence('employee_count', id)} />
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
            info="Why this company stands out."
            summary={a.flags.length ? `${a.flags.length} flag${a.flags.length > 1 ? 's' : ''}` : 'none'}
          >
            {a.flags.length === 0 ? <p className="muted small">No flags.</p> : a.flags.map((f, i) => <FlagRow key={i} f={f} />)}
          </Section>
        )}

        {/* Research */}
        <Section
          id="research"
          openSignal={highlight?.at}
          title="Public research"
          info="What public sources say. Click a field for details."
          summary={
            okRun ? (
              <>
                {okRun.replayed && (
                  <span className="badge rel rel-synthetic" style={{ fontWeight: 600 }} title="Recorded real Claude run replayed in demo mode (no API key)">Recorded</span>
                )}
                {covFound}/8 found · {covGaps} gaps
                <Info text={`Last updated ${when(okRun.finished_at)}.`} />
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
                onClick={async () => {
                  const ok = await confirm({
                    title: `${okRun ? 'Re-run' : 'Run'} research for ${p.company_name}?`,
                    confirmLabel: okRun ? 'Re-run research' : 'Run research',
                    body: <p>Checks industry, locations, employees, funding and hiring. Takes about a minute.{okRun ? ' Updates the current results.' : ''}</p>,
                  })
                  if (ok) run('research', () => api.research(p.id, !!okRun, reviewer || 'user'))
                }}
              >
                {busy === 'research' && <Spinner />} {okRun ? 'Re-run' : 'Run research'}
              </button>
              <Hint text={g('deep_research')} align="right">
                <button className="small" disabled={!!busy || !okRun} onClick={runDeep}>Deep Research…</button>
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
          {a && okRun && Object.values(a.coverage).some((c) => c.status === 'not_searched') && (
            <div className="section-body small muted" style={{ paddingTop: 0 }}>
              Fields marked “Not searched” are covered by Deep Research. Not searched does not mean nothing exists.
            </div>
          )}
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
              <div className="section-body spread" style={{ paddingBottom: 6 }}>
                <h3>{FIELD_LABELS[openField]}</h3>
                <button className="more" onClick={() => setOpenField(null)}>Close</button>
              </div>
              <EvidenceList
                companyDomain={p.domain}
                highlightId={highlight?.id}
                items={data.evidence.filter((e) => e.field === openField)}
                onWithdraw={async (e) => {
                  const ok = await confirm({
                    title: 'Withdraw this value?',
                    confirmLabel: 'Withdraw',
                    tone: 'danger',
                    body: <p>“{e.claim}” will no longer be used.</p>,
                  })
                  if (ok) run('withdraw', () => api.withdraw(e.id, reviewer || 'user', 'Withdrawn from company page'))
                }}
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

        <Day30Section data={data} busy={busy} onRelease={async () => {
          const ok = await confirm({
            title: `Receive Day 30 activity for ${p.company_name}?`,
            confirmLabel: 'Receive Day 30 data',
            body: <p>Adds the company’s first 30 days on Navan. Strong activity may suggest a tier change for review. This can’t be undone.</p>,
          })
          if (ok) run('day30', () => api.releaseDay30(p.id))
        }} />

        {data.proposals.length > 0 && (
          <Section id="proposals" title="Tier proposals" info="Tier changes need a person’s approval." summary={`${data.proposals.length}`} flush>
            <ul className="timeline">
              {data.proposals.map((x) => (
                <li key={x.id} className="spread">
                  <span className="row">
                    <TierBadge tier={x.from_tier} /> <TierArrow from={x.from_tier} to={x.proposed_tier} />
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

      {busy === 'deep' && (
        <div className="modal-backdrop"><div className="modal card-pad"><Spinner /> Running Deep Research… up to two minutes.</div></div>
      )}
    </div>
  )
}

/** Employee row with inline correction. */
function EmployeeRow({ data, reviewer, onSaved, onShowEvidence }: { data: ProspectDetail; reviewer: string; onSaved: (b: Assessment | null, a: Assessment) => void; onShowEvidence: (evidenceId: number) => void }) {
  const a = data.assessment!
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState('')
  const [url, setUrl] = useState('')
  const [verified, setVerified] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const found = a.accepted_values.employee_sources.filter((s) => s.origin === 'ai_research' || s.origin === 'synthetic_test')
  const usedSource = a.accepted_values.employee_sources.find((s) => s.label === a.accepted_values.employee_source)

  const confirm = useConfirm()
  const save = async () => {
    const newValue = Number(value.replace(/,/g, ''))
    const before = rulesTier(a.accepted_values.gbv_usd, a.accepted_values.employees)
    const after = rulesTier(a.accepted_values.gbv_usd, newValue)
    if (before !== after) {
      const ok = await confirm({
        title: `Change employees to ${num(newValue)}?`,
        confirmLabel: 'Save and rerun rules',
        body: <p>This points to <strong>Tier {after}</strong> instead of Tier {before}. A tier change will be suggested for review; nothing changes until someone approves.</p>,
      })
      if (!ok) return
    }
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
            {usedSource?.evidence_id ? (
              <button type="button" className="value-link" onClick={() => onShowEvidence(usedSource.evidence_id!)}>
                <strong className="vbig">{num(a.accepted_values.employees)}</strong>
              </button>
            ) : (
              <strong className="vbig">{a.accepted_values.employees == null ? 'unknown' : num(a.accepted_values.employees)}</strong>
            )}
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
                  <button
                    type="button"
                    className={`badge rel rel-${s.company_site ? 'primary own-site' : s.reliability} chip-link`}
                    onClick={() => s.evidence_id && onShowEvidence(s.evidence_id)}
                    aria-label={`Show evidence for ${num(s.value)}`}
                  >
                    {num(s.value)}
                    {s.company_site && <CompanySiteBadge domain={hostOf(s.url) ?? data.prospect.domain} date={s.as_of} plain />}
                  </button>
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
                <Info text="Tick if you checked the source. Checked values settle disagreements." />
              </label>
              <button className="primary small" disabled={busy || !reviewer || !/^\d[\d,]*$/.test(value.trim())} onClick={save}>
                {busy && <Spinner />} Save
              </button>
              <button className="small" onClick={() => { setEditing(false); setErr(null) }}>Cancel</button>
            </div>
            {!reviewer && <p className="small muted" style={{ marginTop: 6 }}>Set your name (top right) to save.</p>}
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
      {!reviewer && <p className="small muted">Set your name (top right) to save.</p>}
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
      <Info text={`${first.date} → ${last.date}.`} />
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
      info={g('day30')}
      summary={day30 ? COMPARISON[day30.comparison] ?? day30.comparison : undefined}
    >
      <div className="grid-3">
        <div className="stat" style={{ padding: 0 }}><div className="v">{num(d.travelers)}</div><div className="l">travelers</div></div>
        <div className="stat" style={{ padding: 0 }}><div className="v">{num(d.bookings)}</div><div className="l">bookings</div></div>
        <div className="stat" style={{ padding: 0 }}>
          <div className="v"><TrendArrow pct={d.trend_pct} /></div>
          <div className="l">
            booking trend <Info text="Second half of the month vs. the first." />
          </div>
        </div>
      </div>
      {day30?.notes.length ? <p className="small muted" style={{ marginTop: 10 }}>{day30.notes.join(' ')}</p> : null}
    </Section>
  )
}

function rulesTier(gbv: number | null, employees: number | null): number | null {
  if (gbv == null || gbv < 0) return null
  if (gbv >= 500_000) return 1
  if (gbv >= 100_000 || (employees ?? 0) >= 150) return 2
  return 3
}
