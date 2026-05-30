---

#### S3-C — Frontend: Upload Flow

**Phase 3 | Frontend | Needs: S1-F, S2-B**

##### Objective

Build the client-side file upload flow — drag-and-drop file selection, browser-side SHA-256 hashing, blocklist pre-check, presigned S3 upload with progress reporting, and upload-complete signalling — so that users can submit PDF and DWG drawings for ML processing without any file bytes transiting the API server.

##### Scope

**P0 MVP.** All work in this session is P0.

| Story | Scope |
|---|---|
| US-003 — PDF and DWG file upload with format, size, raster, DWG version, and blocklist validation | P0 — implement fully |
| US-018 — Free tier 3-drawing/month limit enforcement; upgrade prompt on limit hit | P0 — implement the client-side upgrade-prompt surface triggered by server response; counter logic is server-owned (S2-B) |

P1 stub required for: none. No P1 upload features exist in the spec.

##### Technology constraints

From §1.8 (non-negotiable):

| Layer | Technology |
|---|---|
| Frontend SPA | React + Vite |
| Canvas / UI | No Konva for this session — standard React DOM only |
| Auth | Supabase Auth (tokens read from `AuthContext` — S1-F) |

**Must NOT use:**
- `crypto-js` or any third-party SHA-256 library — use the browser-native `SubtleCrypto` API (`window.crypto.subtle.digest('SHA-256', ...)`) for hash computation, as no third-party crypto dependency is introduced.
- `fetch` for the S3 PUT step — `fetch` does not expose upload progress events; use `XMLHttpRequest` so `UploadProgress.tsx` can display byte-level progress.
- Any server-proxied upload path — files go directly from browser to S3 via the presigned URL; no bytes may transit the FastAPI API server.

##### Performance targets

None — see downstream sessions. The upload itself is gated by network bandwidth and S3 latency, which are outside this session's control. No hard SLA is assigned to this session directly.

##### Owned files

```
frontend/src/pages/Upload.tsx
frontend/src/features/upload/DropZone.tsx
frontend/src/features/upload/hashClient.ts
frontend/src/features/upload/uploadOrchestrator.ts
frontend/src/features/upload/UploadProgress.tsx
```

##### Read-only imports

| Owning session | File path | Named exports required |
|---|---|---|
| S1-F | `frontend/src/api/client.ts` | `apiClient` (Axios / fetch wrapper with auth headers) |
| S1-F | `frontend/src/api/endpoints.ts` | `ENDPOINTS` (URL constants for all API routes) |
| S1-F | `frontend/src/auth/AuthContext.tsx` | `AuthContext` |
| S1-F | `frontend/src/auth/useAuth.ts` | `useAuth` (returns `user`, `session`, `loading`) |
| S1-F | `frontend/src/components/Layout.tsx` | `Layout` |
| S1-F | `frontend/src/components/ProtectedRoute.tsx` | `ProtectedRoute` |
| S0-A | `frontend/src/types/contracts.ts` | `HashCheckRequest`, `HashCheckResponse`, `DrawingProcessingState` |

##### Do not touch

- `frontend/src/main.tsx` — entry point, pre-stubbed by S0-A
- `frontend/src/App.tsx` — app root, pre-stubbed by S0-A
- `frontend/src/router.tsx` — all page routes pre-stubbed by S0-A
- `frontend/src/pages/_stubs.tsx` — stub container owned by S0-A
- `frontend/src/api/client.ts` — owned by S1-F
- `frontend/src/api/endpoints.ts` — owned by S1-F
- `frontend/src/auth/AuthContext.tsx`, `frontend/src/auth/useAuth.ts`, `frontend/src/auth/supabaseClient.ts` — owned by S1-F
- `frontend/src/hooks/useSSE.ts`, `frontend/src/hooks/usePolling.ts` — owned by S1-F
- `frontend/src/components/Layout.tsx`, `frontend/src/components/Nav.tsx`, `frontend/src/components/GraceBanner.tsx`, `frontend/src/components/ProtectedRoute.tsx` — owned by S1-F
- `frontend/src/lib/storage.ts`, `frontend/src/lib/analytics.ts` — owned by S1-F
- All `frontend/src/pages/auth/*`, `frontend/src/features/library/*`, `frontend/src/features/canvas/*`, `frontend/src/features/account/*`, `frontend/src/features/subscription/*`, `frontend/src/features/exports/*`, `frontend/src/features/notifications/*` — owned by other Phase 3 sessions

##### Architecture context

Verbatim from §1.4 Critical Ordering Rules:

> **1. Hash check before pre-signed URL issuance.** "Client calls `POST /drawings/hash-check` with `{sha256_hash, filename, size_bytes}`. Server checks `FILE_HASH_BLOCKLIST`. If the hash is present, returns `409 Conflict` — no Drawing record is created, no S3 URL is issued." A `POST /drawings` without a valid prior hash-check pass returns `400`.

