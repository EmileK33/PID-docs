---

#### S3-D — Frontend: Review Canvas (Konva)

**Phase 3 | Frontend | Needs: S1-F, S2-B, S2-C**

##### Objective

Build the interactive P&ID drawing review canvas that renders color-coded bounding box overlays on rasterized drawings using Konva.js, and provides symbol inspection, reclassification, rejection, restoration, and manual annotation with server-persistent correction state — the primary value-delivery surface of the application.

##### Scope

**P0 MVP.** All work in this session is P0, serving US-011 (display), US-012, US-013, US-014, and US-015.

P1 stubs required (clearly marked `// P1 STUB — US-021/US-022`):
- Table region overlay layer (US-021: ML instrument table detection display)
- Table cell inspection and editing panel (US-022: table cell review/edit on canvas)

These stubs must appear as exported no-op components/functions with TODO comments so downstream P1 sessions can fill them in without touching P0 code.

##### Technology constraints

**Required (non-negotiable, from §1.8):**
- **React + Vite** — SPA framework; no Next.js/SSR in this package
- **Konva.js** (or Fabric.js) — canvas rendering; "Virtualized canvas with layer isolation is the chosen approach to meet <200ms NFR-19 with 500+ symbols; SVG overlay on top of rasterized DWG/PDF output" (§1.8)
- **TypeScript** — strict mode; all component props and store interfaces must be fully typed

**Must NOT use:**
- SVG-only rendering (prohibitively slow at 500+ symbols; violates NFR-19 architectural decision)
- Any canvas rendering library other than Konva.js or Fabric.js
- Lazy correction data fetching on symbol click (violates <200ms SLA — all correction history must be pre-loaded)
- Client-side resolution of team-level training consent (violates §1.4 rule 7)

**Testing stack:** vitest + @testing-library/react + @testing-library/user-event; canvas imperative calls mocked via jest-canvas-mock or equivalent vitest mock.

##### Performance targets

| Metric | Target | Type | Constraint source |
|---|---|---|---|
| Symbol select + panel open | <200ms P95 | **Hard SLA (NFR-19)** | §1.9; achieved by pre-loading all correction history at canvas init — zero additional network fetches on panel open |
| Initial canvas load (symbol fetch) | <3s P95 | Monitoring target | §1.9; `GET /drawings/{id}/symbols` + JSONB bbox storage |

The <200ms SLA is the dominant architectural constraint of this session. Every design decision (pre-loading, layer isolation, optimistic local updates) is subordinate to it.

##### Owned files

```
frontend/src/pages/Review.tsx
frontend/src/features/canvas/Canvas.tsx
frontend/src/features/canvas/SymbolLayer.tsx
frontend/src/features/canvas/BoundingBox.tsx
frontend/src/features/canvas/PageNav.tsx
frontend/src/features/canvas/InspectionPanel.tsx
frontend/src/features/canvas/ManualAnnotate.tsx
frontend/src/features/canvas/CorrectionStore.ts
frontend/src/features/canvas/useCanvasShortcuts.ts
```

##### Read-only imports

| Owning session | File path | Named exports required |
|---|---|---|
| S0-A | `frontend/src/types/contracts.ts` | `SymbolRecord`, `CorrectionRecord`, `EntityClassId`, `CorrectionType`, `SymbolSource`, `BoundingBox`, `DrawingProcessingState`, `SymbolsPageResponse` |
| S1-F | `frontend/src/api/client.ts` | `apiClient` |
| S1-F | `frontend/src/api/endpoints.ts` | `API_ENDPOINTS` |
| S1-F | `frontend/src/auth/useAuth.ts` | `useAuth` |
| S1-F | `frontend/src/hooks/useSSE.ts` | `useSSE` |
| S1-F | `frontend/src/hooks/usePolling.ts` | `usePolling` |
| S1-F | `frontend/src/components/Layout.tsx` | `Layout` |
| S1-F | `frontend/src/lib/storage.ts` | `localStorageGet`, `localStorageSet`, `localStorageRemove` |
| S1-F | `frontend/src/lib/analytics.ts` | `trackEvent` |

##### Do not touch

- `frontend/src/main.tsx` — entry point, pre-stubbed by S0-A
- `frontend/src/App.tsx` — app root, pre-stubbed by S0-A
- `frontend/src/router.tsx` — lazy route stubs, pre-stubbed by S0-A
- `frontend/src/pages/_stubs.tsx` — page stubs, owned by S0-A
- `frontend/src/types/contracts.ts` — shared types, owned by S0-A
- `frontend/src/api/client.ts` — API client, owned by S1-F
- `frontend/src/api/endpoints.ts` — endpoint constants, owned by S1-F
- `frontend/src/auth/AuthContext.tsx` — owned by S1-F
- `frontend/src/auth/useAuth.ts` — owned by S1-F
- `frontend/src/auth/supabaseClient.ts` — owned by S1-F
- `frontend/src/hooks/useSSE.ts` — owned by S1-F
- `frontend/src/hooks/usePolling.ts` — owned by S1-F
- `frontend/src/components/Layout.tsx` — owned by S1-F
- `frontend/src/components/Nav.tsx` — owned by S1-F
- `frontend/src/components/GraceBanner.tsx` — owned by S1-F
- `frontend/src/components/ProtectedRoute.tsx` — owned by S1-F
- `frontend/src/lib/storage.ts` — owned by S1-F
- `frontend/src/lib/analytics.ts` — owned by S1-F
- `frontend/src/styles/globals.css` — owned by S1-F
- All files under `frontend/src/pages/auth/` — owned by S3-A
- All files under `frontend/src/pages/Dashboard.tsx`, `frontend/src/features/library/` — owned by S3-B
- All files under `frontend/src/pages/Upload.tsx`, `frontend/src/features/upload/` — owned by S3-C
- All files under `frontend/src/pages/Account.tsx`, `frontend/src/features/account/` — owned by S3-E
- All files under `frontend/src/pages/Subscription.tsx`, `frontend/src/features/subscription/` — owned by S3-F
- All files under `frontend/src/features/exports/`, `frontend/src/features/notifications/` — owned by S3-G

##### Architecture context

From §1.8 Technology Stack:

