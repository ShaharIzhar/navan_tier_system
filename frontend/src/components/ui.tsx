import { useEffect, useState, type ReactNode } from 'react'
import type { Attention } from '../api'
import { g } from '../glossary'
import { Hint } from './Section'

export const SUPPORT_LEVEL: Record<number, string> = {
  1: 'dedicated AE and account manager',
  2: 'AE for launch and adoption',
  3: 'mostly self-serve',
}

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
  if (tier == null) return <span className="tier">—</span>
  const text = title ?? [g(`tier${tier}`), provisional ? g('provisional') : ''].filter(Boolean).join(' ')
  return (
    <Hint text={text}>
      <span className={`tier t${tier}${provisional ? ' prov' : ''}`}>
        T{tier}
        {provisional ? '?' : ''}
      </span>
    </Hint>
  )
}

export function AttentionBadge({ attention, label }: { attention: Attention; label?: string }) {
  const text = label ?? (attention === 'review_now' ? 'Review Now' : attention === 'review_suggested' ? 'Review Suggested' : attention === 'monitor' ? 'Monitor' : 'No action')
  return (
    <Hint text={g(attention ?? 'no_action')}>
      <span className={`badge att-${attention ?? 'none'}`}>{text}</span>
    </Hint>
  )
}

const FLAG_KEY: Record<string, string> = {
  'Tier Mismatch': 'tier_mismatch', 'Data Conflict': 'data_conflict', 'Travel Potential': 'travel_potential',
  'Growth Opportunity': 'growth_opportunity', 'Insufficient Evidence': 'insufficient_evidence',
}

export function FlagChip({ label, severity, explain }: { label: string; severity?: string; explain?: string }) {
  const text = explain ?? [g(FLAG_KEY[label]), severity ? g(severity) : ''].filter(Boolean).join(' ')
  return (
    <Hint text={text}>
      <span className={`badge flag${severity ? ` sev-${severity}` : ''}`}>{label}</span>
    </Hint>
  )
}

export function StatusChip({ status, explain }: { status: string; explain?: string }) {
  return (
    <Hint text={explain ?? g(status)}>
      <span className={`badge st-${status}`}>{STATUS_LABELS[status] ?? status}</span>
    </Hint>
  )
}

export function ReliabilityChip({ reliability }: { reliability: string }) {
  return (
    <Hint text={g(reliability)}>
      <span className={`badge rel rel-${reliability}`}>{RELIABILITY_LABELS[reliability] ?? reliability}</span>
    </Hint>
  )
}

/** True when the source URL is on the company's own website (same domain or a subdomain). */
export function isCompanySite(url: string | null | undefined, companyDomain: string | null | undefined) {
  const host = hostOf(url)
  const d = (companyDomain ?? '').toLowerCase().replace(/^www\./, '')
  return !!host && !!d && (host === d || host.endsWith(`.${d}`))
}

/** One-line description of where a figure came from, for hover tooltips. */
export function sourceText(s: { label: string; origin: string; reliability: string; as_of?: string | null; stale?: boolean; url?: string | null; company_site?: boolean }) {
  if (s.origin === 'dataset') return 'From the signup data.'
  if (s.company_site) return `From the company’s own website${s.as_of ? ` (${s.as_of})` : ''}. Click to see it.`
  const name = s.label.replace(/\s*\([^)]*\)\s*/g, ' ').trim() // drop the AI's own "(aggregator estimate)" notes
  return `${name}${s.as_of ? ` · ${s.as_of}` : ''}${s.stale ? ' · old' : ''}. Click to see it.`
}

/** Blue verified check for figures that come from the company's own website. */
export function CompanySiteBadge({ domain, date, plain = false }: { domain: string; date?: string | null; plain?: boolean }) {
  const icon = (
    <span className="verified" aria-label="From the company's own website">
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden>
        <circle cx="8" cy="8" r="8" fill="currentColor" />
        <path d="M4.6 8.3l2.2 2.2 4.6-4.8" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  )
  if (plain) return icon // the surrounding element already explains it on hover
  const text = `From ${domain}, the company’s own website${date ? ` (${date})` : ''}.`
  return <Hint text={text}>{icon}</Hint>
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

/** Small line icons for buttons (same size and weight everywhere). */
export function Icon({ name }: { name: 'edit' | 'refresh' | 'search' }) {
  const paths: Record<string, string> = {
    edit: 'M3 13.5V16h2.5l7.4-7.4-2.5-2.5L3 13.5zM14.7 6.8a.7.7 0 0 0 0-1l-1.5-1.5a.7.7 0 0 0-1 0l-1.2 1.2 2.5 2.5 1.2-1.2z',
    refresh: 'M15 9a6 6 0 1 1-1.8-4.3M15 3.5v3.7h-3.7',
    search: 'M8.5 14a5.5 5.5 0 1 0 0-11 5.5 5.5 0 0 0 0 11zM16 16l-3.6-3.6',
  }
  const filled = name === 'edit'
  return (
    <svg className="btn-icon" viewBox="0 0 18 18" width="14" height="14" aria-hidden>
      <path d={paths[name]} fill={filled ? 'currentColor' : 'none'} stroke={filled ? 'none' : 'currentColor'}
        strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
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
const DEFAULT_REVIEWER = 'Employee 23' // placeholder identity for the prototype (no login)

export function useReviewer(): [string, (v: string) => void] {
  const read = () => {
    try {
      return localStorage.getItem(REVIEWER_KEY) || DEFAULT_REVIEWER
    } catch {
      return DEFAULT_REVIEWER
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
