import { useState } from 'react'
import { api, type Assessment } from '../api'
import { AttentionBadge, FlagChip, TierBadge, Spinner } from './ui'

const PARAMS: { key: string; label: string; kind: 'number' | 'text'; help: string }[] = [
  { key: 'employee_count', label: 'Employee count', kind: 'number', help: 'Used by the 150+ employee Tier 2 rule.' },
  { key: 'travel_requirement', label: 'Direct travel requirement', kind: 'text', help: 'e.g. "Engineers travel to customer sites weekly". Counts as a direct travel signal.' },
  { key: 'funding', label: 'Funding / financial development', kind: 'text', help: 'Growth signal. Never treated as proof of higher GBV.' },
  { key: 'expansion', label: 'Expansion (office / market)', kind: 'text', help: 'Growth signal.' },
  { key: 'geographic_footprint', label: 'Geographic footprint', kind: 'text', help: 'Growth signal (e.g. offices in 4 countries).' },
  { key: 'note', label: 'Free-text note', kind: 'text', help: 'Explanatory only. Does not change flags or tiers.' },
]

export default function EnrichmentForm({ prospectId, reviewer, onDone }: { prospectId: string; reviewer: string; onDone: () => void }) {
  const [param, setParam] = useState('employee_count')
  const [value, setValue] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [note, setNote] = useState('')
  const [verified, setVerified] = useState(false)
  const [accepted, setAccepted] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<{ before: Assessment | null; after: Assessment } | null>(null)
  const spec = PARAMS.find((p) => p.key === param)!

  if (result) return <Diff before={result.before} after={result.after} onClose={onDone} />

  return (
    <form
      className="stack"
      onSubmit={async (e) => {
        e.preventDefault()
        setBusy(true)
        setError(null)
        try {
          const r = await api.enrich(prospectId, { param, value, entered_by: reviewer, source_url: sourceUrl || undefined, note: note || undefined, verified, accepted })
          setResult(r)
        } catch (err) {
          setError(String((err as Error).message))
        } finally {
          setBusy(false)
        }
      }}
    >
      {!reviewer && <div className="callout warn small">Enter your name under “Acting as” in the sidebar first — it is recorded in the audit trail.</div>}
      <label>
        Field
        <select value={param} onChange={(e) => setParam(e.target.value)}>
          {PARAMS.map((p) => (
            <option key={p.key} value={p.key}>{p.label}</option>
          ))}
        </select>
        <span className="muted">{spec.help}</span>
      </label>
      <label>
        Value
        <input required inputMode={spec.kind === 'number' ? 'numeric' : undefined} value={value} onChange={(e) => setValue(e.target.value)} />
      </label>
      <label>
        Source URL (optional)
        <input type="url" placeholder="https://…" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} />
      </label>
      <label>
        Note (optional)
        <textarea value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      <label className="inline">
        <input type="checkbox" checked={verified} onChange={(e) => setVerified(e.target.checked)} disabled={!sourceUrl} />
        I checked this against the source (marks it verified; needs a source URL)
      </label>
      {param !== 'note' && (
        <label className="inline">
          <input type="checkbox" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} />
          Use this value for reassessment
        </label>
      )}
      <p className="small muted">Original research evidence is kept. Saving reruns the rules only — no AI call.</p>
      {error && <div className="callout error small">{error}</div>}
      <div className="row">
        <button className="primary" type="submit" disabled={busy || !reviewer || !value}>
          {busy && <Spinner />} Save and reassess
        </button>
      </div>
    </form>
  )
}

function Diff({ before, after, onClose }: { before: Assessment | null; after: Assessment; onClose: () => void }) {
  const flags = (a: Assessment | null) => (a?.flags ?? []).map((f) => f.label)
  const same = JSON.stringify(flags(before)) === JSON.stringify(flags(after)) && before?.baseline.tier === after.baseline.tier && before?.attention === after.attention
  return (
    <div className="stack">
      <div className="callout action small">Reassessed with the rules only (0 AI calls).{same ? ' Nothing changed in the outcome.' : ''}</div>
      <div className="diff">
        <div>
          <div className="small muted">Before</div>
          <Summary a={before} />
        </div>
        <div>
          <div className="small muted">After</div>
          <Summary a={after} />
        </div>
      </div>
      {after.proposal_ids.length > 0 && <p className="small">A tier proposal is open for review. The applied tier has not changed.</p>}
      <div className="row">
        <button className="primary" onClick={onClose}>Done</button>
      </div>
    </div>
  )
}

function Summary({ a }: { a: Assessment | null }) {
  if (!a) return <span className="muted">—</span>
  return (
    <div className="stack" style={{ gap: 6 }}>
      <div className="row">
        Baseline <TierBadge tier={a.baseline.tier} provisional={a.baseline.provisional} />
      </div>
      <div className="row">
        Employees used: <strong>{a.accepted_values.employees ?? 'unknown'}</strong>
      </div>
      <div className="row"><AttentionBadge attention={a.attention} label={a.attention_label} /></div>
      <div className="row">
        {a.flags.length ? a.flags.map((f, i) => <FlagChip key={i} label={f.label} severity={f.severity} />) : <span className="muted small">No flags</span>}
      </div>
    </div>
  )
}
