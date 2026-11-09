import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { ErrorBox, Spinner, TierBadge, useAsync, when } from '../components/ui'
import { Hint, Info } from '../components/Section'
import { SortTh, useSort } from '../components/sort'
import { g } from '../glossary'

const FILTERS = [
  { key: 'unresolved', label: 'Unresolved' },
  { key: 'approved', label: 'Approved' },
  { key: 'rejected', label: 'Rejected' },
  { key: 'superseded', label: 'Superseded' },
  { key: 'all', label: 'All' },
]

export default function Reviews() {
  const { data, error, loading } = useAsync(() => api.proposals(), [])
  const [filter, setFilter] = useState('unresolved')
  const nav = useNavigate()
  const rows = (data ?? []).filter((p) =>
    filter === 'all' ? true : filter === 'unresolved' ? ['open', 'needs_info'].includes(p.status) : p.status === filter,
  )
  const sort = useSort(rows, {
    id: (p) => p.id,
    company: (p) => (p.company_name ?? '').toLowerCase(),
    change: (p) => p.proposed_tier - (p.from_tier ?? 0),
    type: (p) => p.proposal_type,
    stage: (p) => p.stage,
    status: (p) => p.status_label,
    updated: (p) => p.updated_at,
  })
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Tier reviews</h1>
          <p className="small">Proposed tier changes. Nothing changes until a person approves. <Info text={`${g('standard_rule_correction')} ${g('evidence_override')}`} /></p>
        </div>
      </div>
      <ErrorBox error={error} />
      <div className="tabs">
        {FILTERS.map((f) => (
          <button key={f.key} className={`tab${filter === f.key ? ' active' : ''}`} onClick={() => setFilter(f.key)}>
            {f.label}
          </button>
        ))}
      </div>
      <div className="card">
        {loading && !data ? (
          <div className="empty"><Spinner /></div>
        ) : rows.length === 0 ? (
          <div className="empty">No proposals here.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <SortTh k="id" sort={sort}>#</SortTh>
                <SortTh k="company" sort={sort}>Company</SortTh>
                <SortTh k="change" sort={sort}>Change</SortTh>
                <SortTh k="type" sort={sort}>Type</SortTh>
                <SortTh k="stage" sort={sort}>Stage</SortTh>
                <SortTh k="status" sort={sort}>Status</SortTh>
                <SortTh k="updated" sort={sort}>Updated</SortTh>
              </tr>
            </thead>
            <tbody>
              {sort.sorted.map((p) => (
                <tr key={p.id} className="clickable" onClick={() => nav(`/reviews/${p.id}`)}>
                  <td className="muted">#{p.id}</td>
                  <td className="company-cell">
                    <strong>{p.company_name}</strong>

                  </td>
                  <td>
                    <TierBadge tier={p.from_tier} /> → <TierBadge tier={p.proposed_tier} />
                  </td>
                  <td>
                    <Hint text={g(p.proposal_type)}>{p.proposal_type === 'standard_rule_correction' ? 'Rule correction' : 'Override'}</Hint>
                  </td>
                  <td>{p.stage === 'day30' ? 'Day 30' : 'Day 0'}</td>
                  <td>
                    <span className={`status-pill${p.status === 'open' ? ' awaiting' : ''}`}>{p.status_label}</span>
                  </td>
                  <td className="muted small">{when(p.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}
