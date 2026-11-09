import type { ReactNode } from 'react'
import type { Assessment, Proposal } from '../api'

/** GitHub-style diff: "-" = what is there now, "+" = what is proposed or found, " " = context. */
export type DiffLine = { sign: '-' | '+' | ' '; field?: string; value: ReactNode; note?: ReactNode; action?: ReactNode }

export function Diff({ title, lines }: { title?: string; lines: DiffLine[] }) {
  return (
    <div className="diffbox">
      {title && <div className="diff-title">{title}</div>}
      {lines.map((l, i) => (
        <div key={i} className={`diff-line ${l.sign === '-' ? 'del' : l.sign === '+' ? 'add' : 'ctx'}`}>
          <span className="diff-sign">{l.sign === ' ' ? '' : l.sign === '-' ? '−' : '+'}</span>
          <span className="diff-field">{l.field ?? ''}</span>
          <span className="diff-value">{l.value}</span>
          <span className="diff-note">{l.note}</span>
          {l.action && <span className="diff-action">{l.action}</span>}
        </div>
      ))}
    </div>
  )
}

export const SUPPORT: Record<number, string> = {
  1: 'Dedicated AE + account manager',
  2: 'AE for launch and adoption',
  3: 'Mostly self-serve',
}

/** The concrete changes a tier proposal would make. */
export function proposalDiff(p: Proposal, a: Assessment | null): DiffLine[] {
  const lines: DiffLine[] = [
    { sign: '-', field: 'Tier', value: `Tier ${p.from_tier}`, note: SUPPORT[p.from_tier ?? 0] },
    { sign: '+', field: 'Tier', value: `Tier ${p.proposed_tier}`, note: SUPPORT[p.proposed_tier] },
  ]
  const basis = (p.basis ?? {}) as Record<string, unknown>
  const current = a?.accepted_values.employees
  if (typeof basis.employees === 'number' && basis.employees !== current) {
    lines.push({ sign: '-', field: 'Employees used', value: current == null ? 'unknown' : current.toLocaleString(), note: a?.accepted_values.employee_source ?? undefined })
    const research = (a?.accepted_values.employee_sources ?? []).filter((s) => s.origin === 'ai_research' || s.origin === 'synthetic_test').map((s) => s.value)
    const note = basis.employee_source === 'research'
      ? research.length > 1
        ? `middle of the research figures (${research.join(', ')}); accepted on approval`
        : 'research figure; accepted on approval'
      : 'manual value'
    lines.push({ sign: '+', field: 'Employees used', value: (basis.employees as number).toLocaleString(), note })
  } else if (a) {
    lines.push({ sign: ' ', field: 'Employees used', value: current == null ? 'unknown' : current.toLocaleString(), note: 'unchanged' })
  }
  if (a) lines.push({ sign: ' ', field: 'Reported GBV', value: a.accepted_values.gbv_usd == null ? '—' : `$${a.accepted_values.gbv_usd.toLocaleString()}`, note: 'unchanged' })
  if (p.stage === 'day30' && a?.day30) {
    const d = a.day30
    lines.push({ sign: ' ', field: 'Evidence', value: `${d.travelers} travelers · ${d.bookings} bookings`, note: d.trend_pct != null ? `${d.trend_pct > 0 ? '+' : ''}${d.trend_pct}% trend (Day 30)` : 'Day 30' })
  }
  return lines
}
