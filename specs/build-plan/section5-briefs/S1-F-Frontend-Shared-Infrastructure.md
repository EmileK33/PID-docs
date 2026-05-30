---

#### S1-F — Frontend Shared Infrastructure

**Phase 1 | Frontend | Needs: S0-A, S0-B**

##### Objective

Provides the shared frontend infrastructure (API client, auth context, SSE/polling hooks, layout chrome, browser storage, analytics) that every Phase 3 SPA page imports, so feature pages can be built without reinventing cross-cutting concerns.

##### Scope

**P0 MVP.** All exports in this session support P0 user stories (US-001 through US-020). No P1-only features (teams UI, comparison UI, table UI) are part of this session, but the API client's `endpoints.ts` MAY include P1 endpoint URLs as constants so downstream P1 sessions don't have to extend it — they are inert until consumed.

##### Technology constraints

From §1.8 (irreversible):
- **React + Vite** for the SPA. Do not use Next.js, CRA, Remix, or Webpack in this directory.
- **Supabase Auth (self-hosted)** for JWT/OAuth. Use `@supabase/supabase-js` client; do not use Auth0, Firebase Auth, or NextAuth.
- **Konva.js** is the canvas library (consumed in S3-D). This session does not import Konva.
- SSE must use the native `EventSource` API (not a 3rd-party SSE library); polling fallback must trigger after detection of EventSource failure or after 10s without an event (§1.9).
- Browser storage keys must exactly match §1.11: `correction_state:{drawing_id}` (localStorage, ≤2MB cap) and `graceBannerDismissed` (sessionStorage).
- Analytics: client emits **only** UI-tracking events; the 9 structured events in §1.10 fire server-side. Client analytics helper wraps PostHog browser SDK (`posthog-js`) and must be a no-op if `VITE_POSTHOG_API_KEY` is absent.

##### Performance targets

None directly owned. Indirectly supports:
- Canvas interaction <200ms P95 (NFR-19) — the `useSSE`/storage helpers must not block render.
- Status push ≤10s polling fallback (§1.9) — `useSSE` must fall back to `usePolling` within 10s of SSE connection failure.

##### Owned files

- `frontend/src/api/client.ts`
- `frontend/src/api/endpoints.ts`
- `frontend/src/auth/AuthContext.tsx`
- `frontend/src/auth/useAuth.ts`
- `frontend/src/auth/supabaseClient.ts`
- `frontend/src/hooks/useSSE.ts`
- `frontend/src/hooks/usePolling.ts`
- `frontend/src/components/Layout.tsx`
- `frontend/src/components/Nav.tsx`
- `frontend/src/components/GraceBanner.tsx`
- `frontend/src/components/ProtectedRoute.tsx`
- `frontend/src/lib/storage.ts`
- `frontend/src/lib/analytics.ts`
- `frontend/src/styles/globals.css`

##### Read-only imports

- From **S0-A**:
  - `frontend/src/types/contracts.ts` — all TS types defined in §1.1 (`DrawingProcessingState`, `DrawingStatusSSEEvent`, `HashCheckRequest`, `HashCheckResponse`, `SymbolsPageResponse`, `BillingState`, `TierId`, `UserRole`, `SymbolSource`, `CorrectionType`, `ExportFormat`, `ExportStatus`, `EntityClassId`, `SymbolRecord`, `CorrectionRecord`, `BoundingBox`, etc.)
  - `frontend/src/router.tsx` — only for understanding route names; do not modify.

##### Do not touch

- `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/router.tsx` (S0-A entry / router stubs).
- `frontend/src/types/contracts.ts` (S0-A owned).
- `frontend/src/pages/_stubs.tsx` and any future `frontend/src/pages/**` or `frontend/src/features/**` (owned by S3-A through S3-G).
- All backend files (`backend/**`), marketing files (`marketing/**`), and integration tests.

##### Architecture context

Pasted verbatim from §1.6, §1.8, §1.9, §1.11:

> **Frontend SPA** — React + Vite. Canvas rendering via Konva.js requires rich ecosystem; pure SPA sufficient for authenticated views; changing post-build would require full frontend rewrite.

