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
  const toggle = (v: string) => onChange(selected.includes(v) ? selected.filter((x) => x !== v) : [...selected, v])

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
              <input type="checkbox" checked={selected.includes(o.value)} onChange={() => toggle(o.value)} />
              <span>{o.label}</span>
            </label>
          ))}
          {selected.length > 0 && (
            <button type="button" className="more multi-clear" onClick={() => onChange([])}>Clear</button>
          )}
        </div>
      )}
    </div>
  )
}
