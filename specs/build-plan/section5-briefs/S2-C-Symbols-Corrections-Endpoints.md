#### S2-C — Symbols & Corrections Endpoints

**Phase 2 | Backend API | Needs: S1-A, S1-B, S1-D, S1-E**

---

##### Objective

Build the `GET /drawings/{id}/symbols`, `PATCH /symbols/{id}`, and `POST /drawings/{id}/symbols` FastAPI endpoints with their service layer, enforcing server-side training-consent snapshotting, Under\_Review state transition on first correction, and `correction_action` analytics emission — forming the core of the drawing review workflow.

---

##### Scope

**P0 MVP** — all work in this session is P0.

| Story | Scope |
|---|---|
| US-011 (partial) | GET /drawings/{id}/symbols — serve symbols + corrections co-loaded |
| US-012 (partial) | Under\_Review state transition triggered by first correction action |
| US-013 | PATCH /symbols/{id} — reclassify, reject, restore (undo rejection) |
| US-014 | POST /drawings/{id}/symbols — manual annotation |
| US-015 | Server-side training\_consent snapshot; team-level consent resolution |
| US-010 (partial) | Fire `correction_action` analytics event on persistence |

**P1 stubs required:**
- Table-cell correction path in `correction_service.py`: stub with `# P1-STUB: table_cell corrections — US-022` comment and raise `NotImplementedError("P1: table_cell_id corrections not yet implemented")` guarded by `if payload.table_cell_id is not None`.
- `GET /drawings/{id}/tables` and `PATCH /table-cells/{id}` are **not** owned by this session and must not be implemented here.

---

##### Technology constraints

Per §1.8 — Technology Stack (non-negotiable):

| Layer | Selected Technology |
|---|---|
| **API Server** | FastAPI (Python) |
| **Database** | PostgreSQL via SQLAlchemy ORM + Alembic migrations |
| **Schema validation** | Pydantic v2 |
| **Connection pooling** | PgBouncer (via `DATABASE_URL` from environment) |
| **Cache / Pub-Sub** | Redis (ElastiCache) via `backend/app/redis/client.py` (S1-D) |
| **Analytics** | PostHog via `backend/app/analytics/events.py` (S1-E) |

**Must NOT use:**
- No `asyncpg` raw queries for correction atomicity — use SQLAlchemy sessions with explicit `db.begin()` blocks for transaction control.
- No in-process thread pools or `concurrent.futures` — all DB operations synchronous within request/Celery-task context.
- No client-supplied `training_consent` field accepted in any request body — this field is derived server-side exclusively.
- No import from `backend/app/services/drawing_state_machine.py` (owned by S2-B, not a prerequisite) — implement the Under\_Review conditional UPDATE inline in `correction_service.py`.
- No import from `backend/app/services/consent_service.py` (owned by S2-F, not a prerequisite) — implement consent resolution inline in `correction_service.py`.

---

##### Performance targets

| Metric | Target | Type | Owner |
|---|---|---|---|
| `GET /drawings/{id}/symbols` response (canvas load) | <3s P95 | Monitoring target | This session (co-loads corrections in same response) |
| Symbol panel open after canvas load | <200ms P95 | **Hard SLA (NFR-19)** | Upstream React SPA (S3-D) — enabled by this session pre-loading `corrections_by_symbol_id` in the GET response; **no additional network fetch must be needed when user opens an inspection panel** |
| Symbols pagination | 200 default / 500 max per page | Hard constraint | This session — enforced server-side |

From §1.9:
> "Canvas load (symbol fetch): <3s P95 — FastAPI `GET /drawings/{id}/symbols` + PostgreSQL JSONB bbox storage; correction history co-loaded in same response"

> "Canvas interaction (symbol select + panel open): <200ms P95 — React SPA; correction history pre-loaded at canvas init — no additional network fetch on panel open"

> "Symbol pagination default / max: 200 default / 500 max per page — Hard constraint — `GET /drawings/{id}/symbols`"

---

##### Owned files

```
backend/app/api/routers/symbols.py
backend/app/services/symbol_service.py
backend/app/services/correction_service.py
tests/integration/test_symbols_api.py
```

All Pydantic request/response schemas specific to this session are defined within `symbols.py` (router file). No new schema module is created — load-bearing shared types are already in `backend/app/schemas/contracts.py` (S0-A).

---

##### Read-only imports

| Session | File | Named exports required |
|---|---|---|
| S0-A | `backend/app/schemas/contracts.py` | `SymbolsPageResponse`, `SymbolRecord`, `CorrectionRecord`, `BoundingBox`, `EntityClassId`, `CorrectionType`, `SymbolSource` |
| S0-A | `backend/app/db/session.py` | `get_db` (FastAPI dependency) |
| S1-A | `backend/app/db/models/detected_symbol.py` | `DetectedSymbol` |
| S1-A | `backend/app/db/models/user_correction.py` | `UserCorrection` |
| S1-A | `backend/app/db/models/drawing.py` | `Drawing` |
| S1-A | `backend/app/db/models/ml_training_consent.py` | `MLTrainingConsent` |
| S1-A | `backend/app/db/models/entity_class.py` | `EntityClass` |
| S1-B | `backend/app/auth/dependencies.py` | `get_current_user`, `CurrentUser` |
| S1-B | `backend/app/auth/permissions.py` | `assert_drawing_access` (raises `HTTPException(403)` if user has no access to the drawing) |
| S1-E | `backend/app/analytics/events.py` | `emit_correction_action` |

---

##### Do not touch