> **Canvas Rendering** | Konva.js (or Fabric.js) | Virtualized canvas with layer isolation is the chosen approach to meet <200ms NFR-19 with 500+ symbols; SVG overlay on top of rasterized DWG/PDF output

From §1.9 Performance Targets:

> | Canvas load (symbol fetch) | <3s P95 | Monitoring target | FastAPI `GET /drawings/{id}/symbols` + PostgreSQL JSONB bbox storage; correction history co-loaded in same response |
> | Canvas interaction (symbol select + panel open) | <200ms P95 | **Hard SLA (NFR-19)** | React SPA; correction history pre-loaded at canvas init — no additional network fetch on panel open |

From §1.1 Shared Contracts — Symbols API Response:

> ```typescript
> interface SymbolsPageResponse {
>   symbols: SymbolRecord[];
>   corrections_by_symbol_id: Record<string, CorrectionRecord[]>;
>   total: number;
>   limit: number;
>   offset: number;
> }
>
> interface SymbolRecord {
>   id: string;
>   drawing_id: string;
>   entity_class_id: EntityClassId;
>   subtype: string;
>   tag_label: string | null;
>   confidence: number;
>   bbox: BoundingBox;
>   source: SymbolSource;
>   rejected: boolean;
>   page_number: number;
> }
>
> interface CorrectionRecord {
>   id: string;
>   detected_symbol_id: string | null;
>   table_cell_id: string | null;
>   user_id: string;
>   correction_type: CorrectionType;
>   new_class_id: EntityClassId | null;
>   training_consent: boolean;
>   created_at: string;
> }
> ```

From §1.1 — BoundingBox:

> ```typescript
> interface BoundingBox {
>   x: number;
>   y: number;
>   w: number;
>   h: number;
> }
> ```

From §1.3 State Machines:

> ```typescript
> const DRAWING_STATE_TRANSITIONS: Record<DrawingProcessingState, DrawingProcessingState[]> = {
>   Complete:     ['Under_Review', 'Queued'],     // → Under_Review on first correction action
>   Under_Review: ['Queued'],
>   ...
> }
> // Under_Review trigger: first user correction action (reclassify, reject, manual_add) — NOT canvas open
> ```

From §1.4 Critical Ordering Rules:

> **Rule 6:** "Each correction save sends... the resolved `training_consent` value... at time of creation; the consent value must be snapshotted at correction time, not resolved lazily."

> **Rule 7:** "Team-level consent resolution must be evaluated server-side to prevent client-side bypass; the resolved value is not a client-supplied field."

> **Rule 13:** "The drawing transitions from `Complete` to `Under_Review` on the user's first correction action (e.g., accepting, rejecting, or editing a detected symbol), not on canvas open."

From §1.11 Cross-Session Runtime Patterns — Browser Storage Keys:

> | `correction_state:{drawing_id}` | localStorage (≤2MB cap) | Canvas review SPA | Canvas review SPA on reload | Unsaved correction state flush; server-saved state takes precedence if timestamps conflict |

From §1.9 Performance Targets — Symbol pagination:

> | Symbol pagination default / max | 200 default / 500 max per page | Hard constraint | `GET /drawings/{id}/symbols` |

From §1.1 — Entity Classes:

> ```typescript
> type EntityClassId =
>   | 'pipe'
>   | 'valve_gate'
>   | 'valve_globe'
>   | 'valve_ball'
>   | 'valve_butterfly'
>   | 'valve_check'
>   | 'valve_control'
>   | 'instrument';
> ```

From §1.2 Database Schema — entity_class table:

> ```sql
> CREATE TABLE entity_class (
>   id           VARCHAR PRIMARY KEY,  -- EntityClassId values
>   name         VARCHAR NOT NULL,
>   parent_class VARCHAR,
>   color_hex    VARCHAR NOT NULL
> );
> ```

From §1.2 — detected_symbol constraints:

> ```sql
> CREATE TABLE detected_symbol (
>   ...
>   source   VARCHAR NOT NULL CHECK (source IN ('ml','manual')),
>   rejected BOOLEAN NOT NULL DEFAULT FALSE,
>   ...
> );
> ```

From §1.10 Analytics Event Contracts:

> | `correction_action` | `{ event: 'correction_action', timestamp: string, user_id: string, drawing_id: string, symbol_id: string }` | FastAPI — `PATCH /symbols/{id}` and `POST /drawings/{id}/symbols` handlers | User submits a reclassify, reject, restore, or manual_add correction | None specified | Browser client directly; must fire server-side on persistence |

From §1.3 — Role-Permission Matrix:

> ```typescript
> user: {
>   symbol_correct: 'own',
>   ...
> },
> team_member: {
>   symbol_correct: 'team',
>   ...
> },
> team_admin: {
>   symbol_correct: 'team',
>   ...
> }
> ```

##### User stories and acceptance criteria

**US-011 — Detection Results Display (display half only; processing trigger owned by S2-H/S2-J)**

As a user, when I navigate to a drawing that has been successfully processed, I can see all detected symbols overlaid on the drawing so I can review what the ML model found.

- AC-1: When `drawing.processing_state` is `Complete` or `Under_Review`, the canvas page renders with the rasterized drawing image as background and all detected symbols as bounding box overlays.
- AC-2: Each symbol's confidence score (0–100%) is shown in the inspection panel when that symbol is selected.
- AC-3: Symbols where `rejected=true` are visually distinguished from active symbols (e.g., dimmed stroke, dashed border).
- AC-4: When `drawing.processing_state` is not `Complete` or `Under_Review` (e.g., `Processing`, `Failed`), the canvas page shows the current state (processing indicator or error message) and does not attempt to render symbol overlays.
- AC-5: For drawings in `Processing` or `Queued` state, the page subscribes to `GET /drawings/{id}/status` SSE stream and transitions to the canvas view when state reaches `Complete`.

**US-012 — Color-Coded Overlays, Multi-Page Navigation, Under_Review Transition**

As a user reviewing a processed P&ID drawing, I can see color-coded bounding boxes distinguishing entity types, navigate multi-page PDFs, and my first correction action marks the drawing as under review.

