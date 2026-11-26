import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  // The app uses /api/v1; proxy the whole API prefix to FastAPI in dev.
  server: {
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: process.env.FRONTEND_API_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