> **Auth** — Supabase Auth (self-hosted). JWT RS256, Google OAuth, session invalidation via `admin.signOut(userId)`, Postgres-native; selected over Auth0 to reduce vendor lock-in.

> **Frontend Page Routes**
> ```
> /                          (marketing/landing — Next.js)
> /register
> /login
> /verify-email
> /dashboard                 (Drawing Library)
> /upload                    (File Upload Drop Zone)
> /drawings/{id}/review      (Drawing Review Canvas)
> /account                   (Account Settings)
> /subscription              (Subscription & Upgrade)
> ```

> **Status push to client during processing** — ≤10 second polling fallback. Monitoring target. SSE via Redis pub/sub; 10s polling fallback for proxied connections.

> **Canvas interaction (symbol select + panel open)** — <200ms P95. Hard SLA (NFR-19). React SPA; correction history pre-loaded at canvas init — no additional network fetch on panel open.

> **Browser Storage Keys**
> | Key | Storage Type | Written By | Read By | Purpose |
> |---|---|---|---|---|
> | `correction_state:{drawing_id}` | localStorage (≤2MB cap) | Canvas review SPA | Canvas review SPA on reload | Unsaved correction state flush; server-saved state takes precedence if timestamps conflict |
> | `graceBannerDismissed` | sessionStorage | Drawing Library / global nav component | Global nav component | Session-scoped suppression of grace period banner; resets on new session |

> **Redis Pub/Sub Channels (SSE)** — `drawing:status:{drawing_id}` published by Ingest/Scan/ML Workers, consumed by FastAPI SSE handler (`GET /drawings/{id}/status`) → client. Payload shape: `DrawingStatusSSEEvent` (see §1.1).

##### User stories and acceptance criteria

This session is infrastructure shared by all P0 frontend stories. No individual user story is fully implemented here. The session is validated by its exports being correctly consumed in S3-A through S3-G. Indirectly supports:

- **US-002 login/logout flow** — `AuthContext` must persist Supabase session, expose `signOut()`, and clear local state on `token_invalidated_at` change.
- **US-008 live status updates** — `useSSE` must subscribe to `GET /drawings/{id}/status`, parse `DrawingStatusSSEEvent`, and fall back to `usePolling` of the same endpoint within 10s on failure.
- **US-015 session-restore for corrections** — `storage.ts` must implement the `correction_state:{drawing_id}` localStorage contract with ≤2MB cap.
- **US-020 grace period banner** — `GraceBanner` shows when subscription billing_state is `Grace`; dismissal stored in `sessionStorage['graceBannerDismissed']` for the session.

##### UX and design specification

This session provides chrome and primitives; pixel-level UX lives in the consuming page sessions. Minimal specs that this session DOES own:

- **`<Layout>`**: renders `<Nav />` at top, `<GraceBanner />` below nav (only when applicable), then children. Full-bleed; max-width on inner content set via CSS class `.app-container` in `globals.css`.
- **`<Nav>`**: shows app name (left), and right side: current user email + role badge + signOut button when authenticated; "Log in" / "Register" links when not. Links: Dashboard, Upload, Account, Subscription (only when authenticated). Active route highlighted.
- **`<GraceBanner>`**: full-width yellow banner. Copy: `"Your subscription payment failed. Resolve by {grace_period_end} to keep access."` Includes "Update payment" link to `/subscription` and dismiss "×" button. Dismissal sets `sessionStorage['graceBannerDismissed']='true'`; banner does not show again until next session. Shows ONLY when `subscription.billing_state === 'Grace'` AND `sessionStorage.graceBannerDismissed !== 'true'`.
- **`<ProtectedRoute>`**: renders children if authenticated; redirects to `/login?next={pathname}` otherwise.

##### Critical implementation notes

