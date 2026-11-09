import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'
import { Modal } from './ui'

export type ConfirmOptions = {
  title: string
  body: ReactNode
  confirmLabel: string
  tone?: 'primary' | 'approve' | 'danger'
}

type Ctx = (o: ConfirmOptions) => Promise<boolean>
const ConfirmContext = createContext<Ctx>(async () => true)

/** App-wide confirmation dialog. `await confirm({...})` resolves true only on an explicit Confirm. */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [opts, setOpts] = useState<ConfirmOptions | null>(null)
  const resolver = useRef<(v: boolean) => void>(() => {})
  const confirm = useCallback<Ctx>((o) => {
    setOpts(o)
    return new Promise<boolean>((resolve) => {
      resolver.current = resolve
    })
  }, [])
  const close = (v: boolean) => {
    resolver.current(v)
    setOpts(null)
  }
  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {opts && (
        <Modal title={opts.title} onClose={() => close(false)}>
          <div className="stack" style={{ gap: 14 }}>
            <div className="confirm-body">{opts.body}</div>
            <div className="row" style={{ justifyContent: 'flex-end' }}>
              <button onClick={() => close(false)}>Cancel</button>
              <button className={opts.tone ?? 'primary'} autoFocus onClick={() => close(true)}>{opts.confirmLabel}</button>
            </div>
          </div>
        </Modal>
      )}
    </ConfirmContext.Provider>
  )
}

export const useConfirm = () => useContext(ConfirmContext)
