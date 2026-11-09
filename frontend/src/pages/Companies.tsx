import { useMemo, useState } from 'react'
import { api } from '../api'
import ProspectTable from '../components/ProspectTable'
import { ErrorBox, Icon, Spinner, useAsync } from '../components/ui'
import { useConfirm } from '../components/confirm'
import MultiSelect from '../components/MultiSelect'

const FLAG_OPTIONS: Record<string, string> = {
  tier_mismatch: 'Tier Mismatch',
  data_conflict: 'Data Conflict',
  travel_potential: 'Travel Potential',
  growth_opportunity: 'Growth Opportunity',
  insufficient_evidence: 'Insufficient Evidence',
}

const ATTENTION_ORDER: Record<string, number> = { review_now: 0, review_suggested: 1, monitor: 2, none: 3 }

export default function Companies() {
  const { data, error, loading, reload } = useAsync(api.prospects, [])
  const [q, setQ] = useState('')
  const [tier, setTier] = useState<string[]>([])
  const [flag, setFlag] = useState<string[]>([])
  const [attention, setAttention] = useState<string[]>([])
  const [research, setResearch] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const confirm = useConfirm()

  const rows = useMemo(() => {
    const term = q.trim().toLowerCase()
    const researchState = (r: { research_status: string }) =>
      ['ok', 'partial'].includes(r.research_status) ? 'researched' : r.research_status
    // Any ticked value within a filter; all filters together.
    return (data ?? []).filter(
      (r) =>
        (!term || r.company_name.toLowerCase().includes(term) || r.domain.includes(term) || r.id.toLowerCase().includes(term)) &&
        (!tier.length || tier.includes(String(r.applied_tier))) &&
        (!flag.length || flag.some((f) => r.flags.includes(f))) &&
        (!attention.length || attention.includes(r.attention ?? 'none')) &&
        (!research.length || research.includes(researchState(r))),
    )
      // Default order: Review Now → Review Suggested → Monitor → no action, most important first in each.
      .sort((a, b) => (ATTENTION_ORDER[a.attention ?? 'none'] ?? 3) - (ATTENTION_ORDER[b.attention ?? 'none'] ?? 3)
        || b.priority_score - a.priority_score || a.id.localeCompare(b.id))
  }, [data, q, tier, flag, attention, research])

  const pendingDay30 = (data ?? []).length > 0

  return (
    <>
      <div className="page-head">
        <div>
          <h1>All companies</h1>
          <p className="small">{data ? `${data.length} imported prospects` : 'Loading…'} · reported values are fictional scenario data.</p>
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
          <MultiSelect label="Tier" selected={tier} onChange={setTier} shortLabels={{ 1: '1', 2: '2', 3: '3' }}
            options={[{ value: '1', label: 'Tier 1' }, { value: '2', label: 'Tier 2' }, { value: '3', label: 'Tier 3' }]} />
          <MultiSelect label="Flag" allLabel="Any" selected={flag} onChange={setFlag}
            options={Object.entries(FLAG_OPTIONS).map(([value, label]) => ({ value, label }))} />
          <MultiSelect label="Attention" allLabel="Any" selected={attention} onChange={setAttention}
            options={[{ value: 'review_now', label: 'Review Now' }, { value: 'review_suggested', label: 'Review Suggested' },
              { value: 'monitor', label: 'Monitor' }, { value: 'none', label: 'No action' }]} />
          <MultiSelect label="Research" allLabel="Any" selected={research} onChange={setResearch}
            options={[{ value: 'researched', label: 'Researched' }, { value: 'not_researched', label: 'Not researched' }, { value: 'failed', label: 'Failed' }]} />
          {(q || tier.length || flag.length || attention.length || research.length) ? (
            <button className="more" onClick={() => { setQ(''); setTier([]); setFlag([]); setAttention([]); setResearch([]) }}>Clear</button>
          ) : null}
          <span className="muted small filters-count">{rows.length} of {data?.length ?? 0}</span>
        </div>
        {loading && !data ? <div className="empty"><Spinner /></div> : <ProspectTable rows={rows} />}
      </div>
    </>
  )
}