- `backend/app/main.py` — pre-stubbed by S0-A; router inclusion already wired
- `backend/app/api/routers/__init__.py` — owned by S0-A
- `backend/app/api/routers/_stubs.py` — owned by S0-A (stub placeholder replaced by real router in this session)
- `backend/app/schemas/contracts.py` — owned by S0-A
- `backend/app/db/session.py` — owned by S0-A
- `backend/app/db/base.py` — owned by S0-A
- `backend/app/config.py` — owned by S0-A
- `backend/app/workers/celery_app.py` — owned by S0-A
- All S1-A model files (`backend/app/db/models/*.py`)
- All S1-B auth files (`backend/app/auth/*.py`)
- All S1-D Redis files (`backend/app/redis/*.py`)
- All S1-E analytics files (`backend/app/analytics/*.py`)
- `backend/app/services/drawing_state_machine.py` — owned by S2-B (do not create or import)
- `backend/app/services/drawing_service.py` — owned by S2-B
- `backend/app/services/hash_check_service.py` — owned by S2-B
- `backend/app/services/upload_complete_service.py` — owned by S2-B
- `backend/app/services/free_tier_counter.py` — owned by S2-B
- `backend/app/sse/drawing_status.py` — owned by S2-B
- `backend/app/services/consent_service.py` — owned by S2-F (do not create or import)
- `backend/app/services/account_service.py` — owned by S2-F
- `backend/app/services/gdpr_init_service.py` — owned by S2-F
- `backend/app/api/routers/drawings.py` — owned by S2-B
- `backend/app/api/routers/account.py` — owned by S2-F
- `backend/app/api/routers/exports.py` — owned by S2-D
- `backend/app/api/routers/subscription.py` — owned by S2-E
- `backend/app/api/routers/stripe_webhook.py` — owned by S2-E
- `backend/app/api/routers/entity_classes.py` — owned by S2-G
- All worker files under `backend/app/workers/`

---

##### Architecture context

From **§1.1 Shared Contracts** (verbatim):

```typescript
// Symbols API Response (GET /drawings/{id}/symbols)
interface SymbolsPageResponse {
  symbols: SymbolRecord[];
  corrections_by_symbol_id: Record<string, CorrectionRecord[]>;
  total: number;
  limit: number;
  offset: number;
}

interface SymbolRecord {
  id: string;
  drawing_id: string;
  entity_class_id: EntityClassId;
  subtype: string;
  tag_label: string | null;
  confidence: number;
  bbox: BoundingBox;
  source: SymbolSource;
  rejected: boolean;
  page_number: number;
}

interface CorrectionRecord {
  id: string;
  detected_symbol_id: string | null;
  table_cell_id: string | null;
  user_id: string;
  correction_type: CorrectionType;
  new_class_id: EntityClassId | null;
  training_consent: boolean;
  created_at: string;
}

interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

// Symbol Source
type SymbolSource = 'ml' | 'manual';

// Correction Type
type CorrectionType = 'reclassify' | 'reject' | 'restore' | 'manual_add';

// Entity Classes (from FR-2 AC-2)
type EntityClassId =
  | 'pipe'
  | 'valve_gate'
  | 'valve_globe'
  | 'valve_ball'
  | 'valve_butterfly'
  | 'valve_check'
  | 'valve_control'
  | 'instrument';
```

From **§1.2 Database Schema** (verbatim):

```sql
-- DETECTED_SYMBOL
CREATE TABLE detected_symbol (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  drawing_id      UUID NOT NULL REFERENCES drawing(id) ON DELETE CASCADE,
  entity_class_id VARCHAR NOT NULL REFERENCES entity_class(id),
  subtype         VARCHAR,
  tag_label       VARCHAR,
  confidence      FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  bbox            JSONB NOT NULL,
  source          VARCHAR NOT NULL CHECK (source IN ('ml','manual')),
  rejected        BOOLEAN NOT NULL DEFAULT FALSE,
  page_number     INTEGER NOT NULL
);

CREATE INDEX idx_detected_symbol_drawing_rejected_class ON detected_symbol(drawing_id, rejected, entity_class_id);
CREATE INDEX idx_detected_symbol_drawing_page ON detected_symbol(drawing_id, page_number);

-- USER_CORRECTION
CREATE TABLE user_correction (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  detected_symbol_id  UUID REFERENCES detected_symbol(id),
  table_cell_id       UUID REFERENCES table_cell(id),
  user_id             UUID NOT NULL REFERENCES "user"(id),
  correction_type     VARCHAR NOT NULL CHECK (correction_type IN ('reclassify','reject','restore','manual_add')),
  new_class_id        VARCHAR REFERENCES entity_class(id),
  training_consent    BOOLEAN NOT NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT correction_symbol_or_cell CHECK (
    (detected_symbol_id IS NOT NULL AND table_cell_id IS NULL) OR
    (detected_symbol_id IS NULL AND table_cell_id IS NOT NULL)
  )
);

-- ML_TRAINING_CONSENT
CREATE TABLE ml_training_consent (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES "user"(id),
  team_id     UUID REFERENCES team(id),
  opted_in    BOOLEAN NOT NULL DEFAULT FALSE,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT consent_user_or_team CHECK (
    (user_id IS NOT NULL AND team_id IS NULL) OR
    (user_id IS NULL AND team_id IS NOT NULL)
  )
);
```

From **§1.3 State Machines and Permission Matrices** (verbatim):

```typescript
// Drawing Processing State Transitions
const DRAWING_STATE_TRANSITIONS: Record<DrawingProcessingState, DrawingProcessingState[]> = {
  Complete:     ['Under_Review', 'Queued'],     // → Under_Review on first correction action; → Queued on retry (shouldn't occur)
  Under_Review: ['Queued'],                     // → Queued on retry (edge case)
  ...
} as const;

// Under_Review trigger: first user correction action (reclassify, reject, manual_add) — NOT canvas open
// Retry: re-uses existing StoredFile; no new file written to S3
```

```typescript
// Role-Permission Matrix
const ROLE_PERMISSIONS = {
  user: {
    symbol_correct: 'own',     // own drawings only
  },
  team_member: {
    symbol_correct: 'team',    // all team drawings
  },
  team_admin: {
    symbol_correct: 'team',    // all team drawings
  },
} as const;
```

From **§1.4 Critical Ordering Rules** (verbatim):

> **Rule 6 — training\_consent snapshotted at correction creation time.** "Each correction save sends... the resolved `training_consent` value... at time of creation; the consent value must be snapshotted at correction time, not resolved lazily."

