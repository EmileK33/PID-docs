import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// Vitest config for S1-F unit tests. Kept separate from vite.config.ts (an
// S0-A entry-point file) so the build config stays untouched.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}', 'src/**/*.test.{ts,tsx}'],
    // Mirror the test pre-conditions from the S1-F manifest.
    env: {
      VITE_API_BASE_URL: 'http://localhost:8000',
      VITE_SUPABASE_URL: 'http://localhost:54321',
      VITE_SUPABASE_ANON_KEY: 'test-anon-key',
      // VITE_POSTHOG_API_KEY intentionally unset → analytics is a no-op.
    },
  },
});
