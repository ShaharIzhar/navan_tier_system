import { useEffect, useRef, useState } from 'react'
import { useReviewer } from './ui'

/** Top-right user badge. The name is recorded on every decision and correction (audit trail). */
export default function UserMenu() {
  const [name, setName] = useReviewer()
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState(name)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const initials = name.split(/\s+/).filter(Boolean).map((w) => w[0]).join('').slice(0, 2).toUpperCase() || '?'
  const save = () => {
    const v = draft.trim()
    if (v) setName(v)
    setOpen(false)
  }

  return (
    <div className="user-menu" ref={ref}>
      <button className="user-btn" onClick={() => { setDraft(name); setOpen(!open) }} aria-haspopup="dialog" aria-expanded={open}>
        <span className="avatar" aria-hidden>{initials}</span>
        <span className="user-name">{name}</span>
        <span className="chev" aria-hidden>▾</span>
      </button>
      {open && (
        <div className="user-pop" role="dialog" aria-label="Change your name">
          <label>
            Your name
            <input autoFocus value={draft} onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setOpen(false) }} />
          </label>
          <p className="small muted">Shown on your reviews and corrections.</p>
          <div className="row">
            <button className="primary small" onClick={save} disabled={!draft.trim()}>Save</button>
            <button className="small" onClick={() => setOpen(false)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  )
}
