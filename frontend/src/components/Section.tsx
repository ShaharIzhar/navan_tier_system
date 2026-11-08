import { useState, type ReactNode, type SyntheticEvent } from 'react'

type Align = 'center' | 'left' | 'right'

/** Pick a side so the bubble (max 280px) stays on screen. */
function useAutoAlign(preferred?: Align) {
  const [align, setAlign] = useState<Align>(preferred ?? 'center')
  const onEnter = (e: SyntheticEvent<HTMLElement>) => {
    if (preferred) return
    const r = e.currentTarget.getBoundingClientRect()
    const mid = r.left + r.width / 2
    if (mid < 160) setAlign('left')
    else if (window.innerWidth - mid < 160) setAlign('right')
    else setAlign('center')
  }
  return { align, onEnter }
}

/** Small ⓘ that explains something on hover or keyboard focus. */
export function Info({ text, align }: { text: string; align?: Align }) {
  const a = useAutoAlign(align)
  if (!text) return null
  return (
    <span className={`tip tip-${a.align}`} tabIndex={0} aria-label={text} onMouseEnter={a.onEnter} onFocus={a.onEnter}
      onClick={(e) => e.stopPropagation()}>
      <span className="tip-icon" aria-hidden>i</span>
      <span className="tip-bubble" role="tooltip">{text}</span>
    </span>
  )
}

/** Wraps any element with a hover explanation (dotted underline). */
export function Hint({ text, children, align }: { text: string; children: ReactNode; align?: Align }) {
  const a = useAutoAlign(align)
  if (!text) return <>{children}</>
  return (
    <span className={`tip hint tip-${a.align}`} tabIndex={0} onMouseEnter={a.onEnter} onFocus={a.onEnter}>
      {children}
      <span className="tip-bubble" role="tooltip">{text}</span>
    </span>
  )
}

/** Text clamped to a few lines, expandable on click. */
export function Clamp({ text, lines = 2 }: { text: string; lines?: number }) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <div className={open ? '' : 'clamp'} style={open ? undefined : { WebkitLineClamp: lines }}>{text}</div>
      <button className="more" onClick={() => setOpen(!open)}>{open ? 'Less' : 'More'}</button>
    </div>
  )
}

function readOpen(id: string, fallback: boolean) {
  try {
    const v = localStorage.getItem(`ngi.section.${id}`)
    return v == null ? fallback : v === '1'
  } catch {
    return fallback
  }
}

/** Titled, collapsible card. Remembers open/closed per section. */
export function Section({
  id, title, info, summary, actions, defaultOpen = true, children, flush = false,
}: {
  id: string
  title: string
  info?: string
  summary?: ReactNode
  actions?: ReactNode
  defaultOpen?: boolean
  children: ReactNode
  flush?: boolean
}) {
  const [open, setOpen] = useState(() => readOpen(id, defaultOpen))
  const toggle = () => {
    setOpen((o) => {
      try {
        localStorage.setItem(`ngi.section.${id}`, o ? '0' : '1')
      } catch {
        /* storage unavailable */
      }
      return !o
    })
  }
  return (
    <section className={`card section${open ? ' open' : ''}`}>
      <div className="section-head">
        <button className="section-toggle" onClick={toggle} aria-expanded={open}>
          <span className="chev" aria-hidden>{open ? '▾' : '▸'}</span>
          <h2>{title}</h2>
        </button>
        {info && <Info text={info} />}
        {summary && <span className="section-summary">{summary}</span>}
        {actions && <span className="section-actions">{actions}</span>}
      </div>
      {open && <div className={flush ? 'section-body flush' : 'section-body'}>{children}</div>}
    </section>
  )
}