> **Rule 7 — Team-level consent evaluated server-side.** "Team-level consent resolution must be evaluated server-side to prevent client-side bypass; the resolved value is not a client-supplied field."

> **Rule 13 — Under\_Review transition triggered by first correction action, not canvas open.** "The drawing transitions from `Complete` to `Under_Review` on the user's first correction action (e.g., accepting, rejecting, or editing a detected symbol), not on canvas open."

From **§1.5 HTTP Status Code Contracts** (verbatim):

| Condition | Required code | Must never return |
|---|---|---|
| Unauthenticated request to protected endpoint | `401` | `403`, `200` |
| Authenticated user accessing resource they do not own | `403` | `404`, `200` |

From **§1.9 Performance Targets** (verbatim):

> "Canvas load (symbol fetch): <3s P95 — FastAPI `GET /drawings/{id}/symbols` + PostgreSQL JSONB bbox storage; correction history co-loaded in same response"

> "Canvas interaction (symbol select + panel open): <200ms P95 — React SPA; correction history pre-loaded at canvas init — no additional network fetch on panel open"

> "Symbol pagination default / max: 200 default / 500 max per page — Hard constraint — `GET /drawings/{id}/symbols`"

From **§1.10 Analytics Event Contracts** (verbatim):

| Event Name | Payload Shape | Code Surface That Fires It | Trigger Condition |
|---|---|---|---|
| `correction_action` | `{ event: 'correction_action', timestamp: string (UTC ISO8601), user_id: string, drawing_id: string, symbol_id: string }` | FastAPI — `PATCH /symbols/{id}` and `POST /drawings/{id}/symbols` handlers | User submits a reclassify, reject, restore, or manual\_add correction |

> "Must fire server-side on persistence"

From **§1.6 Route Manifest** (verbatim):

```
GET    /drawings/{id}/symbols
PATCH  /symbols/{id}
POST   /drawings/{id}/symbols
```

P1 only (not in this session):
```
GET    /drawings/{id}/tables
PATCH  /table-cells/{id}
```

---

##### User stories and acceptance criteria

The following user stories are derived from the P0 scope declarations in **§1.13 Feature Scope**, cross-referenced with schema, state machine, and API contracts throughout the specification.

---

**US-011 (partial) — Detection results with confidence scores**

> As a reviewer, I want to see all ML-detected symbols for a drawing with their confidence scores so that I can identify which detections need review.

- **AC-1:** `GET /drawings/{id}/symbols` returns HTTP 200 with a `SymbolsPageResponse` body containing all detected symbols for the drawing, each with a `confidence` value between 0.0 and 1.0.
- **AC-2:** The response `corrections_by_symbol_id` map contains all `UserCorrection` records keyed by `detected_symbol_id` for every symbol in the current page. No separate correction-fetch request is needed.
- **AC-3:** Pagination: `limit` defaults to 200 and is capped server-side at 500; `offset` defaults to 0. Requests with `limit > 500` receive HTTP 422.
- **AC-4:** Optional query param `page_number` (integer ≥ 1) filters symbols to a specific PDF/drawing page.
- **AC-5:** Optional query param `entity_class_id` filters symbols by class.
- **AC-6:** Optional query param `rejected` (boolean) filters symbols by rejection state.
- **AC-7:** The `total` field reflects the count of all symbols matching the applied filters (not just the current page).
- **AC-8:** An unauthenticated request returns HTTP 401.
- **AC-9:** An authenticated user requesting symbols for a drawing they do not own (and are not a team member of) receives HTTP 403.
- **AC-10:** Requesting symbols for a non-existent `drawing_id` returns HTTP 404.

---

**US-012 (partial) — Under\_Review state transition on first correction**

> As a system, I want the drawing to transition from `Complete` to `Under_Review` the moment a user submits their first correction, so that the review state is accurately tracked.

- **AC-1:** When `PATCH /symbols/{id}` or `POST /drawings/{id}/symbols` is called and the drawing's current `processing_state` is `Complete`, the drawing is atomically transitioned to `Under_Review` within the same DB transaction as the correction creation.
- **AC-2:** If the drawing is already `Under_Review` when a correction is submitted, the state remains `Under_Review` (no error — correction is still persisted).
- **AC-3:** `GET /drawings/{id}/symbols` (canvas load) does **not** trigger the `Under_Review` transition.
- **AC-4:** The transition is a conditional UPDATE (`WHERE processing_state = 'Complete'`) — concurrent corrections do not produce a constraint violation or duplicate transition.

---

**US-013 — Reclassify, reject, and restore symbols**

> As a reviewer, I want to reclassify a symbol to a different entity class, reject a false positive, or undo a rejection, so that I can correct ML detection errors.

- **AC-1:** `PATCH /symbols/{id}` with `correction_type = 'reclassify'` and a valid `new_class_id` creates a `UserCorrection` record with `correction_type = 'reclassify'` and updates `detected_symbol.entity_class_id` to `new_class_id`, all in a single transaction.
- **AC-2:** `PATCH /symbols/{id}` with `correction_type = 'reject'` creates a `UserCorrection` record and sets `detected_symbol.rejected = true`.
- **AC-3:** `PATCH /symbols/{id}` with `correction_type = 'restore'` creates a `UserCorrection` record and sets `detected_symbol.rejected = false`.
- **AC-4:** `PATCH /symbols/{id}` with `correction_type = 'reclassify'` but no `new_class_id` returns HTTP 422 with a validation error.
- **AC-5:** `PATCH /symbols/{id}` with `correction_type = 'reclassify'` and a `new_class_id` not in the predefined `EntityClassId` enum returns HTTP 422.
- **AC-6:** `PATCH /symbols/{id}` with `correction_type = 'manual_add'` returns HTTP 422 (manual\_add is only valid via `POST /drawings/{id}/symbols`).
- **AC-7:** A successful `PATCH` returns HTTP 200 with the updated `SymbolRecord` in the response body.
- **AC-8:** `PATCH /symbols/{id}` on a symbol that does not exist returns HTTP 404.
- **AC-9:** `PATCH /symbols/{id}` on a symbol belonging to a drawing the authenticated user has no access to returns HTTP 403.
- **AC-10:** An unauthenticated `PATCH /symbols/{id}` returns HTTP 401.

