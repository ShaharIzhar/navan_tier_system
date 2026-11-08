import '@testing-library/jest-dom/vitest'

// Node 25 ships an experimental global `localStorage` that shadows jsdom's and is
// non-functional without --localstorage-file. Provide a simple in-memory Storage.
class MemoryStorage {
  private m = new Map<string, string>()
  get length() { return this.m.size }
  clear() { this.m.clear() }
  getItem(k: string) { return this.m.has(k) ? this.m.get(k)! : null }
  key(i: number) { return Array.from(this.m.keys())[i] ?? null }
  removeItem(k: string) { this.m.delete(k) }
  setItem(k: string, v: string) { this.m.set(k, String(v)) }
}
Object.defineProperty(globalThis, 'localStorage', { value: new MemoryStorage(), configurable: true })
