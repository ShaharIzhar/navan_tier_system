import { useNavigate } from 'react-router-dom'
import type { ProspectRow } from '../api'
import { AttentionBadge, FlagChip, TierBadge, num, usd } from './ui'

export default function ProspectTable({ rows, showAttention = true, empty }: { rows: ProspectRow[]; showAttention?: boolean; empty?: string }) {
  const nav = useNavigate()
  if (!rows.length) return <div className="empty">{empty ?? 'No companies match.'}</div>
  return (
    <table>
      <thead>
        <tr>
          <th>Company</th>
          <th>Applied tier</th>
          <th>Baseline</th>
          <th className="num">Reported GBV</th>
          <th className="num">Est. employees</th>
          <th>Primary reason</th>
          {showAttention && <th>Attention</th>}
          <th>Review status</th>
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
            <td className="num">{r.zi_employees == null ? <span className="muted">missing</span> : num(r.zi_employees)}</td>
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