> **2. Pre-signed URL issued only after hash-check pass.** "The upload flow enforces FR-17 AC-2 (no blocked file byte reaches S3) through a mandatory hash pre-check before pre-signed URL issuance."

> **4. Upload-complete idempotency check before enqueue.** "`POST /drawings/{id}/upload-complete` is idempotent. If the Drawing record is already in `Queued` or any later processing state, the endpoint returns `200` without re-enqueuing the ingest job."

> **8. Free-tier monthly counter incremented at job enqueue, not completion.** "The counter increment must occur at the point processing is initiated (job enqueued), not at job completion, to prevent race conditions from concurrent uploads."

Verbatim from §1.5 HTTP Status Code Contracts:

| Condition | Required code | Must never return |
|---|---|---|
| Hash blocked on `POST /drawings/hash-check` | `409 Conflict` | `200`, `400` |
| `POST /drawings` without valid prior hash-check pass | `400` | `200`, `201` |
| `POST /drawings/{id}/upload-complete` when Drawing already in `Queued` or later state (idempotent) | `200` | `201`, `409` |
| `POST /drawings/{id}/upload-complete` initial success (job enqueued) | `202` | `200`, `201` |
| Unauthenticated request to protected endpoint | `401` | `403`, `200` |
| Authenticated user accessing resource they do not own | `403` | `404`, `200` |

Verbatim from §1.9 Performance Targets:

> **Pre-signed S3 URL expiry** — 15 minutes — Hard constraint (security). FastAPI URL generation.

Verbatim from §1.12 Environment Variable Schema:

> `MAX_UPLOAD_SIZE_BYTES` — integer — Positive integer — Default: `104857600` (100MB).

> `PRESIGNED_URL_EXPIRY_SECONDS` — integer — Positive integer — Default: `900` (15 min).

Verbatim from §1.10 Analytics Event Contracts (firing surface relevant to upload):

> **`drawing_uploaded`** — `{ event: 'drawing_uploaded', timestamp: string (UTC ISO8601), user_id: string, drawing_id: string }` — FastAPI — `POST /drawings/{id}/upload-complete` handler — Drawing transitions to `Queued` state after upload-complete signal — **Must NOT fire from** Browser client; ML worker.

> **`free_limit_reached`** — `{ event: 'free_limit_reached', timestamp: string, user_id: string, drawing_id: string, subscription_id: string }` — FastAPI — processing initiation handler — Free tier user attempts to initiate processing of drawing that would exceed 3/month limit — **Must NOT fire from** Browser client; must fire before upgrade prompt is shown.

Verbatim from §1.11 Cross-Session Runtime Patterns — Browser Storage Keys:

> `correction_state:{drawing_id}` — localStorage — Canvas review SPA — Canvas review SPA on reload — Unsaved correction state flush; server-saved state takes precedence if timestamps conflict.

Verbatim from §1.13 Feature Scope — P0:

> **US-003**: PDF and DWG file upload with format, size, raster, DWG version, and blocklist validation

> **US-018**: Free tier 3-drawing/month limit enforcement; upgrade prompt on limit hit; tier-gated features visible but inaccessible

Verbatim from §1.6 Route Manifest — Frontend Page Routes:

> `/upload` — File Upload Drop Zone

Verbatim from §1.7 Third-Party Dependencies (ODA/DWG):

> **ODA File Converter** — Highest risk: success rate on complex DWGs unknown; 50-file prototype required before engineering; license expiry must be monitored with 30-day alert; commercial license must be procured before any DWG processing; fallback: LibreCAD/ezdxf for DXF path.

Verbatim from §1.1 Shared Contracts:

```typescript
// Hash Check Request/Response
interface HashCheckRequest {
  sha256_hash: string;
  filename: string;
  size_bytes: number;
}

interface HashCheckResponse {
  allowed: boolean;
  drawing_id?: string;
}

// Drawing Processing State Machine
type DrawingProcessingState =
  | 'Pending'
  | 'Queued'
  | 'Scanning'
  | 'Processing'
  | 'Complete'
  | 'Under_Review'
  | 'Failed'
  | 'Scan_Failed';
```

##### User stories and acceptance criteria

The full verbatim user story text is not reproduced in the provided spec documents; what follows is derived directly from §1.13 Feature Scope and the technical requirements in §1.4, §1.5, §1.9, §1.10, §1.12 without paraphrase.

---

**US-003 — PDF and DWG file upload with format, size, raster, DWG version, and blocklist validation**

AC-1 (Happy path — PDF upload): Given an authenticated user on `/upload`, when they drop or select a valid `.pdf` file ≤ 100 MB, then the upload orchestrator: (a) computes the SHA-256 hash client-side, (b) calls `POST /drawings/hash-check` with `{sha256_hash, filename, size_bytes}`, (c) on `allowed: true` response calls `POST /drawings` to create the drawing record and receive a presigned S3 URL, (d) PUTs the file bytes directly to the presigned URL with progress reporting, (e) calls `POST /drawings/{id}/upload-complete`, and (f) on `202` response navigates the user to `/dashboard`.