- AC-1: Each entity class is rendered with its `color_hex` value (from `GET /entity-classes`). All eight entity classes have visually distinct colors.
- AC-2: Pipe bounding boxes, valve (all subtypes) bounding boxes, and instrument bounding boxes are visually distinct from each other via color.
- AC-3: For drawings with `page_count > 1`, page navigation controls (previous page, next page, current page number, total pages) are visible.
- AC-4: Only symbols whose `page_number` equals the currently displayed page are rendered on the canvas.
- AC-5: Navigating to a different page clears the current selection and re-renders the symbol layer for the new page.
- AC-6: The first correction action (reclassify, reject, or manual_add) by the user triggers a drawing state change to `Under_Review`. Canvas-open alone does not trigger this transition (the state change is handled server-side via the correction endpoints; the frontend must not make any drawing state PATCH on canvas open).

**US-013 — Symbol Inspection Panel, Reclassify, Reject, Restore, Server Persistence**

As a user, I can click any symbol to open an inspection panel showing its details and history, reclassify or reject it, and see my changes saved to the server with a visual indicator.

- AC-1: Clicking a symbol on the canvas opens the inspection panel with: entity class name and color, subtype, tag_label, confidence percentage, source (ML or Manual), and correction history (all prior corrections for that symbol).
- AC-2: The inspection panel opens within <200ms because correction history is pre-loaded at canvas init via `corrections_by_symbol_id` in the symbols response — no additional network fetch is made when opening the panel.
- AC-3: The inspection panel shows a dropdown list of all entity classes (from `GET /entity-classes`) for reclassification. Only classes in the predefined `EntityClassId` list are available.
- AC-4: Submitting a reclassification calls `PATCH /symbols/{id}` with `correction_type: "reclassify"` and `new_class_id`. The bounding box color updates optimistically to the new entity class color before the server responds.
- AC-5: Clicking "Reject" on a symbol calls `PATCH /symbols/{id}` with `correction_type: "reject"`. The symbol is immediately rendered as rejected (dimmed) optimistically.
- AC-6: Clicking "Restore" on a rejected symbol calls `PATCH /symbols/{id}` with `correction_type: "restore"`. The symbol is immediately rendered as active again optimistically.
- AC-7: An optimistic save indicator transitions through states: no indicator (idle) → "Saving…" (request in flight) → "Saved" (200 response received) → "Error — retry?" (non-2xx response). On error, the local state is rolled back to the pre-correction state.
- AC-8: On server error during save, the failed correction attempt is written to `localStorage` at key `correction_state:{drawing_id}` so it can be retried.

**US-014 — Manual Annotation (Draw Bounding Box)**

As a user, I can draw a new bounding box on the canvas, assign it an entity class, and optionally set a tag label to add a symbol the ML model missed.

- AC-1: The canvas has a togglable "annotate" mode (button or keyboard shortcut). When active, the cursor changes to crosshair and drag-to-create creates a new bounding box.
- AC-2: After completing a drag-draw, a modal/panel appears prompting for: entity class (required, dropdown of all EntityClassId values), and tag_label (optional text input).
- AC-3: Cancelling the modal discards the drawn rectangle without creating a symbol.
- AC-4: Submitting the form calls `POST /drawings/{id}/symbols`. The new symbol is added to the canvas optimistically and confirmed on server 201 response.
- AC-5: Manually created symbols received back from the server have `confidence: 1.0` and `source: "manual"` — the canvas must use these server-returned values (not hardcode them client-side for display).
- AC-6: The minimum bounding box dimension is 5px in each direction; boxes smaller than this are discarded on mouse-up with no modal shown.

**US-015 — Session Restore, Training Consent Gating**

As a user, my correction work is never lost across page reloads, and my training consent preference is attached to every correction I submit.

- AC-1: On canvas load, server-persisted corrections (from `GET /drawings/{id}/symbols`) are the authoritative state and are loaded first.
- AC-2: Any unsaved corrections stored in `localStorage` at `correction_state:{drawing_id}` are loaded and merged with server state. If a correction exists in both localStorage and server state, the server state takes precedence (server `created_at` timestamp wins on conflict).
- AC-3: Every local correction is written to `localStorage` at `correction_state:{drawing_id}` before the server request is dispatched. The localStorage entry is removed once the server confirms the save (200/201 response).
- AC-4: The localStorage payload is capped at 2MB. If writing a new entry would exceed 2MB, the oldest unconfirmed entries are evicted (FIFO) before writing the new entry.
- AC-5: Each correction request body includes `training_consent: boolean` representing the user's current individual consent preference (loaded from `GET /account/consent` at canvas init). The server is authoritative for the final snapshotted value; the frontend must not assume its sent value was honored.
- AC-6: The training consent flag sent with each correction defaults to the `opted_in` value returned by `GET /account/consent`. The UI displays a non-editable indicator showing "Training consent: On/Off" reflecting this preference; users must go to Account settings to change it (no inline toggle on the canvas).

##### UX and design specification

**Page structure — `Review.tsx`**

The review page is a full-viewport layout:
- **Top bar** (fixed, ~48px): drawing filename, revision label, processing state badge, page navigation controls (if multi-page), export button (delegates to S3-G `ExportButton`), "Annotate" mode toggle button, back-to-library link.
- **Main area**: canvas fills remaining viewport height and full width. Canvas is scrollable/zoomable. On small viewports (< 768px), the inspection panel renders below the canvas (stacked layout). On ≥ 768px, the inspection panel slides in from the right (side-by-side with canvas).
- **Right panel** (`InspectionPanel`): 320px wide, slides in when a symbol is selected. Empty state when no selection: "Select a symbol to inspect."
- **Processing overlay**: if drawing state is not `Complete` or `Under_Review` on load, an overlay covers the canvas area showing current state name, a spinner for in-progress states, or an error message for `Failed`/`Scan_Failed` states.

**Canvas Konva.js layer structure**

```
Stage (viewport-sized, responsive)
├── Layer 0 — Background: Konva.Image of rasterized drawing page
├── Layer 1 — Symbols: one Konva.Rect per non-rejected symbol + label text
├── Layer 2 — Rejected: one Konva.Rect per rejected symbol (dashed stroke, 40% opacity)
├── Layer 3 — Selection: single Konva.Rect outline + glow effect for selected symbol
└── Layer 4 — Annotation: active only in annotate mode; captures drag to draw new Rect
```

