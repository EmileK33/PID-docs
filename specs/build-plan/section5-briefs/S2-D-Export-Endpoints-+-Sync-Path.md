#### S2-D — Export Endpoints + Sync Path

**Phase 2 | Backend API | Needs: S1-A, S1-B, S1-C, S1-D, S1-E**

---

##### Objective

Implement the `POST /drawings/{id}/exports` and `GET /exports/{id}` endpoints, synchronous CSV/XLSX file generation for drawings with ≤1,000 symbols, async job enqueueing for drawings with >1,000 symbols (worker handled by S2-K), and the `export_initiated` / `export_downloaded` analytics events — giving users a complete export lifecycle from request to pre-signed download URL.

---

##### Scope

**P0 MVP** — this session is entirely P0. Both US-016 and US-017 are P0 per §1.13.

- **US-016 (P0):** CSV and XLSX export synchronous path (<1,000 symbols), pre-signed download URL, re-export without overwriting prior exports.
- **US-017 (P0):** Async export queue initiation for >1,000 symbols (enqueueing only — the worker task execution lives in S2-K); status-polling via `GET /exports/{id}`; export failure state.

S2-K (Export Worker) is a sibling session that owns `backend/app/workers/export/tasks.py`. S2-D must **not** import from S2-K directly; use `celery_app.send_task("pid_analyzer.workers.export.tasks.generate_export_task", args=[export_id])` by name string to remain independently deployable.

---

##### Technology constraints

From §1.8 — non-negotiable:

| Layer | Selected Technology |
|---|---|
| API Server | FastAPI (Python) |
| Async Workers / Queue | Celery on Redis broker |
| Database | PostgreSQL via SQLAlchemy (Alembic-managed) |
| Object Storage | AWS S3-compatible; pre-signed URLs, 15-min expiry |
| Cache / Pub-Sub | Redis (ElastiCache) |

Additional constraints for this session:
- **XLSX generation:** use `openpyxl` (pure-Python, no C extensions required on Fargate CPU containers). Do **not** use `xlwt` (XLS-only, deprecated) or `xlrd` (read-only).
- **CSV generation:** use Python stdlib `csv` module — do not use pandas for this operation (adds 50 MB to image, no other usage in this session).
- **Symbol count threshold:** evaluated server-side at `POST /drawings/{id}/exports` time by counting `detected_symbol` rows for the drawing. Never trust a client-supplied count.
- **Export file storage:** uploaded to S3 via `s3_client` from S1-C; object key pattern `exports/{export_id}/{drawing_id}.{format}`. Create a `stored_file` DB record for every completed export.
- **No CDN for export files** (§1.7): "no CDN for export files (confidential)" — pre-signed S3 URLs only.

---

##### Performance targets

| Metric | Target | Hard SLA or Monitoring |
|---|---|---|
| Export (<1,000 symbols) | <30s P95 | Monitoring target (§1.9) |
| Async export threshold | >1,000 symbols triggers async path | Hard constraint — evaluated server-side (§1.4 rule 15, §1.9) |
| Pre-signed S3 URL expiry | 15 minutes (900 seconds default) | Hard constraint — security (§1.9) |

---

##### Owned files

```
backend/app/api/routers/exports.py
backend/app/services/export_service.py
backend/app/services/export_generators.py
tests/integration/test_exports_api.py
```

---

##### Read-only imports

