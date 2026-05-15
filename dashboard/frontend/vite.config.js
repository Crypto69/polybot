import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Dev: Vite on :5173 proxies API + WebSocket to the FastAPI server on :8787.
// Prod: `npm run build` -> dist/, served directly by server.py (single process).
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8787', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:8787', ws: true },
    },
  },
  build: { outDir: 'dist', emptyOutDir: true },
})
