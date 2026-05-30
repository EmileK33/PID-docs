#### S3-G — Frontend: Exports UI + Notifications

**Phase 3 | Frontend | Needs: S1-F, S2-D**

---

##### Objective

Build the export format-selection modal, synchronous and asynchronous export status polling, in-app notification tray, and the shared notifications state store — enabling users to export detected symbols as CSV/XLSX and receive persistent in-session notifications when large (>1,000 symbol) async exports complete or fail.

---

##### Scope

**P0 MVP** — all work in this session is P0.

- US-016 (CSV/XLSX sync export, pre-signed download URL, re-export) — **P0**
- US-017 (async export queue, in-app notification on completion/failure, retry) — **P0**

No P1 stubs required from this session.

---

##### Technology constraints

From §1.8 (verbatim):

> **Frontend SPA** | React + Vite | Canvas rendering via Konva.js requires rich ecosystem; pure SPA sufficient for authenticated views; changing post-build would require full frontend rewrite

The following libraries **must** be used:
- **React + Vite + TypeScript** — primary SPA stack
- **Vitest + React Testing Library** — test runner and component testing (established by S0-B)
- **Zustand** — for `notificationsStore.ts` (consistent with `CorrectionStore.ts` in S3-D which uses the same pattern; project-wide state management convention)
- **`usePolling` hook from S1-F** — for polling `GET /exports/{id}`; do **not** implement a custom polling mechanism when the shared hook exists

The following **must not** be used:
- **Redux / MobX / Jotai** — not part of the selected stack; would conflict with the project-wide Zustand convention established by S3-D
- **Any direct browser `analytics` or PostHog calls** from this session — all analytics events (`export_initiated`, `export_downloaded`) must fire server-side only; per §1.10 these events must NEVER fire from the browser client

---

##### Performance targets

From §1.9:

> **Export (<1,000 symbols)** | <30s P95 | Monitoring target | Export Worker (synchronous generation); pre-signed URL returned on poll completion

This session is responsible for the client-side polling behavior that surfaces this SLA to users. Specifically:
- The polling interval in `useExportStatus` must be ≤3 seconds to ensure the frontend does not add perceptible lag on top of the server-side <30s target.
- This is a **monitoring target** (not a hard SLA); the frontend must not enforce a timeout that rejects a still-running export before the server does.

No other SLAs are directly owned by this session.

---

##### Owned files

```
frontend/src/features/exports/ExportButton.tsx
frontend/src/features/exports/ExportModal.tsx
frontend/src/features/exports/useExportStatus.ts
frontend/src/features/notifications/InAppNotifications.tsx
frontend/src/features/notifications/notificationsStore.ts
```

---

##### Read-only imports

| Owning Session | File | Named Exports Required |
|---|---|---|
| S1-F | `frontend/src/api/client.ts` | `apiClient` (typed fetch wrapper) |
| S1-F | `frontend/src/api/endpoints.ts` | `ENDPOINTS.exports.create(drawingId)`, `ENDPOINTS.exports.get(exportId)` |
| S1-F | `frontend/src/hooks/usePolling.ts` | `usePolling` |
| S1-F | `frontend/src/auth/useAuth.ts` | `useAuth` (for current user context) |
| S0-A | `frontend/src/types/contracts.ts` | `ExportFormat`, `ExportStatus`, `ExportRecord` |

---

##### Do not touch

- `frontend/src/main.tsx` — entry point, pre-stubbed by S0-A
- `frontend/src/App.tsx` — pre-stubbed by S0-A
- `frontend/src/router.tsx` — route stubs owned by S0-A
- `frontend/src/pages/_stubs.tsx` — owned by S0-A
- `frontend/src/api/client.ts` — owned by S1-F
- `frontend/src/api/endpoints.ts` — owned by S1-F
- `frontend/src/hooks/usePolling.ts` — owned by S1-F
- `frontend/src/hooks/useSSE.ts` — owned by S1-F
- `frontend/src/auth/AuthContext.tsx` — owned by S1-F
- `frontend/src/auth/useAuth.ts` — owned by S1-F
- `frontend/src/auth/supabaseClient.ts` — owned by S1-F
- `frontend/src/components/Layout.tsx` — owned by S1-F
- `frontend/src/components/Nav.tsx` — owned by S1-F
- `frontend/src/components/GraceBanner.tsx` — owned by S1-F
- `frontend/src/components/ProtectedRoute.tsx` — owned by S1-F
- `frontend/src/lib/storage.ts` — owned by S1-F
- `frontend/src/lib/analytics.ts` — owned by S1-F
- `frontend/src/styles/globals.css` — owned by S1-F
- `frontend/src/types/contracts.ts` — owned by S0-A
- All S3-D canvas files (`frontend/src/features/canvas/**`) — owned by S3-D
- All S3-B library files (`frontend/src/features/library/**`) — owned by S3-B
- All S2-D backend files — owned by S2-D