| Owning Session | File Path | Named Exports Required |
|---|---|---|
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` (for `send_task` — no import of S2-K task module) |
| S0-A | `backend/app/schemas/contracts.py` | `ExportFormat`, `ExportStatus`, `SymbolRecord`, `BoundingBox` |
| S1-A | `backend/app/db/models/export_record.py` | `ExportRecord` |
| S1-A | `backend/app/db/models/stored_file.py` | `StoredFile` |
| S1-A | `backend/app/db/models/drawing.py` | `Drawing` |
| S1-A | `backend/app/db/models/detected_symbol.py` | `DetectedSymbol` |
| S1-A | `backend/app/db/models/user_correction.py` | `UserCorrection` |
| S1-A | `backend/app/db/session.py` | `get_db` |
| S1-B | `backend/app/auth/dependencies.py` | `get_current_user` |
| S1-B | `backend/app/auth/permissions.py` | `assert_drawing_access` |
| S1-C | `backend/app/storage/s3_client.py` | `S3Client` |
| S1-C | `backend/app/storage/presigned.py` | `generate_presigned_get_url` |
| S1-D | `backend/app/workers/queues.py` | `EXPORT_QUEUE` |
| S1-E | `backend/app/analytics/events.py` | `emit_export_initiated`, `emit_export_downloaded` |

---

##### Do not touch

- `backend/app/main.py` — entry point, pre-stubbed by S0-A
- `backend/app/api/routers/__init__.py` — router includes, pre-stubbed by S0-A
- `backend/app/api/routers/_stubs.py` — placeholder endpoints, owned by S0-A
- `backend/app/workers/export/tasks.py` — owned by S2-K
- `backend/app/workers/export/__init__.py` — owned by S2-K
- All S1-A model files — `backend/app/db/models/*.py`
- All S1-B auth files — `backend/app/auth/*.py`
- All S1-C storage files — `backend/app/storage/*.py`
- All S1-D Redis/queue files — `backend/app/redis/*.py`, `backend/app/workers/queues.py`, `backend/app/workers/base.py`
- All S1-E analytics files — `backend/app/analytics/*.py`
- `tests/integration/test_drawings_api.py` — owned by S2-B
- `tests/integration/test_symbols_api.py` — owned by S2-C

---

##### Architecture context

From §1.6 — Route Manifest (verbatim):
```
POST   /drawings/{id}/exports
GET    /exports/{id}
```

P1-only export routes (must be stubbed as `HTTP 501 Not Implemented`, not silently omitted):
```
GET    /exports/{id}/comparison-csv
```

From §1.1 — Shared Contracts (verbatim):

```typescript
// Export Format
type ExportFormat = 'csv' | 'xlsx';

// Export Status
type ExportStatus = 'Queued' | 'Generating' | 'Complete' | 'Failed';
```

From §1.2 — Database Schema (verbatim):
```sql
-- EXPORT_RECORD
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

-- STORED_FILE
CREATE TABLE stored_file (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  bucket       VARCHAR NOT NULL,
  object_key   VARCHAR NOT NULL,
  sha256_hash  VARCHAR NOT NULL,
  file_type    VARCHAR NOT NULL,
  size_bytes   BIGINT NOT NULL,
  CONSTRAINT stored_file_object_key_unique UNIQUE (bucket, object_key)
);

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
  ...
);
```

From §1.3 — Role-Permission Matrix (verbatim):
```typescript
const ROLE_PERMISSIONS = {
  user: {
    export_initiate: 'own',
    ...
  },
  team_member: {
    export_initiate: 'team',
    ...
  },
  team_admin: {
    export_initiate: 'team',
    ...
  },
} as const;
```

From §1.4 — Critical Ordering Rules (verbatim, rule 15):
> "**Async export threshold evaluated server-side.** The 1,000-symbol threshold for triggering async vs. synchronous export (FR-4 AC-3) must be evaluated server-side at job creation time, not client-side, to prevent bypass."

From §1.9 — Performance Targets (verbatim):
> "Export (<1,000 symbols) | <30s P95 | Monitoring target | Export Worker (synchronous generation); pre-signed URL returned on poll completion"
> "Async export threshold | >1,000 symbols triggers async path | Hard constraint | Export Worker; evaluated server-side"
> "Pre-signed S3 URL expiry | 15 minutes | Hard constraint (security) | FastAPI URL generation"

From §1.10 — Analytics Event Contracts (verbatim):
| Event | Payload | Code Surface | Trigger | Must NOT have happened yet | Must NEVER fire from |
|---|---|---|---|---|---|
| `export_initiated` | `{ event: 'export_initiated', timestamp: string (UTC ISO8601), user_id: string, drawing_id: string, export_id: string, format: ExportFormat }` | FastAPI — `POST /drawings/{id}/exports` handler | Export job created (both sync and async paths) | Export file generated | Export Worker; browser client |
| `export_downloaded` | `{ event: 'export_downloaded', timestamp: string, user_id: string, drawing_id: string, export_id: string }` | FastAPI — pre-signed URL access or download endpoint | User accesses pre-signed download URL | None specified | Export Worker |

From §1.11 — Cross-Session Runtime Patterns, Celery Job Queue Names (verbatim):
| Queue | Workers | Job Types |
|---|---|---|
| `export` | Export Worker (CPU) | CSV/XLSX generation |

From §1.13 — Feature Scope P0 (verbatim):
> "US-016: CSV and XLSX export (synchronous path, <1,000 symbols); pre-signed download URL; re-export without overwriting prior exports"
> "US-017: Async export queue for >1,000 symbols; in-app notification when ready; async export failure with retry"

---

##### User stories and acceptance criteria

*The full user story prose is not reproduced verbatim in the distilled spec; the following ACs are derived from §1.13 feature scope descriptions, §1.4 ordering rules, §1.9 performance targets, and §1.10 analytics contracts — all quoted verbatim above.*

**US-016 — CSV and XLSX Export (Synchronous Path)**

- AC-1: `POST /drawings/{id}/exports` with `format=csv` and a drawing that has ≤1,000 total symbols generates a CSV file synchronously during the request and returns HTTP 201 with `status=Complete` and a `download_url` (pre-signed S3 GET URL).
- AC-2: `POST /drawings/{id}/exports` with `format=xlsx` and a drawing that has ≤1,000 total symbols generates a valid XLSX file synchronously and returns HTTP 201 with `status=Complete` and a `download_url`.
- AC-3: The CSV output contains one row per symbol with columns: `symbol_id`, `entity_class_id`, `subtype`, `tag_label`, `confidence`, `page_number`, `bbox_x`, `bbox_y`, `bbox_w`, `bbox_h`, `source`, `rejected`. Effective `entity_class_id` reflects the most recent `reclassify` correction if one exists.
- AC-4: The XLSX output contains the same columns as the CSV on a worksheet named `Symbols`, plus a second worksheet named `Corrections` containing all correction records for the drawing.
- AC-5: Calling `POST /drawings/{id}/exports` a second time for the same drawing (same or different format) creates a new `export_record` row; the original `export_record` is not modified (re-export does not overwrite).
- AC-6: The `export_initiated` analytics event fires with `{ event, timestamp, user_id, drawing_id, export_id, format }` after the `export_record` row is committed but before the response is sent. It fires for **both** sync and async paths. It must **not** fire from the Export Worker.
- AC-7: The pre-signed download URL returned in `download_url` expires after 15 minutes (900 seconds, configurable via `PRESIGNED_URL_EXPIRY_SECONDS`).
- AC-8: `GET /exports/{id}` for a Complete export record returns HTTP 200 with `status=Complete` and a fresh pre-signed `download_url`. The `export_downloaded` analytics event fires on this response.
- AC-9: A `stored_file` record is created for each successfully generated export file, with `bucket`, `object_key` (pattern `exports/{export_id}/{drawing_id}.{format}`), `sha256_hash`, `file_type` (`text/csv` or `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`), and `size_bytes` populated.
- AC-10: Unauthenticated `POST /drawings/{id}/exports` returns HTTP 401.
- AC-11: `POST /drawings/{id}/exports` for a drawing owned by a different user (non-team) returns HTTP 403.
- AC-12: `POST /drawings/{id}/exports` for a non-existent drawing_id returns HTTP 404.
- AC-13: `POST /drawings/{id}/exports` with an invalid `format` value (not `csv` or `xlsx`) returns HTTP 422.

**US-017 — Async Export Queue (Initiation)**

- AC-1: `POST /drawings/{id}/exports` for a drawing with >1,000 symbols returns HTTP 202 with `status=Queued` and no `download_url` field (or `download_url: null`).
- AC-2: The threshold is evaluated server-side by counting `detected_symbol` rows for `drawing_id` at job creation time. A client-supplied symbol count must not influence the path selection.
- AC-3: The boundary condition: exactly 1,000 symbols → synchronous path (≤1,000); exactly 1,001 symbols → async path (>1,000).
- AC-4: An `export_record` row is created with `status=Queued` before the Celery task is enqueued. If task enqueue fails, the row persists in `Queued` state for subsequent retry by the worker.
- AC-5: `GET /exports/{id}` for a Queued or Generating export returns HTTP 200 with current `status` and `download_url: null`.
- AC-6: `GET /exports/{id}` for a Failed export returns HTTP 200 with `status=Failed` and `download_url: null`.
- AC-7: `GET /exports/{id}` where the export belongs to a different user returns HTTP 403.
- AC-8: `GET /exports/{id}` for a non-existent export_id returns HTTP 404.
- AC-9: The `export_initiated` analytics event fires for the async path at the same point as the sync path (after `export_record` commit, before response).

---

##### UX and design specification

N/A — no frontend component. This session is a pure backend API session.

---

##### Critical implementation notes

- **Async threshold is a hard server-side gate.** From §1.4 rule 15: "The 1,000-symbol threshold for triggering async vs. synchronous export (FR-4 AC-3) must be evaluated server-side at job creation time, not client-side, to prevent bypass." Count with `SELECT COUNT(*) FROM detected_symbol WHERE drawing_id = :drawing_id`. Do not use an estimate, a client header, or the drawing's `estimated_symbol_count` column.

- **`export_initiated` must fire AFTER the export_record is committed, not before.** The spec states "Export job created (both sync and async paths)" as the trigger and "Export file generated" as what must NOT have happened. For sync: fire immediately after `export_record` INSERT commits, before S3 upload begins. For async: fire after `export_record` INSERT commits, before `send_task`. Analytics failure must not raise an exception or block the response (§1.10: "non-blocking and asynchronous").

- **`export_downloaded` fires on GET, not at S3 access time.** Since S3 pre-signed URLs are direct browser downloads, FastAPI cannot intercept the actual S3 GET. The `export_downloaded` event fires whenever `GET /exports/{id}` returns a Complete export with a fresh URL. This may fire multiple times for a single file download (each poll). This is an acceptable approximation — the spec says "FastAPI — pre-signed URL access or download endpoint."

- **Do not import from S2-K.** S2-K (Export Worker) is a sibling Phase 2 session. Enqueue using `celery_app.send_task("pid_analyzer.workers.export.tasks.generate_export_task", kwargs={"export_id": str(export_id)})`. The task name string is a [LOAD-BEARING] contract with S2-K — it must match exactly.

- **Sync path atomicity.** The following must be committed in a single DB transaction after S3 upload succeeds: `StoredFile` INSERT + `ExportRecord` UPDATE (`status=Complete`, `stored_file_id`, `completed_at`). S3 upload is external and cannot be inside the transaction. Pattern: (1) INSERT `ExportRecord` status=Queued → commit; (2) generate bytes in memory; (3) SHA-256 hash bytes; (4) upload to S3; (5) in one transaction: INSERT `StoredFile`, UPDATE `ExportRecord` → commit. If step 4 fails, the `ExportRecord` remains in `Queued` state (the async worker retry logic in S2-K will pick it up, or the endpoint returns a 500 and the client may retry).

- **Re-export creates a new record; never UPSERT.** Always INSERT a new `ExportRecord` row. The constraint in the spec is "re-export without overwriting prior exports" (US-016 AC-5). Do not check for existing completed exports.

- **S3 object key deduplication.** Key pattern `exports/{export_id}/{drawing_id}.{format}` uses the new `export_id` UUID, making collisions impossible across re-exports.

- **Permission check uses drawing ownership.** The `assert_drawing_access` helper from S1-B enforces `owner_user_id` = current user for `role=user`, or `owner_team_id` = user's team for `role=team_member` / `role=team_admin`. A 403 (not 404) is returned when the drawing exists but the user lacks access — from §1.5: "Authenticated user accessing resource they do not own | 403 | Must never return 404."

- **GET /exports/{id} must also check ownership.** Verify `export_record.user_id == current_user.id`. Do not allow cross-user export record access even if the user can access the drawing.

- **`GET /exports/{id}/comparison-csv` is P1** — stub it as `raise HTTPException(status_code=501, detail="Not implemented")` in `exports.py`. Do not silently omit it.

- **XLSX worksheet structure.** Sheet 1: `Symbols` — one row per non-rejected `DetectedSymbol` with effective `entity_class_id` (applying latest `reclassify` correction if any). Sheet 2: `Corrections` — all `UserCorrection` rows for all symbols in the drawing (both rejected and non-rejected). Effective `entity_class_id` is computed by: joining `user_correction` where `correction_type='reclassify'` ordered by `created_at DESC LIMIT 1` per symbol; if none, use `detected_symbol.entity_class_id`.

- **CSV includes all symbols including rejected ones**, with a `rejected` boolean column, so downstream tooling can filter. Do not silently drop rejected symbols from the export.

- **`export_record.status` must follow the state machine.** Valid transitions for this session: `Queued → Complete` (sync path), `Queued → Failed` (sync path on S3 error), `Queued` (async path — worker transitions to `Generating → Complete/Failed` in S2-K).

- **Presigned URL expiry.** Read from `settings.PRESIGNED_URL_EXPIRY_SECONDS` (default 900). Use `generate_presigned_get_url` from S1-C. Never hardcode 900.

---

##### Mocking contract

This is a backend session. The following internal service interfaces are depended on:

**From S1-C — `generate_presigned_get_url`:**
```python
# Expected interface (defined by S1-C)
def generate_presigned_get_url(
    bucket: str,
    object_key: str,
    expiry_seconds: int
) -> str:
    ...  # returns HTTPS pre-signed S3 URL
```
Test double: `unittest.mock.MagicMock(return_value="https://s3.example.com/exports/test-export-id/test-drawing-id.csv?X-Amz-Signature=...")`.

**From S1-C — `S3Client.upload_bytes`:**
```python
# Expected interface (defined by S1-C)
def upload_bytes(
    bucket: str,
    object_key: str,
    data: bytes,
    content_type: str
) -> None:
    ...
```
Test double: `unittest.mock.MagicMock(return_value=None)`.

**From S1-E — `emit_export_initiated`:**
```python
# Expected interface (defined by S1-E)
def emit_export_initiated(
    user_id: str,
    drawing_id: str,
    export_id: str,
    format: ExportFormat
) -> None:
    ...  # non-blocking, fire-and-forget
```
Test double: spy via `unittest.mock.patch`.

**From S1-E — `emit_export_downloaded`:**
```python
def emit_export_downloaded(
    user_id: str,
    drawing_id: str,
    export_id: str
) -> None:
    ...
```
Test double: spy via `unittest.mock.patch`.

**From S0-A — `celery_app.send_task`:**
```python
# Task name contract with S2-K [LOAD-BEARING]
EXPORT_TASK_NAME = "pid_analyzer.workers.export.tasks.generate_export_task"
# Kwargs payload shape consumed by S2-K:
{"export_id": "<UUID string>"}
```
Test double: `unittest.mock.patch.object(celery_app, "send_task")` — assert called with correct task name and `kwargs={"export_id": str(export_record.id)}`.

**GET /exports/{id} endpoint response shape (consumed by S3-G and S2-K):**
```python
class ExportRecordResponse(BaseModel):
    id: str                        # UUID
    drawing_id: str                # UUID
    user_id: str                   # UUID
    format: ExportFormat           # 'csv' | 'xlsx'
    status: ExportStatus           # 'Queued' | 'Generating' | 'Complete' | 'Failed'
    initiated_at: str              # ISO 8601 UTC
    completed_at: Optional[str]    # ISO 8601 UTC, null if not complete
    download_url: Optional[str]    # pre-signed S3 URL, null unless status=Complete
```

**POST /drawings/{id}/exports request body:**
```python
class ExportCreateRequest(BaseModel):
    format: ExportFormat  # 'csv' | 'xlsx' — required
```

---

##### Acceptance criteria checklist

- [ ] `POST /drawings/{id}/exports` with `format=csv` and drawing with ≤1,000 symbols returns HTTP 201 with `status=Complete` and non-null `download_url` [US-016 AC-1]
- [ ] `POST /drawings/{id}/exports` with `format=xlsx` and drawing with ≤1,000 symbols returns HTTP 201 with `status=Complete` and non-null `download_url` [US-016 AC-2]
- [ ] CSV output contains required columns: `symbol_id`, `entity_class_id`, `subtype`, `tag_label`, `confidence`, `page_number`, `bbox_x`, `bbox_y`, `bbox_w`, `bbox_h`, `source`, `rejected` [US-016 AC-3]
- [ ] CSV `entity_class_id` reflects latest `reclassify` correction when one exists [US-016 AC-3]
- [ ] XLSX output contains `Symbols` worksheet with same columns as CSV [US-016 AC-4]
- [ ] XLSX output contains `Corrections` worksheet with correction records for the drawing [US-016 AC-4]
- [ ] Calling `POST /drawings/{id}/exports` twice creates two separate `export_record` rows; original is unmodified [US-016 AC-5]
- [ ] `export_initiated` analytics event fires with correct payload after export_record commit, for sync path [US-016 AC-6]
- [ ] `export_initiated` fires for async path as well [US-017 AC-9]
- [ ] `download_url` expires after `PRESIGNED_URL_EXPIRY_SECONDS` seconds (default 900) [US-016 AC-7]
- [ ] `GET /exports/{id}` for Complete export returns HTTP 200 with `download_url` populated [US-016 AC-8]
- [ ] `export_downloaded` analytics event fires on `GET /exports/{id}` when export is Complete [US-016 AC-8]
- [ ] `stored_file` record created with correct `bucket`, `object_key`, `sha256_hash`, `file_type`, `size_bytes` [US-016 AC-9]
- [ ] Unauthenticated `POST /drawings/{id}/exports` returns HTTP 401 [US-016 AC-10]
- [ ] `POST /drawings/{id}/exports` for drawing owned by different user returns HTTP 403 (not 404) [US-016 AC-11]
- [ ] `POST /drawings/{id}/exports` for non-existent drawing_id returns HTTP 404 [US-016 AC-12]
- [ ] `POST /drawings/{id}/exports` with invalid format value returns HTTP 422 [US-016 AC-13]
- [ ] `POST /drawings/{id}/exports` for drawing with >1,000 symbols returns HTTP 202 with `status=Queued` and null `download_url` [US-017 AC-1]
- [ ] Symbol threshold evaluated by server-side DB count — client cannot influence path selection [US-017 AC-2]
- [ ] Exactly 1,000 symbols → sync path (201); exactly 1,001 symbols → async path (202) [US-017 AC-3]
- [ ] `export_record` row INSERT with `status=Queued` committed before Celery `send_task` is called [US-017 AC-4]
- [ ] `GET /exports/{id}` for Queued export returns HTTP 200 with `status=Queued` and null `download_url` [US-017 AC-5]
- [ ] `GET /exports/{id}` for Failed export returns HTTP 200 with `status=Failed` and null `download_url` [US-017 AC-6]
- [ ] `GET /exports/{id}` for export belonging to different user returns HTTP 403 [US-017 AC-7]
- [ ] `GET /exports/{id}` for non-existent export_id returns HTTP 404 [US-017 AC-8]
- [ ] `GET /exports/{id}/comparison-csv` returns HTTP 501 (P1 stub) [MANUAL]
- [ ] Celery `send_task` called with task name `"pid_analyzer.workers.export.tasks.generate_export_task"` and `kwargs={"export_id": "<uuid>"}` for async path [US-017 AC-4]
- [ ] S3 object key follows pattern `exports/{export_id}/{drawing_id}.{format}` [US-016 AC-9]
- [ ] Sync path: `StoredFile` INSERT and `ExportRecord` UPDATE committed in a single DB transaction after successful S3 upload [Technical — atomicity]
- [ ] CSV includes rejected symbols (with `rejected=true`) — does not silently drop them [Technical — correctness]
- [ ] `export_initiated` does not fire from the Export Worker (S2-K task boundary) — verified by asserting it fires in `export_service.py` before `send_task` [Technical — analytics contract §1.10]

---

##### Independent Test

**Test file path (TDD — written first, must fail before implementation):** `tests/integration/test_exports_api.py`

**Exact CI command:**
```bash
pytest tests/integration/test_exports_api.py -v
```

**AC → assertion mapping:**

| AC | `it(...)` / `test(...)` block |
|---|---|
| US-016 AC-1 | `test_post_export_csv_sync_returns_201_with_download_url` |
| US-016 AC-2 | `test_post_export_xlsx_sync_returns_201_with_download_url` |
| US-016 AC-3 (columns) | `test_csv_output_contains_required_columns` |
| US-016 AC-3 (reclassify) | `test_csv_entity_class_reflects_latest_reclassify_correction` |
| US-016 AC-4 (Symbols sheet) | `test_xlsx_symbols_worksheet_contains_required_columns` |
| US-016 AC-4 (Corrections sheet) | `test_xlsx_corrections_worksheet_contains_correction_rows` |
| US-016 AC-5 | `test_re_export_creates_new_record_does_not_overwrite` |
| US-016 AC-6 | `test_export_initiated_event_fires_sync_path` |
| US-017 AC-9 | `test_export_initiated_event_fires_async_path` |
| US-016 AC-7 | `test_presigned_url_uses_configured_expiry_seconds` |
| US-016 AC-8 (200 + URL) | `test_get_export_complete_returns_200_with_download_url` |
| US-016 AC-8 (event) | `test_export_downloaded_event_fires_on_get_complete_export` |
| US-016 AC-9 | `test_stored_file_record_created_with_correct_fields` |
| US-016 AC-10 | `test_post_export_unauthenticated_returns_401` |
| US-016 AC-11 | `test_post_export_wrong_owner_returns_403` |
| US-016 AC-12 | `test_post_export_nonexistent_drawing_returns_404` |
| US-016 AC-13 | `test_post_export_invalid_format_returns_422` |
| US-017 AC-1 | `test_post_export_over_threshold_returns_202_queued` |
| US-017 AC-2 | `test_threshold_evaluated_server_side_not_from_client` |
| US-017 AC-3 (boundary) | `test_threshold_boundary_exactly_1000_sync_1001_async` |
| US-017 AC-4 (DB before enqueue) | `test_export_record_committed_before_celery_send_task` |
| US-017 AC-5 | `test_get_export_queued_returns_200_null_url` |
| US-017 AC-6 | `test_get_export_failed_returns_200_null_url` |
| US-017 AC-7 | `test_get_export_wrong_user_returns_403` |
| US-017 AC-8 | `test_get_export_nonexistent_returns_404` |
| Technical — Celery task name | `test_async_path_sends_task_with_correct_name_and_kwargs` |
| Technical — S3 key pattern | `test_s3_object_key_follows_exports_pattern` |
| Technical — atomicity | `test_stored_file_and_export_record_updated_atomically_after_s3` |
| Technical — CSV includes rejected | `test_csv_includes_rejected_symbols_with_flag` |
| Technical — analytics contract | `test_export_initiated_fires_before_send_task_not_from_worker` |

**Fixtures / test doubles:**

```python
# conftest.py additions needed for this test file:

@pytest.fixture
def test_user(db_session) -> User:
    """Creates a user with active Free tier subscription."""
    ...

@pytest.fixture
def test_drawing_small(db_session, test_user) -> Drawing:
    """Drawing owned by test_user with 5 DetectedSymbol rows."""
    ...

@pytest.fixture
def test_drawing_large(db_session, test_user) -> Drawing:
    """Drawing owned by test_user with 1001 DetectedSymbol rows."""
    ...

@pytest.fixture
def test_drawing_boundary(db_session, test_user) -> Drawing:
    """Drawing owned by test_user with exactly 1000 DetectedSymbol rows."""
    ...

@pytest.fixture
def test_drawing_with_corrections(db_session, test_user) -> Drawing:
    """Drawing with 5 symbols, 2 of which have reclassify corrections."""
    ...

@pytest.fixture
def other_user(db_session) -> User:
    """Second user — cannot access test_user's drawings."""
    ...

@pytest.fixture
def mock_s3_client(monkeypatch):
    """Patches S3Client.upload_bytes to no-op; patches generate_presigned_get_url."""
    mock_upload = MagicMock(return_value=None)
    mock_presign = MagicMock(
        return_value="https://s3.example.com/exports/mock-id/mock-drawing.csv"
                     "?X-Amz-Expires=900&X-Amz-Signature=abc123"
    )
    monkeypatch.setattr("backend.app.storage.s3_client.S3Client.upload_bytes", mock_upload)
    monkeypatch.setattr("backend.app.storage.presigned.generate_presigned_get_url", mock_presign)
    return mock_upload, mock_presign

@pytest.fixture
def mock_analytics(monkeypatch):
    """Spies on emit_export_initiated and emit_export_downloaded."""
    mock_initiated = MagicMock()
    mock_downloaded = MagicMock()
    monkeypatch.setattr("backend.app.analytics.events.emit_export_initiated", mock_initiated)
    monkeypatch.setattr("backend.app.analytics.events.emit_export_downloaded", mock_downloaded)
    return mock_initiated, mock_downloaded

@pytest.fixture
def mock_celery_send_task(monkeypatch):
    """Patches celery_app.send_task to capture calls."""
    mock_send = MagicMock()
    monkeypatch.setattr("backend.app.workers.celery_app.celery_app.send_task", mock_send)
    return mock_send

@pytest.fixture
def auth_headers(test_user, client) -> dict:
    """Returns Authorization header for test_user."""
    # Uses Supabase JWT test keypair from integration test fixtures (S0-B)
    ...
```

**Pre-conditions:**
- PostgreSQL test database with Alembic migrations applied (provides all tables including `export_record`, `stored_file`, `detected_symbol`, `user_correction`).
- Redis available (from S0-B `tests/integration/fixtures/redis.py`) — needed for Celery broker mock.
- Seed data: `tier` rows (`free`, `pro`, `team`) from `backend/app/db/seed_tiers.py` (S1-A); `entity_class` rows from `backend/app/db/seed_entity_classes.py` (S1-A).
- Environment variables: `DATABASE_URL`, `REDIS_URL`, `S3_BUCKET_NAME`, `S3_REGION`, `JWT_RS256_PUBLIC_KEY` set from `docker-compose.test.yml` (S0-B).
- S3 is mocked at the `S3Client` level — no real S3 bucket required in CI.

**Isolation rule:** This test file passes when only S1-A, S1-B, S1-C, S1-D, S1-E, and S2-D have merged. It does not require S2-K (Export Worker), S2-B (Drawings API), or S2-C (Symbols API). It creates all fixture data inline via SQLAlchemy and does not call sibling API endpoints.

---

##### Checkpoint

`POST /drawings/{id}/exports` for a drawing with 5 symbols returns HTTP 201 with `status=Complete` and a pre-signed `download_url`; for a drawing with 1,001 symbols it returns HTTP 202 with `status=Queued`; `GET /exports/{id}` returns the current status and fires `export_downloaded` analytics when the export is Complete.

**Shippability claim:** This PR is independently mergeable to main even if no other session in the same wave has merged, provided S1-A, S1-B, S1-C, S1-D, and S1-E have merged (Phase 1 gate). No Phase 2 sibling session needs to have merged first.

---

##### Output and handoff

| Export | Kind | Shape | Consuming Sessions |
|---|---|---|---|
| `ExportRecordResponse` | Pydantic model / type | `{ id: str, drawing_id: str, user_id: str, format: ExportFormat, status: ExportStatus, initiated_at: str, completed_at: Optional[str], download_url: Optional[str] }` | S2-K (reads export_record state), S3-G (renders export status UI) |
| `ExportCreateRequest` | Pydantic model | `{ format: ExportFormat }` | S3-G (matches request body) |
| `EXPORT_TASK_NAME` constant | string constant [LOAD-BEARING] | `"pid_analyzer.workers.export.tasks.generate_export_task"` | S2-K (must define task with exactly this name) |
| `export_service.py::create_export` | function | `(drawing_id: UUID, user_id: UUID, format: ExportFormat, db: Session) -> ExportRecordResponse` | S2-K, S4-A |
| `POST /drawings/{id}/exports` | HTTP endpoint | Request: `ExportCreateRequest`; Response sync 201: `ExportRecordResponse`; Response async 202: `ExportRecordResponse` | S3-G, S4-A |
| `GET /exports/{id}` | HTTP endpoint [LOAD-BEARING] | Response 200: `ExportRecordResponse` with optional `download_url` | S2-K (polls to verify completion), S3-G, S4-A |

---

```json
{
  "test": {
    "cmd": "pytest tests/integration/test_exports_api.py -v",
    "file": "tests/integration/test_exports_api.py"
  },
  "checkpoint": "POST /drawings/{id}/exports for a drawing with 5 symbols returns HTTP 201 with status=Complete and a pre-signed download_url; for a drawing with 1,001 symbols returns HTTP 202 with status=Queued; GET /exports/{id} returns current status and fires export_downloaded analytics when Complete.",
  "manualAcs": [
    {
      "id": "US-017-AC-P1-STUB",
      "text": "GET /exports/{id}/comparison-csv returns HTTP 501 (P1 stub — not implemented)."
    }
  ],
  "exports": [
    {
      "kind": "type",
      "name": "ExportRecordResponse",
      "shape": "{ id: str; drawing_id: str; user_id: str; format: 'csv' | 'xlsx'; status: 'Queued' | 'Generating' | 'Complete' | 'Failed'; initiated_at: str; completed_at: str | null; download_url: str | null }"
    },
    {
      "kind": "type",
      "name": "ExportCreateRequest",
      "shape": "{ format: 'csv' | 'xlsx' }"
    },
    {
      "kind": "function",
      "name": "create_export",
      "shape": "(drawing_id: UUID, user_id: UUID, format: ExportFormat, db: Session) -> ExportRecordResponse"
    },
    {
      "kind": "function",
      "name": "get_export",
      "shape": "(export_id: UUID, user_id: UUID, db: Session) -> ExportRecordResponse"
    },
    {
      "kind": "module",
      "name": "EXPORT_TASK_NAME",
      "shape": "pid_analyzer.workers.export.tasks.generate_export_task"
    },
    {
      "kind": "module",
      "name": "backend/app/api/routers/exports.py",
      "shape": "backend/app/api/routers/exports.py"
    },
    {
      "kind": "module",
      "name": "backend/app/services/export_service.py",
      "shape": "backend/app/services/export_service.py"
    },
    {
      "kind": "module",
      "name": "backend/app/services/export_generators.py",
      "shape": "backend/app/services/export_generators.py"
    }
  ]
}
```