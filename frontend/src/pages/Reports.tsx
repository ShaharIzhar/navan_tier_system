import { Link } from 'react-router-dom'
import { api } from '../api'
import { ErrorBox, FIELD_LABELS, Spinner, StatusChip, useAsync } from '../components/ui'

/* eslint-disable @typescript-eslint/no-explicit-any */

function Stat({ v, l }: { v: string | number; l: string }) {
  return (
    <div className="card stat">
      <div className="v">{v}</div>
      <div className="l">{l}</div>
    </div>
  )
}

function Counts({ data, empty = 'None yet' }: { data: Record<string, number>; empty?: string }) {
  const entries = Object.entries(data ?? {})
  if (!entries.length) return <p className="muted small">{empty}</p>
  return (
    <table>
      <tbody>
        {entries.map(([k, v]) => (
          <tr key={k}><td>{k.replace(/_/g, ' ')}</td><td className="num">{v}</td></tr>
        ))}
      </tbody>
    </table>
  )
}

export default function Reports() {
  const { data: r, error, loading } = useAsync(api.reports, [])
  if (loading && !r) return <div className="empty"><Spinner /></div>
  if (error || !r) return <ErrorBox error={error} />
  const checks: any[] = r.scenario_checks
  const passed = checks.filter((c) => c.passed).length

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Reports & evaluation</h1>
          <p>What the prototype can show today, and what needs verified outcomes before it means anything.</p>
        </div>
      </div>

      <div className="grid-3" style={{ gridTemplateColumns: 'repeat(5, 1fr)', marginBottom: 16 }}>
        <Stat v={r.totals.prospects} l="prospects imported" />
        <Stat v={r.totals.researched} l="with public research" />
        <Stat v={r.totals.research_failed} l="failed research runs" />
        <Stat v={r.totals.day30_received} l="Day 30 summaries received" />
        <Stat v={`$${r.research_cost.total_usd.toFixed(3)}`} l="approx. research cost" />
      </div>

      <div className="grid-3" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-head"><h2>Attention</h2></div>
          <Counts data={Object.fromEntries(Object.entries(r.attention).map(([k, v]) => [({ review_now: 'Review Now', review_suggested: 'Review Suggested', monitor: 'Monitor', none: 'No action' } as any)[k] ?? k, v as number]))} />
        </div>
        <div className="card">
          <div className="card-head"><h2>Reason flags (latest)</h2></div>
          <Counts data={r.flags} />
        </div>
        <div className="card">
          <div className="card-head"><h2>Reviews</h2></div>
          <Counts data={r.proposals} empty="No proposals yet" />
          <div className="card-pad small muted">
            Decisions: {Object.entries(r.decisions).map(([k, v]) => `${k.replace('_', ' ')} ${v}`).join(' · ') || 'none'}
          </div>
        </div>
      </div>

      <div className="grid-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-head"><h2>Missing and conflicting research</h2><span className="card-sub">{r.totals.researched} researched companies</span></div>
          <div className="card-pad small text-2">
            Employee estimate missing in dataset: <strong>{r.missing_data.employee_estimate_missing}</strong> of {r.totals.prospects} · provisional baseline tiers: <strong>{r.missing_data.provisional_baseline}</strong>
          </div>
          <table>
            <thead><tr><th>Field</th><th>Status counts</th></tr></thead>
            <tbody>
              {Object.entries(r.missing_data.coverage_by_field as Record<string, Record<string, number>>).map(([f, c]) => (
                <tr key={f}>
                  <td>{FIELD_LABELS[f] ?? f}</td>
                  <td className="row">{Object.entries(c).map(([s, n]) => <span key={s} className="row" style={{ gap: 4 }}><StatusChip status={s} /> {n}</span>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <div className="card-head"><h2>Research usage</h2></div>
          <dl className="kv card-pad">
            <dt>Web searches</dt><dd>{r.research_cost.web_searches}</dd>
            <dt>LLM calls</dt><dd>{r.research_cost.llm_calls}</dd>
            <dt>Tokens in / out</dt><dd>{r.research_cost.input_tokens.toLocaleString()} / {r.research_cost.output_tokens.toLocaleString()}</dd>
            <dt>Standard / deep</dt><dd>${r.research_cost.by_kind.standard.toFixed(3)} / ${r.research_cost.by_kind.deep.toFixed(3)}</dd>
            <dt>Per researched company</dt><dd>{r.research_cost.per_researched_prospect_usd != null ? `$${r.research_cost.per_researched_prospect_usd.toFixed(3)}` : '—'}</dd>
          </dl>
          <div className="card-pad small muted" style={{ paddingTop: 0 }}>Costs are estimates from token and search counts at list prices. Manual reassessment costs nothing (0 AI calls).</div>
          <div className="card-head" style={{ borderTop: '1px solid var(--border)' }}><h2>Citation validation</h2></div>
          <div className="card-pad small">
            {r.citation_validation.findings_dropped} finding(s) removed because their URL was not among the search results actually returned ({r.citation_validation.runs_with_drops} run(s)).
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head">
          <h2>Evaluation signals</h2>
          <span className="card-sub">Candidates for error analysis, not accuracy figures</span>
        </div>
        <div className="grid-3 card-pad">
          <div>
            <h3>Possible false positives</h3>
            <p className="small muted" style={{ margin: '4px 0 8px' }}>Proposals a reviewer rejected. {r.review_outcomes.note}</p>
            {r.review_outcomes.rejected_proposals_candidate_false_positives.length === 0 ? <p className="small muted">None yet.</p> : (
              <ul className="reasons">
                {r.review_outcomes.rejected_proposals_candidate_false_positives.map((x: any) => (
                  <li key={x.proposal_id}><Link to={`/reviews/${x.proposal_id}`}>#{x.proposal_id}</Link> {x.prospect_id}: {x.title}</li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <h3>Unsupported recommendations</h3>
            <p className="small muted" style={{ margin: '4px 0 8px' }}>Proposals without cited evidence, or relying only on aggregator, synthetic or inferred evidence.</p>
            {r.unsupported_recommendations.length === 0 ? <p className="small muted">None found.</p> : (
              <ul className="reasons">
                {r.unsupported_recommendations.map((x: any) => (
                  <li key={x.proposal_id}><Link to={`/reviews/${x.proposal_id}`}>#{x.proposal_id}</Link> {x.prospect_id}: {x.reasons.join('; ')}</li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <h3>Possible false negatives</h3>
            <p className="small muted" style={{ margin: '4px 0 8px' }}>
              Retrospective only: companies whose Day 30 activity was strong but had no Day 0 flag. Day 30 data is never used for the signup decision.
            </p>
            {r.retrospective_day30.length === 0 ? <p className="small muted">No Day 30 data received yet.</p> : (
              <ul className="reasons">
                {r.retrospective_day30.map((x: any) => (
                  <li key={x.prospect_id}><Link to={`/companies/${x.prospect_id}`}>{x.company_name}</Link>: {x.label}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head">
          <h2>Scenario checks</h2>
          <span className="card-sub">{passed}/{checks.length} passing · prove the rules behave as specified, not predictive accuracy</span>
        </div>
        <table>
          <thead><tr><th>Scenario</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead>
          <tbody>
            {checks.map((c, i) => (
              <tr key={i}>
                <td>{c.name}</td>
                <td className="mono">{c.expected}</td>
                <td className="mono">{c.actual}</td>
                <td>{c.passed ? <span className="badge st-found">Pass</span> : <span className="badge st-conflicting">Fail</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card card-pad">
        <h2>What these numbers can and cannot tell you</h2>
        <ul className="reasons">
          <li><strong>Can show now:</strong> rule correctness (scenario checks), research coverage and gaps, citation validation, cost per company, review outcomes, and whether every proposal cites evidence.</li>
          <li><strong>Needs verified outcomes:</strong> precision and recall of flags, false-positive and false-negative rates, and business impact. The dataset is fictional and has no verified tier outcomes, so no accuracy figure is reported.</li>
          <li><strong>Reviewer approval is not accuracy.</strong> Approvals show agreement, not that the recommendation was right. Measuring recall needs a labelled sample that includes companies the system did not flag.</li>
        </ul>
      </div>
    </>
  )
}