---

##### Architecture context

From §1.1 (verbatim — Shared Contracts):

```typescript
// Export Format
type ExportFormat = 'csv' | 'xlsx';

// Export Status
type ExportStatus = 'Queued' | 'Generating' | 'Complete' | 'Failed';
```

From §1.2 (verbatim — EXPORT_RECORD table):

```sql
CREATE TABLE export_record (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  drawing_id      UUID NOT NULL REFERENCES drawing(id),
  user_id         UUID NOT NULL REFERENCES "user"(id),
  format          VARCHAR NOT NULL CHECK (format IN ('csv','xlsx')),
  status          VARCHAR NOT NULL CHECK (status IN ('Queued','Generating','Complete','Failed')),
  stored_file_id  UUID REFERENCES stored_file(id),
  initiated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at    TIMESTAMPTZ
);
```

From §1.4 Critical Ordering Rules (verbatim):

> **Rule 15. Async export threshold evaluated server-side.** "The 1,000-symbol threshold for triggering async vs. synchronous export (FR-4 AC-3) must be evaluated server-side at job creation time, not client-side, to prevent bypass."

From §1.9 Performance Targets (verbatim):

> | Export (<1,000 symbols) | <30s P95 | Monitoring target | Export Worker (synchronous generation); pre-signed URL returned on poll completion |
> | Async export threshold | >1,000 symbols triggers async path | Hard constraint | Export Worker; evaluated server-side |
> | Pre-signed S3 URL expiry | 15 minutes | Hard constraint (security) | FastAPI URL generation |

From §1.10 Analytics Event Contracts (verbatim):

> | `export_initiated` | `{ event: 'export_initiated', timestamp: string (UTC ISO8601), user_id: string, drawing_id: string, export_id: string, format: ExportFormat }` | FastAPI — `POST /drawings/{id}/exports` handler | Export job created (both sync and async paths) | Export file generated | **Export Worker; browser client** |
> | `export_downloaded` | `{ event: 'export_downloaded', timestamp: string, user_id: string, drawing_id: string, export_id: string }` | FastAPI — pre-signed URL access or download endpoint | User accesses pre-signed download URL | None specified | **Export Worker** |

Both events must NEVER fire from the browser client. The frontend opens the download URL via a standard `<a>` anchor tag or `window.open()`; the server-side handler fires `export_downloaded` as appropriate.

From §1.11 Cross-Session Runtime Patterns (verbatim):

> | `subscription:flags:{user_id}` | Written By: FastAPI on login / Stripe webhook handler | Read By: FastAPI middleware (every authenticated request, feature-gate evaluation) | TTL: 5 minutes; invalidated on webhook receipt |

The subscription flags cache is read-only for this session (to gate feature availability) — the cache is not written by this session.

From §1.13 Feature Scope — P0 (verbatim):

> - US-016: CSV and XLSX export (synchronous path, <1,000 symbols); pre-signed download URL; re-export without overwriting prior exports
> - US-017: Async export queue for >1,000 symbols; in-app notification when ready; async export failure with retry

---

##### User stories and acceptance criteria

**US-016 — CSV and XLSX export (sync path)**

Given a drawing in `Complete` or `Under_Review` state:

