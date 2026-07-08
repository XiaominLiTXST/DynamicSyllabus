import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Dev: proxy /api to the FastAPI backend so there are no CORS issues locally.
// Override the backend URL with VITE_BACKEND_URL if you run it on another port.
const backend = process.env.VITE_BACKEND_URL ?? 'http://localhost:8010'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': backend,
    },
  },
})
