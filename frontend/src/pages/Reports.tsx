import { Link } from 'react-router-dom'
import { api } from '../api'
import { Info, Section } from '../components/Section'
import { ErrorBox, FIELD_LABELS, Spinner, StatusChip, useAsync } from '../components/ui'
import { g } from '../glossary'

/* eslint-disable @typescript-eslint/no-explicit-any */

const ATT_LABEL: Record<string, string> = { review_now: 'Review Now', review_suggested: 'Review Suggested', monitor: 'Monitor', none: 'No action' }
const ATT_COLOR: Record<string, string> = { review_now: 'var(--red)', review_suggested: 'var(--amber)', monitor: 'var(--slate)', none: 'var(--border-strong)' }
const STATUS_COLOR: Record<string, string> = {
  found: 'var(--green)', not_found: 'var(--border-strong)', conflicting: 'var(--red)', stale: 'var(--amber)',
  not_searched: 'var(--surface-2)', not_applicable: 'var(--surface-2)',
}

function Kpi({ v, l, info }: { v: string | number; l: string; info?: string }) {
  return (
    <div className="card kpi">
      <div className="v">{v}</div>
      <div className="l">{l} {info && <Info text={info} />}</div>
    </div>
  )
}

function Counts({ data, labels, empty = 'None yet' }: { data: Record<string, number>; labels?: Record<string, string>; empty?: string }) {
  const entries = Object.entries(data ?? {}).sort((a, b) => b[1] - a[1])
  if (!entries.length) return <p className="muted small">{empty}</p>
  const max = Math.max(...entries.map(([, v]) => v))
  return (
    <div className="stack" style={{ gap: 8 }}>
      {entries.map(([k, v]) => (
        <div key={k}>
          <div className="spread small"><span>{labels?.[k] ?? k.replace(/_/g, ' ')}</span><strong>{v}</strong></div>
          <div className="bar"><span style={{ width: `${(v / max) * 100}%`, background: 'var(--accent)' }} /></div>
        </div>
      ))}
    </div>
  )
}