- AC-1: An **Export** button is rendered; clicking it opens the Export Modal.
- AC-2: The Export Modal displays two mutually exclusive format options: **CSV** and **XLSX**. One must be selected before export can be confirmed.
- AC-3: Clicking the confirm button calls `POST /drawings/{id}/exports` with the selected `format`. The button is disabled and shows a loading indicator after the first click until a terminal state is reached.
- AC-4: When the server response (or a subsequent poll result) returns `status: 'Complete'` with a non-null `download_url`, the modal transitions to a **Download** state showing a download button linked to `download_url`. The download link opens in a new tab or triggers a file download (standard anchor `href` with `download` attribute); the frontend does **not** fire any analytics event at this point.
- AC-5: Multiple exports of the same drawing can be initiated sequentially. Each new export creates a distinct export record. The Export Modal does not prevent re-exporting when a prior export already exists for the same drawing.
- AC-6: The Export Modal can be cancelled at any time before a `Complete` or `Failed` state is reached; cancellation does not abort an already-initiated server-side job.

**US-017 — Async export queue (>1,000 symbols path)**

Given a drawing whose server-side export produces an initial response with `status: 'Queued'` or `status: 'Generating'` (indicating async path):

- AC-1: The Export Modal transitions to an **In Progress** state displaying a progress/loading indicator and the message "Your export is being prepared. We'll notify you when it's ready." The modal may be closed by the user without cancelling the background export.
- AC-2: `useExportStatus` begins polling `GET /exports/{id}` at ≤3-second intervals immediately after the modal receives a non-`Complete` initial response. Polling persists even if the modal is dismissed.
- AC-3: When polling returns `status: 'Complete'` with a non-null `download_url`, `useExportStatus` adds a notification to `notificationsStore` of type `export_complete` with the `downloadUrl` and stops polling.
- AC-4: The `InAppNotifications` component renders the `export_complete` notification with a visible **Download** link bound to `downloadUrl`. Clicking the link opens/downloads the file; the frontend does not fire any analytics event.
- AC-5: When polling returns `status: 'Failed'`, `useExportStatus` adds a notification to `notificationsStore` of type `export_failed` with the drawing name and a **Retry** action, and stops polling.
- AC-6: Clicking **Retry** on an `export_failed` notification closes the notification and re-opens the Export Modal for the same drawing pre-populated with the same format, allowing the user to re-initiate the export.
- AC-7: Each notification can be individually dismissed via a close button. Dismissed notifications are removed from the store and do not reappear for the remainder of the session.
- AC-8: If multiple async exports are in flight simultaneously (different drawings), each produces an independent notification. The notification tray renders all active/complete notifications.

---

##### UX and design specification

**ExportButton component**
- Renders as a standard button with label "Export"
- Props: `{ drawingId: string; drawingName?: string; disabled?: boolean; className?: string }`
- Disabled state: when `disabled` prop is `true` (e.g., drawing not in `Complete`/`Under_Review` state — evaluated by the consuming component S3-D based on drawing status)
- On click: opens `ExportModal` as an overlay/dialog

**ExportModal component**
- Modal overlay with backdrop
- Props: `{ drawingId: string; drawingName?: string; initialFormat?: ExportFormat; isOpen: boolean; onClose: () => void }`
- **Idle state** (no export in progress):
  - Title: "Export Drawing"
  - Format picker: two options — "CSV (.csv)" and "XLSX (.xlsx)"; XLSX selected by default
  - "Export" primary button, "Cancel" secondary button
  - "Export" disabled until a format is selected
- **Loading state** (POST call in flight):
  - "Export" button shows spinner and is disabled
  - Format picker disabled
- **Sync complete state** (response or poll returns `status: 'Complete'`):
  - Shows: "✓ Export ready — [Drawing Name].[format]"
  - Primary button: "Download" (anchor tag with `href=download_url`, `target="_blank"`, `download` attribute)
  - Secondary button: "Close"
- **Async queued state** (response returns `status: 'Queued'` or `'Generating'`):
  - Shows spinner + message: "Your export is being prepared. We'll notify you when it's ready."
  - Primary button: "Got it" (closes modal; background polling continues)
- **Failed state** (response or poll returns `status: 'Failed'`):
  - Shows: "✗ Export failed. Please try again."
  - Primary button: "Retry" (resets modal to idle state with same format pre-selected)
  - Secondary button: "Cancel"

