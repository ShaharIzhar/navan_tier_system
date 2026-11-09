import { Link, useNavigate } from 'react-router-dom'
import type { ProspectRow } from '../api'
import { g } from '../glossary'
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
            Tier <Info text={`${g('applied_tier')} An arrow shows a tier change waiting for review.`} />
          </SortTh>
          <SortTh k="gbv" sort={sort} className="num">Reported GBV</SortTh>
          <SortTh k="employees" sort={sort} className="num">
            Employees <Info text="Enrichment estimate from the dataset (fictional). Research may disagree." align="right" />
          </SortTh>
          <SortTh k="reason" sort={sort}>
            Main reason <Info text="The most important reason flag. Open the company to see all flags." />
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

function Suggestion({ s }: { s: NonNullable<ProspectRow['suggestion']> }) {
  const up = s.to_tier < (s.from_tier ?? 3) // lower tier number = more support
  const text = `${up ? 'Suggested upgrade' : 'Suggested downgrade'} to Tier ${s.to_tier}: ${s.title}.${s.status === 'needs_info' ? ' Waiting for more information.' : ' Awaiting review.'} Click to open the review.`
  return (
    <Hint text={text}>
      <Link to={`/reviews/${s.proposal_id}`} className={`suggest ${up ? 'up' : 'down'}`} onClick={(e) => e.stopPropagation()}
        aria-label={`Suggested Tier ${s.to_tier}`}>
        <span className="suggest-arrow" aria-hidden>{up ? '↑' : '↓'}</span>T{s.to_tier}
      </Link>
    </Hint>
  )
}