---

**US-014 — Manual annotation**

> As a reviewer, I want to draw a bounding box on the canvas and assign an entity class to add a symbol that the ML model missed.

- **AC-1:** `POST /drawings/{id}/symbols` creates a new `DetectedSymbol` row with `source = 'manual'`, `confidence = 1.0`, and the provided `entity_class_id`, `subtype`, `bbox`, and `page_number`.
- **AC-2:** A `UserCorrection` row with `correction_type = 'manual_add'` and `detected_symbol_id` pointing to the newly created symbol is created in the same transaction.
- **AC-3:** `tag_label` is optional — if absent, `detected_symbol.tag_label` is stored as `NULL`.
- **AC-4:** `page_number` must be a positive integer ≥ 1; missing or ≤ 0 returns HTTP 422.
- **AC-5:** `entity_class_id` must be a valid `EntityClassId` value; invalid values return HTTP 422.
- **AC-6:** `bbox` fields (`x`, `y`, `w`, `h`) must all be present and numeric; missing or non-numeric values return HTTP 422.
- **AC-7:** A successful `POST` returns HTTP 201 with the created `SymbolRecord` in the response body.
- **AC-8:** `POST /drawings/{id}/symbols` on a non-existent drawing returns HTTP 404.
- **AC-9:** `POST /drawings/{id}/symbols` on a drawing the authenticated user has no access to returns HTTP 403.
- **AC-10:** An unauthenticated `POST /drawings/{id}/symbols` returns HTTP 401.

---

**US-015 — Server-side training consent snapshot**

> As the system, I want the training consent value to be permanently snapshotted into each correction record at creation time so that later consent changes do not retroactively affect submitted data.

- **AC-1:** Every `UserCorrection` record stored has a non-null `training_consent` boolean that was evaluated server-side at the moment of creation; it is never supplied by the client.
- **AC-2:** The consent resolution logic is: if the drawing belongs to a team, query `ml_training_consent` for `team_id` and use `opted_in`; otherwise query for `user_id` and use `opted_in`. If no consent record exists for either, default to `opted_in = False`.
- **AC-3:** A client request body that includes a `training_consent` field is ignored (the field is silently stripped from input or Pydantic model forbids extra fields).
- **AC-4:** The `training_consent` value snapshotted in `user_correction` is not changed if the user subsequently updates their consent preference.

---

**US-010 (partial) — correction\_action analytics event**

> As the system, I want a `correction_action` event emitted to PostHog every time a correction is persisted so that review activity can be tracked.

- **AC-1:** A `correction_action` event is emitted (non-blocking, after DB commit) on every successful `PATCH /symbols/{id}` call.
- **AC-2:** A `correction_action` event is emitted (non-blocking, after DB commit) on every successful `POST /drawings/{id}/symbols` call.
- **AC-3:** The event payload includes `{ event: 'correction_action', timestamp: <UTC ISO8601>, user_id: <str>, drawing_id: <str>, symbol_id: <str> }` where `symbol_id` is the `detected_symbol.id` that was created or mutated.
- **AC-4:** Analytics failure (PostHog unreachable) does not cause the API response to fail or change status code.
- **AC-5:** The `correction_action` event is never emitted from the browser client — it is emitted exclusively server-side on DB persistence.

---

##### UX and design specification

N/A — this is a backend-only session. No frontend component.

---

##### Critical implementation notes

**Ordering rules that apply:**

- **Rule 6 (verbatim):** "the consent value must be snapshotted at correction time, not resolved lazily." The `training_consent` boolean must be computed and stored within the same transaction as the `UserCorrection` insert. Never query consent after the transaction or at read time.

- **Rule 7 (verbatim):** "Team-level consent resolution must be evaluated server-side to prevent client-side bypass; the resolved value is not a client-supplied field." All Pydantic request models must use `model_config = ConfigDict(extra='ignore')` (or equivalent) so a client-supplied `training_consent` is silently discarded, not stored.

- **Rule 13 (verbatim):** "The drawing transitions from `Complete` to `Under_Review` on the user's first correction action (e.g., accepting, rejecting, or editing a detected symbol), not on canvas open." The `GET /drawings/{id}/symbols` endpoint must perform **no** state mutation.

**HTTP status code contracts:**

- `GET /drawings/{id}/symbols` unauthenticated → `401` (must not return `403` or `200`)
- `GET /drawings/{id}/symbols` authenticated but no drawing access → `403` (must not return `404`)
- `GET /drawings/{id}/symbols` authenticated, drawing not found → `404`
- `PATCH /symbols/{id}` — symbol not found → `404`; no access → `403`; unauthenticated → `401`; invalid body → `422`
- `PATCH /symbols/{id}` success → `200`
- `POST /drawings/{id}/symbols` success → `201` (must not return `200`)
- `POST /drawings/{id}/symbols` drawing not found → `404`; no access → `403`; unauthenticated → `401`

**Atomicity requirements:**

- `PATCH /symbols/{id}` (reclassify): `UPDATE detected_symbol` + `INSERT user_correction` + conditional `UPDATE drawing SET processing_state = 'Under_Review' WHERE processing_state = 'Complete'` — all three in one transaction.
- `PATCH /symbols/{id}` (reject/restore): `UPDATE detected_symbol.rejected` + `INSERT user_correction` + conditional drawing state UPDATE — all in one transaction.
- `POST /drawings/{id}/symbols`: `INSERT detected_symbol` + `INSERT user_correction` + conditional drawing state UPDATE — all in one transaction.
- Analytics event emission via `emit_correction_action` occurs **after** the transaction commits — never inside the transaction.

**Cross-session contracts:**