**useExportStatus hook**
- Signature: `useExportStatus(exportId: string | null): { status: ExportStatus | null; downloadUrl: string | null; isPolling: boolean; error: string | null }`
- Starts polling when `exportId` is non-null and stops when it becomes null or a terminal state is reached
- Uses `usePolling` from S1-F with `intervalMs: 3000`
- On terminal `Complete`: writes to `notificationsStore`; sets `isPolling: false`
- On terminal `Failed`: writes to `notificationsStore`; sets `isPolling: false`
- Does **not** fire if the notification for this `exportId` already exists in the store (idempotent — prevents duplicate notifications on re-render)

**notificationsStore (Zustand)**

```typescript
interface AppNotification {
  id: string;                            // uuid, generated client-side
  type: 'export_complete' | 'export_failed';
  drawingId: string;
  exportId: string;
  format: ExportFormat;
  drawingName?: string;
  downloadUrl?: string;                  // present on export_complete
  createdAt: string;                     // ISO 8601
}

interface NotificationsState {
  notifications: AppNotification[];
  addNotification: (n: Omit<AppNotification, 'id' | 'createdAt'>) => void;
  dismissNotification: (id: string) => void;
  clearAll: () => void;
}
```

- Store is in-memory only (no localStorage/sessionStorage persistence per §1.11 — no browser storage key is defined for notifications)
- `addNotification` is idempotent per `exportId`: if a notification for the same `exportId` already exists, the call is a no-op

**InAppNotifications component**
- Props: none (reads directly from `useNotificationsStore`)
- Renders a fixed-position notification tray (top-right, `position: fixed, top: 1rem, right: 1rem, z-index: 9999`)
- Each notification card:
  - Icon: ✓ (complete) or ✗ (failed)
  - Title: `export_complete` → "Export ready"; `export_failed` → "Export failed"
  - Body: drawing name + format
  - Action button: `export_complete` → "Download" (`<a href={downloadUrl} target="_blank" download>`); `export_failed` → "Retry" (calls `onRetry` callback via prop or triggers modal re-open — see cross-session contract below)
  - Dismiss button: "×" icon, calls `dismissNotification(id)`
- Renders nothing when `notifications` array is empty

**Interaction behaviors**
- The "Retry" action in `InAppNotifications` requires the parent context (Review canvas / S3-D) to handle re-opening the Export Modal. `InAppNotifications` accepts an optional `onRetry?: (exportId: string, drawingId: string, format: ExportFormat) => void` prop; if not provided, the Retry button is hidden.
- Downloads must use `<a>` anchor tags — no programmatic `fetch` download — so the server-side `export_downloaded` analytics event fires correctly via the pre-signed URL access pattern.
- The polling mechanism in `useExportStatus` must not create multiple concurrent polling intervals for the same `exportId`. If the hook is remounted (e.g., component unmounts and remounts), it reads the existing notification from the store first — if a terminal state already exists for that `exportId`, no new poll is started.

---

##### Critical implementation notes

- **Threshold evaluation is server-side only.** From §1.4 Rule 15: "The 1,000-symbol threshold for triggering async vs. synchronous export must be evaluated server-side at job creation time, not client-side, to prevent bypass." The frontend must **not** inspect symbol count or attempt to predict sync vs. async path. The frontend must handle both paths based solely on the `status` field in the POST response.

- **`export_initiated` and `export_downloaded` must never fire from the browser client.** From §1.10: both events list "Browser client" in the "Must NEVER fire from" column. This means `frontend/src/lib/analytics.ts` must NOT be called with either event name anywhere in this session's files. Download is triggered via standard anchor `href` only.

- **Pre-signed URL expiry is 15 minutes.** From §1.9: `PRESIGNED_URL_EXPIRY_SECONDS: 900`. The `download_url` in a `GET /exports/{id}` response is freshly generated by FastAPI at response time. The UI should not cache or store this URL beyond the current render cycle; if the user needs to download after the notification has been in the tray for >15 minutes, the notification's "Download" link may be stale. Graceful handling: if the download link returns a 403, the notification should visually indicate "Link expired — Re-export to get a new download." This is a best-effort graceful degradation, not a hard requirement.

- **Re-export must not overwrite prior exports.** Each call to `POST /drawings/{id}/exports` creates a new `ExportRecord` (server-side behavior). The frontend must not disable or hide the Export button when a prior export exists; it must allow initiating a new export unconditionally (subject only to the drawing state check in the consuming component).

