import { useEffect, useRef, useState } from 'react'

export type Option = { value: string; label: string }

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
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false)
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', esc)
    }
  }, [open])

  const names = selected.map((v) => shortLabels?.[v] ?? options.find((o) => o.value === v)?.label ?? v)
  const summary = selected.length === 0 ? allLabel : selected.length === 1 || shortLabels ? names.join(', ') : `${selected.length} selected`
  // Empty selection means "all", so every box shows as ticked. Unticking narrows the filter;
  // ticking everything again (or unticking the last one) goes back to "all".
  const all = options.map((o) => o.value)
  const isChecked = (v: string) => selected.length === 0 || selected.includes(v)
  const toggle = (v: string) => {
    const current = selected.length === 0 ? all : selected
    const next = current.includes(v) ? current.filter((x) => x !== v) : [...current, v]
    onChange(next.length === 0 || next.length === all.length ? [] : all.filter((x) => next.includes(x)))
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
          {selected.length > 0 && (
            <button type="button" className="more multi-clear" onClick={() => onChange([])}>Select all</button>
          )}
        </div>
      )}
    </div>
  )
}