export default function Reports() {
  const { data: r, error, loading } = useAsync(api.reports, [])
  if (loading && !r) return <div className="empty"><Spinner /></div>
  if (error || !r) return <ErrorBox error={error} />
  const checks: any[] = r.scenario_checks
  const passed = checks.filter((c) => c.passed).length
  const attTotal = Object.values(r.attention as Record<string, number>).reduce((a, b) => a + b, 0)

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Reports</h1>
          <p className="small">
            What the prototype shows today. <Info text="The dataset is fictional and has no verified outcomes, so no accuracy number is reported. These views show rule behaviour, research quality, cost, and candidates for error analysis." />
          </p>
        </div>
      </div>

      <div className="kpis">
        <Kpi v={r.totals.prospects} l="companies" />
        <Kpi v={r.totals.researched} l="researched" info="Companies with at least one successful public-research run." />
        <Kpi v={r.totals.research_failed} l="failed runs" info="Research runs that failed (timeout, API error, malformed output). Shown, never hidden." />
        <Kpi v={r.totals.day30_received} l="Day 30 received" info={g('day30')} />
        <Kpi v={`$${r.research_cost.total_usd.toFixed(2)}`} l="research cost" info={g('cost')} />
      </div>

      <div className="stack">
        <Section id="rep-overview" title="Overview" info="Where companies sit right now (latest assessment).">
          <div className="grid-3">
            <div>
              <h3 className="row" style={{ marginBottom: 8 }}>Attention <Info text={`${g('review_now')} ${g('review_suggested')} ${g('monitor')}`} /></h3>
              <div className="bar" style={{ height: 10, marginBottom: 8 }}>
                {Object.entries(r.attention as Record<string, number>).map(([k, v]) => (
                  <span key={k} title={`${ATT_LABEL[k] ?? k}: ${v}`} style={{ width: `${(v / attTotal) * 100}%`, background: ATT_COLOR[k] }} />
                ))}
              </div>
              <Counts data={r.attention} labels={ATT_LABEL} />
            </div>
            <div>
              <h3 className="row" style={{ marginBottom: 8 }}>Reason flags <Info text="A company can have several flags." /></h3>
              <Counts data={r.flags} />
            </div>
            <div>
              <h3 className="row" style={{ marginBottom: 8 }}>Tier proposals <Info text="Superseded = the latest evidence no longer supports it." /></h3>
              <Counts data={r.proposals} empty="No proposals yet" />
              {r.tier_changes.length > 0 && (
                <p className="small muted" style={{ marginTop: 8 }}>{r.tier_changes.length} tier change(s) approved</p>
              )}
            </div>
          </div>
        </Section>

        <Section
          id="rep-eval"
          title="Evaluation signals"
          info="Candidates to investigate, not accuracy figures."
          summary={`${r.review_outcomes.rejected_proposals_candidate_false_positives.length} possible FP · ${r.retrospective_day30.filter((x: any) => x.label.startsWith('Possible miss')).length} possible FN · ${r.unsupported_recommendations.length} unsupported`}
        >
          <div className="grid-3">
            <EvalList
              title="Possible false positives"
              info={g('false_positives')}
              items={r.review_outcomes.rejected_proposals_candidate_false_positives.map((x: any) => ({ key: x.proposal_id, link: `/reviews/${x.proposal_id}`, label: `#${x.proposal_id} ${x.prospect_id}`, hint: x.title }))}
            />
            <EvalList
              title="Possible false negatives"
              info={g('false_negatives')}
              items={r.retrospective_day30
                .filter((x: any) => x.label.startsWith('Possible'))
                .map((x: any) => ({ key: x.prospect_id, link: `/companies/${x.prospect_id}`, label: x.company_name, hint: x.label }))}
              empty={r.retrospective_day30.length ? 'None' : 'No Day 30 data received yet'}
            />
            <EvalList
              title="Unsupported recommendations"
              info={g('unsupported')}
              items={r.unsupported_recommendations.map((x: any) => ({ key: x.proposal_id, link: `/reviews/${x.proposal_id}`, label: `#${x.proposal_id} ${x.prospect_id}`, hint: x.reasons.join('; ') }))}
            />
          </div>
        </Section>

        <Section
          id="rep-coverage"
          title="Research coverage"
          info="For researched companies: how often each field was found, missing, conflicting or stale. Hover a bar segment for counts."
          summary={`${r.missing_data.employee_estimate_missing} missing employee estimates · ${r.missing_data.provisional_baseline} provisional tiers`}
          flush
        >
          <table>
            <tbody>
              {Object.entries(r.missing_data.coverage_by_field as Record<string, Record<string, number>>).map(([f, c]) => {
                const total = Object.values(c).reduce((a, b) => a + b, 0) || 1
                return (
                  <tr key={f}>
                    <td style={{ width: 220 }}>{FIELD_LABELS[f] ?? f}</td>
                    <td>
                      <div className="bar" style={{ height: 10 }}>
                        {Object.entries(c).map(([s, n]) => (
                          <span key={s} title={`${s.replace('_', ' ')}: ${n}`} style={{ width: `${(n / total) * 100}%`, background: STATUS_COLOR[s] }} />
                        ))}
                      </div>
                    </td>
                    <td style={{ width: 300 }}>
                      <div className="row">
                        {Object.entries(c).map(([s, n]) => <span key={s} className="row small" style={{ gap: 3 }}><StatusChip status={s} />{n}</span>)}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Section>

        <Section
          id="rep-cost"
          title="Research usage"
          info={g('cost')}
          summary={`${r.research_cost.web_searches} searches · ${r.research_cost.llm_calls} AI calls · ${r.citation_validation.findings_dropped} citations removed`}
          defaultOpen={false}
        >
          <dl className="kv">
            <dt>Per researched company</dt><dd>{r.research_cost.per_researched_prospect_usd != null ? `$${r.research_cost.per_researched_prospect_usd.toFixed(3)}` : '—'}</dd>
            <dt>Standard / deep</dt><dd>${r.research_cost.by_kind.standard.toFixed(3)} / ${r.research_cost.by_kind.deep.toFixed(3)}</dd>
            <dt>Tokens in / out</dt><dd>{r.research_cost.input_tokens.toLocaleString()} / {r.research_cost.output_tokens.toLocaleString()}</dd>
            <dt className="row">Citations removed <Info text={g('citation_validation')} align="left" /></dt><dd>{r.citation_validation.findings_dropped}</dd>
          </dl>
        </Section>

        <Section
          id="rep-checks"
          title="Scenario checks"
          info={g('scenario_checks')}
          summary={<span className={`badge ${passed === checks.length ? 'st-found' : 'st-conflicting'}`}>{passed}/{checks.length} passing</span>}
          defaultOpen={false}
          flush
        >
          <table>
            <tbody>
              {checks.map((c, i) => (
                <tr key={i}>
                  <td>{c.name}</td>
                  <td style={{ width: 90 }}>
                    <span title={`expected ${c.expected}, got ${c.actual}`} className={`badge ${c.passed ? 'st-found' : 'st-conflicting'}`}>{c.passed ? 'Pass' : 'Fail'}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      </div>
    </>
  )
}

function EvalList({ title, info, items, empty = 'None yet' }: { title: string; info: string; items: { key: string | number; link: string; label: string; hint: string }[]; empty?: string }) {
  return (
    <div>
      <h3 className="row" style={{ marginBottom: 8 }}>{title} <Info text={info} /> <span className="badge att-none">{items.length}</span></h3>
      {items.length === 0 ? (
        <p className="small muted">{empty}</p>
      ) : (
        <ul className="reasons" style={{ marginTop: 0 }}>
          {items.map((x) => (
            <li key={x.key} className="small">
              <Link to={x.link}>{x.label}</Link> <Info text={x.hint} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
