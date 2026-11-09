import { useMemo, useState, type ReactNode } from 'react'

export type SortDir = 'asc' | 'desc'
type Getter<T> = (row: T) => string | number | null | undefined

/** Click-to-sort for tables. No sort key = keep the incoming order (e.g. priority). */
export function useSort<T>(rows: T[], getters: Record<string, Getter<T>>) {
  const [key, setKey] = useState<string | null>(null)
  const [dir, setDir] = useState<SortDir>('asc')
  const sorted = useMemo(() => {
    if (!key || !getters[key]) return rows
    const get = getters[key]
    const out = [...rows].sort((a, b) => {
      const x = get(a), y = get(b)
      if (x == null && y == null) return 0
      if (x == null) return 1 // empty values always last
      if (y == null) return -1
      const c = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y))
      return dir === 'asc' ? c : -c
    })
    return out
    // getters are stable per render for our purposes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, key, dir])
  const toggle = (k: string) => {
    if (key === k) setDir(dir === 'asc' ? 'desc' : 'asc')
    else {
      setKey(k)
      setDir('asc')
    }
  }
  return { sorted, key, dir, toggle }
}

export function SortTh({ k, sort, children, className }: {
  k: string
  sort: { key: string | null; dir: SortDir; toggle: (k: string) => void }
  children: ReactNode
  className?: string
}) {
  const active = sort.key === k
  return (
    <th className={className} aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button type="button" className={`sort-btn${active ? ' active' : ''}`} onClick={() => sort.toggle(k)}>
        {children}
        <span className="sort-ind" aria-hidden>{active ? (sort.dir === 'asc' ? '▲' : '▼') : '↕'}</span>
      </button>
    </th>
  )
}