- **JWT token invalidation check (§1.4 rule 12)**: API client must surface 401 responses; `AuthContext` MUST clear local session state and redirect to `/login` on 401 from any authenticated endpoint. Do not silently retry.
- **SSE fallback timing**: "≤10 second polling fallback for proxied connections" (§1.9). `useSSE` MUST switch to `usePolling` within 10s if EventSource emits `error` or never reaches `open`. Polling interval is also 10s.
- **localStorage cap**: "localStorage (≤2MB cap)" (§1.11). `storage.ts` MUST estimate UTF-16 byte size before writing and throw / return false if write would exceed 2MB. Do not silently truncate.
- **`graceBannerDismissed` scope**: session-only. Use `sessionStorage`, not `localStorage`. New tab = new session = banner reappears.
- **Client-side analytics ≠ §1.10 events**: the 9 structured events in §1.10 MUST fire server-side. `lib/analytics.ts` is for UI-only telemetry (page views, button clicks) and MUST NOT emit any event name from §1.10. Reviewer must reject PRs that emit `drawing_uploaded`, `processing_complete`, etc. from the browser.
- **API base URL**: read from `import.meta.env.VITE_API_BASE_URL`. Refuse to construct client if absent in production build.
- **Pre-signed URL handling**: downloads use S3 URLs directly; the API client must NOT add `Authorization` headers when target host ≠ API base host. Otherwise S3 will reject the signed request.
- **HTTP status contract awareness (§1.5)**: API client must NOT auto-treat 409 (hash blocked) or 403 (forbidden) as errors that retry; expose status code in error object so callers can branch.

##### Mocking contract

This session is the API client; downstream frontend sessions use it. The endpoint manifest (`endpoints.ts`) must list method + path constants for every P0 route in §1.6 plus P1 endpoints as inert constants:

```ts
// P0 — all required
POST   /auth/register
POST   /auth/login
POST   /auth/oauth/google
POST   /auth/refresh
POST   /auth/logout                        → 204
POST   /auth/password-reset/request        → 204
POST   /auth/password-reset/confirm        → 204
POST   /drawings/hash-check                → 200 HashCheckResponse | 409
GET    /drawings
POST   /drawings                           → requires prior hash-check; 400 otherwise
GET    /drawings/{id}
PATCH  /drawings/{id}
DELETE /drawings/{id}                      → 204
POST   /drawings/{id}/retry
GET    /drawings/{id}/status               (SSE)
GET    /drawings/{id}/symbols              → SymbolsPageResponse
PATCH  /symbols/{id}
POST   /drawings/{id}/symbols
POST   /drawings/{id}/exports
GET    /exports/{id}
POST   /drawings/{id}/upload-complete      → 202 first time, 200 idempotent
GET    /account
PATCH  /account
DELETE /account                            → 204
GET    /account/consent
PATCH  /account/consent
GET    /subscription
POST   /subscription/checkout
POST   /webhooks/stripe                    (not called from client)
GET    /entity-classes
```

For SSE `GET /drawings/{id}/status`, payload conforms to `DrawingStatusSSEEvent` from §1.1:
```ts
{ drawing_id: string; state: DrawingProcessingState; timestamp: string }
```

For tests in this session, mock `fetch` and `EventSource` with shapes matching the above. Do not mock real backends.

##### Acceptance criteria checklist

- [ ] `apiClient.get/post/patch/delete` attach Bearer JWT from current Supabase session when target host = API base host [tech]
- [ ] `apiClient` does NOT attach Authorization header when calling a non-API host (e.g., S3 pre-signed URL) [tech]
- [ ] On any 401 response from API host, `AuthContext` clears session and redirects to `/login` [tech]
- [ ] `apiClient` errors expose the HTTP status code (so callers can distinguish 409 hash-blocked from 400 generic) [tech]
- [ ] `useSSE` opens EventSource to `GET /drawings/{id}/status` and emits typed `DrawingStatusSSEEvent` objects to consumers [tech]
- [ ] `useSSE` falls back to `usePolling` within 10 seconds if EventSource errors or never opens [tech]
- [ ] `usePolling` polls the same endpoint every 10 seconds and emits the same `DrawingStatusSSEEvent` shape [tech]
- [ ] `storage.setItem` rejects writes that would push the key past 2MB UTF-16 (returns false / throws) [tech]
- [ ] `storage.getCorrectionState(drawingId)` reads from `correction_state:{drawing_id}` localStorage key; `setCorrectionState` writes to it [tech]
- [ ] `GraceBanner` renders only when `subscription.billing_state === 'Grace'` AND `sessionStorage.graceBannerDismissed !== 'true'` [tech]
- [ ] `GraceBanner` dismiss button sets `sessionStorage.graceBannerDismissed = 'true'` and hides banner immediately [tech]
- [ ] `ProtectedRoute` redirects unauthenticated users to `/login?next={current pathname}` [tech]
- [ ] `ProtectedRoute` renders children when `AuthContext.user` is set [tech]
- [ ] `AuthContext` exposes `user`, `session`, `signIn`, `signOut`, `loading` [tech]
- [ ] `lib/analytics.ts` is a no-op when `VITE_POSTHOG_API_KEY` is absent (does not throw) [tech]
- [ ] `lib/analytics.ts` exports do not include any of the 9 server-side event names from §1.10 [tech]
- [ ] `endpoints.ts` exports a constant for every P0 route in §1.6 [tech]
- [ ] Visual chrome (Layout/Nav) renders without runtime errors when wrapped around an empty page [MANUAL]

