import { useNavigate } from 'react-router-dom'
import type { ProspectRow } from '../api'
import { AttentionBadge, FlagChip, TierBadge, num, usd } from './ui'
import { Info } from './Section'
import { g } from '../glossary'

export default function ProspectTable({ rows, showAttention = true, empty }: { rows: ProspectRow[]; showAttention?: boolean; empty?: string }) {
  const nav = useNavigate()
  if (!rows.length) return <div className="empty">{empty ?? 'No companies match.'}</div>
  return (
    <table>
      <thead>
        <tr>
          <th>Company</th>
          <th>Applied <Info text={g('applied_tier')} /></th>
          <th>Rules say <Info text={g('baseline_tier')} /></th>
          <th className="num">Reported GBV</th>
          <th className="num">Employees <Info text="Enrichment estimate from the dataset (fictional). Research may disagree." align="right" /></th>
          <th>Main reason <Info text="The most important reason flag. Open the company to see all flags." /></th>
          {showAttention && <th>Attention</th>}
          <th>Review <Info text="Where the tier proposal stands, if there is one." align="right" /></th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.id} className="clickable" onClick={() => nav(`/companies/${r.id}`)}>
            <td className="company-cell">
              <strong>{r.company_name}</strong>
              <span>
                {r.id} · {r.domain}
                {r.stage === 'day30' ? ' · Day 30' : ''}
              </span>
            </td>
            <td>
              <TierBadge tier={r.applied_tier} />
              {r.applied_tier !== r.original_tier && <span className="muted small"> (was T{r.original_tier})</span>}
            </td>
            <td>
              <TierBadge tier={r.baseline_tier} provisional={r.baseline_provisional} />
            </td>
            <td className="num">{usd(r.entered_gbv_usd)}</td>
            <td className="num">{r.zi_employees == null ? <span className="muted">—</span> : num(r.zi_employees)}</td>
            <td>{r.primary_flag_label ? <FlagChip label={r.primary_flag_label} /> : <span className="muted">—</span>}</td>
            {showAttention && (
              <td>
                <AttentionBadge attention={r.attention} label={r.attention_label} />
              </td>
            )}
            <td>
              <span className={`status-pill${r.review_status === 'Awaiting review' ? ' awaiting' : ''}`}>{r.review_status ?? '—'}</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
