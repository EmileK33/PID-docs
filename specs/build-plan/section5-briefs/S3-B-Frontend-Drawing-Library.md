#### S3-B — Frontend: Drawing Library

**Phase 3 | Frontend | Needs: S1-F, S2-B**

---

##### Objective

Build the authenticated Drawing Library page (`/dashboard`) — including list rendering, status badges, search/filter, pagination, retry/delete actions, and auto-polling for in-progress drawings — giving users full visibility and control over their processing queue.

---

##### Scope

**P0 MVP.** All work in this session is P0.

| Story | Priority |
|---|---|
| US-006 Drawing Library with pagination, status badges, revision labels | P0 |
| US-007 Drawing Library search and filter (filename/revision, status, date range) | P0 |
| US-008 Live status updates (polling fallback in library view) | P0 |
| US-009 Retry failed jobs; delete drawings with confirmation | P0 |
| US-018 Free-tier upgrade prompt in library (partial — display only; enforcement is backend) | P0 |

No P1 work is in scope for this session. Team library views (US-024) and revision comparison entry points (US-025) are P1 and must **not** be silently omitted; instead, add clearly marked `// P1 STUB` comments in `DrawingRow.tsx` at the locations where team-ownership attribution and comparison links will be inserted.

---

##### Technology constraints

From §1.8 — these are non-negotiable:

| Layer | Mandated Choice | Rationale |
|---|---|---|
| Frontend SPA | **React + Vite** | Architecturally irreversible — Canvas rendering via Konva.js requires rich ecosystem; pure SPA sufficient for authenticated views |
| Language | **TypeScript** | Project-wide; all `.tsx`/`.ts` files must be typed |
| State management | **React hooks + context only** | No Redux or Zustand introduced in this session; the existing `AuthContext` (S1-F) covers auth state |
| HTTP client | **`frontend/src/api/client.ts`** from S1-F | Do not introduce `axios` or a separate fetch wrapper |
| Test runner | **Vitest + React Testing Library** | Consistent with Vite toolchain; do not introduce Jest |

**Must NOT use:**
- `axios` — the project's HTTP layer is the shared `client.ts`
- `react-query` / `swr` / `tanstack-query` — introduce no external data-fetching libraries; use the `usePolling` hook from S1-F for polling
- Any CSS-in-JS library — use `globals.css` plus Tailwind utility classes (or CSS modules) only

---

##### Performance targets

| Metric | Target | Hard SLA or Monitoring Target | Source |
|---|---|---|---|
| Dashboard (Drawing Library) load | **<2s P95** | Monitoring target | §1.9 — "FastAPI + PostgreSQL (paginated 25 records, indexed queries)" |

The 25-records-per-page default is specified in §1.9 and must be honored as the `limit` default in `useDrawings`. The frontend is responsible for rendering within that budget; backend pagination is already indexed.

---

##### Owned files

```
frontend/src/pages/Dashboard.tsx
frontend/src/features/library/DrawingList.tsx
frontend/src/features/library/DrawingRow.tsx
frontend/src/features/library/StatusBadge.tsx
frontend/src/features/library/SearchFilter.tsx
frontend/src/features/library/Pagination.tsx
frontend/src/features/library/useDrawings.ts
```

---

##### Read-only imports

| Owning Session | File | Named Exports Required |
|---|---|---|
| S1-F | `frontend/src/api/client.ts` | `apiClient` (or default export — the configured fetch wrapper) |
| S1-F | `frontend/src/api/endpoints.ts` | `DRAWINGS_LIST`, `DRAWING_DELETE`, `DRAWING_RETRY` endpoint constants |
| S1-F | `frontend/src/auth/AuthContext.tsx` | `AuthContext` |
| S1-F | `frontend/src/auth/useAuth.ts` | `useAuth` |
| S1-F | `frontend/src/hooks/usePolling.ts` | `usePolling` |
| S1-F | `frontend/src/components/Layout.tsx` | `Layout` |
| S1-F | `frontend/src/components/Nav.tsx` | `Nav` |
| S1-F | `frontend/src/components/GraceBanner.tsx` | `GraceBanner` |
| S1-F | `frontend/src/components/ProtectedRoute.tsx` | `ProtectedRoute` |
| S1-F | `frontend/src/lib/storage.ts` | `getSessionItem`, `setSessionItem` |
| S0-A | `frontend/src/types/contracts.ts` | `DrawingProcessingState`, `BillingState`, `TierId`, `UserRole` |
| S0-A | `frontend/src/router.tsx` | *(import only for `<Link>` navigation — do not modify)* |

---

##### Do not touch

- `frontend/src/main.tsx` — entry point, pre-stubbed by S0-A
- `frontend/src/App.tsx` — pre-stubbed by S0-A
- `frontend/src/router.tsx` — route stubs pre-wired by S0-A; do not add or modify routes
- `frontend/src/pages/_stubs.tsx` — placeholder stubs owned by S0-A
- `frontend/src/types/contracts.ts` — owned by S0-A
- `frontend/src/api/client.ts` — owned by S1-F
- `frontend/src/api/endpoints.ts` — owned by S1-F
- `frontend/src/auth/AuthContext.tsx` — owned by S1-F
- `frontend/src/auth/useAuth.ts` — owned by S1-F
- `frontend/src/hooks/usePolling.ts` — owned by S1-F
- `frontend/src/hooks/useSSE.ts` — owned by S1-F (used by S3-D review canvas, not this session)
- `frontend/src/components/Layout.tsx` — owned by S1-F
- `frontend/src/components/Nav.tsx` — owned by S1-F
- `frontend/src/components/GraceBanner.tsx` — owned by S1-F
- `frontend/src/components/ProtectedRoute.tsx` — owned by S1-F
- `frontend/src/lib/storage.ts` — owned by S1-F
- `frontend/src/lib/analytics.ts` — owned by S1-F
- `frontend/src/styles/globals.css` — owned by S1-F
- All files under `frontend/src/features/canvas/` — owned by S3-D
- All files under `frontend/src/features/upload/` — owned by S3-C
- All files under `frontend/src/features/exports/` — owned by S3-G
- All files under `frontend/src/features/subscription/` — owned by S3-F
- All files under `frontend/src/features/account/` — owned by S3-E
- All backend files — owned by Phase 1 and Phase 2 sessions