Layers 1–3 are redrawn only when their data changes. Layer 3 only redraws on selection change. Layer 0 redraws only on page change.

**BoundingBox rendering**

Each `SymbolRecord` maps to a Konva.Rect:
- `x`, `y`, `w`, `h` from `bbox` (coordinate system: pixels relative to the full rasterized image)
- `stroke`: `color_hex` of the symbol's `entity_class_id` (looked up from entity classes cache)
- `strokeWidth`: 2px (normal), 3px (hover), 4px (selected)
- `fill`: `color_hex` at 10% opacity (normal), 20% opacity (hover)
- Label: Konva.Text with `tag_label` if non-null, positioned above the bbox; font 11px, same color as stroke
- Rejected symbols: `stroke` gray `#9E9E9E`, `fill` gray 10%, `dash: [6, 3]`, `opacity: 0.5`

**Interaction states**

- **Idle**: cursor default; hovering a symbol shows tooltip with entity class name + confidence %
- **Hover**: symbol stroke thickens to 3px, fill opacity 20%
- **Selected**: stroke 4px, glow ring, Layer 3 rect renders; InspectionPanel opens
- **Annotate mode**: cursor crosshair; drawing a rect triggers ManualAnnotate modal on mouse-up

**InspectionPanel fields and layout**

```
Header:  [EntityClass color chip] EntityClass Name  [Close ×]
         Subtype: <value or "—">
         Tag: <value or "—">
         Confidence: <e.g., "92%"> [progress bar]
         Source: ML | Manual
         Training consent: On | Off [read-only chip]

Actions: [Reclassify ▾] — dropdown of all 8 entity classes
         [Reject] / [Restore] — contextual on rejected state

Save indicator: (idle) | ⟳ Saving… | ✓ Saved | ✕ Error — Retry

History section (collapsible, "Correction History"):
  For each CorrectionRecord (newest first):
    - correction_type label, new_class_id (if reclassify), timestamp (relative)
```

**PageNav controls**

Visible only when `drawing.page_count > 1`:
```
[← Prev]  Page 2 of 5  [Next →]
```
Keyboard: `ArrowLeft` / `ArrowRight` for page navigation (when no input focused).

**ManualAnnotate modal**

Appears as a floating panel near the drawn rect:
```
Add Symbol
─────────────────
Entity Class* [dropdown — required]
Tag Label     [text input — optional, max 32 chars]

[Cancel]  [Add Symbol]
```

Validation: entity class required; show inline error if submitted empty. Cancel discards the rect. Add Symbol calls `POST /drawings/{id}/symbols`.

**Keyboard shortcuts (`useCanvasShortcuts`)**

| Key | Action | Condition |
|---|---|---|
| `Escape` | Deselect symbol; exit annotate mode | Always |
| `Delete` / `Backspace` | Reject selected symbol | Symbol selected, not rejected |
| `r` | Open reclassify dropdown | Symbol selected |
| `a` | Toggle annotate mode | Not in input |
| `ArrowLeft` | Previous page | `page_count > 1`, not in input |
| `ArrowRight` | Next page | `page_count > 1`, not in input |
| `+` / `-` | Zoom in / out | Not in input |

**State management — `CorrectionStore.ts`**

```typescript
interface LocalCorrectionEntry {
  symbolId: string;
  correctionType: CorrectionType;
  newClassId: EntityClassId | null;
  trainingConsent: boolean;
  localTimestamp: string;   // ISO 8601, set at creation
  confirmed: boolean;       // true once server 200/201 received
}

// localStorage key: `correction_state:{drawing_id}`
// Shape: LocalCorrectionEntry[]
// Cap: 2MB; evict oldest unconfirmed entries when at cap
```

Merge rule on load:
1. Load `symbols` + `corrections_by_symbol_id` from server.
2. Load `correction_state:{drawing_id}` from localStorage.
3. For each localStorage entry: if a matching server `CorrectionRecord` exists with `created_at > localTimestamp`, discard the localStorage entry. Otherwise keep the localStorage entry (will be displayed as pending/unsaved).
4. Write back cleaned localStorage (remove confirmed entries).

**Optimistic update pattern**

1. Apply correction to local state immediately (re-render canvas Layer 1/2/3).
2. Write to localStorage.
3. Dispatch `PATCH /symbols/{id}` or `POST /drawings/{id}/symbols`.
4. On success: mark localStorage entry as confirmed; remove it.
5. On error: roll back local state to pre-correction snapshot; show "Error — Retry?" in InspectionPanel; keep localStorage entry.

##### Critical implementation notes

- **Pre-load all correction history at canvas init.** The `GET /drawings/{id}/symbols` response includes `corrections_by_symbol_id` — this must be stored in `CorrectionStore` on init. `InspectionPanel` must read exclusively from this store, never issue a network fetch when opening. Violating this silently destroys the <200ms Hard SLA while appearing to work correctly.

- **Under_Review transition is server-side only.** "The drawing transitions from `Complete` to `Under_Review` on the user's first correction action… not on canvas open." (§1.4 rule 13). The frontend must NOT call `PATCH /drawings/{id}` or any state-change endpoint on canvas open. The `drawing.processing_state` in local state should be updated to `Under_Review` after the first successful `PATCH /symbols/{id}` or `POST /drawings/{id}/symbols` response (if the server returns the updated drawing state in the response, or via a re-fetch of `GET /drawings/{id}`).

- **Training consent sent but not authoritative.** Per §1.4 rules 6 and 7: `training_consent` must be snapshotted at correction creation time; team-level override is evaluated server-side. The frontend sends the value from `GET /account/consent`'s `opted_in` field. The client must not attempt to compute team-level overrides. The value stored in `CorrectionRecord.training_consent` (returned by server) is the resolved value.

- **Free tier counter.** This session does not interact with the free tier counter directly — it is gated in `POST /drawings/{id}/upload-complete` (S2-B). The `free_limit_reached` analytics event fires server-side. The canvas page is only reachable for drawings that have already been processed.

- **Symbol pagination — load all pages.** The symbol pagination default is 200/page, max 500/page (§1.9). If `total > limit`, the canvas must fetch all pages sequentially on init (using `offset` parameter) before rendering, so that multi-page drawings show all symbols. Do not render a partial symbol set then load more lazily — this would cause symbols to appear/disappear and would violate the pre-load contract. Use `limit=500` to minimize round trips.