AC-2 (Happy path — DWG upload): Same as AC-1 but with a `.dwg` file. The client treats DWG files identically to PDF for all client-side steps; server-side DWG conversion is handled by the Ingest Worker (S2-H) and is invisible to the client.

AC-3 (Format rejection — client-side): When a user drops or selects a file whose extension is not `.pdf` or `.dwg` (e.g., `.png`, `.docx`, `.exe`), the DropZone rejects the file immediately with an inline error message before any network call is made. No `POST /drawings/hash-check` is issued.

AC-4 (Size rejection — client-side): When a user drops or selects a file whose `size` in bytes exceeds 104,857,600 (100 MB), the DropZone rejects the file immediately with an inline error message before any network call is made. No `POST /drawings/hash-check` is issued.

AC-5 (Blocklist rejection): When `POST /drawings/hash-check` returns `409 Conflict`, the upload is aborted, no Drawing record is created (confirmed by no `POST /drawings` being issued), and the user sees an error message stating the file cannot be uploaded. The user may select a different file.

AC-6 (Duplicate detection via drawing_id): When `POST /drawings/hash-check` returns `200` with `{ allowed: true, drawing_id: "<uuid>" }`, the orchestrator treats the file as a known duplicate: it skips `POST /drawings` and the S3 PUT, calls `POST /drawings/{drawing_id}/upload-complete`, and on `200` (idempotent response) navigates to `/dashboard`. The user sees a status message indicating the file was already processed.

AC-7 (Hash-check prerequisite enforced): The orchestrator must never call `POST /drawings` without a preceding successful `POST /drawings/hash-check` response of `{ allowed: true }` for the same file in the same upload session. If `POST /drawings` returns `400` (server enforces the ordering rule), the user sees an error and the upload does not proceed.

AC-8 (Upload progress display): During the S3 PUT, `UploadProgress.tsx` displays a byte-level progress indicator that updates as the upload progresses (0% → 100%). The progress indicator is visible from the moment the PUT begins until the call to `POST /drawings/{id}/upload-complete` completes.

AC-9 (Optional revision label): The upload form includes an optional text field for `revision_label`. If provided, it is included in the `POST /drawings` request body. If left blank, it is omitted.

AC-10 (Network error during S3 PUT): If the S3 PUT XHR fails (network error or non-2xx response from S3), the user sees an error state with a "Try again" affordance. No `POST /drawings/{id}/upload-complete` is called.

AC-11 (Network error during upload-complete): If `POST /drawings/{id}/upload-complete` fails with a non-200/202 response (excluding free-tier limit cases), the user sees an error state with a "Try again" affordance. The retry re-issues only the `POST /drawings/{id}/upload-complete` call (the file has already been stored in S3).

AC-12 (Multiple file rejection): The DropZone accepts exactly one file per upload session. If multiple files are dropped simultaneously, the DropZone rejects all with a message indicating only one file may be uploaded at a time.

AC-13 (Presigned URL expiry — client guard): If the elapsed time between presigned URL receipt and the start of the S3 PUT exceeds 14 minutes (conservative threshold below the 15-minute hard expiry from §1.9), the orchestrator aborts the upload and prompts the user to restart the flow.

---

**US-018 — Free tier 3-drawing/month limit enforcement; upgrade prompt on limit hit**

AC-1 (Free tier limit hit at upload-complete): When `POST /drawings/{id}/upload-complete` returns a `402` or `403` response with error code `monthly_limit_reached`, the upload UI renders the `UpgradePrompt` component in place of the progress/success view. The user is presented with a call-to-action linking to `/subscription`. No navigation to `/dashboard` occurs.

AC-2 (Tier-gated feature still visible): The upload page is accessible to free tier users at all times; the limit is not enforced at page load. The limit surface appears only after the server confirms the limit is reached during the upload-complete call.

AC-3 (Analytics not fired client-side): The `free_limit_reached` analytics event must NOT be fired from the client. The frontend only renders the upgrade prompt in response to the server's error response; it does not emit any PostHog event directly. (Per §1.10: fires server-side from FastAPI processing initiation handler.)

##### UX and design specification

The upload page (`/upload`) is a protected route accessible only to authenticated users, wrapped in `ProtectedRoute`.

**Page Layout**

The page uses the shared `Layout` component. The upload area is centred both vertically and horizontally within the main content area.

**DropZone component**