---

##### Architecture context

The following sections are quoted verbatim from the distilled specification:

**From §1.3 — Role-Permission Matrix (relevant rows):**

```typescript
const ROLE_PERMISSIONS = {
  user: {
    drawing_upload:          true,
    drawing_view:            'own',     // own drawings only
    drawing_delete:          'own',
    drawing_retry:           'own',
    symbol_correct:          'own',
    export_initiate:         'own',
    team_manage:             false,
    billing_manage:          true,      // personal subscription
    gdpr_delete_account:     true,
  },
  team_member: {
    drawing_upload:          true,      // uploads to shared team library
    drawing_view:            'team',    // all team drawings
    drawing_delete:          false,     // blocked — admin only
    drawing_retry:           'team',
    symbol_correct:          'team',
    export_initiate:         'team',
    team_manage:             false,
    billing_manage:          false,
    gdpr_delete_account:     true,
  },
  team_admin: {
    drawing_upload:          true,
    drawing_view:            'team',
    drawing_delete:          'team',    // all team drawings
    drawing_retry:           'team',
    symbol_correct:          'team',
    export_initiate:         'team',
    team_manage:             true,      // invite, remove members, set team consent
    billing_manage:          true,      // team subscription
    gdpr_delete_account:     true,
  },
} as const;
```

**From §1.3 — Feature-Tier Gate Matrix (relevant rows):**

```typescript
const TIER_FEATURE_GATES = {
  free: {
    monthly_drawing_limit:   3,
    export_csv_xlsx:         true,
    revision_comparison:     false,     // Pro/Team only
    team_library:            false,     // Team only
    api_access:              false,
  },
  pro: {
    monthly_drawing_limit:   null,      // unlimited
    export_csv_xlsx:         true,
    revision_comparison:     true,
    team_library:            false,
    api_access:              false,
  },
  team: {
    monthly_drawing_limit:   null,
    export_csv_xlsx:         true,
    revision_comparison:     true,
    team_library:            true,
    api_access:              false,     // P1 (FR-11)
  },
} as const;
```

**From §1.3 — Drawing Processing State Transitions:**

```typescript
const DRAWING_STATE_TRANSITIONS: Record<DrawingProcessingState, DrawingProcessingState[]> = {
  Pending:      ['Queued', 'Failed'],
  Queued:       ['Scanning', 'Failed'],
  Scanning:     ['Processing', 'Scan_Failed', 'Failed'],
  Processing:   ['Complete', 'Failed'],
  Complete:     ['Under_Review', 'Queued'],
  Under_Review: ['Queued'],
  Failed:       ['Queued'],
  Scan_Failed:  [],                             // Terminal — no retry permitted
} as const;
```

**From §1.9 — Performance Targets:**

> Dashboard (Drawing Library) load | <2s P95 | Monitoring target | FastAPI + PostgreSQL (paginated 25 records, indexed queries)

> Symbol pagination default / max | 200 default / 500 max per page | Hard constraint | `GET /drawings/{id}/symbols`

> Status push to client during processing | ≤10 second polling fallback | Monitoring target | SSE via Redis pub/sub; 10s polling fallback for proxied connections

**From §1.11 — Browser Storage Keys:**

> | `graceBannerDismissed` | sessionStorage | Drawing Library / global nav component | Global nav component | Session-scoped suppression of grace period banner; resets on new session |

**From §1.6 — Frontend Page Routes:**

```
/dashboard                 (Drawing Library)
/upload                    (File Upload Drop Zone)
/drawings/{id}/review      (Drawing Review Canvas)
/subscription              (Subscription & Upgrade)
```