- **S3-D (Frontend: Review Canvas)** depends on `corrections_by_symbol_id` being fully populated for all symbols on the current page in a single `GET /drawings/{id}/symbols` response — enabling the <200ms hard SLA for panel open. Never return an empty map and require a second fetch.
- **S1-E analytics contract:** `emit_correction_action` must be called with `symbol_id` = the `detected_symbol.id` that was acted upon (the newly created ID for `manual_add`). The payload shape must match `§1.10` exactly.
- **S1-B permissions contract:** use `assert_drawing_access(user, drawing, db)` from `backend/app/auth/permissions.py` — do not reimplement ownership/team-membership logic in this session.

**Silent failure modes (things that will appear to work but produce wrong behavior if done incorrectly):**

1. **Lazy consent resolution**: if `training_consent` is resolved by querying `ml_training_consent` outside the transaction (e.g., in a `background_task`), the stored value may differ from the user's actual consent at the correction moment. Always resolve within the transaction.
2. **Under\_Review transition as a separate call**: if the drawing state transition is performed in a second DB call after the correction is committed, a server crash between the two leaves the drawing in `Complete` with corrections present. Must be in the same transaction.
3. **`corrections_by_symbol_id` N+1 queries**: fetching corrections per-symbol in a loop will cause >200ms response times at 200 symbols. Use a single `WHERE detected_symbol_id = ANY(:ids)` query after fetching the symbol page.
4. **Returning 404 instead of 403 for access-denied symbols**: the spec states authenticated users accessing resources they do not own must get `403`, never `404` — do not use a single ORM query that implicitly filters by ownership (which would make the record appear not-found).
5. **`manual_add` accepted in PATCH**: `correction_type = 'manual_add'` in a PATCH request body must return `422`, not create a new symbol — silently accepting it would create orphaned corrections.
6. **Analytics event inside transaction**: if `emit_correction_action` is called before `db.commit()`, a subsequent rollback would fire the event for a correction that was never persisted.

**Explicitly avoided approaches:**

- Do not call `backend/app/services/drawing_state_machine.py` — this file is owned by S2-B and is not importable from this session. Implement the `Under_Review` conditional UPDATE inline using: `db.execute(update(Drawing).where(Drawing.id == drawing_id, Drawing.processing_state == 'Complete').values(processing_state='Under_Review'))`.
- Do not call `backend/app/services/consent_service.py` — owned by S2-F. Implement consent resolution inline in `correction_service.py`.
- Do not accept `limit > 500` — enforce at the FastAPI Query parameter level with `le=500`.

---

##### Mocking contract

This is a backend session. Internal event/service interfaces this session depends on from prerequisite sessions:

**From S1-A (DB Models):**

```python
# DetectedSymbol model — expected columns accessible as attributes:
# .id: UUID, .drawing_id: UUID, .entity_class_id: str,
# .subtype: str|None, .tag_label: str|None, .confidence: float,
# .bbox: dict (JSONB), .source: str ('ml'|'manual'),
# .rejected: bool, .page_number: int

# UserCorrection model:
# .id: UUID, .detected_symbol_id: UUID|None, .table_cell_id: UUID|None,
# .user_id: UUID, .correction_type: str, .new_class_id: str|None,
# .training_consent: bool, .created_at: datetime

# Drawing model:
# .id: UUID, .owner_user_id: UUID|None, .owner_team_id: UUID|None,
# .processing_state: str

# MLTrainingConsent model:
# .user_id: UUID|None, .team_id: UUID|None, .opted_in: bool
```

**From S1-B (Auth Dependencies):**

```python
# get_current_user: FastAPI Depends -> CurrentUser
# CurrentUser shape: { id: UUID, email: str, role: str, team_id: UUID|None }

# assert_drawing_access(user: CurrentUser, drawing: Drawing, db: Session) -> None
# Raises HTTPException(403) if user does not own the drawing
# and is not a member of the drawing's owner team
```

**From S1-E (Analytics):**

```python
# emit_correction_action(
#   user_id: str,
#   drawing_id: str,
#   symbol_id: str
# ) -> None
# Non-blocking. Payload: {
#   event: 'correction_action',
#   timestamp: str,   # UTC ISO8601
#   user_id: str,
#   drawing_id: str,
#   symbol_id: str
# }
# Failure is swallowed internally — never raises to caller.
```

**From S0-A (Session):**

```python
# get_db: FastAPI Depends -> Generator[Session, None, None]
# Yields a SQLAlchemy Session. Caller must manage commit/rollback.
```

---

##### Acceptance criteria checklist

