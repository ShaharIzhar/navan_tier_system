import { useEffect, useState, type ReactNode } from 'react'
import type { Attention } from '../api'

export const FIELD_LABELS: Record<string, string> = {
  industry_business_model: 'Industry & business model',
  geographic_footprint: 'Geographic footprint',
  employee_count: 'Employee count',
  hiring_trends: 'Hiring & workforce trends',
  travel_indicators: 'Direct travel indicators',
  funding_financial: 'Funding & financials',
  recent_expansion: 'Recent expansion',
  support_complexity: 'Support complexity',
}

export const STATUS_LABELS: Record<string, string> = {
  found: 'Found',
  not_found: 'Not found',
  not_searched: 'Not searched',
  conflicting: 'Conflicting',
  stale: 'Stale',
  not_applicable: 'Not applicable',
}

export const RELIABILITY_LABELS: Record<string, string> = {
  primary: 'Company site / registry',
  secondary: 'Independent source',
  aggregator: 'Data aggregator (estimate)',
  manual_verified: 'Manual · verified',
  manual_unverified: 'Manual · unverified',
  synthetic: 'SYNTHETIC TEST',
}

export const TRIGGER_LABELS: Record<string, string> = {
  import: 'Signup (rules only)',
  research: 'Standard research',
  deep_research: 'Deep research',
  manual_enrichment: 'Manual enrichment',
  day30: 'Day 30 activity received',
  review: 'Review decision',
  manual: 'Reassessed',
}

export function TierBadge({ tier, provisional, title }: { tier: number | null | undefined; provisional?: boolean | null; title?: string }) {
  if (tier == null) return <span className="tier" title="No tier could be calculated">—</span>
  return (
    <span className={`tier t${tier}${provisional ? ' prov' : ''}`} title={title ?? (provisional ? 'Provisional: employee count unknown' : undefined)}>
      T{tier}
      {provisional ? '?' : ''}
    </span>
  )
}

export function AttentionBadge({ attention, label }: { attention: Attention; label?: string }) {
  const text = label ?? (attention === 'review_now' ? 'Review Now' : attention === 'review_suggested' ? 'Review Suggested' : attention === 'monitor' ? 'Monitor' : 'No action')
  return <span className={`badge att-${attention ?? 'none'}`}>{text}</span>
}

export function FlagChip({ label, severity }: { label: string; severity?: string }) {
  return <span className={`badge flag${severity ? ` sev-${severity}` : ''}`}>{label}</span>
}

export function StatusChip({ status }: { status: string }) {
  return <span className={`badge st-${status}`}>{STATUS_LABELS[status] ?? status}</span>
}

export function ReliabilityChip({ reliability }: { reliability: string }) {
  return <span className={`badge rel rel-${reliability}`}>{RELIABILITY_LABELS[reliability] ?? reliability}</span>
}

/** Only rendered for genuine comparable values. Never infers a change. */
export function TrendArrow({ pct, label }: { pct: number | null | undefined; label?: string }) {
  if (pct == null) return null
  if (pct > 0) return <span className="trend-up" title={label}>↑ {pct.toFixed(0)}%</span>
  if (pct < 0) return <span className="trend-down" title={label}>↓ {Math.abs(pct).toFixed(0)}%</span>
  return <span className="trend-flat" title={label}>→ 0%</span>
}

export function usd(v: number | null | undefined) {
  if (v == null) return '—'
  return v >= 1000 ? `$${Math.round(v / 1000).toLocaleString()}K` : `$${v.toLocaleString()}`
}

export function num(v: number | null | undefined) {
  return v == null ? '—' : v.toLocaleString()
}

export function when(iso: string | null | undefined) {
  if (!iso) return '—'
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`)
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function hostOf(url: string | null | undefined) {
  if (!url) return null
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

export function Spinner() {
  return <span className="spinner" aria-label="loading" />
}

export function ErrorBox({ error }: { error: string | null }) {
  if (!error) return null
  return <div className="callout error banner">{error}</div>
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <div className="card-head">
          <h2>{title}</h2>
          <button className="ghost" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <div className="card-pad">{children}</div>
      </div>
    </div>
  )
}

const REVIEWER_KEY = 'ngi.reviewer'

export function useReviewer(): [string, (v: string) => void] {
  const read = () => {
    try {
      return localStorage.getItem(REVIEWER_KEY) ?? ''
    } catch {
      return ''
    }
  }
  const [name, setName] = useState(read)
  useEffect(() => {
    const h = () => setName(read())
    window.addEventListener('ngi-reviewer', h)
    return () => window.removeEventListener('ngi-reviewer', h)
  }, [])
  const update = (v: string) => {
    try {
      localStorage.setItem(REVIEWER_KEY, v)
    } catch {
      /* storage unavailable: keep in memory only */
    }
    setName(v)
    window.dispatchEvent(new Event('ngi-reviewer'))
  }
  return [name, update]
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let alive = true
    setLoading(true)
    fn()
      .then((d) => alive && (setData(d), setError(null)))
      .catch((e) => alive && setError(String(e.message ?? e)))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])
  return { data, error, loading, reload: () => setTick((t) => t + 1), setData }
}
