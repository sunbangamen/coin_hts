import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true, // Docker에서 0.0.0.0으로 바인드
    proxy: {
      '/api': {
        // Docker 환경에서는 backend 서비스로, 로컬에서는 localhost로 연결
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '/api')
      }
    }
  }
})