- [ ] `GET /drawings/{id}/symbols` returns HTTP 200 with valid `SymbolsPageResponse` body [US-011 AC-1]
- [ ] Response `corrections_by_symbol_id` is populated for all symbols on the current page [US-011 AC-2]
- [ ] `limit` defaults to 200 and is capped at 500; requests with `limit > 500` return HTTP 422 [US-011 AC-3]
- [ ] `page_number` query param filters symbols to the specified page [US-011 AC-4]
- [ ] `entity_class_id` query param filters symbols by class [US-011 AC-5]
- [ ] `rejected` query param filters symbols by rejection state [US-011 AC-6]
- [ ] `total` reflects count of all symbols matching applied filters [US-011 AC-7]
- [ ] Unauthenticated `GET /drawings/{id}/symbols` returns HTTP 401 [US-011 AC-8]
- [ ] Authenticated user with no drawing access on `GET /drawings/{id}/symbols` returns HTTP 403 [US-011 AC-9]
- [ ] `GET /drawings/{id}/symbols` for non-existent drawing\_id returns HTTP 404 [US-011 AC-10]
- [ ] First correction on a `Complete` drawing transitions it to `Under_Review` atomically in the same transaction [US-012 AC-1]
- [ ] Correction on an already `Under_Review` drawing succeeds without error [US-012 AC-2]
- [ ] `GET /drawings/{id}/symbols` does NOT transition drawing to `Under_Review` [US-012 AC-3]
- [ ] Concurrent corrections do not cause constraint violations on the state transition [US-012 AC-4]
- [ ] `PATCH /symbols/{id}` with `reclassify` creates `UserCorrection` and updates `entity_class_id` [US-013 AC-1]
- [ ] `PATCH /symbols/{id}` with `reject` creates `UserCorrection` and sets `rejected = true` [US-013 AC-2]
- [ ] `PATCH /symbols/{id}` with `restore` creates `UserCorrection` and sets `rejected = false` [US-013 AC-3]
- [ ] `PATCH /symbols/{id}` with `reclassify` but no `new_class_id` returns HTTP 422 [US-013 AC-4]
- [ ] `PATCH /symbols/{id}` with `reclassify` and invalid `new_class_id` returns HTTP 422 [US-013 AC-5]
- [ ] `PATCH /symbols/{id}` with `correction_type = 'manual_add'` returns HTTP 422 [US-013 AC-6]
- [ ] Successful `PATCH /symbols/{id}` returns HTTP 200 with updated `SymbolRecord` [US-013 AC-7]
- [ ] `PATCH /symbols/{id}` on non-existent symbol returns HTTP 404 [US-013 AC-8]
- [ ] `PATCH /symbols/{id}` on drawing user has no access to returns HTTP 403 [US-013 AC-9]
- [ ] Unauthenticated `PATCH /symbols/{id}` returns HTTP 401 [US-013 AC-10]
- [ ] `POST /drawings/{id}/symbols` creates `DetectedSymbol` with `source='manual'`, `confidence=1.0` [US-014 AC-1]
- [ ] `POST /drawings/{id}/symbols` creates `UserCorrection` with `correction_type='manual_add'` linked to new symbol [US-014 AC-2]
- [ ] `tag_label` is optional in `POST /drawings/{id}/symbols`; null stored when absent [US-014 AC-3]
- [ ] `page_number ≤ 0` or absent in `POST /drawings/{id}/symbols` returns HTTP 422 [US-014 AC-4]
- [ ] Invalid `entity_class_id` in `POST /drawings/{id}/symbols` returns HTTP 422 [US-014 AC-5]
- [ ] Incomplete `bbox` (missing x/y/w/h) in `POST /drawings/{id}/symbols` returns HTTP 422 [US-014 AC-6]
- [ ] Successful `POST /drawings/{id}/symbols` returns HTTP 201 with created `SymbolRecord` [US-014 AC-7]
- [ ] `POST /drawings/{id}/symbols` for non-existent drawing returns HTTP 404 [US-014 AC-8]
- [ ] `POST /drawings/{id}/symbols` on drawing user has no access to returns HTTP 403 [US-014 AC-9]
- [ ] Unauthenticated `POST /drawings/{id}/symbols` returns HTTP 401 [US-014 AC-10]
- [ ] `training_consent` in stored `UserCorrection` matches the user's (or team's) consent record at correction creation time [US-015 AC-1]
- [ ] If drawing belongs to a team, consent is resolved from `ml_training_consent.team_id`; otherwise from `ml_training_consent.user_id` [US-015 AC-2]
- [ ] Client-supplied `training_consent` in request body is silently ignored; server-derived value is used [US-015 AC-3]
- [ ] Stored `training_consent` is not retroactively updated when user changes their consent preference post-correction [US-015 AC-4]
- [ ] `correction_action` analytics event is emitted after DB commit on successful `PATCH /symbols/{id}` [US-010 AC-1]
- [ ] `correction_action` analytics event is emitted after DB commit on successful `POST /drawings/{id}/symbols` [US-010 AC-2]
- [ ] `correction_action` event payload matches `{ event, timestamp, user_id, drawing_id, symbol_id }` shape from §1.10 [US-010 AC-3]
- [ ] Analytics failure does not alter HTTP response status code or body [US-010 AC-4]
- [ ] `corrections_by_symbol_id` is populated using two queries (symbols page + batch correction fetch), not N+1 queries [technical AC — NFR-19 pre-condition]
- [ ] All three DB operations in a correction (symbol update + correction insert + state transition) are in a single transaction [technical AC — atomicity]

---

##### Independent Test

**Test file path** (TDD — written first, must fail before implementation):
`tests/sessions/test_s2c.py`

**Exact CI command:**
```bash
pytest tests/sessions/test_s2c.py -v
```

**AC → assertion mapping:**

