/// <reference types="vite/client" />

// Typed view of the environment variables this app reads. All are optional at
// the type level; runtime guards (e.g. in api/client.ts) enforce presence where
// it matters (production builds require VITE_API_BASE_URL).
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_SUPABASE_URL?: string;
  readonly VITE_SUPABASE_ANON_KEY?: string;
  readonly VITE_POSTHOG_API_KEY?: string;
  readonly VITE_POSTHOG_HOST?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