##### Independent Test

- **Test file path**: `frontend/tests/sessions/s1-f.test.ts`
- **Exact CI command**: `cd frontend && npm test -- tests/sessions/s1-f`
- **AC → assertion mapping**:
  - JWT attach → `it("attaches Bearer token for API host requests")`
  - No JWT on S3 → `it("does not attach Authorization header for non-API hosts")`
  - 401 logout → `it("clears session and redirects on 401")`
  - Error status exposed → `it("exposes status code on error responses")`
  - SSE typed → `it("useSSE emits DrawingStatusSSEEvent objects")`
  - SSE fallback ≤10s → `it("useSSE falls back to polling within 10 seconds on error")`
  - Polling interval → `it("usePolling polls every 10 seconds")`
  - Storage 2MB cap → `it("storage rejects writes exceeding 2MB cap")`
  - Correction state keys → `it("reads/writes correction_state:{drawingId} key")`
  - GraceBanner visibility → `it("shows banner only when billing_state=Grace and not dismissed")`
  - GraceBanner dismiss → `it("dismissing sets sessionStorage and hides banner")`
  - ProtectedRoute redirect → `it("redirects to /login?next= when unauthenticated")`
  - ProtectedRoute render → `it("renders children when authenticated")`
  - AuthContext shape → `it("exposes user, session, signIn, signOut, loading")`
  - Analytics no-op → `it("analytics is no-op without VITE_POSTHOG_API_KEY")`
  - No server event names → `it("analytics module does not export server event names")`
  - Endpoint manifest → `it("endpoints.ts includes every P0 route")`

- **Fixtures / test doubles**:
  - Mock `fetch` via `vi.fn()` / MSW for status code assertions.
  - Mock `EventSource` global with controllable `open`/`error`/`message` events.
  - Mock `@supabase/supabase-js` to return a stub session object with `access_token`.
  - JSDOM provides localStorage/sessionStorage.

- **Pre-conditions**: `VITE_API_BASE_URL=http://localhost:8000` set in test env; `@supabase/supabase-js`, `posthog-js`, `react-router-dom`, `vitest`, `@testing-library/react` installed via S0-B's `frontend/package.json`.

- **Isolation rule**: All tests use mocks; no backend, no Supabase, no PostHog network calls. Passes when only this PR is merged.

##### Checkpoint

- **Observable outcome**: A developer can wrap an empty placeholder page in `<Layout>` + `<ProtectedRoute>` and the unit test suite for `frontend/src/api`, `frontend/src/auth`, `frontend/src/hooks`, `frontend/src/components`, and `frontend/src/lib` passes green.
- **Shippability claim**: this PR is independently mergeable to main even if no other session in the same wave has merged. It depends only on S0-A scaffold and S0-B test harness, both gating Phase 0 → Phase 1.

##### Output and handoff

Consumed by S3-A, S3-B, S3-C, S3-D, S3-E, S3-F, S3-G:

- `apiClient` from `frontend/src/api/client.ts` [LOAD-BEARING] — `{ get, post, patch, delete: <T>(path: string, opts?) => Promise<T> }`
- `endpoints` from `frontend/src/api/endpoints.ts` [LOAD-BEARING] — route constants map
- `AuthContext`, `AuthProvider` from `frontend/src/auth/AuthContext.tsx` [LOAD-BEARING]
- `useAuth` from `frontend/src/auth/useAuth.ts` [LOAD-BEARING]
- `supabase` client from `frontend/src/auth/supabaseClient.ts`
- `useSSE<T>(url: string)` from `frontend/src/hooks/useSSE.ts` [LOAD-BEARING]
- `usePolling<T>(url: string, intervalMs?: number)` from `frontend/src/hooks/usePolling.ts`
- `Layout`, `Nav`, `GraceBanner`, `ProtectedRoute` from `frontend/src/components/*` [LOAD-BEARING]
- `storage` namespace from `frontend/src/lib/storage.ts` — `getCorrectionState`, `setCorrectionState`, `clearCorrectionState`, `isGraceBannerDismissed`, `dismissGraceBanner`
- `analytics` from `frontend/src/lib/analytics.ts` — `track(event: string, props?: Record<string, unknown>)`, `identify(userId: string)`

---

```json
{
  "test": { "cmd": "cd frontend && npm test -- tests/sessions/s1-f", "file": "frontend/tests/sessions/s1-f.test.ts" },
  "checkpoint": "A developer can wrap an empty placeholder page in <Layout> + <ProtectedRoute> and the unit tests for frontend/src/api, /auth, /hooks, /components, /lib pass green.",
  "manualAcs": [
    { "id": "TECH-VISUAL-1", "text": "Visual chrome (Layout/Nav) renders without runtime errors when wrapped around an empty page." }
  ],
  "exports": [
    { "kind": "module", "name": "frontend/src/api/client", "shape": "frontend/src/api/client.ts" },
    { "kind": "module", "name": "frontend/src/api/endpoints", "shape": "frontend/src/api/endpoints.ts" },
    { "kind": "function", "name": "apiClient.get", "shape": "<T>(path: string, opts?: { headers?: Record<string,string> }) => Promise<T>" },
    { "kind": "function", "name": "apiClient.post", "shape": "<T>(path: string, body?: unknown, opts?: { headers?: Record<string,string> }) => Promise<T>" },
    { "kind": "function", "name": "apiClient.patch", "shape": "<T>(path: string, body?: unknown) => Promise<T>" },
    { "kind": "function", "name": "apiClient.delete", "shape": "<T>(path: string) => Promise<T>" },
    { "kind": "module", "name": "frontend/src/auth/AuthContext", "shape": "frontend/src/auth/AuthContext.tsx" },
    { "kind": "function", "name": "useAuth", "shape": "() => { user: User | null; session: Session | null; signIn: (email:string,password:string)=>Promise<void>; signOut: ()=>Promise<void>; loading: boolean }" },
    { "kind": "function", "name": "useSSE", "shape": "<T>(url: string) => { data: T | null; error: Error | null; isPolling: boolean }" },
    { "kind": "function", "name": "usePolling", "shape": "<T>(url: string, intervalMs?: number) => { data: T | null; error: Error | null }" },
    { "kind": "module", "name": "frontend/src/components/Layout", "shape": "frontend/src/components/Layout.tsx" },
    { "kind": "module", "name": "frontend/src/components/Nav", "shape": "frontend/src/components/Nav.tsx" },
    { "kind": "module", "name": "frontend/src/components/GraceBanner", "shape": "frontend/src/components/GraceBanner.tsx" },
    { "kind": "module", "name": "frontend/src/components/ProtectedRoute", "shape": "frontend/src/components/ProtectedRoute.tsx" },
    { "kind": "function", "name": "storage.getCorrectionState", "shape": "(drawingId: string) => unknown | null" },
    { "kind": "function", "name": "storage.setCorrectionState", "shape": "(drawingId: string, state: unknown) => boolean" },
    { "kind": "function", "name": "storage.clearCorrectionState", "shape": "(drawingId: string) => void" },
    { "kind": "function", "name": "storage.isGraceBannerDismissed", "shape": "() => boolean" },
    { "kind": "function", "name": "storage.dismissGraceBanner", "shape": "() => void" },
    { "kind": "function", "name": "analytics.track", "shape": "(event: string, props?: Record<string, unknown>) => void" },
    { "kind": "function", "name": "analytics.identify", "shape": "(userId: string) => void" }
  ]
}
```