| AC | `it(...)` / `test(...)` block name |
|---|---|
| US-011 AC-1 | `test_list_symbols_returns_200_with_symbol_records` |
| US-011 AC-2 | `test_list_symbols_corrections_by_symbol_id_populated` |
| US-011 AC-3 | `test_list_symbols_limit_default_200_cap_500` |
| US-011 AC-4 | `test_list_symbols_page_number_filter` |
| US-011 AC-5 | `test_list_symbols_entity_class_filter` |
| US-011 AC-6 | `test_list_symbols_rejected_filter` |
| US-011 AC-7 | `test_list_symbols_total_reflects_filter` |
| US-011 AC-8 | `test_list_symbols_unauthenticated_returns_401` |
| US-011 AC-9 | `test_list_symbols_wrong_owner_returns_403` |
| US-011 AC-10 | `test_list_symbols_drawing_not_found_returns_404` |
| US-012 AC-1 | `test_first_correction_transitions_drawing_to_under_review` |
| US-012 AC-2 | `test_correction_on_under_review_drawing_succeeds` |
| US-012 AC-3 | `test_get_symbols_does_not_trigger_under_review` |
| US-012 AC-4 | `test_concurrent_corrections_no_constraint_violation` |
| US-013 AC-1 | `test_patch_reclassify_creates_correction_and_updates_class` |
| US-013 AC-2 | `test_patch_reject_sets_rejected_true` |
| US-013 AC-3 | `test_patch_restore_sets_rejected_false` |
| US-013 AC-4 | `test_patch_reclassify_without_new_class_id_returns_422` |
| US-013 AC-5 | `test_patch_reclassify_invalid_class_id_returns_422` |
| US-013 AC-6 | `test_patch_manual_add_correction_type_returns_422` |
| US-013 AC-7 | `test_patch_symbol_success_returns_200_with_symbol_record` |
| US-013 AC-8 | `test_patch_symbol_not_found_returns_404` |
| US-013 AC-9 | `test_patch_symbol_wrong_owner_returns_403` |
| US-013 AC-10 | `test_patch_symbol_unauthenticated_returns_401` |
| US-014 AC-1 | `test_post_symbol_creates_manual_with_source_and_confidence` |
| US-014 AC-2 | `test_post_symbol_creates_manual_add_correction_record` |
| US-014 AC-3 | `test_post_symbol_tag_label_optional_stored_null` |
| US-014 AC-4 | `test_post_symbol_invalid_page_number_returns_422` |
| US-014 AC-5 | `test_post_symbol_invalid_entity_class_returns_422` |
| US-014 AC-6 | `test_post_symbol_incomplete_bbox_returns_422` |
| US-014 AC-7 | `test_post_symbol_success_returns_201` |
| US-014 AC-8 | `test_post_symbol_drawing_not_found_returns_404` |
| US-014 AC-9 | `test_post_symbol_wrong_owner_returns_403` |
| US-014 AC-10 | `test_post_symbol_unauthenticated_returns_401` |
| US-015 AC-1 | `test_correction_snapshots_training_consent_at_creation` |
| US-015 AC-2 | `test_correction_team_consent_resolved_from_team_record` |
| US-015 AC-3 | `test_correction_client_supplied_training_consent_ignored` |
| US-015 AC-4 | `test_correction_consent_not_updated_on_later_consent_change` |
| US-010 AC-1 | `test_patch_symbol_emits_correction_action_event` |
| US-010 AC-2 | `test_post_symbol_emits_correction_action_event` |
| US-010 AC-3 | `test_correction_action_event_payload_shape` |
| US-010 AC-4 | `test_analytics_failure_does_not_fail_response` |
| Technical AC — N+1 | `test_list_symbols_uses_batch_correction_query_not_n_plus_1` |
| Technical AC — atomicity | `test_correction_creates_symbol_update_correction_state_in_one_transaction` |

**Fixtures / test doubles:**

```python
# conftest.py for tests/sessions/test_s2c.py

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

# -- In-memory SQLite for model structure tests (or PostgreSQL test DB)
# The test uses a real PostgreSQL DB for transaction atomicity tests
# (per pre-conditions below). For unit-level tests, mock get_db.

@pytest.fixture
def mock_db():
    """SQLAlchemy session mock for unit tests that don't need real DB."""
    session = MagicMock()
    session.__enter__ = lambda s: s
    session.__exit__ = MagicMock(return_value=False)
    return session

@pytest.fixture
def current_user_owner():
    return {
        "id": str(uuid.uuid4()),
        "email": "owner@example.com",
        "role": "user",
        "team_id": None,
    }

@pytest.fixture
def current_user_other():
    return {
        "id": str(uuid.uuid4()),
        "email": "other@example.com",
        "role": "user",
        "team_id": None,
    }

@pytest.fixture
def sample_drawing(current_user_owner):
    return {
        "id": str(uuid.uuid4()),
        "owner_user_id": current_user_owner["id"],
        "owner_team_id": None,
        "processing_state": "Complete",
        "filename": "test.pdf",
    }

@pytest.fixture
def sample_symbol(sample_drawing):
    return {
        "id": str(uuid.uuid4()),
        "drawing_id": sample_drawing["id"],
        "entity_class_id": "valve_gate",
        "subtype": "gate",
        "tag_label": "V-101",
        "confidence": 0.92,
        "bbox": {"x": 10.0, "y": 20.0, "w": 5.0, "h": 5.0},
        "source": "ml",
        "rejected": False,
        "page_number": 1,
    }

@pytest.fixture
def sample_correction(sample_symbol, current_user_owner):
    return {
        "id": str(uuid.uuid4()),
        "detected_symbol_id": sample_symbol["id"],
        "table_cell_id": None,
        "user_id": current_user_owner["id"],
        "correction_type": "reclassify",
        "new_class_id": "valve_ball",
        "training_consent": False,
        "created_at": "2024-01-15T10:00:00Z",
    }

@pytest.fixture
def mock_emit_correction_action():
    """Mock analytics emitter — verifies correct payload without real PostHog."""
    with patch("backend.app.analytics.events.emit_correction_action") as mock:
        mock.return_value = None  # Non-blocking, no return value
        yield mock

@pytest.fixture
def mock_assert_drawing_access_pass():
    """Mock permission check that passes (user has access)."""
    with patch("backend.app.auth.permissions.assert_drawing_access") as mock:
        mock.return_value = None
        yield mock

@pytest.fixture
def mock_assert_drawing_access_fail():
    """Mock permission check that raises 403."""
    from fastapi import HTTPException
    with patch("backend.app.auth.permissions.assert_drawing_access") as mock:
        mock.side_effect = HTTPException(status_code=403, detail="Forbidden")
        yield mock

# SymbolsPageResponse mock shape (matches §1.1 contract):
MOCK_SYMBOLS_PAGE_RESPONSE = {
    "symbols": [
        {
            "id": "sym-uuid-1",
            "drawing_id": "drw-uuid-1",
            "entity_class_id": "valve_gate",
            "subtype": "gate",
            "tag_label": "V-101",
            "confidence": 0.92,
            "bbox": {"x": 10.0, "y": 20.0, "w": 5.0, "h": 5.0},
            "source": "ml",
            "rejected": False,
            "page_number": 1,
        }
    ],
    "corrections_by_symbol_id": {
        "sym-uuid-1": [
            {
                "id": "cor-uuid-1",
                "detected_symbol_id": "sym-uuid-1",
                "table_cell_id": None,
                "user_id": "usr-uuid-1",
                "correction_type": "reclassify",
                "new_class_id": "valve_ball",
                "training_consent": False,
                "created_at": "2024-01-15T10:00:00Z",
            }
        ]
    },
    "total": 1,
    "limit": 200,
    "offset": 0,
}

# Correction action event payload shape (matches §1.10 contract):
MOCK_CORRECTION_ACTION_EVENT = {
    "event": "correction_action",
    "timestamp": "2024-01-15T10:00:00Z",  # UTC ISO8601
    "user_id": "usr-uuid-1",
    "drawing_id": "drw-uuid-1",
    "symbol_id": "sym-uuid-1",
}
```