- Renders a visually distinct rectangular drop target (dashed border, 400px × 260px minimum size, responsive).
- States:
  - `idle`: instruction text "Drag and drop your PDF or DWG file here, or click to browse". A secondary line: "Max file size: 100 MB. Accepted formats: .pdf, .dwg".
  - `drag-over`: border colour changes to active/highlight colour; background tint applied.
  - `hashing`: shows a spinner and the text "Computing file hash…" while SHA-256 is computed. The drop target is non-interactive during hashing.
  - `checking`: shows a spinner and the text "Checking file…" while `POST /drawings/hash-check` is in flight.
  - `error`: border colour changes to error colour; an inline error message is displayed below the drop target. A "Try again" or "Select a different file" link resets to `idle`. Error messages are human-readable, not raw API error strings.
  - `blocked`: specific error variant for 409 response: "This file cannot be uploaded." No retry that re-uses the same file is offered; user must select a different file.
  - `duplicate`: informational variant for `allowed: true, drawing_id` case: "This file has already been uploaded. We'll check on it for you."

- The click-to-browse behaviour opens a native `<input type="file">` with `accept=".pdf,.dwg"` and `multiple` attribute absent.
- Drag events handled: `dragenter`, `dragleave`, `dragover`, `drop`. Default browser behaviours are prevented.

**Revision Label field**

- Rendered below the DropZone as an optional text input (`<input type="text" maxLength={120} placeholder="Revision label (optional)">`).
- Only visible / interactive in `idle` state.
- Hidden once file selection begins (state transitions away from `idle`).

**UploadProgress component**

Rendered below the DropZone once the S3 PUT begins. States:

- `uploading`: a horizontal progress bar driven by XHR `progress` events. Shows "Uploading… N%" where N is the integer percentage (0–99). The cancel button is present but calls `xhr.abort()` and resets to `idle` with a cancellation message.
- `completing`: progress bar frozen at 100%; status text "Finishing upload…" while `POST /drawings/{id}/upload-complete` is in flight.
- `success`: green check icon; text "Upload complete. Redirecting to your library…". Automatic redirect to `/dashboard` after 1.5 s.
- `error`: red X icon; error message text; "Try again" button (retries `POST /drawings/{id}/upload-complete` only).
- `free_limit_reached`: renders the `UpgradePrompt` inline component (see below).

**UpgradePrompt (inline, within UploadProgress)**

- Heading: "You've reached your free plan limit"
- Body: "Free plan users can process up to 3 drawings per month. Upgrade to Pro or Team for unlimited drawings."
- CTA button: "View Plans" — links to `/subscription` via React Router `Link` (no full page reload).
- Secondary link: "Go to my library" — links to `/dashboard`.

**State machine for the page**

```
idle
  → [file selected/dropped valid] → hashing
  → [file rejected (format/size)] → idle (error shown)
hashing
  → [hash computed] → checking
checking
  → [POST /drawings/hash-check 409] → idle (blocked error)
  → [POST /drawings/hash-check 200, drawing_id present] → uploading (skip to upload-complete)
  → [POST /drawings/hash-check 200, no drawing_id] → creating
creating (POST /drawings in flight)
  → [201 received, presigned URL received] → uploading
  → [400 or other error] → idle (error shown)
uploading (XHR PUT to S3 in flight)
  → [progress event] → uploading (percent updated)
  → [xhr load, S3 2xx] → completing
  → [xhr error / S3 non-2xx] → idle (upload error)
  → [user cancels] → idle (cancel message)
completing (POST /drawings/{id}/upload-complete in flight)
  → [202] → success
  → [200 (idempotent)] → success
  → [402 / 403 monthly_limit_reached] → free_limit_reached
  → [other error] → idle (error shown, retry available)
success
  → [1.5 s timer] → redirect to /dashboard
free_limit_reached
  → [user clicks "View Plans"] → navigate to /subscription
  → [user clicks "Go to my library"] → navigate to /dashboard
```

**Accessibility requirements**

- DropZone must be keyboard-focusable (`tabIndex={0}`) and activatable with Enter/Space to open the file picker.
- All state transitions must announce their status via `aria-live="polite"` region.
- Progress bar uses `role="progressbar"` with `aria-valuenow`, `aria-valuemin="0"`, `aria-valuemax="100"`.
- Error messages are associated with the DropZone via `aria-describedby`.

##### Critical implementation notes

- **Hash-check ordering is mandatory**: The orchestrator MUST call `POST /drawings/hash-check` and receive `{ allowed: true }` before calling `POST /drawings`. If this ordering is violated, the server returns `400` (§1.5). The orchestrator must store the hash-check result (including the `sha256_hash`) in local state and pass it through to the `POST /drawings` call body.