- **`correction_action` analytics event fires server-side.** Per §1.10: the `correction_action` event fires from `FastAPI — PATCH /symbols/{id}` and `POST /drawings/{id}/symbols` handlers. The frontend must NOT fire this event — doing so would cause double-counting.

- **Konva.js layer isolation for 500+ symbols.** Layer 1 (active symbols) and Layer 2 (rejected symbols) must be separate Konva layers. Selection state lives on Layer 3. Changing selection state must only redraw Layer 3, not Layers 1–2. If all symbols are on a single layer, selection changes will trigger a full repaint of 500+ Rects and will violate the <200ms SLA.

- **localStorage 2MB cap enforcement.** "correction_state:{drawing_id} — localStorage (≤2MB cap)" (§1.11). When writing to localStorage, measure `JSON.stringify(entries).length` against `2 * 1024 * 1024`. If over cap, evict oldest unconfirmed entries (by `localTimestamp` ascending) until under cap.

- **Server state takes precedence on conflict.** "server-saved state takes precedence if timestamps conflict" (§1.11). Compare `server CorrectionRecord.created_at` against `LocalCorrectionEntry.localTimestamp` — if server is newer for the same symbol, drop the localStorage entry.

- **Drawings not in Complete/Under_Review must not render canvas.** If `drawing.processing_state` is `Pending`, `Queued`, `Scanning`, or `Processing`, render a processing status overlay and subscribe to SSE (`GET /drawings/{id}/status`) to update when state changes. If `Failed` or `Scan_Failed`, render error state with no canvas. This prevents attempting to load symbols for unprocessed drawings.

- **Optimistic rollback on error.** The CorrectionStore must snapshot the full symbol state before dispatching each PATCH/POST. On non-2xx response, restore from snapshot. The canvas re-renders from the rolled-back state. The failed correction remains in localStorage for retry.

- **HTTP status code contract for PATCH /symbols/{id}.** Expect `200` on success. `401` redirects to login. `403` shows "You do not have permission to correct this symbol." `404` removes the symbol from local state (it was deleted by another session). Any `5xx` triggers rollback and retry UI.

- **`POST /drawings/{id}/symbols` returns `201` on success** with the full `SymbolRecord` including server-assigned `id`, `confidence: 1.0`, `source: "manual"`. The optimistic local symbol (created before server response) must be replaced with the server-returned record on 201.

- **P1 stubs must be exported no-ops.** `TableRegionLayer` and `TableCellInspectionPanel` must be exported from `Canvas.tsx` as stub components with `// P1 STUB — US-021` comments. They must render `null` and accept props of the correct P1 shape (to be filled by the P1 session without touching P0 files).

##### Mocking contract

**Endpoint mocks required for this session's tests:**

---

`GET /drawings/{id}` (S2-B)
```json
{
  "id": "drawing-uuid-1",
  "owner_user_id": "user-uuid-1",
  "owner_team_id": null,
  "filename": "refinery-unit-4.pdf",
  "revision_label": "Rev B",
  "processing_state": "Complete",
  "page_count": 3,
  "estimated_symbol_count": 25,
  "uploaded_at": "2024-06-01T09:00:00Z",
  "processed_at": "2024-06-01T09:07:00Z",
  "stored_file_id": "file-uuid-1",
  "image_url": "https://s3.example.com/presigned/page-1.png?sig=abc"
}
```

`GET /drawings/{id}/symbols?limit=500&offset=0` (S2-B)
```json
{
  "symbols": [
    {
      "id": "sym-uuid-1",
      "drawing_id": "drawing-uuid-1",
      "entity_class_id": "valve_gate",
      "subtype": "gate",
      "tag_label": "FV-101",
      "confidence": 0.92,
      "bbox": { "x": 100, "y": 200, "w": 50, "h": 50 },
      "source": "ml",
      "rejected": false,
      "page_number": 1
    },
    {
      "id": "sym-uuid-2",
      "drawing_id": "drawing-uuid-1",
      "entity_class_id": "pipe",
      "subtype": "",
      "tag_label": null,
      "confidence": 0.78,
      "bbox": { "x": 300, "y": 150, "w": 200, "h": 10 },
      "source": "ml",
      "rejected": false,
      "page_number": 1
    },
    {
      "id": "sym-uuid-3",
      "drawing_id": "drawing-uuid-1",
      "entity_class_id": "instrument",
      "subtype": "",
      "tag_label": "PI-201",
      "confidence": 0.55,
      "bbox": { "x": 500, "y": 300, "w": 40, "h": 40 },
      "source": "ml",
      "rejected": false,
      "page_number": 2
    }
  ],
  "corrections_by_symbol_id": {
    "sym-uuid-1": [
      {
        "id": "corr-uuid-1",
        "detected_symbol_id": "sym-uuid-1",
        "table_cell_id": null,
        "user_id": "user-uuid-1",
        "correction_type": "reclassify",
        "new_class_id": "valve_ball",
        "training_consent": true,
        "created_at": "2024-06-01T10:00:00Z"
      }
    ]
  },
  "total": 3,
  "limit": 500,
  "offset": 0
}
```

`GET /entity-classes` (S2-G)
```json
[
  { "id": "pipe",             "name": "Pipe",             "parent_class": null,   "color_hex": "#2196F3" },
  { "id": "valve_gate",       "name": "Gate Valve",       "parent_class": null,   "color_hex": "#4CAF50" },
  { "id": "valve_globe",      "name": "Globe Valve",      "parent_class": null,   "color_hex": "#8BC34A" },
  { "id": "valve_ball",       "name": "Ball Valve",       "parent_class": null,   "color_hex": "#CDDC39" },
  { "id": "valve_butterfly",  "name": "Butterfly Valve",  "parent_class": null,   "color_hex": "#FFC107" },
  { "id": "valve_check",      "name": "Check Valve",      "parent_class": null,   "color_hex": "#FF9800" },
  { "id": "valve_control",    "name": "Control Valve",    "parent_class": null,   "color_hex": "#FF5722" },
  { "id": "instrument",       "name": "Instrument",       "parent_class": null,   "color_hex": "#9C27B0" }
]
```