**Pre-conditions:**

- For transaction atomicity tests (`test_correction_creates_symbol_update_correction_state_in_one_transaction`, `test_concurrent_corrections_no_constraint_violation`): a real PostgreSQL test database must be available at `TEST_DATABASE_URL` with the schema from `0001_initial_schema.py` applied, seeded with tier and entity\_class rows via `backend/app/db/seed_tiers.py` and `backend/app/db/seed_entity_classes.py`.
- For all other tests: mocked `get_db` dependency is sufficient (no real DB required).
- `POSTHOG_API_KEY` absent or set to a test key — analytics calls mocked.
- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` may be absent for this session's tests; auth middleware is mocked via `get_current_user` override in `TestClient`.

**Isolation rule:**
All tests in `tests/sessions/test_s2c.py` must pass when only S2-C's PR has merged. Auth middleware (S1-B) and DB models (S1-A) are prerequisites that have already merged by Phase 2. S2-B, S2-D, S2-E, S2-F are sibling sessions in the same wave and must NOT be imported. The two DB-dependent atomicity tests require the integration PostgreSQL fixture from `tests/integration/fixtures/db.py` (S0-B), which is already available from Phase 0.

---

##### Checkpoint

- **One-sentence observable outcome:** A `GET /drawings/{id}/symbols` request by the drawing owner returns HTTP 200 with all ML-detected symbols and their correction history in a single response, and a subsequent `PATCH /symbols/{id}` call with a `reclassify` action persists the correction, transitions the drawing to `Under_Review`, fires the `correction_action` analytics event, and returns HTTP 200 with the updated symbol record.
- **Shippability claim:** This PR is independently mergeable to main even if no other session in the same wave (S2-B, S2-D, S2-E, S2-F, S2-G, S2-H, S2-I, S2-J, S2-K, S2-L, S2-M) has merged.

---

##### Output and handoff

| Export | Kind | Consuming Session(s) | Load-bearing? |
|---|---|---|---|
| `backend/app/api/routers/symbols.py` — `router` (FastAPI `APIRouter` mounting `GET /drawings/{id}/symbols`, `PATCH /symbols/{id}`, `POST /drawings/{id}/symbols`) | module | S0-A (included in `main.py` router registration — already stubbed) | `[LOAD-BEARING]` — router name and prefix must not change |
| `backend/app/services/symbol_service.py` — `get_symbols_page(drawing_id, user, db, limit, offset, page_number, entity_class_id, rejected) -> SymbolsPageResponse` | function | S3-D (Review Canvas) via API; S4-A (E2E tests) | `[LOAD-BEARING]` |
| `backend/app/services/correction_service.py` — `create_correction(symbol_id, payload, user, db) -> SymbolRecord` | function | S4-A (E2E test `test_correction_flow.py`) | `[LOAD-BEARING]` |
| `backend/app/services/correction_service.py` — `create_manual_symbol(drawing_id, payload, user, db) -> SymbolRecord` | function | S4-A (E2E test `test_correction_flow.py`) | `[LOAD-BEARING]` |
| `tests/integration/test_symbols_api.py` | module | S4-A (E2E harness imports fixture helpers) | — |
| Pydantic schema `SymbolCorrectionRequest` (defined in `symbols.py`) — `{ correction_type: CorrectionType, new_class_id: EntityClassId | None }` | type | S3-D (API client TypeScript types mirror this) | `[LOAD-BEARING]` |
| Pydantic schema `ManualSymbolCreateRequest` (defined in `symbols.py`) — `{ entity_class_id: EntityClassId, subtype: str, tag_label: str | None, bbox: BoundingBox, page_number: int }` | type | S3-D (API client TypeScript types mirror this) | `[LOAD-BEARING]` |

---

```json
{
  "test": {
    "cmd": "pytest tests/sessions/test_s2c.py -v",
    "file": "tests/sessions/test_s2c.py"
  },
  "checkpoint": "A GET /drawings/{id}/symbols request by the drawing owner returns HTTP 200 with all ML-detected symbols and their correction history in a single response, and a subsequent PATCH /symbols/{id} call with a reclassify action persists the correction, transitions the drawing to Under_Review, fires the correction_action analytics event, and returns HTTP 200 with the updated symbol record.",
  "manualAcs": [],
  "exports": [
    {
      "kind": "module",
      "name": "backend/app/api/routers/symbols",
      "shape": "backend/app/api/routers/symbols.py"
    },
    {
      "kind": "function",
      "name": "get_symbols_page",
      "shape": "(drawing_id: str, user: CurrentUser, db: Session, limit: int, offset: int, page_number: int | None, entity_class_id: str | None, rejected: bool | None) -> SymbolsPageResponse"
    },
    {
      "kind": "function",
      "name": "create_correction",
      "shape": "(symbol_id: str, payload: SymbolCorrectionRequest, user: CurrentUser, db: Session) -> SymbolRecord"
    },
    {
      "kind": "function",
      "name": "create_manual_symbol",
      "shape": "(drawing_id: str, payload: ManualSymbolCreateRequest, user: CurrentUser, db: Session) -> SymbolRecord"
    },
    {
      "kind": "type",
      "name": "SymbolCorrectionRequest",
      "shape": "{ correction_type: CorrectionType; new_class_id: EntityClassId | None }"
    },
    {
      "kind": "type",
      "name": "ManualSymbolCreateRequest",
      "shape": "{ entity_class_id: EntityClassId; subtype: str; tag_label: str | None; bbox: BoundingBox; page_number: int }"
    }
  ]
}
```