- **SHA-256 must be computed client-side before any network call**: `hashClient.ts` must use `window.crypto.subtle.digest('SHA-256', fileBuffer)` and return the hex-encoded digest. This must complete before `POST /drawings/hash-check` is issued. For large files, read the file as `ArrayBuffer` via `FileReader` or `file.arrayBuffer()` — do NOT stream in chunks unless the SubtleCrypto API requires it (it doesn't; pass the full buffer).

- **XMLHttpRequest for S3 PUT (not fetch)**: `fetch` does not expose upload progress events. Use `XMLHttpRequest` with an `onprogress` handler on `xhr.upload` for the S3 PUT step. This is a silent failure mode: using `fetch` will produce a working upload that appears correct but `UploadProgress` will show 0% until completion.

- **No file bytes transit the API server**: The S3 PUT goes directly to the presigned URL. The orchestrator never posts the file body to any `/drawings` endpoint.

- **Upload-complete idempotency**: `POST /drawings/{id}/upload-complete` returning `200` (idempotent case, e.g., duplicate file flow via `drawing_id`) and `202` (initial enqueue) both constitute success. Both must navigate to `/dashboard`.

- **Presigned URL 15-minute expiry**: The presigned URL is valid for 15 minutes from issuance (§1.9). The orchestrator must track the time of URL receipt and refuse to begin a PUT if more than 14 minutes have elapsed (conservative guard). Silently beginning a PUT with an expired URL will result in a 403 from S3 that is indistinguishable from other S3 errors without this guard.

- **Free tier limit response handling (client-side only)**: The `free_limit_reached` analytics event is fired server-side (§1.10). The frontend MUST NOT fire any PostHog event on receiving the free-tier-limit error response. The UI only renders the `UpgradePrompt` component.

- **analytics.ts must NOT be called for `drawing_uploaded` or `free_limit_reached`**: Both events are server-side-only per §1.10. Using `analytics.ts` (S1-F) for these events from the upload page is prohibited.

- **`drawing_id` in hash-check response — deduplication path**: When `POST /drawings/hash-check` returns `{ allowed: true, drawing_id: "<uuid>" }`, skip `POST /drawings` and the S3 PUT entirely. Call `POST /drawings/{drawing_id}/upload-complete` directly. The `200` response (idempotent) is the expected success case here.

- **Single-file constraint**: The file input element must not have the `multiple` attribute. Drop handlers must reject multi-file drops before hashing begins.

- **`revision_label` field**: Include in `POST /drawings` request body when provided. Omit the key entirely (do not send `null` or empty string) when not provided, to avoid server-side validation issues.

- **No localStorage used for upload state**: The upload flow is transient session state only. `localStorage` is used only for correction state (§1.11, `correction_state:{drawing_id}`) which is not this session's concern.

- **Error message copy must be human-readable**: Never surface raw API error strings (e.g., `detail: "hash_check_required"`) to the user. Map known error codes to UX-friendly messages.

##### Mocking contract

All mock shapes must match the S2-B backend brief contracts exactly.

---

**`POST /drawings/hash-check`**

Request body (matches `HashCheckRequest` from §1.1):
```json
{ "sha256_hash": "string (hex, 64 chars)", "filename": "string", "size_bytes": 12345678 }
```

Mock response — success (allowed):
```json
HTTP 200
{ "allowed": true }
```

Mock response — success (allowed, duplicate detected):
```json
HTTP 200
{ "allowed": true, "drawing_id": "550e8400-e29b-41d4-a716-446655440001" }
```

Mock response — blocklist hit:
```json
HTTP 409
{ "detail": "File is on the blocklist and cannot be uploaded." }
```

---

**`POST /drawings`**

Request body:
```json
{
  "sha256_hash": "abc123...",
  "filename": "piping_rev3.pdf",
  "size_bytes": 4718592,
  "revision_label": "Rev3"
}
```

Mock response — created:
```json
HTTP 201
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "piping_rev3.pdf",
  "revision_label": "Rev3",
  "processing_state": "Pending",
  "upload_url": "https://pid-bucket.s3.eu-central-1.amazonaws.com/drawings/550e8400-e29b-41d4-a716-446655440000/piping_rev3.pdf?X-Amz-Signature=...",
  "uploaded_at": "2024-01-15T10:30:00Z"
}
```

Mock response — hash-check not performed:
```json
HTTP 400
{ "detail": "hash_check_required" }
```

---

**`PUT <presigned_url>`** (direct to S3, not through apiClient)

Mock: XHR to any URL starting with `https://` returns `HTTP 200` with empty body. Progress events are simulated in tests by manually calling `onprogress` with synthetic `ProgressEvent` objects.

---

**`POST /drawings/{id}/upload-complete`**

Mock response — initial enqueue (202):
```json
HTTP 202
{ "drawing_id": "550e8400-e29b-41d4-a716-446655440000", "processing_state": "Queued" }
```

Mock response — idempotent (200):
```json
HTTP 200
{ "drawing_id": "550e8400-e29b-41d4-a716-446655440000", "processing_state": "Queued" }
```

Mock response — free tier limit reached:
```json
HTTP 402
{
  "detail": "monthly_limit_reached",
  "subscription_id": "sub-uuid-0001",
  "upgrade_url": "/subscription"
}
```

Mock response — generic error:
```json
HTTP 500
{ "detail": "Internal server error" }
```

##### Acceptance criteria checklist

- [ ] [US-003 AC-1] Happy path PDF: SHA-256 computed → hash-check 200 → POST /drawings 201 → S3 PUT → upload-complete 202 → navigate to `/dashboard` [US-003 AC-1]
- [ ] [US-003 AC-2] Happy path DWG: same orchestration flow as PDF [US-003 AC-2]
- [ ] [US-003 AC-3] Non-PDF/DWG file dropped/selected is rejected client-side before any network call [US-003 AC-3]
- [ ] [US-003 AC-4] File exceeding 104,857,600 bytes rejected client-side before any network call [US-003 AC-4]
- [ ] [US-003 AC-5] Hash-check 409 → upload aborted, no POST /drawings issued, user sees blocked error message [US-003 AC-5]
- [ ] [US-003 AC-6] Hash-check 200 with `drawing_id` → POST /drawings skipped, S3 PUT skipped, upload-complete called with the returned `drawing_id`, 200 response → navigate to `/dashboard` [US-003 AC-6]
- [ ] [US-003 AC-7] If POST /drawings returns 400, user sees error and no further steps execute [US-003 AC-7]
- [ ] [US-003 AC-8] XHR `progress` events drive UploadProgress byte-level indicator from 0% to 100% during S3 PUT [US-003 AC-8]
- [ ] [US-003 AC-9] `revision_label` text field value is included in POST /drawings body when provided; key is omitted when field is empty [US-003 AC-9]
- [ ] [US-003 AC-10] XHR network error during S3 PUT → error state shown, no upload-complete called, retry affordance offered [US-003 AC-10]
- [ ] [US-003 AC-11] upload-complete non-200/202/402/403 error → error state shown, retry affordance offered, retry re-issues only upload-complete [US-003 AC-11]
- [ ] [US-003 AC-12] Multiple files dropped simultaneously → all rejected, single-file-only error message shown [US-003 AC-12]
- [ ] [US-003 AC-13] Elapsed time ≥ 14 minutes since presigned URL receipt → upload aborted before S3 PUT, user prompted to restart [US-003 AC-13]
- [ ] [US-018 AC-1] upload-complete 402 `monthly_limit_reached` → UpgradePrompt rendered, no navigation to `/dashboard` [US-018 AC-1]
- [ ] [US-018 AC-2] Upload page accessible to free tier users; limit surface appears only after server confirmation, not at page load [US-018 AC-2]
- [ ] [US-018 AC-3] `free_limit_reached` analytics event NOT fired from client on 402 response [US-018 AC-3]
- [ ] `hashClient.ts` returns lowercase hex-encoded 64-character SHA-256 string for a known test buffer [Technical AC]
- [ ] `hashClient.ts` uses `window.crypto.subtle.digest` (Web Crypto API), not any third-party library [Technical AC]
- [ ] S3 PUT uses `XMLHttpRequest`, not `fetch`; `xhr.upload.onprogress` is wired to progress state [Technical AC]
- [ ] `POST /drawings` is never called before a `POST /drawings/hash-check` call returns `{ allowed: true }` in the same session [Technical AC — ordering rule §1.4-1]
- [ ] `upload-complete` returning `200` (idempotent) navigates to `/dashboard` identically to `202` [Technical AC — §1.5]
- [ ] `/upload` page is wrapped in `ProtectedRoute`; unauthenticated access redirects to `/login` [Technical AC] [MANUAL]
- [ ] DropZone is keyboard-focusable and activatable with Enter/Space [Technical AC — accessibility] [MANUAL]
- [ ] `aria-live="polite"` region announces state transitions [Technical AC — accessibility] [MANUAL]
- [ ] Progress bar uses `role="progressbar"` with `aria-valuenow` updated during upload [Technical AC — accessibility] [MANUAL]

##### Independent Test

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/S3-C.test.ts`
- **Exact CI command**: `cd frontend && npx vitest run tests/sessions/S3-C`

**AC → assertion mapping:**

| AC | `it(...)` block name |
|---|---|
| US-003 AC-1 | `it("completes full PDF upload flow and navigates to /dashboard on 202")` |
| US-003 AC-2 | `it("accepts .dwg files through identical orchestration flow as PDF")` |
| US-003 AC-3 | `it("rejects non-PDF/DWG files client-side without issuing any network request")` |
| US-003 AC-4 | `it("rejects files exceeding 104857600 bytes before any network call")` |
| US-003 AC-5 | `it("aborts upload on hash-check 409 and shows blocked error; does not call POST /drawings")` |
| US-003 AC-6 | `it("skips POST /drawings and S3 PUT when hash-check returns drawing_id; calls upload-complete with returned id")` |
| US-003 AC-7 | `it("shows error and stops when POST /drawings returns 400")` |
| US-003 AC-8 | `it("updates progress percentage from XHR onprogress events during S3 PUT")` |
| US-003 AC-9 | `it("includes revision_label in POST /drawings body when provided; omits key when empty")` |
| US-003 AC-10 | `it("shows error state and does not call upload-complete when XHR network error occurs")` |
| US-003 AC-11 | `it("shows error state with retry on non-200/202/402/403 from upload-complete; retry re-issues only upload-complete")` |
| US-003 AC-12 | `it("rejects multi-file drops and shows single-file-only error")` |
| US-003 AC-13 | `it("aborts before S3 PUT when 14 minutes have elapsed since presigned URL was received")` |
| US-018 AC-1 | `it("renders UpgradePrompt and does not navigate on upload-complete 402 monthly_limit_reached")` |
| US-018 AC-2 | `it("renders upload page without limit error at page load regardless of tier")` |
| US-018 AC-3 | `it("does not call PostHog analytics on 402 monthly_limit_reached response")` |
| hashClient SHA-256 | `it("returns lowercase 64-char hex SHA-256 of known test buffer")` |
| hashClient Web Crypto | `it("calls window.crypto.subtle.digest with SHA-256 algorithm")` |
| XHR not fetch | `it("uses XMLHttpRequest for S3 PUT and wires xhr.upload.onprogress to progress state")` |
| Ordering rule | `it("never calls POST /drawings before POST /drawings/hash-check returns allowed:true")` |
| Idempotent 200 | `it("navigates to /dashboard when upload-complete returns 200 idempotent response")` |

**Fixtures / test doubles:**

```typescript
// fixtures/mockFile.ts
export const mockPDFFile = new File(
  [new Uint8Array(1024).fill(0x25)],  // 1 KB synthetic PDF bytes
  'test-drawing.pdf',
  { type: 'application/pdf' }
);
export const mockDWGFile = new File(
  [new Uint8Array(512).fill(0xAC)],
  'test-drawing.dwg',
  { type: 'image/vnd.dwg' }
);
export const mockLargeFile = new File(
  [new Uint8Array(104857601)],  // 100MB + 1 byte
  'too-large.pdf',
  { type: 'application/pdf' }
);
export const mockInvalidFile = new File(
  [new Uint8Array(256)],
  'spreadsheet.xlsx',
  { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }
);

// Mock SHA-256 hash for mockPDFFile (computed deterministically or stubbed)
export const MOCK_SHA256 = 'a'.repeat(64);  // 64-char hex stub for non-crypto tests

// API mock shapes (must match Mocking contract above)
export const mockHashCheckAllowed = { allowed: true };
export const mockHashCheckDuplicate = { allowed: true, drawing_id: '550e8400-e29b-41d4-a716-446655440001' };
export const mockHashCheck409 = { detail: 'File is on the blocklist and cannot be uploaded.' };
export const mockDrawingCreated = {
  id: '550e8400-e29b-41d4-a716-446655440000',
  filename: 'test-drawing.pdf',
  revision_label: null,
  processing_state: 'Pending',
  upload_url: 'https://pid-bucket.s3.eu-central-1.amazonaws.com/test-presigned-url',
  uploaded_at: '2024-01-15T10:30:00Z',
};
export const mockUploadComplete202 = { drawing_id: '550e8400-e29b-41d4-a716-446655440000', processing_state: 'Queued' };
export const mockUploadComplete200 = { drawing_id: '550e8400-e29b-41d4-a716-446655440001', processing_state: 'Queued' };
export const mockUploadComplete402 = { detail: 'monthly_limit_reached', subscription_id: 'sub-uuid-0001', upgrade_url: '/subscription' };
```

Mock strategy:
- `apiClient` from S1-F is mocked via `vi.mock('../../src/api/client')` — each test configures `apiClient.post` return values per scenario.
- XHR is mocked via a custom `MockXHR` class that stores `onprogress`, `onload`, `onerror` callbacks and exposes test helpers `simulateProgress(loaded, total)`, `simulateLoad()`, `simulateError()`.
- `window.crypto.subtle.digest` is spied on via `vi.spyOn(window.crypto.subtle, 'digest')` to verify it is called with `'SHA-256'`; actual hash computation tests use the real Web Crypto API (available in jsdom/happy-dom with Vitest).
- React Router's `useNavigate` is mocked to capture navigation calls.
- `Date.now` is mocked via `vi.useFakeTimers()` for the 14-minute presigned URL expiry test.
- PostHog / `analytics.ts` is mocked via `vi.mock('../../src/lib/analytics')` to assert it is NOT called.

**Pre-conditions:**
- `frontend/package.json` has `vitest`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom` installed (from S0-B / S1-F).
- `frontend/src/api/client.ts` and `frontend/src/api/endpoints.ts` exist (S1-F).
- `frontend/src/auth/AuthContext.tsx` and `useAuth.ts` exist (S1-F).
- `frontend/src/router.tsx` stub includes the `/upload` route (S0-A).
- No environment variables are required by the test runner — all API calls are mocked.

**Isolation rule:** This test file mocks all API calls and external dependencies. It depends on S1-F exports (`apiClient`, `useAuth`, `AuthContext`) being present as modules — those are gated by the Phase 1 → Phase 2 prerequisite. Since S1-F is a Phase 1 session and S3-C is Phase 3, S1-F will always have merged before this PR. No sibling Phase 3 sessions need to merge first. The test passes in isolation.

##### Checkpoint

Users on `/upload` can drag-and-drop or browse-select a `.pdf` or `.dwg` file, see a real-time upload progress bar as bytes transfer to S3, and land on `/dashboard` after upload completes — or see an inline upgrade prompt if they have exhausted their free-tier monthly limit — with blocked files (hash-check 409) stopped before any Drawing record is created.

**Shippability claim:** This PR is independently mergeable to `main` even if no other session in the same Phase 3 wave has merged, provided S1-F and S2-B have both merged (Phase 1 and Phase 2 gates satisfied). The upload page is reachable via the router stub from S0-A; the API endpoints it calls are defined in S2-B. Other Phase 3 sessions (S3-A, S3-B, S3-D, S3-E, S3-F, S3-G) are not required.

##### Output and handoff

| Export | Kind | Consuming session(s) | Load-bearing? |
|---|---|---|---|
| `Upload` (default export from `pages/Upload.tsx`) | React page component | S0-A (router slot pre-stubbed, now fulfilled) | No — router stub already declares the slot |
| `DropZone` (named export from `features/upload/DropZone.tsx`) | React component | None downstream directly | No |
| `computeFileSHA256` (named export from `features/upload/hashClient.ts`) | `(file: File) => Promise<string>` | S4-A (E2E tests may import for hash generation) | No |
| `UploadProgress` (named export from `features/upload/UploadProgress.tsx`) | React component | None downstream directly | No |
| `runUploadOrchestration` (named export from `features/upload/uploadOrchestrator.ts`) | `(params: UploadOrchestrationParams) => Promise<UploadOrchestrationResult>` | S4-A (E2E tests) | No |

`UploadOrchestrationParams` and `UploadOrchestrationResult` types are defined in `uploadOrchestrator.ts`:

```typescript
// [LOAD-BEARING] consumed by S4-A E2E tests
export interface UploadOrchestrationParams {
  file: File;
  revisionLabel?: string;
  onProgress: (percent: number) => void;
}

export type UploadOrchestrationResult =
  | { status: 'success'; drawingId: string }
  | { status: 'blocked' }
  | { status: 'duplicate'; drawingId: string }
  | { status: 'free_limit_reached'; subscriptionId: string }
  | { status: 'error'; message: string };
```

---

```json
{
  "test": {
    "cmd": "cd frontend && npx vitest run tests/sessions/S3-C",
    "file": "tests/sessions/S3-C.test.ts"
  },
  "checkpoint": "Users on /upload can drag-and-drop or browse-select a .pdf or .dwg file, see a real-time upload progress bar as bytes transfer to S3, and land on /dashboard after upload completes — or see an inline upgrade prompt if they have exhausted their free-tier monthly limit — with blocked files (hash-check 409) stopped before any Drawing record is created.",
  "manualAcs": [
    {
      "id": "US-003-AC-MANUAL-1",
      "text": "/upload page is wrapped in ProtectedRoute; unauthenticated access redirects to /login."
    },
    {
      "id": "US-003-AC-MANUAL-2",
      "text": "DropZone is keyboard-focusable and activatable with Enter/Space to open the native file picker."
    },
    {
      "id": "US-003-AC-MANUAL-3",
      "text": "aria-live='polite' region announces upload state transitions to screen readers."
    },
    {
      "id": "US-003-AC-MANUAL-4",
      "text": "Progress bar uses role='progressbar' with aria-valuenow updated during upload."
    }
  ],
  "exports": [
    {
      "kind": "module",
      "name": "pages/Upload",
      "shape": "frontend/src/pages/Upload.tsx"
    },
    {
      "kind": "module",
      "name": "features/upload/DropZone",
      "shape": "frontend/src/features/upload/DropZone.tsx"
    },
    {
      "kind": "function",
      "name": "computeFileSHA256",
      "shape": "(file: File) => Promise<string>"
    },
    {
      "kind": "function",
      "name": "runUploadOrchestration",
      "shape": "(params: UploadOrchestrationParams) => Promise<UploadOrchestrationResult>"
    },
    {
      "kind": "type",
      "name": "UploadOrchestrationParams",
      "shape": "{ file: File; revisionLabel?: string; onProgress: (percent: number) => void }"
    },
    {
      "kind": "type",
      "name": "UploadOrchestrationResult",
      "shape": "{ status: 'success'; drawingId: string } | { status: 'blocked' } | { status: 'duplicate'; drawingId: string } | { status: 'free_limit_reached'; subscriptionId: string } | { status: 'error'; message: string }"
    },
    {
      "kind": "module",
      "name": "features/upload/UploadProgress",
      "shape": "frontend/src/features/upload/UploadProgress.tsx"
    }
  ]
}
```