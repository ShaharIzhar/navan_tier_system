import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Info } from '../components/Section'
import { CompanySiteBadge, ErrorBox, FIELD_LABELS, Spinner, hostOf, num, useAsync } from '../components/ui'

/** Everything the research took from companies' own websites. */
export default function Verified() {
  const { data, error, loading } = useAsync(api.verified, [])
  const [field, setField] = useState('')
  if (loading && !data) return <div className="empty"><Spinner /></div>
  if (error || !data) return <ErrorBox error={error} />

  const fields = Array.from(new Set(data.flatMap((g) => g.evidence.map((e) => e.field))))
  const groups = data
    .map((g) => ({ ...g, evidence: g.evidence.filter((e) => !field || e.field === field) }))
    .filter((g) => g.evidence.length)
  const total = groups.reduce((n, g) => n + g.evidence.length, 0)

  return (
    <div className="single">
      <div className="page-head">
        <div>
          <h1>Verified data</h1>
          <p className="small">
            Facts the research took from each company’s own website.{' '}
            <Info text="A source counts as the company's website when its address is on the company's own domain (e.g. balfourbeatty.com). These are usually more trustworthy than data aggregators, but they are still the company's own claims." />
          </p>
        </div>
        <select value={field} onChange={(e) => setField(e.target.value)} aria-label="Field filter">
          <option value="">All fields</option>
          {fields.map((f) => <option key={f} value={f}>{FIELD_LABELS[f] ?? f}</option>)}
        </select>
      </div>
      <p className="small muted" style={{ marginBottom: 12 }}>{total} finding(s) from {groups.length} companies.</p>

      {groups.length === 0 ? (
        <div className="card empty">No company-website findings yet. Run research on a company first.</div>
      ) : (
        <div className="stack">
          {groups.map((g) => (
            <div className="card" key={g.prospect_id}>
              <div className="section-head">
                <h2><Link to={`/companies/${g.prospect_id}`}>{g.company_name}</Link></h2>
                <span className="muted small">{g.domain} · {g.evidence.length}</span>
              </div>
              <table>
                <tbody>
                  {g.evidence.map((e) => (
                    <tr key={e.id}>
                      <td style={{ width: 190 }} className="muted small">{FIELD_LABELS[e.field] ?? e.field}</td>
                      <td>
                        {e.value_number != null && <strong style={{ marginRight: 8 }}>{num(e.value_number)}</strong>}
                        {e.claim}
                      </td>
                      <td style={{ width: 260 }}>
                        <span className="row small" style={{ gap: 4 }}>
                          <CompanySiteBadge domain={hostOf(e.source_url) ?? g.domain} date={e.published_date} />
                          {e.source_url && (
                            <a href={e.source_url} target="_blank" rel="noreferrer">{e.source_title || hostOf(e.source_url)}</a>
                          )}
                        </span>
                        {e.published_date && <div className="small muted">{e.published_date}{e.is_stale ? ' · stale' : ''}</div>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