**From §1.10 — Analytics Event Contracts (events relevant to this session's UI surface):**

> `free_limit_reached` | `{ event: 'free_limit_reached', timestamp: string, user_id: string, drawing_id: string, subscription_id: string }` | FastAPI — processing initiation handler | Free tier user attempts to initiate processing of drawing that would exceed 3/month limit | Processing job must not be queued | Browser client; must fire before upgrade prompt is shown

Note: this event is fired **server-side by FastAPI**, not by the frontend. The frontend's responsibility is to display the upgrade prompt when the API returns the appropriate response; it must **not** fire the analytics event from the browser.

**From §1.13 — P0 Feature Scope (relevant items):**

> - US-006: Drawing Library with pagination, status badges, revision labels
> - US-007: Drawing Library search (filename/revision) and filter (status, date range)
> - US-008: Processing state machine (Pending → Queued → Scanning → Processing → Complete/Failed/Scan_Failed) with live SSE/poll status updates and in-app notifications
> - US-009: Retry failed processing jobs; delete drawings with confirmation (including mid-processing cancellation)
> - US-018: Free tier 3-drawing/month limit enforcement; upgrade prompt on limit hit; tier-gated features visible but inaccessible

**From §1.13 — P1 Feature Scope (items that must be stubbed, not silently omitted):**

> - US-024: Shared team library with role-based permissions (Members cannot delete; Admin can); drawing attribution; removed-member drawing reassignment
> - US-025: Revision comparison — spatial proximity … stale flag; Free tier gate

---

##### User stories and acceptance criteria

The following user stories and acceptance criteria govern this session's implementation. They are derived from the P0 feature descriptions in §1.13 combined with the constraints in §1.3, §1.5, §1.9, and §1.11.

---

**US-006 — Drawing Library**

*As an authenticated user, I want to see all my drawings in a paginated list so that I can track their processing status and navigate to any drawing for review.*

- **AC-1 (Happy path — list load):** Navigating to `/dashboard` renders a list of drawings belonging to the current user; the page loads within the <2s P95 target with 25 drawings per page by default.
- **AC-2 (Row content):** Each drawing row displays: filename, revision label (omitted/blank when `null`), processing state badge, `uploaded_at` formatted as a human-readable date, and `page_count` when available.
- **AC-3 (Status badge — all states):** `StatusBadge` renders a distinct color-coded label for every valid `DrawingProcessingState` value: `Pending`, `Queued`, `Scanning`, `Processing`, `Complete`, `Under_Review`, `Failed`, `Scan_Failed`.
- **AC-4 (Default sort):** Drawings are displayed ordered by `uploaded_at` descending (newest first).
- **AC-5 (Pagination):** Pagination controls show the current page, total drawing count, and allow navigation to next/previous pages. Navigating pages calls `GET /drawings` with updated `offset`.
- **AC-6 (Empty state):** When the user has no drawings, an empty-state message with a link to `/upload` is shown.
- **AC-7 (Protected route):** Unauthenticated users are redirected to `/login` and never see the dashboard.
- **AC-8 (Team-role visibility):** Users with role `team_member` or `team_admin` see all team drawings; users with role `user` see only drawings where `owner_user_id` matches their own ID. *(The API enforces this; the frontend passes the auth token and renders what the API returns.)*

---

**US-007 — Drawing Library Search and Filter**

*As a user, I want to search and filter my drawing library so that I can quickly locate specific drawings.*

- **AC-1 (Search by filename/revision):** A search input allows free-text search. The query is debounced (≥300 ms) and sent as a query parameter to `GET /drawings`; results update without full page reload.
- **AC-2 (Filter by status):** A status filter dropdown lists all `DrawingProcessingState` values plus an "All statuses" default. Selecting a value appends `status=<value>` to the API request.
- **AC-3 (Filter by date range):** A date range picker (from/to, both optional) filters drawings by `uploaded_at`. Selecting either bound appends the corresponding `from` / `to` ISO 8601 date to the API request.
- **AC-4 (Filter resets pagination):** Applying any search or filter change resets the page to 1 (offset 0).
- **AC-5 (Combined filters):** All active filters are applied simultaneously in a single `GET /drawings` request.
- **AC-6 (No results state):** When the filtered result set is empty, an empty-state message specific to "no matching drawings" is displayed (distinct from the zero-drawings empty state in US-006 AC-6).
- **AC-7 (Clear filters):** A "Clear filters" control resets all active filters and the search query, returning to the default unfiltered view.

---

**US-008 — Live Status Updates in Library (polling path)**

*As a user, I want drawing statuses in my library to update automatically so that I don't have to manually refresh to see processing progress.*

- **AC-1 (Polling when in-progress):** When one or more drawings in the current list view are in a processing state (`Pending`, `Queued`, `Scanning`, `Processing`), the library automatically polls `GET /drawings` at a ≤10-second interval.
- **AC-2 (Polling stops when idle):** When no drawings in the current view are in a processing state, polling stops (no unnecessary background requests).
- **AC-3 (Status badge refresh):** When a drawing transitions to `Complete`, `Failed`, or `Scan_Failed` during a polling cycle, the status badge in the row updates without a full page reload.
- **AC-4 (No duplicate requests):** Only one polling interval is active at a time regardless of how many in-progress drawings are in the list.

---

**US-009 — Retry and Delete**

*As a user, I want to retry failed drawings and delete drawings I no longer need so that I can manage my library.*

- **AC-1 (Retry visible for Failed state only):** A "Retry" action button/link is visible on rows where `processing_state === 'Failed'`. It is absent for all other states, including `Scan_Failed` (terminal state, no retry permitted per §1.3).
- **AC-2 (Retry call):** Clicking Retry issues `POST /drawings/{id}/retry`. On success, the drawing row immediately reflects the updated state returned by the API (or the list is re-fetched). A loading/spinner state is shown on the row during the pending request.
- **AC-3 (Delete gated by role):** The Delete action is rendered only for users whose role grants `drawing_delete`. Specifically: `user` role sees Delete on own drawings; `team_admin` sees Delete on all team drawings; `team_member` does **not** see Delete on any drawing.
- **AC-4 (Delete confirmation — standard):** Clicking Delete opens a confirmation dialog. The dialog shows the drawing filename and a warning. Confirming issues `DELETE /drawings/{id}`.
- **AC-5 (Delete confirmation — processing warning):** When the drawing's `processing_state` is `Pending`, `Queued`, `Scanning`, or `Processing`, the confirmation dialog additionally warns that deleting will cancel in-progress processing.
- **AC-6 (Delete success):** On HTTP 204, the drawing row is removed from the list without a full page reload.
- **AC-7 (Delete error):** On API error (non-204), the dialog closes, the row remains, and an error message is displayed.
- **AC-8 (Navigate to review):** Clicking a drawing row with state `Complete` or `Under_Review` navigates to `/drawings/{id}/review`.

---

**US-018 — Free-Tier Upgrade Prompt (partial — display only)**

*As a free-tier user who has reached the monthly drawing limit, I want to see a clear upgrade prompt so that I know I must upgrade to process more drawings.*

- **AC-1 (Upgrade prompt visibility):** When the authenticated user is on the `free` tier and the API indicates the monthly limit has been reached (via a `429` or flagged field in the subscription response available from auth context), a persistent upgrade banner or inline prompt is displayed on the dashboard.
- **AC-2 (Upgrade link):** The upgrade prompt contains a link/button navigating to `/subscription`.
- **AC-3 (Upload button state):** The "Upload drawing" / "New drawing" call-to-action is visually disabled or replaced with the upgrade prompt when the free limit is reached.
- **AC-4 (Analytics not fired from browser):** The `free_limit_reached` PostHog event is **not** dispatched from the frontend. It is fired server-side by the FastAPI handler per §1.10.

---

##### UX and design specification

**Dashboard layout:**

The `/dashboard` page wraps content in `<Layout>` (from S1-F) which includes `<Nav>`. The `<GraceBanner>` (from S1-F) is rendered immediately below `<Nav>` when `user.billing_state === 'Grace'` and `sessionStorage.getItem('graceBannerDismissed')` is falsy. On dismiss, the banner writes `graceBannerDismissed=true` to sessionStorage (per §1.11: "Session-scoped suppression of grace period banner; resets on new session"). The dashboard itself renders `<ProtectedRoute>` wrapping all content.

**Page structure (top to bottom):**
1. `<GraceBanner>` (conditional)
2. Page heading ("Drawing Library" or equivalent)
3. Action bar: "Upload new drawing" button (→ `/upload`) + free-tier upgrade prompt (conditional, replaces or disables upload CTA)
4. `<SearchFilter>` component
5. `<DrawingList>` component (contains `<DrawingRow>` items)
6. `<Pagination>` component

**SearchFilter component:**
- Text input: placeholder "Search by filename or revision…"; `type="search"`; debounce 300 ms before updating query state
- Status dropdown: options are "All statuses" (value `''`) plus each `DrawingProcessingState` value displayed as human-readable labels (e.g., "Under Review" for `Under_Review`, "Scan Failed" for `Scan_Failed`)
- Date range: two `<input type="date">` fields labeled "From" and "To"; neither is required
- "Clear filters" text button: visible when any filter or search is active; resets all to defaults
- All controls are in a single horizontal row on wide viewports; stack vertically on narrow viewports

**DrawingRow fields and layout:**

| Field | Source | Display |
|---|---|---|
| Filename | `drawing.filename` | Bold, truncated with ellipsis if >60 chars |
| Revision label | `drawing.revision_label` | Muted secondary text; omitted entirely if `null` |
| Status badge | `drawing.processing_state` | `<StatusBadge>` (see below) |
| Upload date | `drawing.uploaded_at` | Formatted as `DD MMM YYYY` (e.g., "14 Jun 2025") |
| Page count | `drawing.page_count` | "N pages" or "—" if null |
| Actions | Role-gated (see US-009) | Right-aligned; "Retry" (Failed only), "Delete" (role-gated), row click → review |

**StatusBadge color mapping:**

| State | Color (Tailwind class reference) | Label |
|---|---|---|
| `Pending` | Gray | Pending |
| `Queued` | Blue | Queued |
| `Scanning` | Blue | Scanning |
| `Processing` | Indigo | Processing |
| `Complete` | Green | Complete |
| `Under_Review` | Amber | Under Review |
| `Failed` | Red | Failed |
| `Scan_Failed` | Red | Scan Failed |

Badges use a pill shape (`rounded-full`) with a filled background at reduced opacity and colored text. `Scanning` and `Processing` states show a subtle animated pulse indicator.

**Delete confirmation dialog:**

- Title: "Delete drawing?"
- Body (standard): "Are you sure you want to delete **{filename}**? This action cannot be undone."
- Body (processing warning, additional paragraph): "⚠️ This drawing is currently being processed. Deleting it now will cancel processing."
- Buttons: "Cancel" (secondary) | "Delete" (destructive/red primary)
- Dialog is modal; focus trapped within; Escape key cancels

**Pagination component:**

- Shows "Showing X–Y of Z drawings"
- "Previous" button (disabled on page 1) and "Next" button (disabled when on last page)
- No page-number buttons required for MVP (prev/next suffices)

**Empty states:**

- Zero drawings ever: illustration + "No drawings yet." + "Upload your first drawing →" (link to `/upload`)
- Zero results from filter: "No drawings match your search." + "Clear filters" link

**Loading state:**

- Initial load: skeleton rows (3–5 placeholder rows with animated shimmer)
- Polling refresh: no visual disruption (data updates in place); do not show a loading spinner on background polls

**Responsive behavior:**

- On viewports < 768px: hide `page_count` column; stack action buttons vertically in each row
- On viewports ≥ 768px: full table layout

**P1 STUB locations in `DrawingRow.tsx`:**

```tsx
{/* P1 STUB: US-024 — Team drawing attribution (show uploader name for team drawings) */}
{/* P1 STUB: US-025 — Revision comparison link (visible for Complete/Under_Review drawings on Pro/Team tier) */}
```

---

##### Critical implementation notes

- **Polling, not individual SSE streams.** The Drawing Library must use `usePolling` (from S1-F) on the `GET /drawings` endpoint — not `useSSE`. The `useSSE` hook (from S1-F) is reserved for the per-drawing review page (S3-D). Opening N individual SSE connections for N in-progress drawings in the library is explicitly prohibited. Poll interval must be ≤10 seconds per §1.9 ("≤10 second polling fallback").

- **Polling enabled condition.** The `usePolling` hook must be called with `enabled` = true **only** when the current page of results contains at least one drawing in `{Pending, Queued, Scanning, Processing}`. When no drawing is in a processing state, the `enabled` flag must be `false` to stop background requests. Failure to implement this produces continuous background polling even for idle libraries.

- **`Scan_Failed` is terminal — no Retry button.** From §1.3: `Scan_Failed: []` (no outbound transitions). The Retry button must not render for `Scan_Failed` state. Rendering it and having the API reject it is a silent failure mode — the button appears to work (the click is handled) but the API will 4xx.

- **`drawing_delete: false` for `team_member`.** From §1.3: team members have `drawing_delete: false`. The Delete action must be completely absent from the DOM (not just disabled) for team_member-role users. A disabled-but-visible delete button constitutes a UX violation.

- **`free_limit_reached` analytics event must NOT be fired from the browser.** From §1.10: "Must NEVER fire from: Browser client". The frontend must only render the upgrade prompt in response to API state (billing context from `useAuth`); it must never call `analytics.capture('free_limit_reached', ...)` or equivalent.

- **Debounce search input at ≥300 ms.** Without debounce, each keystroke fires an API request. This violates the <2s P95 dashboard performance target by creating unnecessary server load. The debounce must be implemented in `SearchFilter.tsx` before the query propagates to `useDrawings`.

- **Filter changes reset offset to 0.** Failing to reset offset when filters change produces an empty result set when, for example, the user is on page 3 and applies a filter that yields only 12 total results. This is a silent failure mode — no error is thrown, but the user sees "0 results" incorrectly.

- **`GET /drawings` query parameter names must match S2-B exactly.** The backend (S2-B) owns the query parameter contract. Parameters must be: `search` (string), `status` (DrawingProcessingState string), `from` (ISO 8601 date string), `to` (ISO 8601 date string), `limit` (integer, default 25), `offset` (integer, default 0). Using mismatched names (e.g., `q` instead of `search`) is a silent failure — the API ignores unknown params and returns unfiltered results.

- **GraceBanner `graceBannerDismissed` key is sessionStorage, not localStorage.** From §1.11: "sessionStorage | Session-scoped suppression of grace period banner; resets on new session." Using `localStorage` would prevent the banner from reappearing in new browser sessions, which is a contract violation. Use the `setSessionItem` / `getSessionItem` helpers from `frontend/src/lib/storage.ts`.

- **`DELETE /drawings/{id}` returns 204 with no body.** From §1.5: "Drawing deletion success | 204 | Must never return 200." Do not attempt to parse a JSON body from the delete response.

- **Row click target for Complete/Under_Review drawings.** The entire row (or a clearly labeled "Review" link) navigates to `/drawings/{id}/review`. Only `Complete` and `Under_Review` drawings should be navigable to the review canvas — drawings in other states should not have an active review link (clicking should be a no-op or show a tooltip like "Processing not yet complete").

- **`POST /drawings/{id}/retry` cross-session contract.** The retry endpoint (owned by S2-B) returns the updated drawing record with the new `processing_state`. The row must reflect the new state returned by the API; do not assume the new state is always `Queued`. If the API returns an error, the row must remain at `Failed` and display an error message.

- **No analytics fired from this session's components.** All nine analytics events in §1.10 are either server-side (FastAPI/workers) or specific user actions on other pages. `S3-B` components must not call `frontend/src/lib/analytics.ts` for any event. Using the analytics library here is a silent failure — events would double-fire or fire at incorrect times.

---

##### Mocking contract

This session consumes the following API endpoints. Mock shapes must match these exactly; field names and types must be identical to what S2-B's backend will produce.

---

**`GET /drawings`**

Query params: `search?: string`, `status?: DrawingProcessingState`, `from?: string`, `to?: string`, `limit?: number` (default 25), `offset?: number` (default 0)

Response `200 OK`:
```typescript
interface DrawingsPageResponse {
  drawings: DrawingRecord[];
  total: number;    // total matching records (for pagination)
  limit: number;    // echoed back
  offset: number;   // echoed back
}

interface DrawingRecord {
  id: string;                          // UUID
  filename: string;
  revision_label: string | null;
  processing_state: DrawingProcessingState;
  uploaded_at: string;                 // ISO 8601 UTC
  processed_at: string | null;         // ISO 8601 UTC
  page_count: number | null;
  estimated_symbol_count: number | null;
  owner_user_id: string | null;        // UUID
  owner_team_id: string | null;        // UUID
  stored_file_id: string | null;       // UUID
}
```

Response `401 Unauthorized`: `{ detail: string }` — unauthenticated request.

---

**`DELETE /drawings/{id}`**

Response `204 No Content`: empty body.

Response `403 Forbidden`: `{ detail: string }` — user does not own the drawing or role forbids delete.

Response `404 Not Found`: `{ detail: string }` — drawing ID does not exist.

---

**`POST /drawings/{id}/retry`**

Body: none.

Response `200 OK`:
```typescript
DrawingRecord  // same shape as above, with updated processing_state
```

Response `403 Forbidden`: `{ detail: string }` — user does not own the drawing.

Response `409 Conflict`: `{ detail: string }` — drawing is not in `Failed` state (cannot retry).

---

**Auth context shape (provided by `useAuth` from S1-F — must match S1-F's contract):**

```typescript
interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;                    // 'user' | 'team_member' | 'team_admin'
  team_id: string | null;
  tier_id: TierId;                   // 'free' | 'pro' | 'team'
  billing_state: BillingState;       // 'Active' | 'Grace' | 'Canceled'
  monthly_drawings_used: number;     // for free-tier limit display
  monthly_drawing_limit: number | null; // null = unlimited
}
```

---

##### Acceptance criteria checklist

- [ ] Navigating to `/dashboard` while authenticated renders the drawing library page [US-006 AC-1]
- [ ] Unauthenticated navigation to `/dashboard` redirects to `/login` [US-006 AC-7]
- [ ] Each drawing row displays filename, revision label (blank when null), status badge, formatted upload date, and page count [US-006 AC-2]
- [ ] Revision label is omitted (no empty placeholder text) when `drawing.revision_label` is `null` [US-006 AC-2]
- [ ] `StatusBadge` renders a distinct color-coded label for `Pending` [US-006 AC-3]
- [ ] `StatusBadge` renders a distinct color-coded label for `Queued` [US-006 AC-3]
- [ ] `StatusBadge` renders a distinct color-coded label for `Scanning` [US-006 AC-3]
- [ ] `StatusBadge` renders a distinct color-coded label for `Processing` [US-006 AC-3]
- [ ] `StatusBadge` renders a distinct color-coded label for `Complete` [US-006 AC-3]
- [ ] `StatusBadge` renders a distinct color-coded label for `Under_Review` [US-006 AC-3]
- [ ] `StatusBadge` renders a distinct color-coded label for `Failed` [US-006 AC-3]
- [ ] `StatusBadge` renders a distinct color-coded label for `Scan_Failed` [US-006 AC-3]
- [ ] Default page size is 25 drawings per request (limit=25) [US-006 AC-1]
- [ ] Pagination controls show total drawing count and allow next/previous page navigation [US-006 AC-5]
- [ ] Navigating to page 2 issues `GET /drawings?offset=25` [US-006 AC-5]
- [ ] Empty state with upload link is shown when API returns `total: 0` and no filters are active [US-006 AC-6]
- [ ] Search input is rendered and debounced ≥300 ms before triggering API request [US-007 AC-1]
- [ ] Typing in search box sends `search=<query>` as query parameter to `GET /drawings` [US-007 AC-1]
- [ ] Status filter dropdown contains all 8 `DrawingProcessingState` values plus "All statuses" option [US-007 AC-2]
- [ ] Selecting a status filter sends `status=<value>` to `GET /drawings` [US-007 AC-2]
- [ ] Date "From" and "To" inputs send `from` and `to` ISO date params to `GET /drawings` when set [US-007 AC-3]
- [ ] Applying a filter resets pagination to page 1 (offset=0) [US-007 AC-4]
- [ ] Multiple active filters are combined in a single `GET /drawings` request [US-007 AC-5]
- [ ] "No matching drawings" empty state is shown when filtered result is empty but filters are active [US-007 AC-6]
- [ ] "Clear filters" control appears when any filter/search is active and resets all params [US-007 AC-7]
- [ ] Polling is active (≤10s interval) when the current list contains a drawing in `Pending`, `Queued`, `Scanning`, or `Processing` [US-008 AC-1]
- [ ] Polling stops when no drawings in the current view are in a processing state [US-008 AC-2]
- [ ] Status badge updates in place when polling reveals a state change (e.g., Processing → Complete) [US-008 AC-3]
- [ ] Only one polling interval is active at a time regardless of number of in-progress drawings [US-008 AC-4]
- [ ] "Retry" button is visible on rows where `processing_state === 'Failed'` [US-009 AC-1]
- [ ] "Retry" button is absent on rows where `processing_state === 'Scan_Failed'` [US-009 AC-1]
- [ ] "Retry" button is absent on rows in any state other than `Failed` [US-009 AC-1]
- [ ] Clicking Retry issues `POST /drawings/{id}/retry` and updates the row to the returned state [US-009 AC-2]
- [ ] A loading indicator is shown on the row while the retry request is pending [US-009 AC-2]
- [ ] "Delete" button is visible for `user`-role users on their own drawings [US-009 AC-3]
- [ ] "Delete" button is visible for `team_admin`-role users on team drawings [US-009 AC-3]
- [ ] "Delete" button is absent from the DOM for `team_member`-role users [US-009 AC-3]
- [ ] Clicking Delete opens a confirmation dialog showing the drawing filename [US-009 AC-4]
- [ ] Delete confirmation dialog includes an extra processing-cancellation warning when state is `Pending`, `Queued`, `Scanning`, or `Processing` [US-009 AC-5]
- [ ] Confirming delete issues `DELETE /drawings/{id}` and removes the row on 204 [US-009 AC-6]
- [ ] API error on delete keeps the row in place and displays an error message [US-009 AC-7]
- [ ] Clicking a drawing row with state `Complete` or `Under_Review` navigates to `/drawings/{id}/review` [US-009 AC-8]
- [ ] Upgrade prompt is displayed on the dashboard when free-tier user has reached the monthly limit (`monthly_drawings_used >= monthly_drawing_limit`) [US-018 AC-1]
- [ ] Upgrade prompt contains a link/button that navigates to `/subscription` [US-018 AC-2]
- [ ] Upload CTA is visually disabled or replaced when free-tier limit is reached [US-018 AC-3]
- [ ] No PostHog `free_limit_reached` event is dispatched from any component in this session [US-018 AC-4]
- [ ] `GraceBanner` is rendered when `user.billing_state === 'Grace'` and `graceBannerDismissed` sessionStorage key is absent [MANUAL]
- [ ] Dismissing `GraceBanner` sets `graceBannerDismissed=true` in sessionStorage and hides the banner for the session [MANUAL]
- [ ] Skeleton loading rows are shown during the initial list fetch (before first response arrives) [MANUAL]
- [ ] On viewports < 768px, the `page_count` column is hidden [MANUAL]

---

##### Independent Test

**Test file path** (TDD — written first, must fail before implementation):
`tests/sessions/S3-B.test.tsx`

**Exact CI command:**
```
cd frontend && npx vitest run ../../tests/sessions/S3-B.test.tsx
```

**AC → assertion mapping:**

| AC | `it(...)` block name |
|---|---|
| US-006 AC-1 — renders library for authenticated user | `it("renders drawing list for authenticated user")` |
| US-006 AC-7 — redirects unauthenticated users | `it("redirects unauthenticated users to /login")` |
| US-006 AC-2 — row displays filename, revision, badge, date, page_count | `it("renders drawing row with all required fields")` |
| US-006 AC-2 — revision label omitted when null | `it("omits revision label when drawing.revision_label is null")` |
| US-006 AC-3 — StatusBadge: Pending | `it("StatusBadge renders label for Pending state")` |
| US-006 AC-3 — StatusBadge: Queued | `it("StatusBadge renders label for Queued state")` |
| US-006 AC-3 — StatusBadge: Scanning | `it("StatusBadge renders label for Scanning state")` |
| US-006 AC-3 — StatusBadge: Processing | `it("StatusBadge renders label for Processing state")` |
| US-006 AC-3 — StatusBadge: Complete | `it("StatusBadge renders label for Complete state")` |
| US-006 AC-3 — StatusBadge: Under_Review | `it("StatusBadge renders label for Under_Review state")` |
| US-006 AC-3 — StatusBadge: Failed | `it("StatusBadge renders label for Failed state")` |
| US-006 AC-3 — StatusBadge: Scan_Failed | `it("StatusBadge renders label for Scan_Failed state")` |
| US-006 AC-1 — default page size 25 | `it("requests drawings with default limit of 25")` |
| US-006 AC-5 — pagination navigation | `it("pagination next button requests next page with correct offset")` |
| US-006 AC-6 — empty state | `it("shows empty state with upload link when no drawings exist")` |
| US-007 AC-1 — search debounce | `it("debounces search input before issuing API request")` |
| US-007 AC-1 — search param sent | `it("sends search query parameter when search input has value")` |
| US-007 AC-2 — status filter options | `it("status filter dropdown contains all 8 DrawingProcessingState values")` |
| US-007 AC-2 — status filter param | `it("sends status query parameter when status filter is selected")` |
| US-007 AC-3 — date range params | `it("sends from and to query parameters when date range is set")` |
| US-007 AC-4 — filter resets pagination | `it("resets to page 1 when any filter changes")` |
| US-007 AC-5 — combined filters | `it("combines search and status filter in a single request")` |
| US-007 AC-6 — filtered empty state | `it("shows filtered empty state when no drawings match active filter")` |
| US-007 AC-7 — clear filters | `it("clear filters button resets all active filters and search")` |
| US-008 AC-1 — polling active when processing | `it("starts polling when drawings list contains in-progress drawings")` |
| US-008 AC-2 — polling stops when idle | `it("stops polling when no drawings are in a processing state")` |
| US-008 AC-3 — status updates in place | `it("updates status badge in place when polling returns changed state")` |
| US-008 AC-4 — single polling interval | `it("maintains only one polling interval regardless of in-progress drawing count")` |
| US-009 AC-1 — Retry visible for Failed | `it("shows Retry button only for drawings with state Failed")` |
| US-009 AC-1 — Retry absent for Scan_Failed | `it("does not render Retry button for Scan_Failed drawings")` |
| US-009 AC-2 — Retry call and row update | `it("issues POST retry and updates row state from API response")` |
| US-009 AC-2 — loading state during retry | `it("shows row loading indicator while retry request is pending")` |
| US-009 AC-3 — Delete visible for user role | `it("renders Delete button for user-role users on own drawings")` |
| US-009 AC-3 — Delete absent for team_member | `it("does not render Delete button for team_member role users")` |
| US-009 AC-4 — confirmation dialog | `it("opens confirmation dialog with filename when Delete is clicked")` |
| US-009 AC-5 — processing warning in dialog | `it("shows processing-cancellation warning in delete dialog for in-progress drawings")` |
| US-009 AC-6 — delete success removes row | `it("removes drawing row from list on successful 204 delete")` |
| US-009 AC-7 — delete error keeps row | `it("keeps row and shows error when delete API returns an error")` |
| US-009 AC-8 — row click navigates to review | `it("navigates to /drawings/{id}/review when Complete drawing row is clicked")` |
| US-018 AC-1 — upgrade prompt visible | `it("displays upgrade prompt when free-tier user has reached monthly drawing limit")` |
| US-018 AC-2 — upgrade link | `it("upgrade prompt links to /subscription")` |
| US-018 AC-3 — upload CTA disabled | `it("disables upload CTA when free-tier limit is reached")` |
| US-018 AC-4 — no analytics from browser | `it("does not call analytics capture for free_limit_reached event")` |

---

**Fixtures / test doubles:**

```typescript
// Mock API client (vitest mock of frontend/src/api/client.ts)
vi.mock('../../frontend/src/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    delete: vi.fn(),
    post: vi.fn(),
  }
}));

// Mock useAuth hook (vitest mock of frontend/src/auth/useAuth.ts)
vi.mock('../../frontend/src/auth/useAuth', () => ({
  useAuth: vi.fn()
}));

// Mock usePolling hook (vitest mock of frontend/src/hooks/usePolling.ts)
vi.mock('../../frontend/src/hooks/usePolling', () => ({
  usePolling: vi.fn((callback, interval, options) => {
    // Immediately invoke callback on first render if enabled
    if (options?.enabled) callback();
  })
}));

// Mock react-router-dom (useNavigate, Link)
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: vi.fn(() => vi.fn()) };
});

// Mock storage helpers
vi.mock('../../frontend/src/lib/storage', () => ({
  getSessionItem: vi.fn(() => null),
  setSessionItem: vi.fn(),
}));

// Factory: DrawingRecord
const makeDrawing = (overrides: Partial<DrawingRecord> = {}): DrawingRecord => ({
  id: 'drawing-uuid-1',
  filename: 'PID_Sheet_A.pdf',
  revision_label: 'Rev A',
  processing_state: 'Complete',
  uploaded_at: '2025-06-14T10:00:00Z',
  processed_at: '2025-06-14T10:05:00Z',
  page_count: 3,
  estimated_symbol_count: 42,
  owner_user_id: 'user-uuid-1',
  owner_team_id: null,
  stored_file_id: 'file-uuid-1',
  ...overrides,
});

// Factory: DrawingsPageResponse
const makeDrawingsPage = (drawings: DrawingRecord[], total?: number): DrawingsPageResponse => ({
  drawings,
  total: total ?? drawings.length,
  limit: 25,
  offset: 0,
});

// Mock auth users
const mockFreeUser: AuthUser = {
  id: 'user-uuid-1',
  email: 'user@example.com',
  display_name: 'Test User',
  role: 'user',
  team_id: null,
  tier_id: 'free',
  billing_state: 'Active',
  monthly_drawings_used: 3,
  monthly_drawing_limit: 3,
};

const mockProUser: AuthUser = {
  ...mockFreeUser,
  tier_id: 'pro',
  billing_state: 'Active',
  monthly_drawings_used: 10,
  monthly_drawing_limit: null,
};

const mockTeamMember: AuthUser = {
  ...mockFreeUser,
  role: 'team_member',
  team_id: 'team-uuid-1',
  tier_id: 'team',
  monthly_drawing_limit: null,
};

const mockGraceUser: AuthUser = {
  ...mockProUser,
  billing_state: 'Grace',
};
```

**Pre-conditions:**

- `frontend/vite.config.ts` must have `test.environment: 'jsdom'` and `test.globals: true` (set by S0-A)
- `@testing-library/react` and `@testing-library/user-event` must be in `frontend/package.json` devDependencies (set by S0-B)
- `vitest` must be in `frontend/package.json` devDependencies (set by S0-B)
- No running server required — all API calls are mocked
- No database or Redis required
- Environment variable stubs: none required for frontend unit tests
- `frontend/src/router.tsx` must export a `MemoryRouter`-compatible setup for test isolation (or tests wrap with `MemoryRouter` from react-router-dom directly)

**Isolation rule:**

This test file mocks all external dependencies (`apiClient`, `useAuth`, `usePolling`, `react-router-dom`) and requires no sibling Phase 3 sessions to be merged. It is fully isolated to this session's owned files.

---

##### Checkpoint

After this session's PR is merged, navigating to `/dashboard` as an authenticated user renders a paginated, searchable list of their drawings with color-coded processing-state badges, functioning search/filter controls, Retry/Delete actions on applicable rows, and automatic status polling for any in-progress drawings — verifiable by logging in and observing the library update a drawing's badge from `Processing` to `Complete` within 10 seconds of backend completion without a page reload.

**Shippability claim:** this PR is independently mergeable to `main` even if no other session in the same wave (S3-A, S3-C, S3-D, S3-E, S3-F, S3-G, S3-H) has merged. The `router.tsx` stubs for `/dashboard` are pre-wired by S0-A; the API endpoints consumed are provided by the already-merged S2-B; and the shared UI primitives are provided by the already-merged S1-F.

---

##### Output and handoff

| Export | File | Consuming Session(s) | Load-bearing? |
|---|---|---|---|
| `DrawingRecord` type | `frontend/src/features/library/useDrawings.ts` | S3-C (upload redirect target), S3-D (drawing context), S3-G (export button receives drawing) | [LOAD-BEARING] — field names and types must not change after merge |
| `DrawingsPageResponse` type | `frontend/src/features/library/useDrawings.ts` | S3-G (export modal needs drawing list context), S4-A (E2E assertions) | [LOAD-BEARING] |
| `StatusBadge` component | `frontend/src/features/library/StatusBadge.tsx` | S3-D (may reuse badge in review canvas header), S3-G (export modal shows drawing status) | Not load-bearing (internal styling only) |
| `useDrawings` hook | `frontend/src/features/library/useDrawings.ts` | S3-G (ExportButton may receive drawing_id and processing_state from parent Dashboard) | Not load-bearing (hook is internal to Drawing Library) |

---

```json
{
  "test": {
    "cmd": "cd frontend && npx vitest run ../../tests/sessions/S3-B.test.tsx",
    "file": "tests/sessions/S3-B.test.tsx"
  },
  "checkpoint": "Navigating to /dashboard as an authenticated user renders a paginated, searchable drawing library with color-coded status badges, Retry/Delete actions, and automatic polling that updates a drawing's badge from Processing to Complete within 10 seconds without a page reload.",
  "manualAcs": [
    {
      "id": "US-006-AC-MANUAL-1",
      "text": "GraceBanner is rendered when user.billing_state === 'Grace' and graceBannerDismissed sessionStorage key is absent."
    },
    {
      "id": "US-006-AC-MANUAL-2",
      "text": "Dismissing GraceBanner sets graceBannerDismissed=true in sessionStorage and hides the banner for the session."
    },
    {
      "id": "US-006-AC-MANUAL-3",
      "text": "Skeleton loading rows are shown during the initial list fetch before the first API response arrives."
    },
    {
      "id": "US-006-AC-MANUAL-4",
      "text": "On viewports narrower than 768px, the page_count column is hidden from the drawing list."
    }
  ],
  "exports": [
    {
      "kind": "type",
      "name": "DrawingRecord",
      "shape": "{ id: string; filename: string; revision_label: string | null; processing_state: DrawingProcessingState; uploaded_at: string; processed_at: string | null; page_count: number | null; estimated_symbol_count: number | null; owner_user_id: string | null; owner_team_id: string | null; stored_file_id: string | null; }"
    },
    {
      "kind": "type",
      "name": "DrawingsPageResponse",
      "shape": "{ drawings: DrawingRecord[]; total: number; limit: number; offset: number; }"
    },
    {
      "kind": "function",
      "name": "useDrawings",
      "shape": "(options?: { initialLimit?: number }) => { drawings: DrawingRecord[]; total: number; loading: boolean; error: Error | null; searchQuery: string; setSearchQuery: (q: string) => void; statusFilter: DrawingProcessingState | ''; setStatusFilter: (s: DrawingProcessingState | '') => void; dateRange: { from: string; to: string } | null; setDateRange: (r: { from: string; to: string } | null) => void; page: number; setPage: (p: number) => void; limit: number; refetch: () => void; deleteDrawing: (id: string) => Promise<void>; retryDrawing: (id: string) => Promise<DrawingRecord>; }"
    },
    {
      "kind": "module",
      "name": "StatusBadge",
      "shape": "frontend/src/features/library/StatusBadge.tsx"
    },
    {
      "kind": "module",
      "name": "DrawingList",
      "shape": "frontend/src/features/library/DrawingList.tsx"
    },
    {
      "kind": "module",
      "name": "DrawingRow",
      "shape": "frontend/src/features/library/DrawingRow.tsx"
    }
  ]
}
```