import { useCallback, useState } from 'react'
import { useDismiss } from './ui'

export type Option = { value: string; label: string }

/** Selection value meaning "nothing ticked". Never matches a real value, so the filter shows no rows. */
export const NONE = '__none__'

/** Pill-style filter with a checkbox list. Empty selection = no filter ("All"). */
export default function MultiSelect({ label, options, selected, onChange, allLabel = 'All', shortLabels }: {
  label: string
  options: Option[]
  selected: string[]
  onChange: (v: string[]) => void
  allLabel?: string
  /** Short names shown on the pill when several are chosen (e.g. "1, 2" for tiers). */
  shortLabels?: Record<string, string>
}) {
  const [open, setOpen] = useState(false)
  const ref = useDismiss(open, useCallback(() => setOpen(false), []))

  // [] = all ticked (no filter). [NONE] = nothing ticked (shows no rows). Otherwise the ticked values.
  const all = options.map((o) => o.value)
  const none = selected.length === 1 && selected[0] === NONE
  const names = selected.map((v) => shortLabels?.[v] ?? options.find((o) => o.value === v)?.label ?? v)
  const summary = selected.length === 0 ? allLabel : none ? 'None'
    : selected.length === 1 || shortLabels ? names.join(', ') : `${selected.length} selected`
  const isChecked = (v: string) => selected.length === 0 || selected.includes(v)
  const toggle = (v: string) => {
    const current = selected.length === 0 ? all : none ? [] : selected
    const next = current.includes(v) ? current.filter((x) => x !== v) : [...current, v]
    onChange(next.length === 0 ? [NONE] : next.length === all.length ? [] : all.filter((x) => next.includes(x)))
  }

  return (
    <div className="multi" ref={ref}>
      <button type="button" className={`pill-select multi-btn${selected.length ? ' on' : ''}`} aria-haspopup="listbox" aria-expanded={open}
        aria-label={`${label} filter`} onClick={() => setOpen(!open)}>
        {label}: {summary}
      </button>
      {open && (
        <div className="multi-pop" role="listbox" aria-multiselectable="true" aria-label={label}>
          {options.map((o) => (
            <label key={o.value} className="multi-opt">
              <input type="checkbox" checked={isChecked(o.value)} onChange={() => toggle(o.value)} />
              <span>{o.label}</span>
            </label>
          ))}
          <div className="multi-actions">
            <button type="button" className="more" disabled={selected.length === 0} onClick={() => onChange([])}>Select all</button>
            <button type="button" className="more" disabled={none} onClick={() => onChange([NONE])}>Clear</button>
          </div>
        </div>
      )}
    </div>
  )
}
