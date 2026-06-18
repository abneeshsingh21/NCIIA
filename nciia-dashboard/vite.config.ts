import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  envPrefix: 'VITE_',
  server: {
    port: 5173,
    proxy: {
      // Proxy /api and /ws to the FastAPI backend so dev has no CORS issues
      '/api': {
        target: process.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/ws': {
        target: process.env.VITE_WS_URL ?? 'ws://localhost:8000',
        changeOrigin: true,
        ws: true,
        secure: false,
      },
      '/health': {
        target: process.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    target: 'esnext',
    sourcemap: true,
    rollupOptions: {
      output: {
        // Code-split heavy 3D libraries into their own chunk
        manualChunks: {
          three: ['three', '@react-three/fiber', '@react-three/drei'],
          charts: ['recharts', 'd3'],
          graph: ['react-force-graph-2d'],
        },
      },
    },
  },
})
