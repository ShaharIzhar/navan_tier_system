
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Optional overrides: PORT (dev server) and API_URL (backend). No @types/node needed for these two.
declare const process: { env: Record<string, string | undefined> }

export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.PORT ?? 5173),
    proxy: { '/api': process.env.API_URL ?? 'http://127.0.0.1:8000' },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
})
