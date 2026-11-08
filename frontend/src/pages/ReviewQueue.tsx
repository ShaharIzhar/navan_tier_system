import { useState } from 'react'
import { api, type ProspectRow } from '../api'
import ProspectTable from '../components/ProspectTable'
import { ErrorBox, Spinner, useAsync } from '../components/ui'
import { Info } from '../components/Section'
import { g } from '../glossary'

const TABS: { key: NonNullable<ProspectRow['attention']>; label: string; help: string }[] = [
  { key: 'review_now', label: 'Review Now', help: 'Important, reasonably supported cases. A tier proposal or a conflict that decides tier eligibility.' },
  { key: 'review_suggested', label: 'Review Suggested', help: 'Meaningful opportunity or discrepancy worth investigating, but not urgent.' },
  { key: 'monitor', label: 'Monitor', help: 'Interesting signals or open gaps. No need to spend sales time yet.' },
]

export default function ReviewQueue() {
  const { data, error, loading } = useAsync(api.prospects, [])
  const [tab, setTab] = useState<(typeof TABS)[number]['key']>('review_now')
  const rows = (data ?? [])
    .filter((r) => r.attention === tab)
    .sort((a, b) => b.priority_score - a.priority_score || a.id.localeCompare(b.id))
  const count = (k: string) => (data ?? []).filter((r) => r.attention === k).length
  const current = TABS.find((t) => t.key === tab)!

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Review queue</h1>
          <p className="small">
            Companies that need a look, most important first. <Info text={g('priority')} />
          </p>
        </div>
      </div>
      <ErrorBox error={error} />
      <div className="tabs" role="tablist" style={{ alignItems: 'center' }}>
        {TABS.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key} className={`tab${tab === t.key ? ' active' : ''}`} onClick={() => setTab(t.key)}>
            {t.label}
            <span className="count">{data ? count(t.key) : '…'}</span>
          </button>
        ))}
        <span style={{ marginLeft: 6 }}><Info text={current.help} /></span>
      </div>
      <div className="card">
        {loading && !data ? (
          <div className="empty"><Spinner /></div>
        ) : (
          <ProspectTable rows={rows} showAttention={false} empty={`Nothing in ${current.label} right now.`} />
        )}
      </div>
    </>
  )
}
