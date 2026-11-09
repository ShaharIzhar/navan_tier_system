import { Link, useNavigate } from 'react-router-dom'
import type { ProspectRow } from '../api'
import { Hint, Info } from './Section'
import { SortTh, useSort } from './sort'
import { AttentionBadge, FlagChip, TierBadge, num, usd } from './ui'

const ATTENTION_RANK: Record<string, number> = { review_now: 0, review_suggested: 1, monitor: 2 }

export default function ProspectTable({ rows, showAttention = true, empty }: { rows: ProspectRow[]; showAttention?: boolean; empty?: string }) {
  const nav = useNavigate()
  const sort = useSort(rows, {
    company: (r) => r.company_name.toLowerCase(),
    tier: (r) => r.applied_tier,
    gbv: (r) => r.entered_gbv_usd,
    employees: (r) => r.zi_employees,
    reason: (r) => r.primary_flag_label,
    attention: (r) => (r.attention ? ATTENTION_RANK[r.attention] : 3),
  })
  if (!rows.length) return <div className="empty">{empty ?? 'No companies match.'}</div>
  return (
    <table>
      <thead>
        <tr>
          <SortTh k="company" sort={sort}>Company</SortTh>
          <SortTh k="tier" sort={sort}>
            Tier <Info text="Current tier. An arrow means a change is waiting for review." />
          </SortTh>
          <SortTh k="gbv" sort={sort} className="num">Reported GBV</SortTh>
          <SortTh k="employees" sort={sort} className="num">
            Employees <Info text="From the signup data." align="right" />
          </SortTh>
          <SortTh k="reason" sort={sort}>
            Main reason <Info text="The main reason it was flagged." />
          </SortTh>
          {showAttention && <SortTh k="attention" sort={sort}>Attention</SortTh>}
        </tr>
      </thead>
      <tbody>
        {sort.sorted.map((r) => (
          <tr key={r.id} className="clickable" onClick={() => nav(`/companies/${r.id}`)}>
            <td className="company-cell">
              <strong>{r.company_name}</strong>
              <span>
                {r.id} · {r.domain}
                {r.stage === 'day30' ? ' · Day 30' : ''}
              </span>
            </td>
            <td>
              <span className="row" style={{ gap: 6, flexWrap: 'nowrap' }}>
                <TierBadge tier={r.applied_tier} />
                {r.suggestion && <Suggestion s={r.suggestion} />}
                {r.applied_tier !== r.original_tier && <span className="muted small">(was T{r.original_tier})</span>}
              </span>
            </td>
            <td className="num">{usd(r.entered_gbv_usd)}</td>
            <td className="num">{r.zi_employees == null ? <span className="muted">—</span> : num(r.zi_employees)}</td>
            <td>{r.primary_flag_label ? <FlagChip label={r.primary_flag_label} /> : <span className="muted">—</span>}</td>
            {showAttention && (
              <td>
                <AttentionBadge attention={r.attention} label={r.attention_label} />
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** "↑T1" / "↓T3" badge: the tier a change points to (lower number = more support = up). */
export function TierArrow({ from, to }: { from: number | null; to: number }) {
  const up = to < (from ?? 3)
  return (
    <span className={`suggest ${up ? 'up' : 'down'}`} aria-label={`Suggested Tier ${to}`}>
      <span className="suggest-arrow" aria-hidden>{up ? '↑' : '↓'}</span>T{to}
    </span>
  )
}

export function Suggestion({ s }: { s: NonNullable<ProspectRow['suggestion']> }) {
  const up = s.to_tier < (s.from_tier ?? 3)
  const text = `Suggested ${up ? 'upgrade' : 'downgrade'} to Tier ${s.to_tier}${s.status === 'needs_info' ? ' (waiting for info)' : ''}. Click to review.`
  return (
    <Hint text={text}>
      <Link to={`/reviews/${s.proposal_id}`} className="suggest-link" onClick={(e) => e.stopPropagation()}>
        <TierArrow from={s.from_tier} to={s.to_tier} />
      </Link>
    </Hint>
  )
}