`GET /account/consent` (S2-F)
```json
{
  "opted_in": true,
  "updated_at": "2024-05-15T08:00:00Z"
}
```

`PATCH /symbols/{id}` — reclassify (S2-C)
- Request: `{ "correction_type": "reclassify", "new_class_id": "valve_ball", "training_consent": true }`
- Response `200`:
```json
{
  "id": "sym-uuid-1",
  "drawing_id": "drawing-uuid-1",
  "entity_class_id": "valve_ball",
  "subtype": "gate",
  "tag_label": "FV-101",
  "confidence": 0.92,
  "bbox": { "x": 100, "y": 200, "w": 50, "h": 50 },
  "source": "ml",
  "rejected": false,
  "page_number": 1
}
```

`PATCH /symbols/{id}` — reject (S2-C)
- Request: `{ "correction_type": "reject", "new_class_id": null, "training_consent": true }`
- Response `200`:
```json
{
  "id": "sym-uuid-1",
  "drawing_id": "drawing-uuid-1",
  "entity_class_id": "valve_gate",
  "subtype": "gate",
  "tag_label": "FV-101",
  "confidence": 0.92,
  "bbox": { "x": 100, "y": 200, "w": 50, "h": 50 },
  "source": "ml",
  "rejected": true,
  "page_number": 1
}
```

`PATCH /symbols/{id}` — restore (S2-C)
- Request: `{ "correction_type": "restore", "new_class_id": null, "training_consent": true }`
- Response `200`:
```json
{
  "id": "sym-uuid-1",
  "drawing_id": "drawing-uuid-1",
  "entity_class_id": "valve_gate",
  "subtype": "gate",
  "tag_label": "FV-101",
  "confidence": 0.92,
  "bbox": { "x": 100, "y": 200, "w": 50, "h": 50 },
  "source": "ml",
  "rejected": false,
  "page_number": 1
}
```

`PATCH /symbols/{id}` — server error mock (S2-C)
- Response `500`: `{ "detail": "Internal server error" }`

`POST /drawings/{id}/symbols` (S2-C)
- Request: `{ "entity_class_id": "instrument", "subtype": "", "tag_label": "FT-301", "bbox": { "x": 600, "y": 400, "w": 45, "h": 45 }, "page_number": 1 }`
- Response `201`:
```json
{
  "id": "sym-uuid-new",
  "drawing_id": "drawing-uuid-1",
  "entity_class_id": "instrument",
  "subtype": "",
  "tag_label": "FT-301",
  "confidence": 1.0,
  "bbox": { "x": 600, "y": 400, "w": 45, "h": 45 },
  "source": "manual",
  "rejected": false,
  "page_number": 1
}
```

`GET /drawings/{id}/status` — SSE (S2-B)
Mock stream event (for processing-state drawings):
```
data: {"drawing_id":"drawing-uuid-2","state":"Complete","timestamp":"2024-06-01T09:07:00Z"}
```

##### Acceptance criteria checklist

- [ ] When `drawing.processing_state` is `Complete`, canvas renders with drawing image background and symbol bounding boxes overlaid [US-011 AC-1]
- [ ] Each symbol's confidence score is displayed as a percentage in the inspection panel when selected [US-011 AC-2]
- [ ] Rejected symbols (`rejected: true`) are rendered with dashed border and reduced opacity, visually distinct from active symbols [US-011 AC-3]
- [ ] When drawing state is `Processing` or `Queued`, an overlay with state name and spinner is shown; no symbol overlays are attempted [US-011 AC-4]
- [ ] When drawing state is `Processing`, the page subscribes to SSE and transitions to canvas view on `Complete` event without page reload [US-011 AC-5]
- [ ] Each entity class bounding box renders using the `color_hex` value from `GET /entity-classes` [US-012 AC-1]
- [ ] Pipe, valve (any subtype), and instrument bounding boxes render in visibly different colors [US-012 AC-2]
- [ ] For drawings with `page_count > 1`, previous/next page controls and "Page N of M" indicator are visible [US-012 AC-3]
- [ ] Only symbols with `page_number` matching current page are rendered [US-012 AC-4]
- [ ] Navigating to a different page clears selection state and renders only the new page's symbols [US-012 AC-5]
- [ ] Canvas open does not trigger any drawing state change or PATCH request to the drawings endpoint [US-012 AC-6]
- [ ] Clicking a symbol opens the inspection panel showing entity class, subtype, tag_label, confidence, source, and correction history [US-013 AC-1]
- [ ] No additional API call is made when opening the inspection panel — all data comes from the pre-loaded CorrectionStore [US-013 AC-2]
- [ ] The inspection panel reclassify dropdown lists exactly the 8 `EntityClassId` values from `GET /entity-classes` [US-013 AC-3]
- [ ] Submitting reclassification calls `PATCH /symbols/{id}` with `correction_type: "reclassify"` and `new_class_id`; bounding box color updates optimistically [US-013 AC-4]
- [ ] Clicking Reject calls `PATCH /symbols/{id}` with `correction_type: "reject"`; symbol renders as rejected optimistically [US-013 AC-5]
- [ ] Clicking Restore on rejected symbol calls `PATCH /symbols/{id}` with `correction_type: "restore"`; symbol renders as active optimistically [US-013 AC-6]
- [ ] Save indicator transitions through idle → Saving… → Saved on successful server response [US-013 AC-7]
- [ ] On 500 response from PATCH, local state rolls back to pre-correction state and "Error — Retry?" is displayed [US-013 AC-7]
- [ ] On save error, the failed correction is written to localStorage at `correction_state:{drawing_id}` [US-013 AC-8]
- [ ] Annotate mode toggle changes canvas cursor to crosshair and enables drag-to-draw [US-014 AC-1]
- [ ] After completing drag-draw, a modal appears with entity class dropdown (required) and tag_label input (optional) [US-014 AC-2]
- [ ] Cancelling the modal discards the rectangle without any API call [US-014 AC-3]
- [ ] Submitting the manual annotation form calls `POST /drawings/{id}/symbols` with correct payload; new symbol appears on canvas [US-014 AC-4]
- [ ] New symbol received from server has `confidence: 1.0` and `source: "manual"`; canvas uses server-returned values [US-014 AC-5]
- [ ] Drag-drawn rectangles smaller than 5×5px are discarded on mouse-up with no modal [US-014 AC-6]
- [ ] On canvas load, symbols and correction history from `GET /drawings/{id}/symbols` are loaded as authoritative state [US-015 AC-1]
- [ ] Unconfirmed localStorage entries at `correction_state:{drawing_id}` are merged on load; server state (newer `created_at`) takes precedence on conflict [US-015 AC-2]
- [ ] Each correction is written to localStorage before the PATCH/POST request is dispatched [US-015 AC-3]
- [ ] Writing to localStorage checks 2MB cap; oldest unconfirmed entries evicted when cap would be exceeded [US-015 AC-4]
- [ ] Each PATCH/POST correction request body includes `training_consent` set to the value from `GET /account/consent`'s `opted_in` field [US-015 AC-5]
- [ ] Training consent display in InspectionPanel is read-only (no inline toggle) and reflects the `opted_in` value from account consent [US-015 AC-6]
- [ ] Keyboard shortcut `Escape` deselects current symbol and exits annotate mode [MANUAL]
- [ ] Keyboard shortcut `Delete`/`Backspace` rejects the selected symbol [MANUAL]
- [ ] Keyboard shortcuts `ArrowLeft`/`ArrowRight` navigate pages when `page_count > 1` and no input is focused [MANUAL]
- [ ] Keyboard shortcut `a` toggles annotate mode [MANUAL]
- [ ] P1 stub components `TableRegionLayer` and `TableCellInspectionPanel` are exported as no-op components with `// P1 STUB` comments [MANUAL]
- [ ] `PATCH /symbols/{id}` is never called on canvas open or symbol hover — only on explicit user correction action [US-012 AC-6, US-013 AC-4/5/6 — technical]
- [ ] `GET /drawings/{id}/symbols` is called with `limit=500` to minimize round trips; if `total > 500`, subsequent pages fetched before render [US-013 AC-2 — technical]
- [ ] Konva Stage uses separate layers for active symbols, rejected symbols, selection, and annotation — selection state change does not trigger repaint of symbol layers [US-013 AC-2 — technical SLA]