- **Polling idempotency.** `useExportStatus` must not add a duplicate notification if it has already added one for the same `exportId`. Check `notificationsStore.notifications` for an existing entry with matching `exportId` before calling `addNotification`.

- **Polling must stop at terminal states.** `useExportStatus` must call the stop function returned by `usePolling` when `status === 'Complete'` or `status === 'Failed'`. Failing to stop polling will cause unnecessary API calls and is a silent failure mode.

- **Modal close does not abort in-progress async export.** When the user closes the modal in the async queued state, `useExportStatus` must continue polling. The hook must be lifted above the modal's lifecycle — mount it at the `ExportButton` level or in a stable parent, not inside `ExportModal`.

- **HTTP status codes.** `POST /drawings/{id}/exports` returns `202 Accepted` for async path and `201 Created` for sync path (standard REST; exact codes follow S2-D's contract). `GET /exports/{id}` returns `200` always while the record exists. `403` if the current user does not own the drawing. Handle `403` as a terminal error: show "You do not have access to this export."

- **Cross-session contract for ExportButton.** S3-D imports `ExportButton`. The props signature `{ drawingId: string; drawingName?: string; disabled?: boolean; className?: string }` is **load-bearing** and must not change after merge.

- **Cross-session contract for InAppNotifications.** S1-F's `Layout.tsx` or the Review page (S3-D) will render `<InAppNotifications />`. The zero-config props interface (`onRetry` is optional) is load-bearing.

---

##### Mocking contract

**Endpoint: `POST /drawings/{drawingId}/exports`**
- Method: POST
- Path: `/drawings/{drawingId}/exports`
- Request body: `{ format: 'csv' | 'xlsx' }`
- Response shape (sync path — status immediately Complete):
```json
{
  "id": "export-sync-001",
  "drawing_id": "drawing-001",
  "user_id": "user-001",
  "format": "csv",
  "status": "Complete",
  "download_url": "https://s3.example.com/exports/file.csv?X-Amz-Expires=900&...",
  "initiated_at": "2024-01-15T10:00:00Z",
  "completed_at": "2024-01-15T10:00:04Z"
}
```
- Response shape (async path — status Queued):
```json
{
  "id": "export-async-002",
  "drawing_id": "drawing-002",
  "user_id": "user-001",
  "format": "xlsx",
  "status": "Queued",
  "download_url": null,
  "initiated_at": "2024-01-15T10:00:00Z",
  "completed_at": null
}
```

**Endpoint: `GET /exports/{exportId}`**
- Method: GET
- Path: `/exports/{exportId}`
- Response shape (Queued):
```json
{
  "id": "export-async-002",
  "drawing_id": "drawing-002",
  "user_id": "user-001",
  "format": "xlsx",
  "status": "Queued",
  "download_url": null,
  "initiated_at": "2024-01-15T10:00:00Z",
  "completed_at": null
}
```
- Response shape (Generating):
```json
{
  "id": "export-async-002",
  "drawing_id": "drawing-002",
  "user_id": "user-001",
  "format": "xlsx",
  "status": "Generating",
  "download_url": null,
  "initiated_at": "2024-01-15T10:00:00Z",
  "completed_at": null
}
```
- Response shape (Complete):
```json
{
  "id": "export-async-002",
  "drawing_id": "drawing-002",
  "user_id": "user-001",
  "format": "xlsx",
  "status": "Complete",
  "download_url": "https://s3.example.com/exports/file.xlsx?X-Amz-Expires=900&...",
  "initiated_at": "2024-01-15T10:00:00Z",
  "completed_at": "2024-01-15T10:01:30Z"
}
```
- Response shape (Failed):
```json
{
  "id": "export-async-002",
  "drawing_id": "drawing-002",
  "user_id": "user-001",
  "format": "xlsx",
  "status": "Failed",
  "download_url": null,
  "initiated_at": "2024-01-15T10:00:00Z",
  "completed_at": "2024-01-15T10:01:30Z"
}
```

These shapes must be identical to those produced by S2-D (`backend/app/api/routers/exports.py`). They are the canonical contract.

---

##### Acceptance criteria checklist

**US-016 — Sync Export**
- [ ] ExportButton renders and is clickable when `disabled` prop is false [US-016 AC-1]
- [ ] Clicking ExportButton opens ExportModal [US-016 AC-1]
- [ ] ExportModal displays CSV and XLSX format options [US-016 AC-2]
- [ ] Export confirm button is disabled until a format is selected [US-016 AC-2]
- [ ] Clicking confirm calls `POST /drawings/{id}/exports` with the selected format [US-016 AC-3]
- [ ] Confirm button is disabled and shows loading state after first click [US-016 AC-3]
- [ ] When POST response returns `status: 'Complete'` with `download_url`, modal shows Download button linked to the URL [US-016 AC-4]
- [ ] When poll (after Queued initial response) returns `status: 'Complete'`, modal transitions to Download state [US-016 AC-4]
- [ ] Download is rendered as an anchor tag (not programmatic fetch); no analytics call is made [US-016 AC-4]
- [ ] ExportButton does not become permanently disabled after a prior export on the same drawing; clicking it again opens a fresh ExportModal [US-016 AC-5]
- [ ] Clicking Cancel in idle/loading state closes the modal without error [US-016 AC-6]

**US-017 — Async Export + Notifications**
- [ ] When POST returns `status: 'Queued'`, modal transitions to async In Progress state showing loading indicator and "We'll notify you" message [US-017 AC-1]
- [ ] Modal can be closed from the async In Progress state without terminating background polling [US-017 AC-1]
- [ ] `useExportStatus` starts polling `GET /exports/{id}` at ≤3s intervals when given a non-null exportId [US-017 AC-2]
- [ ] `useExportStatus` stops polling when status is `Complete` [US-017 AC-2]
- [ ] `useExportStatus` stops polling when status is `Failed` [US-017 AC-2]
- [ ] When poll returns `Complete`, `useExportStatus` calls `notificationsStore.addNotification` exactly once with type `export_complete` and the `downloadUrl` [US-017 AC-3]
- [ ] `InAppNotifications` renders the `export_complete` notification with a Download anchor tag bound to `downloadUrl` [US-017 AC-4]
- [ ] Download anchor in notification does not fire any analytics call [US-017 AC-4]
- [ ] When poll returns `Failed`, `useExportStatus` calls `notificationsStore.addNotification` exactly once with type `export_failed` [US-017 AC-5]
- [ ] `InAppNotifications` renders the `export_failed` notification with a Retry action [US-017 AC-5]
- [ ] Dismissing a notification removes it from the store and it is no longer rendered [US-017 AC-7]
- [ ] A second `addNotification` call with the same `exportId` does not create a duplicate notification (idempotency) [US-017 AC-3, AC-5]
- [ ] When two async exports complete independently, both notifications are rendered simultaneously [US-017 AC-8]

**Technical ACs**
- [ ] `export_initiated` PostHog call is absent from all files owned by this session [§1.10]
- [ ] `export_downloaded` PostHog call is absent from all files owned by this session [§1.10]
- [ ] Server-side symbol count threshold is not evaluated in any frontend file (no comparison against 1,000) [§1.4 Rule 15]
- [ ] `notificationsStore.addNotification` is idempotent: calling it twice with the same `exportId` results in exactly one entry in `notifications` array [US-017 AC-3]
- [ ] `useExportStatus` does not start a new polling interval if the `exportId` already has a terminal notification in the store [§ critical notes]
- [ ] `ExportButton` props interface `{ drawingId: string; drawingName?: string; disabled?: boolean; className?: string }` is exported as a TypeScript type [cross-session contract]

---

##### Independent Test

**Test file path** (TDD — written first, must fail before implementation):
`tests/sessions/s3-g.test.tsx`

**Exact CI command**:
```
npm test -- --run tests/sessions/s3-g
```

**AC → assertion mapping**:

| AC | `it(...)` block name |
|---|---|
| US-016 AC-1 (ExportButton renders, clickable) | `it("renders ExportButton and opens modal on click")` |
| US-016 AC-2 (format options, confirm disabled until selection) | `it("shows CSV and XLSX options; confirm disabled until format selected")` |
| US-016 AC-3 (POST called with format, button loading) | `it("calls POST /drawings/{id}/exports with selected format and disables confirm")` |
| US-016 AC-4 (sync Complete → Download state) | `it("shows Download button when POST response status is Complete")` |
| US-016 AC-4 (poll Complete → Download state) | `it("shows Download button when polling transitions to Complete")` |
| US-016 AC-4 (no analytics call) | `it("does not call analytics on download link render or click")` |
| US-016 AC-5 (re-export allowed) | `it("re-opens ExportModal for same drawing after prior export")` |
| US-016 AC-6 (Cancel closes modal) | `it("closes modal on Cancel without error")` |
| US-017 AC-1 (Queued → async In Progress state) | `it("shows async in-progress message when POST returns Queued")` |
| US-017 AC-1 (modal closeable from async state) | `it("allows modal close from async in-progress state")` |
| US-017 AC-2 (polling starts ≤3s) | `it("starts polling GET /exports/{id} after receiving Queued status")` |
| US-017 AC-2 (polling stops on Complete) | `it("stops polling when export status is Complete")` |
| US-017 AC-2 (polling stops on Failed) | `it("stops polling when export status is Failed")` |
| US-017 AC-3 (Complete → addNotification export_complete, once) | `it("adds export_complete notification exactly once on Complete poll")` |
| US-017 AC-4 (notification renders Download link) | `it("renders export_complete notification with Download anchor")` |
| US-017 AC-4 (no analytics on download) | `it("does not call analytics from notification Download link")` |
| US-017 AC-5 (Failed → addNotification export_failed, once) | `it("adds export_failed notification exactly once on Failed poll")` |
| US-017 AC-5 (failed notification renders Retry) | `it("renders export_failed notification with Retry action")` |
| US-017 AC-7 (dismiss removes notification) | `it("removes notification from store and DOM on dismiss")` |
| US-017 AC-3/5 (addNotification idempotency) | `it("addNotification is idempotent for same exportId")` |
| US-017 AC-8 (multiple notifications) | `it("renders multiple notifications for independent exports")` |
| Tech AC (no export_initiated call) | `it("does not import or invoke analytics export_initiated event")` |
| Tech AC (no threshold check) | `it("does not evaluate symbol count threshold client-side")` |
| Tech AC (ExportButton props type exported) | `it("exports ExportButtonProps TypeScript interface")` |

**Fixtures / test doubles**:

```typescript
// Mock API responses — shapes match Mocking contract above
const MOCK_EXPORT_SYNC_COMPLETE = {
  id: 'export-sync-001',
  drawing_id: 'drawing-001',
  user_id: 'user-001',
  format: 'csv' as const,
  status: 'Complete' as const,
  download_url: 'https://s3.example.com/exports/file.csv?X-Amz-Expires=900',
  initiated_at: '2024-01-15T10:00:00Z',
  completed_at: '2024-01-15T10:00:04Z',
};

const MOCK_EXPORT_ASYNC_QUEUED = {
  id: 'export-async-002',
  drawing_id: 'drawing-002',
  user_id: 'user-001',
  format: 'xlsx' as const,
  status: 'Queued' as const,
  download_url: null,
  initiated_at: '2024-01-15T10:00:00Z',
  completed_at: null,
};

const MOCK_EXPORT_ASYNC_COMPLETE = {
  ...MOCK_EXPORT_ASYNC_QUEUED,
  status: 'Complete' as const,
  download_url: 'https://s3.example.com/exports/file.xlsx?X-Amz-Expires=900',
  completed_at: '2024-01-15T10:01:30Z',
};

const MOCK_EXPORT_ASYNC_FAILED = {
  ...MOCK_EXPORT_ASYNC_QUEUED,
  status: 'Failed' as const,
  completed_at: '2024-01-15T10:01:30Z',
};
```

API calls are mocked using `vi.mock` on `frontend/src/api/client.ts`. The `usePolling` hook from S1-F is mocked with `vi.mock('../../hooks/usePolling', ...)` to control poll timing with `vi.useFakeTimers()`.

**Pre-conditions**:
- Vitest and React Testing Library configured in `frontend/package.json` (established by S0-B)
- `@testing-library/user-event` available for interaction simulation
- `frontend/src/types/contracts.ts` exports `ExportFormat`, `ExportStatus` (S0-A)
- `frontend/src/api/client.ts` and `frontend/src/api/endpoints.ts` exist as stubs (S1-F)
- `frontend/src/hooks/usePolling.ts` exists as a stub (S1-F)
- No real API server required; all calls are intercepted via `vi.mock`

**Isolation rule**:
All dependencies (S1-F exports) are mocked. The test does not require any sibling Phase 3 session to have merged. The test passes with `vi.mock` stubs for S1-F modules even before S1-F is implemented in full, because the stubs in S0-A provide the file paths needed for mock resolution.

---

##### Checkpoint

**One-sentence observable outcome**: On the `/drawings/{id}/review` page, clicking the Export button opens a modal where selecting CSV or XLSX and confirming either immediately shows a Download link (sync path) or shows an async-queued message and later displays a download notification in the top-right notification tray.

**Shippability claim**: This PR is independently mergeable to main even if no other session in the same wave has merged — all API calls use mocked clients, the test file uses `vi.mock` for all S1-F dependencies, and the components have no runtime dependency on S3-D or S3-B being merged.

---

##### Output and handoff

| Export | Kind | Consuming Session(s) | Load-bearing? |
|---|---|---|---|
| `ExportButton` (default export) | React component | S3-D (`frontend/src/pages/Review.tsx`, `frontend/src/features/canvas/InspectionPanel.tsx`) | **[LOAD-BEARING]** — props: `{ drawingId: string; drawingName?: string; disabled?: boolean; className?: string }` |
| `ExportButtonProps` | TypeScript interface | S3-D | **[LOAD-BEARING]** |
| `InAppNotifications` (default export) | React component | S1-F `Layout.tsx` or S3-D `Review.tsx` | **[LOAD-BEARING]** — props: `{ onRetry?: (exportId: string, drawingId: string, format: ExportFormat) => void }` |
| `useNotificationsStore` | Zustand hook | `useExportStatus`, `InAppNotifications`, S3-D (if retry callback needed) | **[LOAD-BEARING]** — store shape must not change after merge |
| `AppNotification` | TypeScript interface | S3-D (for `onRetry` callback type) | **[LOAD-BEARING]** |
| `useExportStatus` | Hook | `ExportModal` (internal), any future session that needs export polling | Stable interface |
| `notificationsStore.ts` | Module | `useExportStatus`, `InAppNotifications` | **[LOAD-BEARING]** |

---

```json
{
  "test": {
    "cmd": "npm test -- --run tests/sessions/s3-g",
    "file": "tests/sessions/s3-g.test.tsx"
  },
  "checkpoint": "On the /drawings/{id}/review page, clicking the Export button opens a modal where selecting CSV or XLSX and confirming either immediately shows a Download link (sync path) or shows an async-queued message and later displays a download notification in the top-right notification tray.",
  "manualAcs": [],
  "exports": [
    {
      "kind": "type",
      "name": "ExportButtonProps",
      "shape": "{ drawingId: string; drawingName?: string; disabled?: boolean; className?: string }"
    },
    {
      "kind": "type",
      "name": "AppNotification",
      "shape": "{ id: string; type: 'export_complete' | 'export_failed'; drawingId: string; exportId: string; format: ExportFormat; drawingName?: string; downloadUrl?: string; createdAt: string }"
    },
    {
      "kind": "type",
      "name": "NotificationsState",
      "shape": "{ notifications: AppNotification[]; addNotification: (n: Omit<AppNotification, 'id' | 'createdAt'>) => void; dismissNotification: (id: string) => void; clearAll: () => void }"
    },
    {
      "kind": "function",
      "name": "useNotificationsStore",
      "shape": "() => NotificationsState"
    },
    {
      "kind": "function",
      "name": "useExportStatus",
      "shape": "(exportId: string | null) => { status: ExportStatus | null; downloadUrl: string | null; isPolling: boolean; error: string | null }"
    },
    {
      "kind": "module",
      "name": "ExportButton",
      "shape": "frontend/src/features/exports/ExportButton.tsx"
    },
    {
      "kind": "module",
      "name": "InAppNotifications",
      "shape": "frontend/src/features/notifications/InAppNotifications.tsx"
    },
    {
      "kind": "module",
      "name": "notificationsStore",
      "shape": "frontend/src/features/notifications/notificationsStore.ts"
    }
  ]
}
```