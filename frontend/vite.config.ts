import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite dev/build config for the React SPA. The API is proxied to the FastAPI
// backend during local development (docker-compose service name `api`).
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL ?? 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