##### Independent Test

**Test file path** (TDD — written first, must fail before implementation): `tests/sessions/S3-D.test.tsx`

**Exact CI command**: `npm test -- tests/sessions/S3-D`

**AC → assertion mapping**:

| AC | `it(...)` block name |
|---|---|
| US-011 AC-1 | `it("renders symbol overlays when drawing state is Complete")` |
| US-011 AC-2 | `it("displays confidence score in inspection panel on symbol selection")` |
| US-011 AC-3 | `it("renders rejected symbols with dashed border and reduced opacity")` |
| US-011 AC-4 | `it("shows processing overlay when drawing state is Processing, does not render symbol overlays")` |
| US-011 AC-5 | `it("subscribes to SSE and transitions to canvas view when Complete event received")` |
| US-012 AC-1 | `it("renders each entity class bounding box with its color_hex from entity-classes API")` |
| US-012 AC-2 | `it("renders pipe, valve, and instrument bounding boxes in visibly different colors")` |
| US-012 AC-3 | `it("shows page navigation controls for multi-page drawings")` |
| US-012 AC-4 | `it("renders only symbols for the current page number")` |
| US-012 AC-5 | `it("clears selection and filters symbols when page navigation changes current page")` |
| US-012 AC-6 | `it("does not call PATCH drawings endpoint on canvas open")` |
| US-013 AC-1 | `it("opens inspection panel with symbol details and correction history on symbol click")` |
| US-013 AC-2 | `it("makes no additional API calls when inspection panel opens — all data is pre-loaded")` |
| US-013 AC-3 | `it("reclassify dropdown lists exactly 8 EntityClassId values from entity-classes endpoint")` |
| US-013 AC-4 | `it("calls PATCH symbols with reclassify correction and updates bounding box color optimistically")` |
| US-013 AC-5 | `it("calls PATCH symbols with reject correction and renders symbol as rejected optimistically")` |
| US-013 AC-6 | `it("calls PATCH symbols with restore correction and renders symbol as active optimistically")` |
| US-013 AC-7 | `it("shows Saving → Saved save indicator on successful PATCH response")` |
| US-013 AC-7 | `it("rolls back local state and shows error indicator on PATCH 500 response")` |
| US-013 AC-8 | `it("writes failed correction to localStorage on server error")` |
| US-014 AC-1 | `it("changes cursor to crosshair when annotate mode is toggled on")` |
| US-014 AC-2 | `it("shows manual annotation modal with entity class and tag_label fields after drag-draw")` |
| US-014 AC-3 | `it("discards drawn rectangle and makes no API call when annotation modal is cancelled")` |
| US-014 AC-4 | `it("calls POST drawings symbols and adds new symbol to canvas on form submit")` |
| US-014 AC-5 | `it("displays confidence 1.0 and source manual from server response on manually added symbol")` |
| US-014 AC-6 | `it("discards rectangles smaller than 5x5px on mouse-up without showing modal")` |
| US-015 AC-1 | `it("loads server symbols and corrections as authoritative state on canvas init")` |
| US-015 AC-2 | `it("merges localStorage unconfirmed corrections on load; server newer timestamp wins conflict")` |
| US-015 AC-3 | `it("writes correction to localStorage before dispatching PATCH request")` |
| US-015 AC-4 | `it("evicts oldest unconfirmed localStorage entries when 2MB cap would be exceeded")` |
| US-015 AC-5 | `it("includes training_consent from account consent endpoint in each PATCH/POST request body")` |
| US-015 AC-6 | `it("shows read-only training consent indicator in inspection panel with no inline toggle")` |
| US-012 AC-6 technical | `it("makes no PATCH request to symbols endpoint on canvas open or symbol hover")` |
| US-013 AC-2 technical | `it("fetches all symbol pages using limit=500 before rendering canvas")` |
| US-013 AC-2 SLA | `it("has no in-flight API requests when inspection panel opens after initial load completes")` |

**Fixtures / test doubles**:

```typescript
// fixtures/drawing.ts
export const mockDrawingComplete = {
  id: "drawing-uuid-1",
  owner_user_id: "user-uuid-1",
  owner_team_id: null,
  filename: "refinery-unit-4.pdf",
  revision_label: "Rev B",
  processing_state: "Complete",
  page_count: 3,
  estimated_symbol_count: 25,
  uploaded_at: "2024-06-01T09:00:00Z",
  processed_at: "2024-06-01T09:07:00Z",
  stored_file_id: "file-uuid-1",
  image_url: "https://s3.example.com/presigned/page-1.png"
};

export const mockDrawingProcessing = {
  ...mockDrawingComplete,
  processing_state: "Processing",
  processed_at: null
};

// fixtures/symbols.ts — exact shapes from Mocking contract above
export const mockSymbolsResponse: SymbolsPageResponse = { ... };
export const mockEntityClasses: EntityClass[] = [ ... ];
export const mockAccountConsent = { opted_in: true, updated_at: "2024-05-15T08:00:00Z" };

// Mocks
// - apiClient: vi.fn() — asserted on call args and return values
// - Konva Stage/Layer/Rect: mocked via jest-canvas-mock; HTMLCanvasElement.prototype.getContext returns mock
// - useSSE: vi.mock('../../../frontend/src/hooks/useSSE') — returns callback to simulate events
// - localStorageGet/localStorageSet/localStorageRemove: vi.mock('../../../frontend/src/lib/storage')
// - router: vi.mock('react-router-dom') — useParams returns { id: 'drawing-uuid-1' }
```

**Pre-conditions**:
- `jsdom` environment (vitest config)
- `jest-canvas-mock` or `vitest-canvas-mock` installed to stub `HTMLCanvasElement.getContext`
- `VITE_API_BASE_URL=http://localhost:8000` set in test environment
- `localStorage` cleared between each test via `beforeEach(() => localStorage.clear())`
- All `apiClient` calls mocked via `vi.mock` — no real network; mock responses match shapes above exactly

**Isolation rule**: All API calls are mocked via `vi.mock`. No running backend, database, or Redis instance required. The test passes when this session's PR is the only one merged — it imports only from S0-A (`types/contracts.ts`) and S1-F stubs (which are pre-existing from Phase 1) via mocked module paths.

##### Checkpoint

After this session's PR is merged, navigating to `/drawings/drawing-uuid-1/review` as an authenticated user renders the Konva canvas with color-coded bounding box overlays on the drawing image, clicking any symbol opens the inspection panel instantly (no loading spinner) with entity class, confidence, and correction history, and submitting a reclassification updates the bounding box color optimistically with a "Saved" indicator.

**Shippability claim**: this PR is independently mergeable to main even if no other session in the same wave (S3-A, S3-B, S3-C, S3-E, S3-F, S3-G, S3-H) has merged. The Review page is lazy-loaded from `router.tsx` (pre-stubbed by S0-A) and the required APIs from S2-B and S2-C are already merged (Phase 2 prerequisites).

##### Output and handoff

| Export | Kind | Shape | Consuming session(s) | Load-bearing? |
|---|---|---|---|---|
| `Review` (default export from `Review.tsx`) | React component | `() => JSX.Element` | `frontend/src/router.tsx` (S0-A, lazy import) | [LOAD-BEARING] |
| `CorrectionStore` | class/module | `{ load, applyCorrection, rollback, getSymbol, getAllForPage }` | S3-G (ExportButton may need symbol count), S4-A (E2E tests) | [LOAD-BEARING] |
| `TableRegionLayer` | React component (P1 stub) | `(props: TableRegionLayerProps) => null` | Future P1 session (US-021) | [LOAD-BEARING] |
| `TableCellInspectionPanel` | React component (P1 stub) | `(props: TableCellPanelProps) => null` | Future P1 session (US-022) | [LOAD-BEARING] |
| `LocalCorrectionEntry` | TypeScript interface | `{ symbolId: string; correctionType: CorrectionType; newClassId: EntityClassId \| null; trainingConsent: boolean; localTimestamp: string; confirmed: boolean }` | S4-A (E2E tests assert localStorage structure) | — |

---

```json
{
  "test": {
    "cmd": "npm test -- tests/sessions/S3-D",
    "file": "tests/sessions/S3-D.test.tsx"
  },
  "checkpoint": "Navigating to /drawings/{id}/review renders a Konva canvas with color-coded bounding box overlays; clicking a symbol opens the inspection panel instantly with entity class, confidence, and correction history; submitting a reclassification updates the bounding box color optimistically and shows a 'Saved' indicator.",
  "manualAcs": [
    {
      "id": "US-012-AC-6-keyboard-escape",
      "text": "Keyboard shortcut Escape deselects current symbol and exits annotate mode."
    },
    {
      "id": "US-013-AC-keyboard-delete",
      "text": "Keyboard shortcut Delete/Backspace rejects the selected symbol."
    },
    {
      "id": "US-012-AC-keyboard-arrows",
      "text": "Keyboard shortcuts ArrowLeft/ArrowRight navigate pages when page_count > 1 and no input is focused."
    },
    {
      "id": "US-014-AC-keyboard-a",
      "text": "Keyboard shortcut 'a' toggles annotate mode."
    },
    {
      "id": "US-021-P1-stub",
      "text": "P1 stub components TableRegionLayer and TableCellInspectionPanel are exported as no-op components with // P1 STUB comments."
    }
  ],
  "exports": [
    {
      "kind": "module",
      "name": "Review",
      "shape": "frontend/src/pages/Review.tsx"
    },
    {
      "kind": "module",
      "name": "CorrectionStore",
      "shape": "frontend/src/features/canvas/CorrectionStore.ts"
    },
    {
      "kind": "type",
      "name": "LocalCorrectionEntry",
      "shape": "{ symbolId: string; correctionType: CorrectionType; newClassId: EntityClassId | null; trainingConsent: boolean; localTimestamp: string; confirmed: boolean }"
    },
    {
      "kind": "function",
      "name": "TableRegionLayer",
      "shape": "(props: { drawingId: string; pageNumber: number }) => null"
    },
    {
      "kind": "function",
      "name": "TableCellInspectionPanel",
      "shape": "(props: { tableCellId: string | null; onClose: () => void }) => null"
    }
  ]
}
```