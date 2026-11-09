import { useMemo, useState } from 'react'
import { api } from '../api'
import ProspectTable from '../components/ProspectTable'
import { ErrorBox, Icon, Spinner, useAsync } from '../components/ui'
import { useConfirm } from '../components/confirm'

const FLAG_OPTIONS: Record<string, string> = {
  tier_mismatch: 'Tier Mismatch',
  data_conflict: 'Data Conflict',
  travel_potential: 'Travel Potential',
  growth_opportunity: 'Growth Opportunity',
  insufficient_evidence: 'Insufficient Evidence',
}

export default function Companies() {
  const { data, error, loading, reload } = useAsync(api.prospects, [])
  const [q, setQ] = useState('')
  const [tier, setTier] = useState('')
  const [flag, setFlag] = useState('')
  const [attention, setAttention] = useState('')
  const [research, setResearch] = useState('')
  const [busy, setBusy] = useState(false)
  const confirm = useConfirm()

  const rows = useMemo(() => {
    const term = q.trim().toLowerCase()
    return (data ?? []).filter(
      (r) =>
        (!term || r.company_name.toLowerCase().includes(term) || r.domain.includes(term) || r.id.toLowerCase().includes(term)) &&
        (!tier || String(r.applied_tier) === tier) &&
        (!flag || r.flags.includes(flag)) &&
        (!attention || (r.attention ?? 'none') === attention) &&
        (!research || (research === 'researched' ? ['ok', 'partial'].includes(r.research_status) : r.research_status === research)),
    )
  }, [data, q, tier, flag, attention, research])

  const pendingDay30 = (data ?? []).length > 0

  return (
    <>
      <div className="page-head">
        <div>
          <h1>All companies</h1>
          <p>{data ? `${data.length} imported prospects` : 'Loading…'} · reported values are fictional scenario data.</p>
        </div>
        {pendingDay30 && (
          <button
            disabled={busy}
            title="Simulates the 30-day activity summaries arriving. Runs a rules-only reassessment for each company with activity."
            onClick={async () => {
              const ok = await confirm({
                title: 'Receive all Day 30 activity?',
                confirmLabel: 'Receive all',
                body: <p>Adds the first 30 days on Navan for every company that has it. Strong activity may suggest tier changes for review. This can’t be undone.</p>,
              })
              if (!ok) return
              setBusy(true)
              try {
                await api.releaseAllDay30()
                reload()
              } finally {
                setBusy(false)
              }
            }}
          >
            {busy && <Spinner />} Receive all Day 30 activity
          </button>
        )}
      </div>
      <ErrorBox error={error} />
      <div className="card">
        <div className="filters">
          <label className="search-box">
            <Icon name="search" />
            <input type="search" placeholder="Search companies" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" />
          </label>
          <select className={`pill-select${tier ? ' on' : ''}`} value={tier} onChange={(e) => setTier(e.target.value)} aria-label="Tier filter">
            <option value="">Tier: All</option>
            <option value="1">Tier 1</option>
            <option value="2">Tier 2</option>
            <option value="3">Tier 3</option>
          </select>
          <select className={`pill-select${flag ? ' on' : ''}`} value={flag} onChange={(e) => setFlag(e.target.value)} aria-label="Flag filter">
            <option value="">Flag: Any</option>
            {Object.entries(FLAG_OPTIONS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <select className={`pill-select${attention ? ' on' : ''}`} value={attention} onChange={(e) => setAttention(e.target.value)} aria-label="Attention filter">
            <option value="">Attention: Any</option>
            <option value="review_now">Review Now</option>
            <option value="review_suggested">Review Suggested</option>
            <option value="monitor">Monitor</option>
            <option value="none">No action</option>
          </select>
          <select className={`pill-select${research ? ' on' : ''}`} value={research} onChange={(e) => setResearch(e.target.value)} aria-label="Research filter">
            <option value="">Research: Any</option>
            <option value="researched">Researched</option>
            <option value="not_researched">Not researched</option>
            <option value="failed">Failed</option>
          </select>
          {(q || tier || flag || attention || research) && (
            <button className="more" onClick={() => { setQ(''); setTier(''); setFlag(''); setAttention(''); setResearch('') }}>Clear</button>
          )}
          <span className="muted small filters-count">{rows.length} of {data?.length ?? 0}</span>
        </div>
        {loading && !data ? <div className="empty"><Spinner /></div> : <ProspectTable rows={rows} />}
      </div>
    </>
  )
}
