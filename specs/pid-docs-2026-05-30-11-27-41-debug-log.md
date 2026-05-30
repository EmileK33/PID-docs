# HyperSpeed Team Debug Log

Generated: 2026-05-30 11:27:41

---

# HyperSpeed Team Run Log

## Command

```
"C:\Program Files\nodejs\node.exe" "C:\Users\emile\Documents\VS Code Samples\HyperSpeed Team\.claude\worktrees\epic-rosalind-51b3b1\dist\hyperspeed.js" --generate-build-plan C:\Users\emile\Downloads\PID-docs\specs
```

Generated: 2026-05-30 11:27:41

---

## Project Configuration

*(not captured)*

---

## Phases

*(no phases recorded)*

---

## Prompts Used Per Agent

### build-plan-distilled-spec [primary]

**System Prompt:**
```
You are generating a distilled specification from software specification documents. Your output replaces the full documents in all subsequent build planning stages — precision is more important than completeness.

Read all attached documents in full. Produce a compressed specification containing ONLY the following subsections. Include only subsections that are relevant to the project — omit any subsection that has no applicable content (e.g., skip Redis/Socket.IO sections for a project that uses neither).

**1.1 Shared contracts** Every TypeScript interface, enum, and constant that more than one part of the system depends on. Define each completely with all field names and types. Mark the single most critical cross-module contract — the payload shape that forms the boundary between independent workstreams — with `[CRITICAL BOUNDARY]`. This contract must not change after the first session that defines it is merged.

**1.2 Database schema** Every table, column with type, CHECK constraint, unique constraint, foreign key, index, RLS policy, and partition rule. Present as SQL DDL only. If the project has no database, omit this section.

**1.3 State machines and permission matrices** Every valid status transition table and every role-permission matrix. Present as TypeScript constant objects with explicit types.

**1.4 Critical ordering rules** Every place in the spec where execution order is mandatory. Number each rule. Quote the original spec language exactly.

**1.5 HTTP status code contracts** Every place the spec defines a required HTTP status code for a specific condition. Present as a table:

| Condition | Required code | Must never return |
| --------- | ------------- | ----------------- |

If the project has no HTTP endpoints, omit this section.

**1.6 Route manifest** Every backend API endpoint (method + path) and every frontend page route the system requires. Two flat lists — no grouping, no descriptions. For CLI tools, list all commands and subcommands instead. For libraries, list all public module exports.

**1.7 Third-party dependencies** Every external API, SDK, or service. For each: auth mechanism, known quota limits, and any risk flags from the spec.

**1.8 Technology stack — selected choices only** The chosen technology for every layer. Do not list alternatives — list only what was selected and state why the choice is architecturally irreversible. List only entries relevant to the project.

**1.9 Performance targets** Every specific SLA stated in the spec. For each: the metric, the target value, whether it is a hard SLA or a monitoring target, and which system component is responsible.

**1.10 Analytics event contracts** Every analytics event the system fires. For each: event name, exact payload shape with field names and types, the single code surface that fires it, the condition that triggers it, and explicit statements of what must NOT have happened yet when it fires and what code surfaces must never fire it. If the project has no analytics events, omit this section.

**1.11 Cross-session runtime patterns** Every key pattern, event name, payload shape, or storage key that is written by one workstream and read by another. Include: cache key patterns, message queue event names, real-time event names and payloads, browser storage keys. If the project has no cross-workstream runtime patterns, omit this section.

**1.12 Environment variable schema** Every environment variable the application reads. Present as a table:

| Variable | Type | Valid values | Default if absent | Startup behavior if invalid | Startup behavior if absent |

**1.13 Feature scope — P0 vs P1** A definitive list of which features, epics, and endpoints are P0 (MVP, first release) and which are P1 (post-MVP). Present as two flat lists. If the spec does not distinguish P0/P1, state "All features are P0 (single release)" and list everything.

IMPORTANT: Do not paraphrase or summarize specification content. Extract and reproduce the relevant details precisely. The distilled spec must be accurate enough that the original documents are not needed again.
```

**User Message:**
```
Produce the distilled specification from the three documents provided in the system context.
```

---

### build-plan-session-table [primary]

**System Prompt:**
```
You are a build planning architect decomposing a software project into discrete Claude Code sessions. Each session will be executed autonomously by a separate Claude Code instance with no human guidance.

The CRITICAL constraint: **A session is discrete when it has zero file ownership overlap with any other session.** If two workstreams write to different files they are different sessions. Do not merge sessions to reduce count. Do not split sessions in ways that create shared file ownership.

**Shared infrastructure files** (e.g., app.ts, routes.tsx, schema files, config files) must be owned by a **Phase 0 scaffold session** that pre-stubs every mount point, route, and configuration needed by all downstream sessions. No other session may modify these files. **EXCEPTION**: `package.json` (and equivalent project manifests — `pyproject.toml`, `go.mod`, `Cargo.toml`, etc.) is reserved for the mandatory Phase 0 integration-harness session described below — the scaffold session must NOT list it. Zero file-ownership overlap is mandatory; `package.json` must appear in exactly ONE session's owned files.

**MANDATORY Phase 0 integration-harness session.** Phase 0 MUST include a dedicated integration-harness session whose responsibilities are:
- **Sole owner of `package.json`** (or project-equivalent manifest). The scaffold session and every other session must NOT list `package.json` in their owned files.
- Owned files MUST also include a `tests/integration/` directory (harness config + shared fixtures + DB/service spin-up scripts, as applicable).
- Produces a passing trivial smoke test so the project-level integration command (e.g., `npm run test:integration`) exits 0 before any feature wave fires.
- Its session brief's `test.cmd` MUST be the project-level integration command (e.g., `npm run test:integration`), NOT a per-file vitest invocation.
- Acceptable to MERGE this with the scaffold session into a single Phase 0 session — but only if `package.json` appears in exactly one row; never two.

This session is non-negotiable — the downstream runner uses its integration command as the wave-boundary gate. For non-Node projects, adapt paths and command equivalents (e.g., `pytest tests/integration`, `go test ./tests/integration/...`) but keep the constraint: a project-level integration command that exits 0 against a trivial smoke test, owned by exactly one Phase 0 session that is the sole owner of the project manifest.

Using the distilled specification provided, identify every discrete session required to build the complete system.

For each session produce one row in this markdown table:

| ID | Name | Category | Phase | Prerequisites | Owned files (exhaustive) | Complexity |
| -- | ---- | -------- | ----- | ------------- | ------------------------ | ---------- |

**ID format**: `S{phase}-{letter}` — e.g. S0-A, S1-B, S2-C

**Category**: one of — Infrastructure · Auth/Contracts · Backend API · Real-time/Queue · Frontend · Testing/Hardening. For non-web projects, adapt categories to fit (e.g., CLI: Core/Commands/Plugins; Library: Core/Modules/Testing; Pipeline: Ingestion/Transform/Output).

**Phase**: 0 = no dependencies. Each subsequent phase depends only on prior phase gates clearing. Within a phase, all sessions are parallel unless an explicit intra-phase dependency exists.

**Owned files**: list every file this session creates or modifies. Be exhaustive — if a session writes to a file it must appear here and nowhere else in the table.

**Complexity**: S = ~1 hr · M = ~2 hrs · L = ~3 hrs Claude Code execution time

After the markdown table, produce:

1. **Gate definitions**: for each phase transition, list exactly which sessions must be merged before the next phase starts, and which sessions are explicitly non-blocking
2. **Intra-phase dependencies**: any session within a phase that must complete before another session in the same phase starts
3. **Early-start optimizations**: any session whose subset of prerequisites clears before the full gate, allowing it to start early
4. **Critical path**: the longest dependency chain from Phase 0 to the final phase

Then output a JSON array with the same session data for programmatic parsing. Use this exact format:

```json
[
  {
    "id": "S0-A",
    "phase": 0,
    "name": "Session Name",
    "category": "Infrastructure",
    "prerequisites": [],
    "ownedFiles": ["src/file1.ts", "src/file2.ts"],
    "complexity": "M",
    "specSections": ["section heading 1", "section heading 2"]
  }
]
```

The `specSections` field lists which specification document section headings are relevant for generating this session's implementation brief. These headings will be used to extract verbatim excerpts from the original specification documents.

State the total session count at the end: "Total: N sessions across M phases"
```

**User Message:**
```
Using the distilled specification, decompose the project into discrete Claude Code sessions with zero file-ownership overlap.
```

---

### build-plan-build-order [primary]

**System Prompt:**
```
You are generating the precise build order for an autonomous build plan. Using the session table provided (no other documents needed), write the execution order:

For each phase:
- List all sessions that start at gate open
- State explicitly which are parallel (no arrows between them) and which have intra-phase sequencing
- State the gate verification checklist — specific observable outcomes a human must confirm before starting the next phase. Each item must be independently verifiable (e.g., "`GET /healthz` returns 200 with `db:ok` and `redis:ok`" not "verify database works")

For each early-start optimization: state which session, which subset of prerequisites enables it, and what the risk is of starting early.

State the critical path in bold at the end of this section.
```

**User Message:**
```
# PID Analyzer — Session Decomposition

| ID | Name | Category | Phase | Prerequisites | Owned files (exhaustive) | Complexity |
| -- | ---- | -------- | ----- | ------------- | ------------------------ | ---------- |
| S0-A | Scaffold & Shared Stubs | Infrastructure | 0 | — | `backend/app/main.py`, `backend/app/config.py`, `backend/app/db/base.py`, `backend/app/db/session.py`, `backend/app/api/__init__.py`, `backend/app/api/routers/__init__.py` (all router include stubs), `backend/app/api/routers/_stubs.py` (placeholder endpoints for every route in §1.6 P0+P1), `backend/app/workers/celery_app.py`, `backend/app/workers/__init__.py`, `backend/app/schemas/contracts.py` (pydantic mirrors of §1.1), `backend/app/schemas/__init__.py`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/Dockerfile`, `backend/Dockerfile.worker`, `backend/Dockerfile.ml`, `frontend/index.html`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/router.tsx` (lazy route stubs for all SPA pages), `frontend/src/pages/_stubs.tsx`, `frontend/src/types/contracts.ts`, `marketing/next.config.js`, `marketing/tsconfig.json`, `marketing/app/layout.tsx`, `marketing/app/page.tsx`, `docker-compose.yml`, `docker-compose.test.yml`, `.env.example`, `README.md`, `ops/oda-sandbox/Dockerfile`, `ops/clamav/Dockerfile` | L |
| S0-B | Integration Harness & Manifests | Testing/Hardening | 0 | — | `package.json` (root workspace), `backend/pyproject.toml`, `backend/poetry.lock`, `frontend/package.json`, `marketing/package.json`, `tests/integration/conftest.py`, `tests/integration/docker-compose.fixtures.yml`, `tests/integration/fixtures/db.py`, `tests/integration/fixtures/redis.py`, `tests/integration/fixtures/s3.py`, `tests/integration/smoke/test_smoke.py`, `tests/integration/README.md`, `scripts/test-integration.sh`, `.github/workflows/integration.yml` | M |
| S1-A | DB Models & Migrations | Infrastructure | 1 | S0-A, S0-B | `backend/app/db/models/__init__.py`, `backend/app/db/models/user.py`, `backend/app/db/models/team.py`, `backend/app/db/models/tier.py`, `backend/app/db/models/subscription.py`, `backend/app/db/models/stored_file.py`, `backend/app/db/models/file_hash_blocklist.py`, `backend/app/db/models/drawing.py`, `backend/app/db/models/entity_class.py`, `backend/app/db/models/detected_symbol.py`, `backend/app/db/models/table_cell.py`, `backend/app/db/models/user_correction.py`, `backend/app/db/models/export_record.py`, `backend/app/db/models/ml_training_consent.py`, `backend/app/db/models/revision_comparison.py`, `backend/app/db/models/audit_log.py`, `backend/app/db/models/stripe_event.py`, `backend/alembic/versions/0001_initial_schema.py`, `backend/alembic/versions/0002_rls_policies.py`, `backend/alembic/versions/0003_audit_partitions.py`, `backend/app/db/seed_tiers.py`, `backend/app/db/seed_entity_classes.py` | L |
| S1-B | Auth Middleware & Supabase Client | Auth/Contracts | 1 | S0-A, S0-B | `backend/app/auth/__init__.py`, `backend/app/auth/supabase_client.py`, `backend/app/auth/jwt_verifier.py`, `backend/app/auth/middleware.py`, `backend/app/auth/dependencies.py`, `backend/app/auth/permissions.py` (role matrix from §1.3), `backend/app/auth/brute_force.py`, `tests/integration/test_auth_middleware.py` | M |
| S1-C | Storage & Hash Utilities | Infrastructure | 1 | S0-A, S0-B | `backend/app/storage/__init__.py`, `backend/app/storage/s3_client.py`, `backend/app/storage/presigned.py`, `backend/app/storage/hashing.py`, `backend/app/storage/blocklist.py`, `tests/integration/test_storage.py` | M |
| S1-D | Redis, Cache, Pub/Sub & Celery Config | Real-time/Queue | 1 | S0-A, S0-B | `backend/app/redis/__init__.py`, `backend/app/redis/client.py`, `backend/app/redis/cache.py` (subscription flags, entity taxonomy), `backend/app/redis/pubsub.py` (drawing:status channels), `backend/app/workers/queues.py` (queue routing config), `backend/app/workers/base.py` (Task base class with retry policy), `tests/integration/test_redis_pubsub.py` | M |
| S1-E | Analytics Emitter (PostHog) | Infrastructure | 1 | S0-A, S0-B | `backend/app/analytics/__init__.py`, `backend/app/analytics/posthog_client.py`, `backend/app/analytics/events.py` (typed emitters for all 9 events §1.10), `backend/app/analytics/dead_letter.py`, `tests/integration/test_analytics.py` | S |
| S1-F | Frontend Shared Infrastructure | Frontend | 1 | S0-A, S0-B | `frontend/src/api/client.ts`, `frontend/src/api/endpoints.ts`, `frontend/src/auth/AuthContext.tsx`, `frontend/src/auth/useAuth.ts`, `frontend/src/auth/supabaseClient.ts`, `frontend/src/hooks/useSSE.ts`, `frontend/src/hooks/usePolling.ts`, `frontend/src/components/Layout.tsx`, `frontend/src/components/Nav.tsx`, `frontend/src/components/GraceBanner.tsx`, `frontend/src/components/ProtectedRoute.tsx`, `frontend/src/lib/storage.ts` (localStorage/sessionStorage helpers), `frontend/src/lib/analytics.ts`, `frontend/src/styles/globals.css` | M |
| S2-A | Auth Endpoints | Auth/Contracts | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/auth.py`, `backend/app/services/auth_service.py`, `backend/app/services/password_reset.py`, `tests/integration/test_auth_endpoints.py` | M |
| S2-B | Drawings Endpoints + SSE Status | Backend API | 2 | S1-A, S1-B, S1-C, S1-D, S1-E | `backend/app/api/routers/drawings.py`, `backend/app/services/drawing_service.py`, `backend/app/services/hash_check_service.py`, `backend/app/services/upload_complete_service.py`, `backend/app/services/drawing_state_machine.py`, `backend/app/services/free_tier_counter.py`, `backend/app/sse/drawing_status.py`, `tests/integration/test_drawings_api.py`, `tests/integration/test_drawings_sse.py` | L |
| S2-C | Symbols & Corrections Endpoints | Backend API | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/symbols.py`, `backend/app/services/symbol_service.py`, `backend/app/services/correction_service.py` (training_consent snapshot, Under_Review trigger), `tests/integration/test_symbols_api.py` | M |
| S2-D | Export Endpoints + Sync Path | Backend API | 2 | S1-A, S1-B, S1-C, S1-D, S1-E | `backend/app/api/routers/exports.py`, `backend/app/services/export_service.py` (sync <1000 path, threshold gate), `backend/app/services/export_generators.py` (CSV/XLSX), `tests/integration/test_exports_api.py` | M |
| S2-E | Subscription + Stripe Webhook | Backend API | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/subscription.py`, `backend/app/api/routers/stripe_webhook.py`, `backend/app/services/stripe_client.py`, `backend/app/services/subscription_service.py`, `backend/app/services/billing_state_machine.py`, `backend/app/services/stripe_event_idempotency.py`, `tests/integration/test_subscription.py`, `tests/integration/test_stripe_webhook.py` | L |
| S2-F | Account, Consent & GDPR Init Endpoints | Backend API | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/account.py`, `backend/app/services/account_service.py`, `backend/app/services/consent_service.py` (server-side team consent resolution), `backend/app/services/gdpr_init_service.py`, `tests/integration/test_account.py` | M |
| S2-G | Entity Classes & Misc Endpoints | Backend API | 2 | S1-A, S1-D | `backend/app/api/routers/entity_classes.py`, `backend/app/services/entity_class_service.py`, `tests/integration/test_entity_classes.py` | S |
| S2-H | Ingest Worker | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/ingest/__init__.py`, `backend/app/workers/ingest/tasks.py`, `backend/app/workers/ingest/oda_converter.py`, `backend/app/workers/ingest/hash_reverify.py`, `backend/app/workers/ingest/format_detect.py`, `tests/integration/test_ingest_worker.py` | L |
| S2-I | Scan Worker (ClamAV) | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/scan/__init__.py`, `backend/app/workers/scan/tasks.py`, `backend/app/workers/scan/clamav_client.py`, `tests/integration/test_scan_worker.py` | S |
| S2-J | ML Worker | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/ml/__init__.py`, `backend/app/workers/ml/tasks.py`, `backend/app/workers/ml/inference.py`, `backend/app/workers/ml/model_loader.py`, `backend/app/workers/ml/result_persistence.py`, `tests/integration/test_ml_worker.py` | L |
| S2-K | Export Worker (Async) | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/export/__init__.py`, `backend/app/workers/export/tasks.py`, `tests/integration/test_export_worker.py` | M |
| S2-L | GDPR Erasure Worker | Real-time/Queue | 2 | S1-A, S1-C, S1-D | `backend/app/workers/gdpr/__init__.py`, `backend/app/workers/gdpr/tasks.py`, `backend/app/workers/gdpr/anonymizer.py` (anonymous_id HMAC, idempotent), `tests/integration/test_gdpr_worker.py` | M |
| S2-M | Notification Worker (SendGrid) | Real-time/Queue | 2 | S1-A, S1-D | `backend/app/workers/notification/__init__.py`, `backend/app/workers/notification/tasks.py`, `backend/app/workers/notification/sendgrid_client.py`, `backend/app/workers/notification/templates.py` (verification, reset, invite, grace day-1/6), `tests/integration/test_notification_worker.py` | M |
| S3-A | Frontend: Auth Pages | Frontend | 3 | S1-F, S2-A | `frontend/src/pages/auth/Register.tsx`, `frontend/src/pages/auth/Login.tsx`, `frontend/src/pages/auth/VerifyEmail.tsx`, `frontend/src/pages/auth/PasswordResetRequest.tsx`, `frontend/src/pages/auth/PasswordResetConfirm.tsx`, `frontend/src/pages/auth/OAuthCallback.tsx`, `frontend/src/pages/auth/AccountLinkPrompt.tsx` | M |
| S3-B | Frontend: Drawing Library | Frontend | 3 | S1-F, S2-B | `frontend/src/pages/Dashboard.tsx`, `frontend/src/features/library/DrawingList.tsx`, `frontend/src/features/library/DrawingRow.tsx`, `frontend/src/features/library/StatusBadge.tsx`, `frontend/src/features/library/SearchFilter.tsx`, `frontend/src/features/library/Pagination.tsx`, `frontend/src/features/library/useDrawings.ts` | M |
| S3-C | Frontend: Upload Flow | Frontend | 3 | S1-F, S2-B | `frontend/src/pages/Upload.tsx`, `frontend/src/features/upload/DropZone.tsx`, `frontend/src/features/upload/hashClient.ts`, `frontend/src/features/upload/uploadOrchestrator.ts`, `frontend/src/features/upload/UploadProgress.tsx` | M |
| S3-D | Frontend: Review Canvas (Konva) | Frontend | 3 | S1-F, S2-B, S2-C | `frontend/src/pages/Review.tsx`, `frontend/src/features/canvas/Canvas.tsx`, `frontend/src/features/canvas/SymbolLayer.tsx`, `frontend/src/features/canvas/BoundingBox.tsx`, `frontend/src/features/canvas/PageNav.tsx`, `frontend/src/features/canvas/InspectionPanel.tsx`, `frontend/src/features/canvas/ManualAnnotate.tsx`, `frontend/src/features/canvas/CorrectionStore.ts`, `frontend/src/features/canvas/useCanvasShortcuts.ts` | L |
| S3-E | Frontend: Account & Consent | Frontend | 3 | S1-F, S2-F | `frontend/src/pages/Account.tsx`, `frontend/src/features/account/ProfileForm.tsx`, `frontend/src/features/account/ConsentToggle.tsx`, `frontend/src/features/account/DeleteAccount.tsx` | S |
| S3-F | Frontend: Subscription & Upgrade | Frontend | 3 | S1-F, S2-E | `frontend/src/pages/Subscription.tsx`, `frontend/src/features/subscription/TierCard.tsx`, `frontend/src/features/subscription/CheckoutRedirect.tsx`, `frontend/src/features/subscription/UpgradePrompt.tsx`, `frontend/src/features/subscription/PendingState.tsx` | M |
| S3-G | Frontend: Exports UI + Notifications | Frontend | 3 | S1-F, S2-D | `frontend/src/features/exports/ExportButton.tsx`, `frontend/src/features/exports/ExportModal.tsx`, `frontend/src/features/exports/useExportStatus.ts`, `frontend/src/features/notifications/InAppNotifications.tsx`, `frontend/src/features/notifications/notificationsStore.ts` | M |
| S3-H | Marketing Site (Next.js) | Frontend | 3 | S0-A | `marketing/app/(marketing)/page.tsx`, `marketing/app/pricing/page.tsx`, `marketing/app/about/page.tsx`, `marketing/app/contact/page.tsx`, `marketing/components/Hero.tsx`, `marketing/components/PricingTable.tsx`, `marketing/components/Footer.tsx`, `marketing/public/robots.txt`, `marketing/public/sitemap.xml` | M |
| S4-A | E2E Integration Tests | Testing/Hardening | 4 | All Phase 2 + Phase 3 | `tests/integration/e2e/test_upload_to_complete.py`, `tests/integration/e2e/test_correction_flow.py`, `tests/integration/e2e/test_export_sync_and_async.py`, `tests/integration/e2e/test_stripe_lifecycle.py`, `tests/integration/e2e/test_gdpr_erasure.py`, `tests/integration/e2e/test_blocklist_two_gate.py`, `tests/integration/e2e/test_free_tier_limit.py` | L |

---

## Gate Definitions

**Phase 0 → Phase 1 gate** (must merge): `S0-A`, `S0-B`. Both required: scaffold provides stubs every Phase 1 session imports; harness provides the green integration baseline (`npm run test:integration` exits 0).

**Phase 1 → Phase 2 gate** (must merge): `S1-A`, `S1-B`, `S1-C`, `S1-D`, `S1-E`. Non-blocking for Phase 2 backend work: `S1-F` (frontend-only; gates Phase 3 only).

**Phase 2 → Phase 3 gate** (must merge per frontend session): each Phase 3 session depends only on its specific Phase 2 endpoint(s) — see prerequisites column. Marketing (`S3-H`) needs only Phase 0.

**Phase 3 → Phase 4 gate** (must merge): all Phase 2 + Phase 3 sessions.

---

## Intra-Phase Dependencies

None within Phase 1 (all five core infra sessions are parallel; they only import from S0-A stubs).

None within Phase 2 — workers and API routers own disjoint files. They communicate only through Celery queues / Redis channels / DB tables defined in Phase 1.

None within Phase 3 — each frontend feature owns its own subdirectory.

---

## Early-Start Optimizations

- **S1-F (frontend shared)** depends only on `S0-A`/`S0-B` — can start with Phase 1 even though it gates Phase 3 frontends.
- **S3-H (marketing site)** depends only on `S0-A` — can start as early as Phase 1.
- **S2-G (entity classes)** needs only `S1-A` + `S1-D`, can start as soon as those two merge (before S1-B/C/E).
- **S2-L (GDPR worker)** and **S2-M (notification worker)** don't need `S1-E` analytics — can start once `S1-A`/`S1-C`/`S1-D` clear.
- **S3-A (auth pages)** can begin as soon as `S2-A` clears, regardless of other Phase 2 progress.

---

## Critical Path

`S0-A` → `S1-A` (DB models) → `S2-B` (Drawings API + SSE) → `S3-D` (Review canvas — largest frontend) → `S4-A` (E2E tests)

Length: 5 sessions, complexity L → L → L → L → L ≈ 15 hrs of Claude execution on the longest chain.

---

```json
[
  {"id":"S0-A","phase":0,"name":"Scaffold & Shared Stubs","category":"Infrastructure","prerequisites":[],"ownedFiles":["backend/app/main.py","backend/app/config.py","backend/app/db/base.py","backend/app/db/session.py","backend/app/api/__init__.py","backend/app/api/routers/__init__.py","backend/app/api/routers/_stubs.py","backend/app/workers/celery_app.py","backend/app/workers/__init__.py","backend/app/schemas/contracts.py","backend/app/schemas/__init__.py","backend/alembic.ini","backend/alembic/env.py","backend/alembic/script.py.mako","backend/Dockerfile","backend/Dockerfile.worker","backend/Dockerfile.ml","frontend/index.html","frontend/vite.config.ts","frontend/tsconfig.json","frontend/src/main.tsx","frontend/src/App.tsx","frontend/src/router.tsx","frontend/src/pages/_stubs.tsx","frontend/src/types/contracts.ts","marketing/next.config.js","marketing/tsconfig.json","marketing/app/layout.tsx","marketing/app/page.tsx","docker-compose.yml","docker-compose.test.yml",".env.example","README.md","ops/oda-sandbox/Dockerfile","ops/clamav/Dockerfile"],"complexity":"L","specSections":["1.1 Shared Contracts","1.6 Route Manifest","1.8 Technology Stack","1.12 Environment Variable Schema"]},
  {"id":"S0-B","phase":0,"name":"Integration Harness & Manifests","category":"Testing/Hardening","prerequisites":[],"ownedFiles":["package.json","backend/pyproject.toml","backend/poetry.lock","frontend/package.json","marketing/package.json","tests/integration/conftest.py","tests/integration/docker-compose.fixtures.yml","tests/integration/fixtures/db.py","tests/integration/fixtures/redis.py","tests/integration/fixtures/s3.py","tests/integration/smoke/test_smoke.py","tests/integration/README.md","scripts/test-integration.sh",".github/workflows/integration.yml"],"complexity":"M","specSections":["1.8 Technology Stack","1.12 Environment Variable Schema"]},
  {"id":"S1-A","phase":1,"name":"DB Models & Migrations","category":"Infrastructure","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/db/models/__init__.py","backend/app/db/models/user.py","backend/app/db/models/team.py","backend/app/db/models/tier.py","backend/app/db/models/subscription.py","backend/app/db/models/stored_file.py","backend/app/db/models/file_hash_blocklist.py","backend/app/db/models/drawing.py","backend/app/db/models/entity_class.py","backend/app/db/models/detected_symbol.py","backend/app/db/models/table_cell.py","backend/app/db/models/user_correction.py","backend/app/db/models/export_record.py","backend/app/db/models/ml_training_consent.py","backend/app/db/models/revision_comparison.py","backend/app/db/models/audit_log.py","backend/app/db/models/stripe_event.py","backend/alembic/versions/0001_initial_schema.py","backend/alembic/versions/0002_rls_policies.py","backend/alembic/versions/0003_audit_partitions.py","backend/app/db/seed_tiers.py","backend/app/db/seed_entity_classes.py"],"complexity":"L","specSections":["1.2 Database Schema","1.3 State Machines and Permission Matrices"]},
  {"id":"S1-B","phase":1,"name":"Auth Middleware & Supabase Client","category":"Auth/Contracts","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/auth/__init__.py","backend/app/auth/supabase_client.py","backend/app/auth/jwt_verifier.py","backend/app/auth/middleware.py","backend/app/auth/dependencies.py","backend/app/auth/permissions.py","backend/app/auth/brute_force.py","tests/integration/test_auth_middleware.py"],"complexity":"M","specSections":["1.3 State Machines and Permission Matrices","1.4 Critical Ordering Rules","1.7 Third-Party Dependencies"]},
  {"id":"S1-C","phase":1,"name":"Storage & Hash Utilities","category":"Infrastructure","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/storage/__init__.py","backend/app/storage/s3_client.py","backend/app/storage/presigned.py","backend/app/storage/hashing.py","backend/app/storage/blocklist.py","tests/integration/test_storage.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.7 Third-Party Dependencies","1.9 Performance Targets"]},
  {"id":"S1-D","phase":1,"name":"Redis, Cache, Pub/Sub & Celery Config","category":"Real-time/Queue","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/redis/__init__.py","backend/app/redis/client.py","backend/app/redis/cache.py","backend/app/redis/pubsub.py","backend/app/workers/queues.py","backend/app/workers/base.py","tests/integration/test_redis_pubsub.py"],"complexity":"M","specSections":["1.11 Cross-Session Runtime Patterns","1.8 Technology Stack"]},
  {"id":"S1-E","phase":1,"name":"Analytics Emitter (PostHog)","category":"Infrastructure","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/analytics/__init__.py","backend/app/analytics/posthog_client.py","backend/app/analytics/events.py","backend/app/analytics/dead_letter.py","tests/integration/test_analytics.py"],"complexity":"S","specSections":["1.10 Analytics Event Contracts"]},
  {"id":"S1-F","phase":1,"name":"Frontend Shared Infrastructure","category":"Frontend","prerequisites":["S0-A","S0-B"],"ownedFiles":["frontend/src/api/client.ts","frontend/src/api/endpoints.ts","frontend/src/auth/AuthContext.tsx","frontend/src/auth/useAuth.ts","frontend/src/auth/supabaseClient.ts","frontend/src/hooks/useSSE.ts","frontend/src/hooks/usePolling.ts","frontend/src/components/Layout.tsx","frontend/src/components/Nav.tsx","frontend/src/components/GraceBanner.tsx","frontend/src/components/ProtectedRoute.tsx","frontend/src/lib/storage.ts","frontend/src/lib/analytics.ts","frontend/src/styles/globals.css"],"complexity":"M","specSections":["1.1 Shared Contracts","1.6 Route Manifest","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-A","phase":2,"name":"Auth Endpoints","category":"Auth/Contracts","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/auth.py","backend/app/services/auth_service.py","backend/app/services/password_reset.py","tests/integration/test_auth_endpoints.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.6 Route Manifest","1.13 Feature Scope"]},
  {"id":"S2-B","phase":2,"name":"Drawings Endpoints + SSE Status","category":"Backend API","prerequisites":["S1-A","S1-B","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/drawings.py","backend/app/services/drawing_service.py","backend/app/services/hash_check_service.py","backend/app/services/upload_complete_service.py","backend/app/services/drawing_state_machine.py","backend/app/services/free_tier_counter.py","backend/app/sse/drawing_status.py","tests/integration/test_drawings_api.py","tests/integration/test_drawings_sse.py"],"complexity":"L","specSections":["1.3 State Machines and Permission Matrices","1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.6 Route Manifest","1.10 Analytics Event Contracts","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-C","phase":2,"name":"Symbols & Corrections Endpoints","category":"Backend API","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/symbols.py","backend/app/services/symbol_service.py","backend/app/services/correction_service.py","tests/integration/test_symbols_api.py"],"complexity":"M","specSections":["1.1 Shared Contracts","1.4 Critical Ordering Rules","1.10 Analytics Event Contracts","1.13 Feature Scope"]},
  {"id":"S2-D","phase":2,"name":"Export Endpoints + Sync Path","category":"Backend API","prerequisites":["S1-A","S1-B","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/exports.py","backend/app/services/export_service.py","backend/app/services/export_generators.py","tests/integration/test_exports_api.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.6 Route Manifest","1.9 Performance Targets","1.10 Analytics Event Contracts"]},
  {"id":"S2-E","phase":2,"name":"Subscription + Stripe Webhook","category":"Backend API","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/subscription.py","backend/app/api/routers/stripe_webhook.py","backend/app/services/stripe_client.py","backend/app/services/subscription_service.py","backend/app/services/billing_state_machine.py","backend/app/services/stripe_event_idempotency.py","tests/integration/test_subscription.py","tests/integration/test_stripe_webhook.py"],"complexity":"L","specSections":["1.3 State Machines and Permission Matrices","1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.7 Third-Party Dependencies","1.10 Analytics Event Contracts"]},
  {"id":"S2-F","phase":2,"name":"Account, Consent & GDPR Init Endpoints","category":"Backend API","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/account.py","backend/app/services/account_service.py","backend/app/services/consent_service.py","backend/app/services/gdpr_init_service.py","tests/integration/test_account.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.13 Feature Scope"]},
  {"id":"S2-G","phase":2,"name":"Entity Classes & Misc Endpoints","category":"Backend API","prerequisites":["S1-A","S1-D"],"ownedFiles":["backend/app/api/routers/entity_classes.py","backend/app/services/entity_class_service.py","tests/integration/test_entity_classes.py"],"complexity":"S","specSections":["1.6 Route Manifest","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-H","phase":2,"name":"Ingest Worker","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/ingest/__init__.py","backend/app/workers/ingest/tasks.py","backend/app/workers/ingest/oda_converter.py","backend/app/workers/ingest/hash_reverify.py","backend/app/workers/ingest/format_detect.py","tests/integration/test_ingest_worker.py"],"complexity":"L","specSections":["1.4 Critical Ordering Rules","1.7 Third-Party Dependencies","1.11 Cross-Session Runtime Patterns","1.13 Feature Scope"]},
  {"id":"S2-I","phase":2,"name":"Scan Worker (ClamAV)","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/scan/__init__.py","backend/app/workers/scan/tasks.py","backend/app/workers/scan/clamav_client.py","tests/integration/test_scan_worker.py"],"complexity":"S","specSections":["1.7 Third-Party Dependencies","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-J","phase":2,"name":"ML Worker","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/ml/__init__.py","backend/app/workers/ml/tasks.py","backend/app/workers/ml/inference.py","backend/app/workers/ml/model_loader.py","backend/app/workers/ml/result_persistence.py","tests/integration/test_ml_worker.py"],"complexity":"L","specSections":["1.1 Shared Contracts","1.4 Critical Ordering Rules","1.9 Performance Targets","1.10 Analytics Event Contracts","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-K","phase":2,"name":"Export Worker (Async)","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/export/__init__.py","backend/app/workers/export/tasks.py","tests/integration/test_export_worker.py"],"complexity":"M","specSections":["1.9 Performance Targets","1.11 Cross-Session Runtime Patterns","1.13 Feature Scope"]},
  {"id":"S2-L","phase":2,"name":"GDPR Erasure Worker","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D"],"ownedFiles":["backend/app/workers/gdpr/__init__.py","backend/app/workers/gdpr/tasks.py","backend/app/workers/gdpr/anonymizer.py","tests/integration/test_gdpr_worker.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.11 Cross-Session Runtime Patterns","1.12 Environment Variable Schema","1.13 Feature Scope"]},
  {"id":"S2-M","phase":2,"name":"Notification Worker (SendGrid)","category":"Real-time/Queue","prerequisites":["S1-A","S1-D"],"ownedFiles":["backend/app/workers/notification/__init__.py","backend/app/workers/notification/tasks.py","backend/app/workers/notification/sendgrid_client.py","backend/app/workers/notification/templates.py","tests/integration/test_notification_worker.py"],"complexity":"M","specSections":["1.3 State Machines and Permission Matrices","1.7 Third-Party Dependencies","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S3-A","phase":3,"name":"Frontend: Auth Pages","category":"Frontend","prerequisites":["S1-F","S2-A"],"ownedFiles":["frontend/src/pages/auth/Register.tsx","frontend/src/pages/auth/Login.tsx","frontend/src/pages/auth/VerifyEmail.tsx","frontend/src/pages/auth/PasswordResetRequest.tsx","frontend/src/pages/auth/PasswordResetConfirm.tsx","frontend/src/pages/auth/OAuthCallback.tsx","frontend/src/pages/auth/AccountLinkPrompt.tsx"],"complexity":"M","specSections":["1.6 Route Manifest","1.13 Feature Scope"]},
  {"id":"S3-B","phase":3,"name":"Frontend: Drawing Library","category":"Frontend","prerequisites":["S1-F","S2-B"],"ownedFiles":["frontend/src/pages/Dashboard.tsx","frontend/src/features/library/DrawingList.tsx","frontend/src/features/library/DrawingRow.tsx","frontend/src/features/library/StatusBadge.tsx","frontend/src/features/library/SearchFilter.tsx","frontend/src/features/library/Pagination.tsx","frontend/src/features/library/useDrawings.ts"],"complexity":"M","specSections":["1.6 Route Manifest","1.9 Performance Targets","1.13 Feature Scope"]},
  {"id":"S3-C","phase":3,"name":"Frontend: Upload Flow","category":"Frontend","prerequisites":["S1-F","S2-B"],"ownedFiles":["frontend/src/pages/Upload.tsx","frontend/src/features/upload/DropZone.tsx","frontend/src/features/upload/hashClient.ts","frontend/src/features/upload/uploadOrchestrator.ts","frontend/src/features/upload/UploadProgress.tsx"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.13 Feature Scope"]},
  {"id":"S3-D","phase":3,"name":"Frontend: Review Canvas (Konva)","category":"Frontend","prerequisites":["S1-F","S2-B","S2-C"],"ownedFiles":["frontend/src/pages/Review.tsx","frontend/src/features/canvas/Canvas.tsx","frontend/src/features/canvas/SymbolLayer.tsx","frontend/src/features/canvas/BoundingBox.tsx","frontend/src/features/canvas/PageNav.tsx","frontend/src/features/canvas/InspectionPanel.tsx","frontend/src/features/canvas/ManualAnnotate.tsx","frontend/src/features/canvas/CorrectionStore.ts","frontend/src/features/canvas/useCanvasShortcuts.ts"],"complexity":"L","specSections":["1.6 Route Manifest","1.8 Technology Stack","1.9 Performance Targets","1.11 Cross-Session Runtime Patterns","1.13 Feature Scope"]},
  {"id":"S3-E","phase":3,"name":"Frontend: Account & Consent","category":"Frontend","prerequisites":["S1-F","S2-F"],"ownedFiles":["frontend/src/pages/Account.tsx","frontend/src/features/account/ProfileForm.tsx","frontend/src/features/account/ConsentToggle.tsx","frontend/src/features/account/DeleteAccount.tsx"],"complexity":"S","specSections":["1.6 Route Manifest","1.13 Feature Scope"]},
  {"id":"S3-F","phase":3,"name":"Frontend: Subscription & Upgrade","category":"Frontend","prerequisites":["S1-F","S2-E"],"ownedFiles":["frontend/src/pages/Subscription.tsx","frontend/src/features/subscription/TierCard.tsx","frontend/src/features/subscription/CheckoutRedirect.tsx","frontend/src/features/subscription/UpgradePrompt.tsx","frontend/src/features/subscription/PendingState.tsx"],"complexity":"M","specSections":["1.3 State Machines and Permission Matrices","1.6 Route Manifest","1.9 Performance Targets","1.13 Feature Scope"]},
  {"id":"S3-G","phase":3,"name":"Frontend: Exports UI + Notifications","category":"Frontend","prerequisites":["S1-F","S2-D"],"ownedFiles":["frontend/src/features/exports/ExportButton.tsx","frontend/src/features/exports/ExportModal.tsx","frontend/src/features/exports/useExportStatus.ts","frontend/src/features/notifications/InAppNotifications.tsx","frontend/src/features/notifications/notificationsStore.ts"],"complexity":"M","specSections":["1.9 Performance Targets","1.13 Feature Scope"]},
  {"id":"S3-H","phase":3,"name":"Marketing Site (Next.js)","category":"Frontend","prerequisites":["S0-A"],"ownedFiles":["marketing/app/(marketing)/page.tsx","marketing/app/pricing/page.tsx","marketing/app/about/page.tsx","marketing/app/contact/page.tsx","marketing/components/Hero.tsx","marketing/components/PricingTable.tsx","marketing/components/Footer.tsx","marketing/public/robots.txt","marketing/public/sitemap.xml"],"complexity":"M","specSections":["1.8 Technology Stack"]},
  {"id":"S4-A","phase":4,"name":"E2E Integration Tests","category":"Testing/Hardening","prerequisites":["S2-A","S2-B","S2-C","S2-D","S2-E","S2-F","S2-G","S2-H","S2-I","S2-J","S2-K","S2-L","S2-M","S3-A","S3-B","S3-C","S3-D","S3-E","S3-F","S3-G"],"ownedFiles":["tests/integration/e2e/test_upload_to_complete.py","tests/integration/e2e/test_correction_flow.py","tests/integration/e2e/test_export_sync_and_async.py","tests/integration/e2e/test_stripe_lifecycle.py","tests/integration/e2e/test_gdpr_erasure.py","tests/integration/e2e/test_blocklist_two_gate.py","tests/integration/e2e/test_free_tier_limit.py"],"complexity":"L","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.10 Analytics Event Contracts","1.13 Feature Scope"]}
]
```

Total: 30 sessions across 5 phases
```

---

### build-plan-mermaid-diagram [primary]

**System Prompt:**
```
You are generating a Mermaid build order diagram for an autonomous build plan. Using the session table provided (no other documents needed), produce a single Mermaid diagram:

```mermaid
graph TD
```

Requirements:
- One labeled subgraph per phase
- One gate node per phase transition — labeled with required sessions and explicitly noting non-blocking sessions
- Every session as a node showing ID and short name
- Intra-phase dependency arrows shown within the subgraph
- Dashed arrows labeled "early start allowed" for early-start optimizations

CRITICAL — keep the diagram compact to avoid truncation:
- **Group parallel sessions**: When a phase has more than 5 parallel sessions with the same prerequisites, group them into a single composite node. Example: instead of 20 individual S2-A through S2-T nodes each with arrows from the gate, create grouped nodes by category:
  - `S2_API["S2-A thru S2-J: Backend APIs (10 parallel)"]`
  - `S2_WORKERS["S2-K thru S2-N: Workers (4 parallel)"]`
  - `S2_FE["S2-O thru S2-T: Frontend Pages (6 parallel)"]`
- Only draw ONE arrow from a gate to each group node, and ONE arrow from each group node to the next gate
- Sessions with unique dependencies (not shared with their group) should remain as individual nodes
- Phases with 5 or fewer sessions should show all sessions individually

This grouping keeps the diagram readable and prevents token exhaustion on large projects. A diagram with 80+ individual arrows is neither useful nor renderable.

Ensure the diagram is syntactically valid Mermaid that will render without errors. Close all subgraphs and the code fence.
```

**User Message:**
```
# PID Analyzer — Session Decomposition

| ID | Name | Category | Phase | Prerequisites | Owned files (exhaustive) | Complexity |
| -- | ---- | -------- | ----- | ------------- | ------------------------ | ---------- |
| S0-A | Scaffold & Shared Stubs | Infrastructure | 0 | — | `backend/app/main.py`, `backend/app/config.py`, `backend/app/db/base.py`, `backend/app/db/session.py`, `backend/app/api/__init__.py`, `backend/app/api/routers/__init__.py` (all router include stubs), `backend/app/api/routers/_stubs.py` (placeholder endpoints for every route in §1.6 P0+P1), `backend/app/workers/celery_app.py`, `backend/app/workers/__init__.py`, `backend/app/schemas/contracts.py` (pydantic mirrors of §1.1), `backend/app/schemas/__init__.py`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/Dockerfile`, `backend/Dockerfile.worker`, `backend/Dockerfile.ml`, `frontend/index.html`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/router.tsx` (lazy route stubs for all SPA pages), `frontend/src/pages/_stubs.tsx`, `frontend/src/types/contracts.ts`, `marketing/next.config.js`, `marketing/tsconfig.json`, `marketing/app/layout.tsx`, `marketing/app/page.tsx`, `docker-compose.yml`, `docker-compose.test.yml`, `.env.example`, `README.md`, `ops/oda-sandbox/Dockerfile`, `ops/clamav/Dockerfile` | L |
| S0-B | Integration Harness & Manifests | Testing/Hardening | 0 | — | `package.json` (root workspace), `backend/pyproject.toml`, `backend/poetry.lock`, `frontend/package.json`, `marketing/package.json`, `tests/integration/conftest.py`, `tests/integration/docker-compose.fixtures.yml`, `tests/integration/fixtures/db.py`, `tests/integration/fixtures/redis.py`, `tests/integration/fixtures/s3.py`, `tests/integration/smoke/test_smoke.py`, `tests/integration/README.md`, `scripts/test-integration.sh`, `.github/workflows/integration.yml` | M |
| S1-A | DB Models & Migrations | Infrastructure | 1 | S0-A, S0-B | `backend/app/db/models/__init__.py`, `backend/app/db/models/user.py`, `backend/app/db/models/team.py`, `backend/app/db/models/tier.py`, `backend/app/db/models/subscription.py`, `backend/app/db/models/stored_file.py`, `backend/app/db/models/file_hash_blocklist.py`, `backend/app/db/models/drawing.py`, `backend/app/db/models/entity_class.py`, `backend/app/db/models/detected_symbol.py`, `backend/app/db/models/table_cell.py`, `backend/app/db/models/user_correction.py`, `backend/app/db/models/export_record.py`, `backend/app/db/models/ml_training_consent.py`, `backend/app/db/models/revision_comparison.py`, `backend/app/db/models/audit_log.py`, `backend/app/db/models/stripe_event.py`, `backend/alembic/versions/0001_initial_schema.py`, `backend/alembic/versions/0002_rls_policies.py`, `backend/alembic/versions/0003_audit_partitions.py`, `backend/app/db/seed_tiers.py`, `backend/app/db/seed_entity_classes.py` | L |
| S1-B | Auth Middleware & Supabase Client | Auth/Contracts | 1 | S0-A, S0-B | `backend/app/auth/__init__.py`, `backend/app/auth/supabase_client.py`, `backend/app/auth/jwt_verifier.py`, `backend/app/auth/middleware.py`, `backend/app/auth/dependencies.py`, `backend/app/auth/permissions.py` (role matrix from §1.3), `backend/app/auth/brute_force.py`, `tests/integration/test_auth_middleware.py` | M |
| S1-C | Storage & Hash Utilities | Infrastructure | 1 | S0-A, S0-B | `backend/app/storage/__init__.py`, `backend/app/storage/s3_client.py`, `backend/app/storage/presigned.py`, `backend/app/storage/hashing.py`, `backend/app/storage/blocklist.py`, `tests/integration/test_storage.py` | M |
| S1-D | Redis, Cache, Pub/Sub & Celery Config | Real-time/Queue | 1 | S0-A, S0-B | `backend/app/redis/__init__.py`, `backend/app/redis/client.py`, `backend/app/redis/cache.py` (subscription flags, entity taxonomy), `backend/app/redis/pubsub.py` (drawing:status channels), `backend/app/workers/queues.py` (queue routing config), `backend/app/workers/base.py` (Task base class with retry policy), `tests/integration/test_redis_pubsub.py` | M |
| S1-E | Analytics Emitter (PostHog) | Infrastructure | 1 | S0-A, S0-B | `backend/app/analytics/__init__.py`, `backend/app/analytics/posthog_client.py`, `backend/app/analytics/events.py` (typed emitters for all 9 events §1.10), `backend/app/analytics/dead_letter.py`, `tests/integration/test_analytics.py` | S |
| S1-F | Frontend Shared Infrastructure | Frontend | 1 | S0-A, S0-B | `frontend/src/api/client.ts`, `frontend/src/api/endpoints.ts`, `frontend/src/auth/AuthContext.tsx`, `frontend/src/auth/useAuth.ts`, `frontend/src/auth/supabaseClient.ts`, `frontend/src/hooks/useSSE.ts`, `frontend/src/hooks/usePolling.ts`, `frontend/src/components/Layout.tsx`, `frontend/src/components/Nav.tsx`, `frontend/src/components/GraceBanner.tsx`, `frontend/src/components/ProtectedRoute.tsx`, `frontend/src/lib/storage.ts` (localStorage/sessionStorage helpers), `frontend/src/lib/analytics.ts`, `frontend/src/styles/globals.css` | M |
| S2-A | Auth Endpoints | Auth/Contracts | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/auth.py`, `backend/app/services/auth_service.py`, `backend/app/services/password_reset.py`, `tests/integration/test_auth_endpoints.py` | M |
| S2-B | Drawings Endpoints + SSE Status | Backend API | 2 | S1-A, S1-B, S1-C, S1-D, S1-E | `backend/app/api/routers/drawings.py`, `backend/app/services/drawing_service.py`, `backend/app/services/hash_check_service.py`, `backend/app/services/upload_complete_service.py`, `backend/app/services/drawing_state_machine.py`, `backend/app/services/free_tier_counter.py`, `backend/app/sse/drawing_status.py`, `tests/integration/test_drawings_api.py`, `tests/integration/test_drawings_sse.py` | L |
| S2-C | Symbols & Corrections Endpoints | Backend API | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/symbols.py`, `backend/app/services/symbol_service.py`, `backend/app/services/correction_service.py` (training_consent snapshot, Under_Review trigger), `tests/integration/test_symbols_api.py` | M |
| S2-D | Export Endpoints + Sync Path | Backend API | 2 | S1-A, S1-B, S1-C, S1-D, S1-E | `backend/app/api/routers/exports.py`, `backend/app/services/export_service.py` (sync <1000 path, threshold gate), `backend/app/services/export_generators.py` (CSV/XLSX), `tests/integration/test_exports_api.py` | M |
| S2-E | Subscription + Stripe Webhook | Backend API | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/subscription.py`, `backend/app/api/routers/stripe_webhook.py`, `backend/app/services/stripe_client.py`, `backend/app/services/subscription_service.py`, `backend/app/services/billing_state_machine.py`, `backend/app/services/stripe_event_idempotency.py`, `tests/integration/test_subscription.py`, `tests/integration/test_stripe_webhook.py` | L |
| S2-F | Account, Consent & GDPR Init Endpoints | Backend API | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/account.py`, `backend/app/services/account_service.py`, `backend/app/services/consent_service.py` (server-side team consent resolution), `backend/app/services/gdpr_init_service.py`, `tests/integration/test_account.py` | M |
| S2-G | Entity Classes & Misc Endpoints | Backend API | 2 | S1-A, S1-D | `backend/app/api/routers/entity_classes.py`, `backend/app/services/entity_class_service.py`, `tests/integration/test_entity_classes.py` | S |
| S2-H | Ingest Worker | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/ingest/__init__.py`, `backend/app/workers/ingest/tasks.py`, `backend/app/workers/ingest/oda_converter.py`, `backend/app/workers/ingest/hash_reverify.py`, `backend/app/workers/ingest/format_detect.py`, `tests/integration/test_ingest_worker.py` | L |
| S2-I | Scan Worker (ClamAV) | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/scan/__init__.py`, `backend/app/workers/scan/tasks.py`, `backend/app/workers/scan/clamav_client.py`, `tests/integration/test_scan_worker.py` | S |
| S2-J | ML Worker | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/ml/__init__.py`, `backend/app/workers/ml/tasks.py`, `backend/app/workers/ml/inference.py`, `backend/app/workers/ml/model_loader.py`, `backend/app/workers/ml/result_persistence.py`, `tests/integration/test_ml_worker.py` | L |
| S2-K | Export Worker (Async) | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/export/__init__.py`, `backend/app/workers/export/tasks.py`, `tests/integration/test_export_worker.py` | M |
| S2-L | GDPR Erasure Worker | Real-time/Queue | 2 | S1-A, S1-C, S1-D | `backend/app/workers/gdpr/__init__.py`, `backend/app/workers/gdpr/tasks.py`, `backend/app/workers/gdpr/anonymizer.py` (anonymous_id HMAC, idempotent), `tests/integration/test_gdpr_worker.py` | M |
| S2-M | Notification Worker (SendGrid) | Real-time/Queue | 2 | S1-A, S1-D | `backend/app/workers/notification/__init__.py`, `backend/app/workers/notification/tasks.py`, `backend/app/workers/notification/sendgrid_client.py`, `backend/app/workers/notification/templates.py` (verification, reset, invite, grace day-1/6), `tests/integration/test_notification_worker.py` | M |
| S3-A | Frontend: Auth Pages | Frontend | 3 | S1-F, S2-A | `frontend/src/pages/auth/Register.tsx`, `frontend/src/pages/auth/Login.tsx`, `frontend/src/pages/auth/VerifyEmail.tsx`, `frontend/src/pages/auth/PasswordResetRequest.tsx`, `frontend/src/pages/auth/PasswordResetConfirm.tsx`, `frontend/src/pages/auth/OAuthCallback.tsx`, `frontend/src/pages/auth/AccountLinkPrompt.tsx` | M |
| S3-B | Frontend: Drawing Library | Frontend | 3 | S1-F, S2-B | `frontend/src/pages/Dashboard.tsx`, `frontend/src/features/library/DrawingList.tsx`, `frontend/src/features/library/DrawingRow.tsx`, `frontend/src/features/library/StatusBadge.tsx`, `frontend/src/features/library/SearchFilter.tsx`, `frontend/src/features/library/Pagination.tsx`, `frontend/src/features/library/useDrawings.ts` | M |
| S3-C | Frontend: Upload Flow | Frontend | 3 | S1-F, S2-B | `frontend/src/pages/Upload.tsx`, `frontend/src/features/upload/DropZone.tsx`, `frontend/src/features/upload/hashClient.ts`, `frontend/src/features/upload/uploadOrchestrator.ts`, `frontend/src/features/upload/UploadProgress.tsx` | M |
| S3-D | Frontend: Review Canvas (Konva) | Frontend | 3 | S1-F, S2-B, S2-C | `frontend/src/pages/Review.tsx`, `frontend/src/features/canvas/Canvas.tsx`, `frontend/src/features/canvas/SymbolLayer.tsx`, `frontend/src/features/canvas/BoundingBox.tsx`, `frontend/src/features/canvas/PageNav.tsx`, `frontend/src/features/canvas/InspectionPanel.tsx`, `frontend/src/features/canvas/ManualAnnotate.tsx`, `frontend/src/features/canvas/CorrectionStore.ts`, `frontend/src/features/canvas/useCanvasShortcuts.ts` | L |
| S3-E | Frontend: Account & Consent | Frontend | 3 | S1-F, S2-F | `frontend/src/pages/Account.tsx`, `frontend/src/features/account/ProfileForm.tsx`, `frontend/src/features/account/ConsentToggle.tsx`, `frontend/src/features/account/DeleteAccount.tsx` | S |
| S3-F | Frontend: Subscription & Upgrade | Frontend | 3 | S1-F, S2-E | `frontend/src/pages/Subscription.tsx`, `frontend/src/features/subscription/TierCard.tsx`, `frontend/src/features/subscription/CheckoutRedirect.tsx`, `frontend/src/features/subscription/UpgradePrompt.tsx`, `frontend/src/features/subscription/PendingState.tsx` | M |
| S3-G | Frontend: Exports UI + Notifications | Frontend | 3 | S1-F, S2-D | `frontend/src/features/exports/ExportButton.tsx`, `frontend/src/features/exports/ExportModal.tsx`, `frontend/src/features/exports/useExportStatus.ts`, `frontend/src/features/notifications/InAppNotifications.tsx`, `frontend/src/features/notifications/notificationsStore.ts` | M |
| S3-H | Marketing Site (Next.js) | Frontend | 3 | S0-A | `marketing/app/(marketing)/page.tsx`, `marketing/app/pricing/page.tsx`, `marketing/app/about/page.tsx`, `marketing/app/contact/page.tsx`, `marketing/components/Hero.tsx`, `marketing/components/PricingTable.tsx`, `marketing/components/Footer.tsx`, `marketing/public/robots.txt`, `marketing/public/sitemap.xml` | M |
| S4-A | E2E Integration Tests | Testing/Hardening | 4 | All Phase 2 + Phase 3 | `tests/integration/e2e/test_upload_to_complete.py`, `tests/integration/e2e/test_correction_flow.py`, `tests/integration/e2e/test_export_sync_and_async.py`, `tests/integration/e2e/test_stripe_lifecycle.py`, `tests/integration/e2e/test_gdpr_erasure.py`, `tests/integration/e2e/test_blocklist_two_gate.py`, `tests/integration/e2e/test_free_tier_limit.py` | L |

---

## Gate Definitions

**Phase 0 → Phase 1 gate** (must merge): `S0-A`, `S0-B`. Both required: scaffold provides stubs every Phase 1 session imports; harness provides the green integration baseline (`npm run test:integration` exits 0).

**Phase 1 → Phase 2 gate** (must merge): `S1-A`, `S1-B`, `S1-C`, `S1-D`, `S1-E`. Non-blocking for Phase 2 backend work: `S1-F` (frontend-only; gates Phase 3 only).

**Phase 2 → Phase 3 gate** (must merge per frontend session): each Phase 3 session depends only on its specific Phase 2 endpoint(s) — see prerequisites column. Marketing (`S3-H`) needs only Phase 0.

**Phase 3 → Phase 4 gate** (must merge): all Phase 2 + Phase 3 sessions.

---

## Intra-Phase Dependencies

None within Phase 1 (all five core infra sessions are parallel; they only import from S0-A stubs).

None within Phase 2 — workers and API routers own disjoint files. They communicate only through Celery queues / Redis channels / DB tables defined in Phase 1.

None within Phase 3 — each frontend feature owns its own subdirectory.

---

## Early-Start Optimizations

- **S1-F (frontend shared)** depends only on `S0-A`/`S0-B` — can start with Phase 1 even though it gates Phase 3 frontends.
- **S3-H (marketing site)** depends only on `S0-A` — can start as early as Phase 1.
- **S2-G (entity classes)** needs only `S1-A` + `S1-D`, can start as soon as those two merge (before S1-B/C/E).
- **S2-L (GDPR worker)** and **S2-M (notification worker)** don't need `S1-E` analytics — can start once `S1-A`/`S1-C`/`S1-D` clear.
- **S3-A (auth pages)** can begin as soon as `S2-A` clears, regardless of other Phase 2 progress.

---

## Critical Path

`S0-A` → `S1-A` (DB models) → `S2-B` (Drawings API + SSE) → `S3-D` (Review canvas — largest frontend) → `S4-A` (E2E tests)

Length: 5 sessions, complexity L → L → L → L → L ≈ 15 hrs of Claude execution on the longest chain.

---

```json
[
  {"id":"S0-A","phase":0,"name":"Scaffold & Shared Stubs","category":"Infrastructure","prerequisites":[],"ownedFiles":["backend/app/main.py","backend/app/config.py","backend/app/db/base.py","backend/app/db/session.py","backend/app/api/__init__.py","backend/app/api/routers/__init__.py","backend/app/api/routers/_stubs.py","backend/app/workers/celery_app.py","backend/app/workers/__init__.py","backend/app/schemas/contracts.py","backend/app/schemas/__init__.py","backend/alembic.ini","backend/alembic/env.py","backend/alembic/script.py.mako","backend/Dockerfile","backend/Dockerfile.worker","backend/Dockerfile.ml","frontend/index.html","frontend/vite.config.ts","frontend/tsconfig.json","frontend/src/main.tsx","frontend/src/App.tsx","frontend/src/router.tsx","frontend/src/pages/_stubs.tsx","frontend/src/types/contracts.ts","marketing/next.config.js","marketing/tsconfig.json","marketing/app/layout.tsx","marketing/app/page.tsx","docker-compose.yml","docker-compose.test.yml",".env.example","README.md","ops/oda-sandbox/Dockerfile","ops/clamav/Dockerfile"],"complexity":"L","specSections":["1.1 Shared Contracts","1.6 Route Manifest","1.8 Technology Stack","1.12 Environment Variable Schema"]},
  {"id":"S0-B","phase":0,"name":"Integration Harness & Manifests","category":"Testing/Hardening","prerequisites":[],"ownedFiles":["package.json","backend/pyproject.toml","backend/poetry.lock","frontend/package.json","marketing/package.json","tests/integration/conftest.py","tests/integration/docker-compose.fixtures.yml","tests/integration/fixtures/db.py","tests/integration/fixtures/redis.py","tests/integration/fixtures/s3.py","tests/integration/smoke/test_smoke.py","tests/integration/README.md","scripts/test-integration.sh",".github/workflows/integration.yml"],"complexity":"M","specSections":["1.8 Technology Stack","1.12 Environment Variable Schema"]},
  {"id":"S1-A","phase":1,"name":"DB Models & Migrations","category":"Infrastructure","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/db/models/__init__.py","backend/app/db/models/user.py","backend/app/db/models/team.py","backend/app/db/models/tier.py","backend/app/db/models/subscription.py","backend/app/db/models/stored_file.py","backend/app/db/models/file_hash_blocklist.py","backend/app/db/models/drawing.py","backend/app/db/models/entity_class.py","backend/app/db/models/detected_symbol.py","backend/app/db/models/table_cell.py","backend/app/db/models/user_correction.py","backend/app/db/models/export_record.py","backend/app/db/models/ml_training_consent.py","backend/app/db/models/revision_comparison.py","backend/app/db/models/audit_log.py","backend/app/db/models/stripe_event.py","backend/alembic/versions/0001_initial_schema.py","backend/alembic/versions/0002_rls_policies.py","backend/alembic/versions/0003_audit_partitions.py","backend/app/db/seed_tiers.py","backend/app/db/seed_entity_classes.py"],"complexity":"L","specSections":["1.2 Database Schema","1.3 State Machines and Permission Matrices"]},
  {"id":"S1-B","phase":1,"name":"Auth Middleware & Supabase Client","category":"Auth/Contracts","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/auth/__init__.py","backend/app/auth/supabase_client.py","backend/app/auth/jwt_verifier.py","backend/app/auth/middleware.py","backend/app/auth/dependencies.py","backend/app/auth/permissions.py","backend/app/auth/brute_force.py","tests/integration/test_auth_middleware.py"],"complexity":"M","specSections":["1.3 State Machines and Permission Matrices","1.4 Critical Ordering Rules","1.7 Third-Party Dependencies"]},
  {"id":"S1-C","phase":1,"name":"Storage & Hash Utilities","category":"Infrastructure","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/storage/__init__.py","backend/app/storage/s3_client.py","backend/app/storage/presigned.py","backend/app/storage/hashing.py","backend/app/storage/blocklist.py","tests/integration/test_storage.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.7 Third-Party Dependencies","1.9 Performance Targets"]},
  {"id":"S1-D","phase":1,"name":"Redis, Cache, Pub/Sub & Celery Config","category":"Real-time/Queue","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/redis/__init__.py","backend/app/redis/client.py","backend/app/redis/cache.py","backend/app/redis/pubsub.py","backend/app/workers/queues.py","backend/app/workers/base.py","tests/integration/test_redis_pubsub.py"],"complexity":"M","specSections":["1.11 Cross-Session Runtime Patterns","1.8 Technology Stack"]},
  {"id":"S1-E","phase":1,"name":"Analytics Emitter (PostHog)","category":"Infrastructure","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/analytics/__init__.py","backend/app/analytics/posthog_client.py","backend/app/analytics/events.py","backend/app/analytics/dead_letter.py","tests/integration/test_analytics.py"],"complexity":"S","specSections":["1.10 Analytics Event Contracts"]},
  {"id":"S1-F","phase":1,"name":"Frontend Shared Infrastructure","category":"Frontend","prerequisites":["S0-A","S0-B"],"ownedFiles":["frontend/src/api/client.ts","frontend/src/api/endpoints.ts","frontend/src/auth/AuthContext.tsx","frontend/src/auth/useAuth.ts","frontend/src/auth/supabaseClient.ts","frontend/src/hooks/useSSE.ts","frontend/src/hooks/usePolling.ts","frontend/src/components/Layout.tsx","frontend/src/components/Nav.tsx","frontend/src/components/GraceBanner.tsx","frontend/src/components/ProtectedRoute.tsx","frontend/src/lib/storage.ts","frontend/src/lib/analytics.ts","frontend/src/styles/globals.css"],"complexity":"M","specSections":["1.1 Shared Contracts","1.6 Route Manifest","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-A","phase":2,"name":"Auth Endpoints","category":"Auth/Contracts","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/auth.py","backend/app/services/auth_service.py","backend/app/services/password_reset.py","tests/integration/test_auth_endpoints.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.6 Route Manifest","1.13 Feature Scope"]},
  {"id":"S2-B","phase":2,"name":"Drawings Endpoints + SSE Status","category":"Backend API","prerequisites":["S1-A","S1-B","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/drawings.py","backend/app/services/drawing_service.py","backend/app/services/hash_check_service.py","backend/app/services/upload_complete_service.py","backend/app/services/drawing_state_machine.py","backend/app/services/free_tier_counter.py","backend/app/sse/drawing_status.py","tests/integration/test_drawings_api.py","tests/integration/test_drawings_sse.py"],"complexity":"L","specSections":["1.3 State Machines and Permission Matrices","1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.6 Route Manifest","1.10 Analytics Event Contracts","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-C","phase":2,"name":"Symbols & Corrections Endpoints","category":"Backend API","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/symbols.py","backend/app/services/symbol_service.py","backend/app/services/correction_service.py","tests/integration/test_symbols_api.py"],"complexity":"M","specSections":["1.1 Shared Contracts","1.4 Critical Ordering Rules","1.10 Analytics Event Contracts","1.13 Feature Scope"]},
  {"id":"S2-D","phase":2,"name":"Export Endpoints + Sync Path","category":"Backend API","prerequisites":["S1-A","S1-B","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/exports.py","backend/app/services/export_service.py","backend/app/services/export_generators.py","tests/integration/test_exports_api.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.6 Route Manifest","1.9 Performance Targets","1.10 Analytics Event Contracts"]},
  {"id":"S2-E","phase":2,"name":"Subscription + Stripe Webhook","category":"Backend API","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/subscription.py","backend/app/api/routers/stripe_webhook.py","backend/app/services/stripe_client.py","backend/app/services/subscription_service.py","backend/app/services/billing_state_machine.py","backend/app/services/stripe_event_idempotency.py","tests/integration/test_subscription.py","tests/integration/test_stripe_webhook.py"],"complexity":"L","specSections":["1.3 State Machines and Permission Matrices","1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.7 Third-Party Dependencies","1.10 Analytics Event Contracts"]},
  {"id":"S2-F","phase":2,"name":"Account, Consent & GDPR Init Endpoints","category":"Backend API","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/account.py","backend/app/services/account_service.py","backend/app/services/consent_service.py","backend/app/services/gdpr_init_service.py","tests/integration/test_account.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.13 Feature Scope"]},
  {"id":"S2-G","phase":2,"name":"Entity Classes & Misc Endpoints","category":"Backend API","prerequisites":["S1-A","S1-D"],"ownedFiles":["backend/app/api/routers/entity_classes.py","backend/app/services/entity_class_service.py","tests/integration/test_entity_classes.py"],"complexity":"S","specSections":["1.6 Route Manifest","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-H","phase":2,"name":"Ingest Worker","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/ingest/__init__.py","backend/app/workers/ingest/tasks.py","backend/app/workers/ingest/oda_converter.py","backend/app/workers/ingest/hash_reverify.py","backend/app/workers/ingest/format_detect.py","tests/integration/test_ingest_worker.py"],"complexity":"L","specSections":["1.4 Critical Ordering Rules","1.7 Third-Party Dependencies","1.11 Cross-Session Runtime Patterns","1.13 Feature Scope"]},
  {"id":"S2-I","phase":2,"name":"Scan Worker (ClamAV)","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/scan/__init__.py","backend/app/workers/scan/tasks.py","backend/app/workers/scan/clamav_client.py","tests/integration/test_scan_worker.py"],"complexity":"S","specSections":["1.7 Third-Party Dependencies","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-J","phase":2,"name":"ML Worker","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/ml/__init__.py","backend/app/workers/ml/tasks.py","backend/app/workers/ml/inference.py","backend/app/workers/ml/model_loader.py","backend/app/workers/ml/result_persistence.py","tests/integration/test_ml_worker.py"],"complexity":"L","specSections":["1.1 Shared Contracts","1.4 Critical Ordering Rules","1.9 Performance Targets","1.10 Analytics Event Contracts","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-K","phase":2,"name":"Export Worker (Async)","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/export/__init__.py","backend/app/workers/export/tasks.py","tests/integration/test_export_worker.py"],"complexity":"M","specSections":["1.9 Performance Targets","1.11 Cross-Session Runtime Patterns","1.13 Feature Scope"]},
  {"id":"S2-L","phase":2,"name":"GDPR Erasure Worker","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D"],"ownedFiles":["backend/app/workers/gdpr/__init__.py","backend/app/workers/gdpr/tasks.py","backend/app/workers/gdpr/anonymizer.py","tests/integration/test_gdpr_worker.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.11 Cross-Session Runtime Patterns","1.12 Environment Variable Schema","1.13 Feature Scope"]},
  {"id":"S2-M","phase":2,"name":"Notification Worker (SendGrid)","category":"Real-time/Queue","prerequisites":["S1-A","S1-D"],"ownedFiles":["backend/app/workers/notification/__init__.py","backend/app/workers/notification/tasks.py","backend/app/workers/notification/sendgrid_client.py","backend/app/workers/notification/templates.py","tests/integration/test_notification_worker.py"],"complexity":"M","specSections":["1.3 State Machines and Permission Matrices","1.7 Third-Party Dependencies","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S3-A","phase":3,"name":"Frontend: Auth Pages","category":"Frontend","prerequisites":["S1-F","S2-A"],"ownedFiles":["frontend/src/pages/auth/Register.tsx","frontend/src/pages/auth/Login.tsx","frontend/src/pages/auth/VerifyEmail.tsx","frontend/src/pages/auth/PasswordResetRequest.tsx","frontend/src/pages/auth/PasswordResetConfirm.tsx","frontend/src/pages/auth/OAuthCallback.tsx","frontend/src/pages/auth/AccountLinkPrompt.tsx"],"complexity":"M","specSections":["1.6 Route Manifest","1.13 Feature Scope"]},
  {"id":"S3-B","phase":3,"name":"Frontend: Drawing Library","category":"Frontend","prerequisites":["S1-F","S2-B"],"ownedFiles":["frontend/src/pages/Dashboard.tsx","frontend/src/features/library/DrawingList.tsx","frontend/src/features/library/DrawingRow.tsx","frontend/src/features/library/StatusBadge.tsx","frontend/src/features/library/SearchFilter.tsx","frontend/src/features/library/Pagination.tsx","frontend/src/features/library/useDrawings.ts"],"complexity":"M","specSections":["1.6 Route Manifest","1.9 Performance Targets","1.13 Feature Scope"]},
  {"id":"S3-C","phase":3,"name":"Frontend: Upload Flow","category":"Frontend","prerequisites":["S1-F","S2-B"],"ownedFiles":["frontend/src/pages/Upload.tsx","frontend/src/features/upload/DropZone.tsx","frontend/src/features/upload/hashClient.ts","frontend/src/features/upload/uploadOrchestrator.ts","frontend/src/features/upload/UploadProgress.tsx"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.13 Feature Scope"]},
  {"id":"S3-D","phase":3,"name":"Frontend: Review Canvas (Konva)","category":"Frontend","prerequisites":["S1-F","S2-B","S2-C"],"ownedFiles":["frontend/src/pages/Review.tsx","frontend/src/features/canvas/Canvas.tsx","frontend/src/features/canvas/SymbolLayer.tsx","frontend/src/features/canvas/BoundingBox.tsx","frontend/src/features/canvas/PageNav.tsx","frontend/src/features/canvas/InspectionPanel.tsx","frontend/src/features/canvas/ManualAnnotate.tsx","frontend/src/features/canvas/CorrectionStore.ts","frontend/src/features/canvas/useCanvasShortcuts.ts"],"complexity":"L","specSections":["1.6 Route Manifest","1.8 Technology Stack","1.9 Performance Targets","1.11 Cross-Session Runtime Patterns","1.13 Feature Scope"]},
  {"id":"S3-E","phase":3,"name":"Frontend: Account & Consent","category":"Frontend","prerequisites":["S1-F","S2-F"],"ownedFiles":["frontend/src/pages/Account.tsx","frontend/src/features/account/ProfileForm.tsx","frontend/src/features/account/ConsentToggle.tsx","frontend/src/features/account/DeleteAccount.tsx"],"complexity":"S","specSections":["1.6 Route Manifest","1.13 Feature Scope"]},
  {"id":"S3-F","phase":3,"name":"Frontend: Subscription & Upgrade","category":"Frontend","prerequisites":["S1-F","S2-E"],"ownedFiles":["frontend/src/pages/Subscription.tsx","frontend/src/features/subscription/TierCard.tsx","frontend/src/features/subscription/CheckoutRedirect.tsx","frontend/src/features/subscription/UpgradePrompt.tsx","frontend/src/features/subscription/PendingState.tsx"],"complexity":"M","specSections":["1.3 State Machines and Permission Matrices","1.6 Route Manifest","1.9 Performance Targets","1.13 Feature Scope"]},
  {"id":"S3-G","phase":3,"name":"Frontend: Exports UI + Notifications","category":"Frontend","prerequisites":["S1-F","S2-D"],"ownedFiles":["frontend/src/features/exports/ExportButton.tsx","frontend/src/features/exports/ExportModal.tsx","frontend/src/features/exports/useExportStatus.ts","frontend/src/features/notifications/InAppNotifications.tsx","frontend/src/features/notifications/notificationsStore.ts"],"complexity":"M","specSections":["1.9 Performance Targets","1.13 Feature Scope"]},
  {"id":"S3-H","phase":3,"name":"Marketing Site (Next.js)","category":"Frontend","prerequisites":["S0-A"],"ownedFiles":["marketing/app/(marketing)/page.tsx","marketing/app/pricing/page.tsx","marketing/app/about/page.tsx","marketing/app/contact/page.tsx","marketing/components/Hero.tsx","marketing/components/PricingTable.tsx","marketing/components/Footer.tsx","marketing/public/robots.txt","marketing/public/sitemap.xml"],"complexity":"M","specSections":["1.8 Technology Stack"]},
  {"id":"S4-A","phase":4,"name":"E2E Integration Tests","category":"Testing/Hardening","prerequisites":["S2-A","S2-B","S2-C","S2-D","S2-E","S2-F","S2-G","S2-H","S2-I","S2-J","S2-K","S2-L","S2-M","S3-A","S3-B","S3-C","S3-D","S3-E","S3-F","S3-G"],"ownedFiles":["tests/integration/e2e/test_upload_to_complete.py","tests/integration/e2e/test_correction_flow.py","tests/integration/e2e/test_export_sync_and_async.py","tests/integration/e2e/test_stripe_lifecycle.py","tests/integration/e2e/test_gdpr_erasure.py","tests/integration/e2e/test_blocklist_two_gate.py","tests/integration/e2e/test_free_tier_limit.py"],"complexity":"L","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.10 Analytics Event Contracts","1.13 Feature Scope"]}
]
```

Total: 30 sessions across 5 phases
```

---

### build-plan-ownership-table [primary]

**System Prompt:**
```
You are generating a shared file ownership table for an autonomous build plan. Using the distilled spec and session table provided, produce a complete table of every file in the project that is imported by more than one session:

| File path | Owner session | Importing sessions | Mutable after merge |
| --------- | ------------- | ------------------ | ------------------- |

Flag every row where "Mutable after merge" is No with **LOAD-BEARING**. A change to any of these files after initial merge requires updating every importing session brief and re-running the consistency check.

Also list any file that appears in only one session's owned files but is architecturally critical (e.g., database schema, shared types, configuration). Mark these as **FOUNDATIONAL**.
```

**User Message:**
```
# PID Analyzer — Session Decomposition

| ID | Name | Category | Phase | Prerequisites | Owned files (exhaustive) | Complexity |
| -- | ---- | -------- | ----- | ------------- | ------------------------ | ---------- |
| S0-A | Scaffold & Shared Stubs | Infrastructure | 0 | — | `backend/app/main.py`, `backend/app/config.py`, `backend/app/db/base.py`, `backend/app/db/session.py`, `backend/app/api/__init__.py`, `backend/app/api/routers/__init__.py` (all router include stubs), `backend/app/api/routers/_stubs.py` (placeholder endpoints for every route in §1.6 P0+P1), `backend/app/workers/celery_app.py`, `backend/app/workers/__init__.py`, `backend/app/schemas/contracts.py` (pydantic mirrors of §1.1), `backend/app/schemas/__init__.py`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/Dockerfile`, `backend/Dockerfile.worker`, `backend/Dockerfile.ml`, `frontend/index.html`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/router.tsx` (lazy route stubs for all SPA pages), `frontend/src/pages/_stubs.tsx`, `frontend/src/types/contracts.ts`, `marketing/next.config.js`, `marketing/tsconfig.json`, `marketing/app/layout.tsx`, `marketing/app/page.tsx`, `docker-compose.yml`, `docker-compose.test.yml`, `.env.example`, `README.md`, `ops/oda-sandbox/Dockerfile`, `ops/clamav/Dockerfile` | L |
| S0-B | Integration Harness & Manifests | Testing/Hardening | 0 | — | `package.json` (root workspace), `backend/pyproject.toml`, `backend/poetry.lock`, `frontend/package.json`, `marketing/package.json`, `tests/integration/conftest.py`, `tests/integration/docker-compose.fixtures.yml`, `tests/integration/fixtures/db.py`, `tests/integration/fixtures/redis.py`, `tests/integration/fixtures/s3.py`, `tests/integration/smoke/test_smoke.py`, `tests/integration/README.md`, `scripts/test-integration.sh`, `.github/workflows/integration.yml` | M |
| S1-A | DB Models & Migrations | Infrastructure | 1 | S0-A, S0-B | `backend/app/db/models/__init__.py`, `backend/app/db/models/user.py`, `backend/app/db/models/team.py`, `backend/app/db/models/tier.py`, `backend/app/db/models/subscription.py`, `backend/app/db/models/stored_file.py`, `backend/app/db/models/file_hash_blocklist.py`, `backend/app/db/models/drawing.py`, `backend/app/db/models/entity_class.py`, `backend/app/db/models/detected_symbol.py`, `backend/app/db/models/table_cell.py`, `backend/app/db/models/user_correction.py`, `backend/app/db/models/export_record.py`, `backend/app/db/models/ml_training_consent.py`, `backend/app/db/models/revision_comparison.py`, `backend/app/db/models/audit_log.py`, `backend/app/db/models/stripe_event.py`, `backend/alembic/versions/0001_initial_schema.py`, `backend/alembic/versions/0002_rls_policies.py`, `backend/alembic/versions/0003_audit_partitions.py`, `backend/app/db/seed_tiers.py`, `backend/app/db/seed_entity_classes.py` | L |
| S1-B | Auth Middleware & Supabase Client | Auth/Contracts | 1 | S0-A, S0-B | `backend/app/auth/__init__.py`, `backend/app/auth/supabase_client.py`, `backend/app/auth/jwt_verifier.py`, `backend/app/auth/middleware.py`, `backend/app/auth/dependencies.py`, `backend/app/auth/permissions.py` (role matrix from §1.3), `backend/app/auth/brute_force.py`, `tests/integration/test_auth_middleware.py` | M |
| S1-C | Storage & Hash Utilities | Infrastructure | 1 | S0-A, S0-B | `backend/app/storage/__init__.py`, `backend/app/storage/s3_client.py`, `backend/app/storage/presigned.py`, `backend/app/storage/hashing.py`, `backend/app/storage/blocklist.py`, `tests/integration/test_storage.py` | M |
| S1-D | Redis, Cache, Pub/Sub & Celery Config | Real-time/Queue | 1 | S0-A, S0-B | `backend/app/redis/__init__.py`, `backend/app/redis/client.py`, `backend/app/redis/cache.py` (subscription flags, entity taxonomy), `backend/app/redis/pubsub.py` (drawing:status channels), `backend/app/workers/queues.py` (queue routing config), `backend/app/workers/base.py` (Task base class with retry policy), `tests/integration/test_redis_pubsub.py` | M |
| S1-E | Analytics Emitter (PostHog) | Infrastructure | 1 | S0-A, S0-B | `backend/app/analytics/__init__.py`, `backend/app/analytics/posthog_client.py`, `backend/app/analytics/events.py` (typed emitters for all 9 events §1.10), `backend/app/analytics/dead_letter.py`, `tests/integration/test_analytics.py` | S |
| S1-F | Frontend Shared Infrastructure | Frontend | 1 | S0-A, S0-B | `frontend/src/api/client.ts`, `frontend/src/api/endpoints.ts`, `frontend/src/auth/AuthContext.tsx`, `frontend/src/auth/useAuth.ts`, `frontend/src/auth/supabaseClient.ts`, `frontend/src/hooks/useSSE.ts`, `frontend/src/hooks/usePolling.ts`, `frontend/src/components/Layout.tsx`, `frontend/src/components/Nav.tsx`, `frontend/src/components/GraceBanner.tsx`, `frontend/src/components/ProtectedRoute.tsx`, `frontend/src/lib/storage.ts` (localStorage/sessionStorage helpers), `frontend/src/lib/analytics.ts`, `frontend/src/styles/globals.css` | M |
| S2-A | Auth Endpoints | Auth/Contracts | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/auth.py`, `backend/app/services/auth_service.py`, `backend/app/services/password_reset.py`, `tests/integration/test_auth_endpoints.py` | M |
| S2-B | Drawings Endpoints + SSE Status | Backend API | 2 | S1-A, S1-B, S1-C, S1-D, S1-E | `backend/app/api/routers/drawings.py`, `backend/app/services/drawing_service.py`, `backend/app/services/hash_check_service.py`, `backend/app/services/upload_complete_service.py`, `backend/app/services/drawing_state_machine.py`, `backend/app/services/free_tier_counter.py`, `backend/app/sse/drawing_status.py`, `tests/integration/test_drawings_api.py`, `tests/integration/test_drawings_sse.py` | L |
| S2-C | Symbols & Corrections Endpoints | Backend API | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/symbols.py`, `backend/app/services/symbol_service.py`, `backend/app/services/correction_service.py` (training_consent snapshot, Under_Review trigger), `tests/integration/test_symbols_api.py` | M |
| S2-D | Export Endpoints + Sync Path | Backend API | 2 | S1-A, S1-B, S1-C, S1-D, S1-E | `backend/app/api/routers/exports.py`, `backend/app/services/export_service.py` (sync <1000 path, threshold gate), `backend/app/services/export_generators.py` (CSV/XLSX), `tests/integration/test_exports_api.py` | M |
| S2-E | Subscription + Stripe Webhook | Backend API | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/subscription.py`, `backend/app/api/routers/stripe_webhook.py`, `backend/app/services/stripe_client.py`, `backend/app/services/subscription_service.py`, `backend/app/services/billing_state_machine.py`, `backend/app/services/stripe_event_idempotency.py`, `tests/integration/test_subscription.py`, `tests/integration/test_stripe_webhook.py` | L |
| S2-F | Account, Consent & GDPR Init Endpoints | Backend API | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/account.py`, `backend/app/services/account_service.py`, `backend/app/services/consent_service.py` (server-side team consent resolution), `backend/app/services/gdpr_init_service.py`, `tests/integration/test_account.py` | M |
| S2-G | Entity Classes & Misc Endpoints | Backend API | 2 | S1-A, S1-D | `backend/app/api/routers/entity_classes.py`, `backend/app/services/entity_class_service.py`, `tests/integration/test_entity_classes.py` | S |
| S2-H | Ingest Worker | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/ingest/__init__.py`, `backend/app/workers/ingest/tasks.py`, `backend/app/workers/ingest/oda_converter.py`, `backend/app/workers/ingest/hash_reverify.py`, `backend/app/workers/ingest/format_detect.py`, `tests/integration/test_ingest_worker.py` | L |
| S2-I | Scan Worker (ClamAV) | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/scan/__init__.py`, `backend/app/workers/scan/tasks.py`, `backend/app/workers/scan/clamav_client.py`, `tests/integration/test_scan_worker.py` | S |
| S2-J | ML Worker | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/ml/__init__.py`, `backend/app/workers/ml/tasks.py`, `backend/app/workers/ml/inference.py`, `backend/app/workers/ml/model_loader.py`, `backend/app/workers/ml/result_persistence.py`, `tests/integration/test_ml_worker.py` | L |
| S2-K | Export Worker (Async) | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/export/__init__.py`, `backend/app/workers/export/tasks.py`, `tests/integration/test_export_worker.py` | M |
| S2-L | GDPR Erasure Worker | Real-time/Queue | 2 | S1-A, S1-C, S1-D | `backend/app/workers/gdpr/__init__.py`, `backend/app/workers/gdpr/tasks.py`, `backend/app/workers/gdpr/anonymizer.py` (anonymous_id HMAC, idempotent), `tests/integration/test_gdpr_worker.py` | M |
| S2-M | Notification Worker (SendGrid) | Real-time/Queue | 2 | S1-A, S1-D | `backend/app/workers/notification/__init__.py`, `backend/app/workers/notification/tasks.py`, `backend/app/workers/notification/sendgrid_client.py`, `backend/app/workers/notification/templates.py` (verification, reset, invite, grace day-1/6), `tests/integration/test_notification_worker.py` | M |
| S3-A | Frontend: Auth Pages | Frontend | 3 | S1-F, S2-A | `frontend/src/pages/auth/Register.tsx`, `frontend/src/pages/auth/Login.tsx`, `frontend/src/pages/auth/VerifyEmail.tsx`, `frontend/src/pages/auth/PasswordResetRequest.tsx`, `frontend/src/pages/auth/PasswordResetConfirm.tsx`, `frontend/src/pages/auth/OAuthCallback.tsx`, `frontend/src/pages/auth/AccountLinkPrompt.tsx` | M |
| S3-B | Frontend: Drawing Library | Frontend | 3 | S1-F, S2-B | `frontend/src/pages/Dashboard.tsx`, `frontend/src/features/library/DrawingList.tsx`, `frontend/src/features/library/DrawingRow.tsx`, `frontend/src/features/library/StatusBadge.tsx`, `frontend/src/features/library/SearchFilter.tsx`, `frontend/src/features/library/Pagination.tsx`, `frontend/src/features/library/useDrawings.ts` | M |
| S3-C | Frontend: Upload Flow | Frontend | 3 | S1-F, S2-B | `frontend/src/pages/Upload.tsx`, `frontend/src/features/upload/DropZone.tsx`, `frontend/src/features/upload/hashClient.ts`, `frontend/src/features/upload/uploadOrchestrator.ts`, `frontend/src/features/upload/UploadProgress.tsx` | M |
| S3-D | Frontend: Review Canvas (Konva) | Frontend | 3 | S1-F, S2-B, S2-C | `frontend/src/pages/Review.tsx`, `frontend/src/features/canvas/Canvas.tsx`, `frontend/src/features/canvas/SymbolLayer.tsx`, `frontend/src/features/canvas/BoundingBox.tsx`, `frontend/src/features/canvas/PageNav.tsx`, `frontend/src/features/canvas/InspectionPanel.tsx`, `frontend/src/features/canvas/ManualAnnotate.tsx`, `frontend/src/features/canvas/CorrectionStore.ts`, `frontend/src/features/canvas/useCanvasShortcuts.ts` | L |
| S3-E | Frontend: Account & Consent | Frontend | 3 | S1-F, S2-F | `frontend/src/pages/Account.tsx`, `frontend/src/features/account/ProfileForm.tsx`, `frontend/src/features/account/ConsentToggle.tsx`, `frontend/src/features/account/DeleteAccount.tsx` | S |
| S3-F | Frontend: Subscription & Upgrade | Frontend | 3 | S1-F, S2-E | `frontend/src/pages/Subscription.tsx`, `frontend/src/features/subscription/TierCard.tsx`, `frontend/src/features/subscription/CheckoutRedirect.tsx`, `frontend/src/features/subscription/UpgradePrompt.tsx`, `frontend/src/features/subscription/PendingState.tsx` | M |
| S3-G | Frontend: Exports UI + Notifications | Frontend | 3 | S1-F, S2-D | `frontend/src/features/exports/ExportButton.tsx`, `frontend/src/features/exports/ExportModal.tsx`, `frontend/src/features/exports/useExportStatus.ts`, `frontend/src/features/notifications/InAppNotifications.tsx`, `frontend/src/features/notifications/notificationsStore.ts` | M |
| S3-H | Marketing Site (Next.js) | Frontend | 3 | S0-A | `marketing/app/(marketing)/page.tsx`, `marketing/app/pricing/page.tsx`, `marketing/app/about/page.tsx`, `marketing/app/contact/page.tsx`, `marketing/components/Hero.tsx`, `marketing/components/PricingTable.tsx`, `marketing/components/Footer.tsx`, `marketing/public/robots.txt`, `marketing/public/sitemap.xml` | M |
| S4-A | E2E Integration Tests | Testing/Hardening | 4 | All Phase 2 + Phase 3 | `tests/integration/e2e/test_upload_to_complete.py`, `tests/integration/e2e/test_correction_flow.py`, `tests/integration/e2e/test_export_sync_and_async.py`, `tests/integration/e2e/test_stripe_lifecycle.py`, `tests/integration/e2e/test_gdpr_erasure.py`, `tests/integration/e2e/test_blocklist_two_gate.py`, `tests/integration/e2e/test_free_tier_limit.py` | L |

---

## Gate Definitions

**Phase 0 → Phase 1 gate** (must merge): `S0-A`, `S0-B`. Both required: scaffold provides stubs every Phase 1 session imports; harness provides the green integration baseline (`npm run test:integration` exits 0).

**Phase 1 → Phase 2 gate** (must merge): `S1-A`, `S1-B`, `S1-C`, `S1-D`, `S1-E`. Non-blocking for Phase 2 backend work: `S1-F` (frontend-only; gates Phase 3 only).

**Phase 2 → Phase 3 gate** (must merge per frontend session): each Phase 3 session depends only on its specific Phase 2 endpoint(s) — see prerequisites column. Marketing (`S3-H`) needs only Phase 0.

**Phase 3 → Phase 4 gate** (must merge): all Phase 2 + Phase 3 sessions.

---

## Intra-Phase Dependencies

None within Phase 1 (all five core infra sessions are parallel; they only import from S0-A stubs).

None within Phase 2 — workers and API routers own disjoint files. They communicate only through Celery queues / Redis channels / DB tables defined in Phase 1.

None within Phase 3 — each frontend feature owns its own subdirectory.

---

## Early-Start Optimizations

- **S1-F (frontend shared)** depends only on `S0-A`/`S0-B` — can start with Phase 1 even though it gates Phase 3 frontends.
- **S3-H (marketing site)** depends only on `S0-A` — can start as early as Phase 1.
- **S2-G (entity classes)** needs only `S1-A` + `S1-D`, can start as soon as those two merge (before S1-B/C/E).
- **S2-L (GDPR worker)** and **S2-M (notification worker)** don't need `S1-E` analytics — can start once `S1-A`/`S1-C`/`S1-D` clear.
- **S3-A (auth pages)** can begin as soon as `S2-A` clears, regardless of other Phase 2 progress.

---

## Critical Path

`S0-A` → `S1-A` (DB models) → `S2-B` (Drawings API + SSE) → `S3-D` (Review canvas — largest frontend) → `S4-A` (E2E tests)

Length: 5 sessions, complexity L → L → L → L → L ≈ 15 hrs of Claude execution on the longest chain.

---

```json
[
  {"id":"S0-A","phase":0,"name":"Scaffold & Shared Stubs","category":"Infrastructure","prerequisites":[],"ownedFiles":["backend/app/main.py","backend/app/config.py","backend/app/db/base.py","backend/app/db/session.py","backend/app/api/__init__.py","backend/app/api/routers/__init__.py","backend/app/api/routers/_stubs.py","backend/app/workers/celery_app.py","backend/app/workers/__init__.py","backend/app/schemas/contracts.py","backend/app/schemas/__init__.py","backend/alembic.ini","backend/alembic/env.py","backend/alembic/script.py.mako","backend/Dockerfile","backend/Dockerfile.worker","backend/Dockerfile.ml","frontend/index.html","frontend/vite.config.ts","frontend/tsconfig.json","frontend/src/main.tsx","frontend/src/App.tsx","frontend/src/router.tsx","frontend/src/pages/_stubs.tsx","frontend/src/types/contracts.ts","marketing/next.config.js","marketing/tsconfig.json","marketing/app/layout.tsx","marketing/app/page.tsx","docker-compose.yml","docker-compose.test.yml",".env.example","README.md","ops/oda-sandbox/Dockerfile","ops/clamav/Dockerfile"],"complexity":"L","specSections":["1.1 Shared Contracts","1.6 Route Manifest","1.8 Technology Stack","1.12 Environment Variable Schema"]},
  {"id":"S0-B","phase":0,"name":"Integration Harness & Manifests","category":"Testing/Hardening","prerequisites":[],"ownedFiles":["package.json","backend/pyproject.toml","backend/poetry.lock","frontend/package.json","marketing/package.json","tests/integration/conftest.py","tests/integration/docker-compose.fixtures.yml","tests/integration/fixtures/db.py","tests/integration/fixtures/redis.py","tests/integration/fixtures/s3.py","tests/integration/smoke/test_smoke.py","tests/integration/README.md","scripts/test-integration.sh",".github/workflows/integration.yml"],"complexity":"M","specSections":["1.8 Technology Stack","1.12 Environment Variable Schema"]},
  {"id":"S1-A","phase":1,"name":"DB Models & Migrations","category":"Infrastructure","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/db/models/__init__.py","backend/app/db/models/user.py","backend/app/db/models/team.py","backend/app/db/models/tier.py","backend/app/db/models/subscription.py","backend/app/db/models/stored_file.py","backend/app/db/models/file_hash_blocklist.py","backend/app/db/models/drawing.py","backend/app/db/models/entity_class.py","backend/app/db/models/detected_symbol.py","backend/app/db/models/table_cell.py","backend/app/db/models/user_correction.py","backend/app/db/models/export_record.py","backend/app/db/models/ml_training_consent.py","backend/app/db/models/revision_comparison.py","backend/app/db/models/audit_log.py","backend/app/db/models/stripe_event.py","backend/alembic/versions/0001_initial_schema.py","backend/alembic/versions/0002_rls_policies.py","backend/alembic/versions/0003_audit_partitions.py","backend/app/db/seed_tiers.py","backend/app/db/seed_entity_classes.py"],"complexity":"L","specSections":["1.2 Database Schema","1.3 State Machines and Permission Matrices"]},
  {"id":"S1-B","phase":1,"name":"Auth Middleware & Supabase Client","category":"Auth/Contracts","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/auth/__init__.py","backend/app/auth/supabase_client.py","backend/app/auth/jwt_verifier.py","backend/app/auth/middleware.py","backend/app/auth/dependencies.py","backend/app/auth/permissions.py","backend/app/auth/brute_force.py","tests/integration/test_auth_middleware.py"],"complexity":"M","specSections":["1.3 State Machines and Permission Matrices","1.4 Critical Ordering Rules","1.7 Third-Party Dependencies"]},
  {"id":"S1-C","phase":1,"name":"Storage & Hash Utilities","category":"Infrastructure","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/storage/__init__.py","backend/app/storage/s3_client.py","backend/app/storage/presigned.py","backend/app/storage/hashing.py","backend/app/storage/blocklist.py","tests/integration/test_storage.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.7 Third-Party Dependencies","1.9 Performance Targets"]},
  {"id":"S1-D","phase":1,"name":"Redis, Cache, Pub/Sub & Celery Config","category":"Real-time/Queue","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/redis/__init__.py","backend/app/redis/client.py","backend/app/redis/cache.py","backend/app/redis/pubsub.py","backend/app/workers/queues.py","backend/app/workers/base.py","tests/integration/test_redis_pubsub.py"],"complexity":"M","specSections":["1.11 Cross-Session Runtime Patterns","1.8 Technology Stack"]},
  {"id":"S1-E","phase":1,"name":"Analytics Emitter (PostHog)","category":"Infrastructure","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/analytics/__init__.py","backend/app/analytics/posthog_client.py","backend/app/analytics/events.py","backend/app/analytics/dead_letter.py","tests/integration/test_analytics.py"],"complexity":"S","specSections":["1.10 Analytics Event Contracts"]},
  {"id":"S1-F","phase":1,"name":"Frontend Shared Infrastructure","category":"Frontend","prerequisites":["S0-A","S0-B"],"ownedFiles":["frontend/src/api/client.ts","frontend/src/api/endpoints.ts","frontend/src/auth/AuthContext.tsx","frontend/src/auth/useAuth.ts","frontend/src/auth/supabaseClient.ts","frontend/src/hooks/useSSE.ts","frontend/src/hooks/usePolling.ts","frontend/src/components/Layout.tsx","frontend/src/components/Nav.tsx","frontend/src/components/GraceBanner.tsx","frontend/src/components/ProtectedRoute.tsx","frontend/src/lib/storage.ts","frontend/src/lib/analytics.ts","frontend/src/styles/globals.css"],"complexity":"M","specSections":["1.1 Shared Contracts","1.6 Route Manifest","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-A","phase":2,"name":"Auth Endpoints","category":"Auth/Contracts","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/auth.py","backend/app/services/auth_service.py","backend/app/services/password_reset.py","tests/integration/test_auth_endpoints.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.6 Route Manifest","1.13 Feature Scope"]},
  {"id":"S2-B","phase":2,"name":"Drawings Endpoints + SSE Status","category":"Backend API","prerequisites":["S1-A","S1-B","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/drawings.py","backend/app/services/drawing_service.py","backend/app/services/hash_check_service.py","backend/app/services/upload_complete_service.py","backend/app/services/drawing_state_machine.py","backend/app/services/free_tier_counter.py","backend/app/sse/drawing_status.py","tests/integration/test_drawings_api.py","tests/integration/test_drawings_sse.py"],"complexity":"L","specSections":["1.3 State Machines and Permission Matrices","1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.6 Route Manifest","1.10 Analytics Event Contracts","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-C","phase":2,"name":"Symbols & Corrections Endpoints","category":"Backend API","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/symbols.py","backend/app/services/symbol_service.py","backend/app/services/correction_service.py","tests/integration/test_symbols_api.py"],"complexity":"M","specSections":["1.1 Shared Contracts","1.4 Critical Ordering Rules","1.10 Analytics Event Contracts","1.13 Feature Scope"]},
  {"id":"S2-D","phase":2,"name":"Export Endpoints + Sync Path","category":"Backend API","prerequisites":["S1-A","S1-B","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/exports.py","backend/app/services/export_service.py","backend/app/services/export_generators.py","tests/integration/test_exports_api.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.6 Route Manifest","1.9 Performance Targets","1.10 Analytics Event Contracts"]},
  {"id":"S2-E","phase":2,"name":"Subscription + Stripe Webhook","category":"Backend API","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/subscription.py","backend/app/api/routers/stripe_webhook.py","backend/app/services/stripe_client.py","backend/app/services/subscription_service.py","backend/app/services/billing_state_machine.py","backend/app/services/stripe_event_idempotency.py","tests/integration/test_subscription.py","tests/integration/test_stripe_webhook.py"],"complexity":"L","specSections":["1.3 State Machines and Permission Matrices","1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.7 Third-Party Dependencies","1.10 Analytics Event Contracts"]},
  {"id":"S2-F","phase":2,"name":"Account, Consent & GDPR Init Endpoints","category":"Backend API","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/account.py","backend/app/services/account_service.py","backend/app/services/consent_service.py","backend/app/services/gdpr_init_service.py","tests/integration/test_account.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.13 Feature Scope"]},
  {"id":"S2-G","phase":2,"name":"Entity Classes & Misc Endpoints","category":"Backend API","prerequisites":["S1-A","S1-D"],"ownedFiles":["backend/app/api/routers/entity_classes.py","backend/app/services/entity_class_service.py","tests/integration/test_entity_classes.py"],"complexity":"S","specSections":["1.6 Route Manifest","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-H","phase":2,"name":"Ingest Worker","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/ingest/__init__.py","backend/app/workers/ingest/tasks.py","backend/app/workers/ingest/oda_converter.py","backend/app/workers/ingest/hash_reverify.py","backend/app/workers/ingest/format_detect.py","tests/integration/test_ingest_worker.py"],"complexity":"L","specSections":["1.4 Critical Ordering Rules","1.7 Third-Party Dependencies","1.11 Cross-Session Runtime Patterns","1.13 Feature Scope"]},
  {"id":"S2-I","phase":2,"name":"Scan Worker (ClamAV)","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/scan/__init__.py","backend/app/workers/scan/tasks.py","backend/app/workers/scan/clamav_client.py","tests/integration/test_scan_worker.py"],"complexity":"S","specSections":["1.7 Third-Party Dependencies","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-J","phase":2,"name":"ML Worker","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/ml/__init__.py","backend/app/workers/ml/tasks.py","backend/app/workers/ml/inference.py","backend/app/workers/ml/model_loader.py","backend/app/workers/ml/result_persistence.py","tests/integration/test_ml_worker.py"],"complexity":"L","specSections":["1.1 Shared Contracts","1.4 Critical Ordering Rules","1.9 Performance Targets","1.10 Analytics Event Contracts","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-K","phase":2,"name":"Export Worker (Async)","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/export/__init__.py","backend/app/workers/export/tasks.py","tests/integration/test_export_worker.py"],"complexity":"M","specSections":["1.9 Performance Targets","1.11 Cross-Session Runtime Patterns","1.13 Feature Scope"]},
  {"id":"S2-L","phase":2,"name":"GDPR Erasure Worker","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D"],"ownedFiles":["backend/app/workers/gdpr/__init__.py","backend/app/workers/gdpr/tasks.py","backend/app/workers/gdpr/anonymizer.py","tests/integration/test_gdpr_worker.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.11 Cross-Session Runtime Patterns","1.12 Environment Variable Schema","1.13 Feature Scope"]},
  {"id":"S2-M","phase":2,"name":"Notification Worker (SendGrid)","category":"Real-time/Queue","prerequisites":["S1-A","S1-D"],"ownedFiles":["backend/app/workers/notification/__init__.py","backend/app/workers/notification/tasks.py","backend/app/workers/notification/sendgrid_client.py","backend/app/workers/notification/templates.py","tests/integration/test_notification_worker.py"],"complexity":"M","specSections":["1.3 State Machines and Permission Matrices","1.7 Third-Party Dependencies","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S3-A","phase":3,"name":"Frontend: Auth Pages","category":"Frontend","prerequisites":["S1-F","S2-A"],"ownedFiles":["frontend/src/pages/auth/Register.tsx","frontend/src/pages/auth/Login.tsx","frontend/src/pages/auth/VerifyEmail.tsx","frontend/src/pages/auth/PasswordResetRequest.tsx","frontend/src/pages/auth/PasswordResetConfirm.tsx","frontend/src/pages/auth/OAuthCallback.tsx","frontend/src/pages/auth/AccountLinkPrompt.tsx"],"complexity":"M","specSections":["1.6 Route Manifest","1.13 Feature Scope"]},
  {"id":"S3-B","phase":3,"name":"Frontend: Drawing Library","category":"Frontend","prerequisites":["S1-F","S2-B"],"ownedFiles":["frontend/src/pages/Dashboard.tsx","frontend/src/features/library/DrawingList.tsx","frontend/src/features/library/DrawingRow.tsx","frontend/src/features/library/StatusBadge.tsx","frontend/src/features/library/SearchFilter.tsx","frontend/src/features/library/Pagination.tsx","frontend/src/features/library/useDrawings.ts"],"complexity":"M","specSections":["1.6 Route Manifest","1.9 Performance Targets","1.13 Feature Scope"]},
  {"id":"S3-C","phase":3,"name":"Frontend: Upload Flow","category":"Frontend","prerequisites":["S1-F","S2-B"],"ownedFiles":["frontend/src/pages/Upload.tsx","frontend/src/features/upload/DropZone.tsx","frontend/src/features/upload/hashClient.ts","frontend/src/features/upload/uploadOrchestrator.ts","frontend/src/features/upload/UploadProgress.tsx"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.13 Feature Scope"]},
  {"id":"S3-D","phase":3,"name":"Frontend: Review Canvas (Konva)","category":"Frontend","prerequisites":["S1-F","S2-B","S2-C"],"ownedFiles":["frontend/src/pages/Review.tsx","frontend/src/features/canvas/Canvas.tsx","frontend/src/features/canvas/SymbolLayer.tsx","frontend/src/features/canvas/BoundingBox.tsx","frontend/src/features/canvas/PageNav.tsx","frontend/src/features/canvas/InspectionPanel.tsx","frontend/src/features/canvas/ManualAnnotate.tsx","frontend/src/features/canvas/CorrectionStore.ts","frontend/src/features/canvas/useCanvasShortcuts.ts"],"complexity":"L","specSections":["1.6 Route Manifest","1.8 Technology Stack","1.9 Performance Targets","1.11 Cross-Session Runtime Patterns","1.13 Feature Scope"]},
  {"id":"S3-E","phase":3,"name":"Frontend: Account & Consent","category":"Frontend","prerequisites":["S1-F","S2-F"],"ownedFiles":["frontend/src/pages/Account.tsx","frontend/src/features/account/ProfileForm.tsx","frontend/src/features/account/ConsentToggle.tsx","frontend/src/features/account/DeleteAccount.tsx"],"complexity":"S","specSections":["1.6 Route Manifest","1.13 Feature Scope"]},
  {"id":"S3-F","phase":3,"name":"Frontend: Subscription & Upgrade","category":"Frontend","prerequisites":["S1-F","S2-E"],"ownedFiles":["frontend/src/pages/Subscription.tsx","frontend/src/features/subscription/TierCard.tsx","frontend/src/features/subscription/CheckoutRedirect.tsx","frontend/src/features/subscription/UpgradePrompt.tsx","frontend/src/features/subscription/PendingState.tsx"],"complexity":"M","specSections":["1.3 State Machines and Permission Matrices","1.6 Route Manifest","1.9 Performance Targets","1.13 Feature Scope"]},
  {"id":"S3-G","phase":3,"name":"Frontend: Exports UI + Notifications","category":"Frontend","prerequisites":["S1-F","S2-D"],"ownedFiles":["frontend/src/features/exports/ExportButton.tsx","frontend/src/features/exports/ExportModal.tsx","frontend/src/features/exports/useExportStatus.ts","frontend/src/features/notifications/InAppNotifications.tsx","frontend/src/features/notifications/notificationsStore.ts"],"complexity":"M","specSections":["1.9 Performance Targets","1.13 Feature Scope"]},
  {"id":"S3-H","phase":3,"name":"Marketing Site (Next.js)","category":"Frontend","prerequisites":["S0-A"],"ownedFiles":["marketing/app/(marketing)/page.tsx","marketing/app/pricing/page.tsx","marketing/app/about/page.tsx","marketing/app/contact/page.tsx","marketing/components/Hero.tsx","marketing/components/PricingTable.tsx","marketing/components/Footer.tsx","marketing/public/robots.txt","marketing/public/sitemap.xml"],"complexity":"M","specSections":["1.8 Technology Stack"]},
  {"id":"S4-A","phase":4,"name":"E2E Integration Tests","category":"Testing/Hardening","prerequisites":["S2-A","S2-B","S2-C","S2-D","S2-E","S2-F","S2-G","S2-H","S2-I","S2-J","S2-K","S2-L","S2-M","S3-A","S3-B","S3-C","S3-D","S3-E","S3-F","S3-G"],"ownedFiles":["tests/integration/e2e/test_upload_to_complete.py","tests/integration/e2e/test_correction_flow.py","tests/integration/e2e/test_export_sync_and_async.py","tests/integration/e2e/test_stripe_lifecycle.py","tests/integration/e2e/test_gdpr_erasure.py","tests/integration/e2e/test_blocklist_two_gate.py","tests/integration/e2e/test_free_tier_limit.py"],"complexity":"L","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.10 Analytics Event Contracts","1.13 Feature Scope"]}
]
```

Total: 30 sessions across 5 phases
```

---

### build-plan-build-summary [primary]

**System Prompt:**
```
You are generating a build summary for an autonomous build plan. Using the session table provided, produce:

| Phase | Sessions | Max parallel | Gate requirement | Est. Claude Code hours |
| ----- | -------- | ------------ | ---------------- | ---------------------- |

Total the hours column. State estimated calendar time assuming same-day human gate reviews between phases. State the critical path total duration separately.

Also include:
- **Cost estimate**: approximate API cost based on session complexity (S ≈ $0.50-1, M ≈ $1-2, L ≈ $2-4 per session)
- **Risk summary**: which sessions are on the critical path, which have the most dependencies, which are the highest complexity
- **Recommended execution strategy**: whether to run all parallel sessions simultaneously or stagger them
```

**User Message:**
```
# PID Analyzer — Session Decomposition

| ID | Name | Category | Phase | Prerequisites | Owned files (exhaustive) | Complexity |
| -- | ---- | -------- | ----- | ------------- | ------------------------ | ---------- |
| S0-A | Scaffold & Shared Stubs | Infrastructure | 0 | — | `backend/app/main.py`, `backend/app/config.py`, `backend/app/db/base.py`, `backend/app/db/session.py`, `backend/app/api/__init__.py`, `backend/app/api/routers/__init__.py` (all router include stubs), `backend/app/api/routers/_stubs.py` (placeholder endpoints for every route in §1.6 P0+P1), `backend/app/workers/celery_app.py`, `backend/app/workers/__init__.py`, `backend/app/schemas/contracts.py` (pydantic mirrors of §1.1), `backend/app/schemas/__init__.py`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/Dockerfile`, `backend/Dockerfile.worker`, `backend/Dockerfile.ml`, `frontend/index.html`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/router.tsx` (lazy route stubs for all SPA pages), `frontend/src/pages/_stubs.tsx`, `frontend/src/types/contracts.ts`, `marketing/next.config.js`, `marketing/tsconfig.json`, `marketing/app/layout.tsx`, `marketing/app/page.tsx`, `docker-compose.yml`, `docker-compose.test.yml`, `.env.example`, `README.md`, `ops/oda-sandbox/Dockerfile`, `ops/clamav/Dockerfile` | L |
| S0-B | Integration Harness & Manifests | Testing/Hardening | 0 | — | `package.json` (root workspace), `backend/pyproject.toml`, `backend/poetry.lock`, `frontend/package.json`, `marketing/package.json`, `tests/integration/conftest.py`, `tests/integration/docker-compose.fixtures.yml`, `tests/integration/fixtures/db.py`, `tests/integration/fixtures/redis.py`, `tests/integration/fixtures/s3.py`, `tests/integration/smoke/test_smoke.py`, `tests/integration/README.md`, `scripts/test-integration.sh`, `.github/workflows/integration.yml` | M |
| S1-A | DB Models & Migrations | Infrastructure | 1 | S0-A, S0-B | `backend/app/db/models/__init__.py`, `backend/app/db/models/user.py`, `backend/app/db/models/team.py`, `backend/app/db/models/tier.py`, `backend/app/db/models/subscription.py`, `backend/app/db/models/stored_file.py`, `backend/app/db/models/file_hash_blocklist.py`, `backend/app/db/models/drawing.py`, `backend/app/db/models/entity_class.py`, `backend/app/db/models/detected_symbol.py`, `backend/app/db/models/table_cell.py`, `backend/app/db/models/user_correction.py`, `backend/app/db/models/export_record.py`, `backend/app/db/models/ml_training_consent.py`, `backend/app/db/models/revision_comparison.py`, `backend/app/db/models/audit_log.py`, `backend/app/db/models/stripe_event.py`, `backend/alembic/versions/0001_initial_schema.py`, `backend/alembic/versions/0002_rls_policies.py`, `backend/alembic/versions/0003_audit_partitions.py`, `backend/app/db/seed_tiers.py`, `backend/app/db/seed_entity_classes.py` | L |
| S1-B | Auth Middleware & Supabase Client | Auth/Contracts | 1 | S0-A, S0-B | `backend/app/auth/__init__.py`, `backend/app/auth/supabase_client.py`, `backend/app/auth/jwt_verifier.py`, `backend/app/auth/middleware.py`, `backend/app/auth/dependencies.py`, `backend/app/auth/permissions.py` (role matrix from §1.3), `backend/app/auth/brute_force.py`, `tests/integration/test_auth_middleware.py` | M |
| S1-C | Storage & Hash Utilities | Infrastructure | 1 | S0-A, S0-B | `backend/app/storage/__init__.py`, `backend/app/storage/s3_client.py`, `backend/app/storage/presigned.py`, `backend/app/storage/hashing.py`, `backend/app/storage/blocklist.py`, `tests/integration/test_storage.py` | M |
| S1-D | Redis, Cache, Pub/Sub & Celery Config | Real-time/Queue | 1 | S0-A, S0-B | `backend/app/redis/__init__.py`, `backend/app/redis/client.py`, `backend/app/redis/cache.py` (subscription flags, entity taxonomy), `backend/app/redis/pubsub.py` (drawing:status channels), `backend/app/workers/queues.py` (queue routing config), `backend/app/workers/base.py` (Task base class with retry policy), `tests/integration/test_redis_pubsub.py` | M |
| S1-E | Analytics Emitter (PostHog) | Infrastructure | 1 | S0-A, S0-B | `backend/app/analytics/__init__.py`, `backend/app/analytics/posthog_client.py`, `backend/app/analytics/events.py` (typed emitters for all 9 events §1.10), `backend/app/analytics/dead_letter.py`, `tests/integration/test_analytics.py` | S |
| S1-F | Frontend Shared Infrastructure | Frontend | 1 | S0-A, S0-B | `frontend/src/api/client.ts`, `frontend/src/api/endpoints.ts`, `frontend/src/auth/AuthContext.tsx`, `frontend/src/auth/useAuth.ts`, `frontend/src/auth/supabaseClient.ts`, `frontend/src/hooks/useSSE.ts`, `frontend/src/hooks/usePolling.ts`, `frontend/src/components/Layout.tsx`, `frontend/src/components/Nav.tsx`, `frontend/src/components/GraceBanner.tsx`, `frontend/src/components/ProtectedRoute.tsx`, `frontend/src/lib/storage.ts` (localStorage/sessionStorage helpers), `frontend/src/lib/analytics.ts`, `frontend/src/styles/globals.css` | M |
| S2-A | Auth Endpoints | Auth/Contracts | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/auth.py`, `backend/app/services/auth_service.py`, `backend/app/services/password_reset.py`, `tests/integration/test_auth_endpoints.py` | M |
| S2-B | Drawings Endpoints + SSE Status | Backend API | 2 | S1-A, S1-B, S1-C, S1-D, S1-E | `backend/app/api/routers/drawings.py`, `backend/app/services/drawing_service.py`, `backend/app/services/hash_check_service.py`, `backend/app/services/upload_complete_service.py`, `backend/app/services/drawing_state_machine.py`, `backend/app/services/free_tier_counter.py`, `backend/app/sse/drawing_status.py`, `tests/integration/test_drawings_api.py`, `tests/integration/test_drawings_sse.py` | L |
| S2-C | Symbols & Corrections Endpoints | Backend API | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/symbols.py`, `backend/app/services/symbol_service.py`, `backend/app/services/correction_service.py` (training_consent snapshot, Under_Review trigger), `tests/integration/test_symbols_api.py` | M |
| S2-D | Export Endpoints + Sync Path | Backend API | 2 | S1-A, S1-B, S1-C, S1-D, S1-E | `backend/app/api/routers/exports.py`, `backend/app/services/export_service.py` (sync <1000 path, threshold gate), `backend/app/services/export_generators.py` (CSV/XLSX), `tests/integration/test_exports_api.py` | M |
| S2-E | Subscription + Stripe Webhook | Backend API | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/subscription.py`, `backend/app/api/routers/stripe_webhook.py`, `backend/app/services/stripe_client.py`, `backend/app/services/subscription_service.py`, `backend/app/services/billing_state_machine.py`, `backend/app/services/stripe_event_idempotency.py`, `tests/integration/test_subscription.py`, `tests/integration/test_stripe_webhook.py` | L |
| S2-F | Account, Consent & GDPR Init Endpoints | Backend API | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/account.py`, `backend/app/services/account_service.py`, `backend/app/services/consent_service.py` (server-side team consent resolution), `backend/app/services/gdpr_init_service.py`, `tests/integration/test_account.py` | M |
| S2-G | Entity Classes & Misc Endpoints | Backend API | 2 | S1-A, S1-D | `backend/app/api/routers/entity_classes.py`, `backend/app/services/entity_class_service.py`, `tests/integration/test_entity_classes.py` | S |
| S2-H | Ingest Worker | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/ingest/__init__.py`, `backend/app/workers/ingest/tasks.py`, `backend/app/workers/ingest/oda_converter.py`, `backend/app/workers/ingest/hash_reverify.py`, `backend/app/workers/ingest/format_detect.py`, `tests/integration/test_ingest_worker.py` | L |
| S2-I | Scan Worker (ClamAV) | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/scan/__init__.py`, `backend/app/workers/scan/tasks.py`, `backend/app/workers/scan/clamav_client.py`, `tests/integration/test_scan_worker.py` | S |
| S2-J | ML Worker | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/ml/__init__.py`, `backend/app/workers/ml/tasks.py`, `backend/app/workers/ml/inference.py`, `backend/app/workers/ml/model_loader.py`, `backend/app/workers/ml/result_persistence.py`, `tests/integration/test_ml_worker.py` | L |
| S2-K | Export Worker (Async) | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/export/__init__.py`, `backend/app/workers/export/tasks.py`, `tests/integration/test_export_worker.py` | M |
| S2-L | GDPR Erasure Worker | Real-time/Queue | 2 | S1-A, S1-C, S1-D | `backend/app/workers/gdpr/__init__.py`, `backend/app/workers/gdpr/tasks.py`, `backend/app/workers/gdpr/anonymizer.py` (anonymous_id HMAC, idempotent), `tests/integration/test_gdpr_worker.py` | M |
| S2-M | Notification Worker (SendGrid) | Real-time/Queue | 2 | S1-A, S1-D | `backend/app/workers/notification/__init__.py`, `backend/app/workers/notification/tasks.py`, `backend/app/workers/notification/sendgrid_client.py`, `backend/app/workers/notification/templates.py` (verification, reset, invite, grace day-1/6), `tests/integration/test_notification_worker.py` | M |
| S3-A | Frontend: Auth Pages | Frontend | 3 | S1-F, S2-A | `frontend/src/pages/auth/Register.tsx`, `frontend/src/pages/auth/Login.tsx`, `frontend/src/pages/auth/VerifyEmail.tsx`, `frontend/src/pages/auth/PasswordResetRequest.tsx`, `frontend/src/pages/auth/PasswordResetConfirm.tsx`, `frontend/src/pages/auth/OAuthCallback.tsx`, `frontend/src/pages/auth/AccountLinkPrompt.tsx` | M |
| S3-B | Frontend: Drawing Library | Frontend | 3 | S1-F, S2-B | `frontend/src/pages/Dashboard.tsx`, `frontend/src/features/library/DrawingList.tsx`, `frontend/src/features/library/DrawingRow.tsx`, `frontend/src/features/library/StatusBadge.tsx`, `frontend/src/features/library/SearchFilter.tsx`, `frontend/src/features/library/Pagination.tsx`, `frontend/src/features/library/useDrawings.ts` | M |
| S3-C | Frontend: Upload Flow | Frontend | 3 | S1-F, S2-B | `frontend/src/pages/Upload.tsx`, `frontend/src/features/upload/DropZone.tsx`, `frontend/src/features/upload/hashClient.ts`, `frontend/src/features/upload/uploadOrchestrator.ts`, `frontend/src/features/upload/UploadProgress.tsx` | M |
| S3-D | Frontend: Review Canvas (Konva) | Frontend | 3 | S1-F, S2-B, S2-C | `frontend/src/pages/Review.tsx`, `frontend/src/features/canvas/Canvas.tsx`, `frontend/src/features/canvas/SymbolLayer.tsx`, `frontend/src/features/canvas/BoundingBox.tsx`, `frontend/src/features/canvas/PageNav.tsx`, `frontend/src/features/canvas/InspectionPanel.tsx`, `frontend/src/features/canvas/ManualAnnotate.tsx`, `frontend/src/features/canvas/CorrectionStore.ts`, `frontend/src/features/canvas/useCanvasShortcuts.ts` | L |
| S3-E | Frontend: Account & Consent | Frontend | 3 | S1-F, S2-F | `frontend/src/pages/Account.tsx`, `frontend/src/features/account/ProfileForm.tsx`, `frontend/src/features/account/ConsentToggle.tsx`, `frontend/src/features/account/DeleteAccount.tsx` | S |
| S3-F | Frontend: Subscription & Upgrade | Frontend | 3 | S1-F, S2-E | `frontend/src/pages/Subscription.tsx`, `frontend/src/features/subscription/TierCard.tsx`, `frontend/src/features/subscription/CheckoutRedirect.tsx`, `frontend/src/features/subscription/UpgradePrompt.tsx`, `frontend/src/features/subscription/PendingState.tsx` | M |
| S3-G | Frontend: Exports UI + Notifications | Frontend | 3 | S1-F, S2-D | `frontend/src/features/exports/ExportButton.tsx`, `frontend/src/features/exports/ExportModal.tsx`, `frontend/src/features/exports/useExportStatus.ts`, `frontend/src/features/notifications/InAppNotifications.tsx`, `frontend/src/features/notifications/notificationsStore.ts` | M |
| S3-H | Marketing Site (Next.js) | Frontend | 3 | S0-A | `marketing/app/(marketing)/page.tsx`, `marketing/app/pricing/page.tsx`, `marketing/app/about/page.tsx`, `marketing/app/contact/page.tsx`, `marketing/components/Hero.tsx`, `marketing/components/PricingTable.tsx`, `marketing/components/Footer.tsx`, `marketing/public/robots.txt`, `marketing/public/sitemap.xml` | M |
| S4-A | E2E Integration Tests | Testing/Hardening | 4 | All Phase 2 + Phase 3 | `tests/integration/e2e/test_upload_to_complete.py`, `tests/integration/e2e/test_correction_flow.py`, `tests/integration/e2e/test_export_sync_and_async.py`, `tests/integration/e2e/test_stripe_lifecycle.py`, `tests/integration/e2e/test_gdpr_erasure.py`, `tests/integration/e2e/test_blocklist_two_gate.py`, `tests/integration/e2e/test_free_tier_limit.py` | L |

---

## Gate Definitions

**Phase 0 → Phase 1 gate** (must merge): `S0-A`, `S0-B`. Both required: scaffold provides stubs every Phase 1 session imports; harness provides the green integration baseline (`npm run test:integration` exits 0).

**Phase 1 → Phase 2 gate** (must merge): `S1-A`, `S1-B`, `S1-C`, `S1-D`, `S1-E`. Non-blocking for Phase 2 backend work: `S1-F` (frontend-only; gates Phase 3 only).

**Phase 2 → Phase 3 gate** (must merge per frontend session): each Phase 3 session depends only on its specific Phase 2 endpoint(s) — see prerequisites column. Marketing (`S3-H`) needs only Phase 0.

**Phase 3 → Phase 4 gate** (must merge): all Phase 2 + Phase 3 sessions.

---

## Intra-Phase Dependencies

None within Phase 1 (all five core infra sessions are parallel; they only import from S0-A stubs).

None within Phase 2 — workers and API routers own disjoint files. They communicate only through Celery queues / Redis channels / DB tables defined in Phase 1.

None within Phase 3 — each frontend feature owns its own subdirectory.

---

## Early-Start Optimizations

- **S1-F (frontend shared)** depends only on `S0-A`/`S0-B` — can start with Phase 1 even though it gates Phase 3 frontends.
- **S3-H (marketing site)** depends only on `S0-A` — can start as early as Phase 1.
- **S2-G (entity classes)** needs only `S1-A` + `S1-D`, can start as soon as those two merge (before S1-B/C/E).
- **S2-L (GDPR worker)** and **S2-M (notification worker)** don't need `S1-E` analytics — can start once `S1-A`/`S1-C`/`S1-D` clear.
- **S3-A (auth pages)** can begin as soon as `S2-A` clears, regardless of other Phase 2 progress.

---

## Critical Path

`S0-A` → `S1-A` (DB models) → `S2-B` (Drawings API + SSE) → `S3-D` (Review canvas — largest frontend) → `S4-A` (E2E tests)

Length: 5 sessions, complexity L → L → L → L → L ≈ 15 hrs of Claude execution on the longest chain.

---

```json
[
  {"id":"S0-A","phase":0,"name":"Scaffold & Shared Stubs","category":"Infrastructure","prerequisites":[],"ownedFiles":["backend/app/main.py","backend/app/config.py","backend/app/db/base.py","backend/app/db/session.py","backend/app/api/__init__.py","backend/app/api/routers/__init__.py","backend/app/api/routers/_stubs.py","backend/app/workers/celery_app.py","backend/app/workers/__init__.py","backend/app/schemas/contracts.py","backend/app/schemas/__init__.py","backend/alembic.ini","backend/alembic/env.py","backend/alembic/script.py.mako","backend/Dockerfile","backend/Dockerfile.worker","backend/Dockerfile.ml","frontend/index.html","frontend/vite.config.ts","frontend/tsconfig.json","frontend/src/main.tsx","frontend/src/App.tsx","frontend/src/router.tsx","frontend/src/pages/_stubs.tsx","frontend/src/types/contracts.ts","marketing/next.config.js","marketing/tsconfig.json","marketing/app/layout.tsx","marketing/app/page.tsx","docker-compose.yml","docker-compose.test.yml",".env.example","README.md","ops/oda-sandbox/Dockerfile","ops/clamav/Dockerfile"],"complexity":"L","specSections":["1.1 Shared Contracts","1.6 Route Manifest","1.8 Technology Stack","1.12 Environment Variable Schema"]},
  {"id":"S0-B","phase":0,"name":"Integration Harness & Manifests","category":"Testing/Hardening","prerequisites":[],"ownedFiles":["package.json","backend/pyproject.toml","backend/poetry.lock","frontend/package.json","marketing/package.json","tests/integration/conftest.py","tests/integration/docker-compose.fixtures.yml","tests/integration/fixtures/db.py","tests/integration/fixtures/redis.py","tests/integration/fixtures/s3.py","tests/integration/smoke/test_smoke.py","tests/integration/README.md","scripts/test-integration.sh",".github/workflows/integration.yml"],"complexity":"M","specSections":["1.8 Technology Stack","1.12 Environment Variable Schema"]},
  {"id":"S1-A","phase":1,"name":"DB Models & Migrations","category":"Infrastructure","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/db/models/__init__.py","backend/app/db/models/user.py","backend/app/db/models/team.py","backend/app/db/models/tier.py","backend/app/db/models/subscription.py","backend/app/db/models/stored_file.py","backend/app/db/models/file_hash_blocklist.py","backend/app/db/models/drawing.py","backend/app/db/models/entity_class.py","backend/app/db/models/detected_symbol.py","backend/app/db/models/table_cell.py","backend/app/db/models/user_correction.py","backend/app/db/models/export_record.py","backend/app/db/models/ml_training_consent.py","backend/app/db/models/revision_comparison.py","backend/app/db/models/audit_log.py","backend/app/db/models/stripe_event.py","backend/alembic/versions/0001_initial_schema.py","backend/alembic/versions/0002_rls_policies.py","backend/alembic/versions/0003_audit_partitions.py","backend/app/db/seed_tiers.py","backend/app/db/seed_entity_classes.py"],"complexity":"L","specSections":["1.2 Database Schema","1.3 State Machines and Permission Matrices"]},
  {"id":"S1-B","phase":1,"name":"Auth Middleware & Supabase Client","category":"Auth/Contracts","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/auth/__init__.py","backend/app/auth/supabase_client.py","backend/app/auth/jwt_verifier.py","backend/app/auth/middleware.py","backend/app/auth/dependencies.py","backend/app/auth/permissions.py","backend/app/auth/brute_force.py","tests/integration/test_auth_middleware.py"],"complexity":"M","specSections":["1.3 State Machines and Permission Matrices","1.4 Critical Ordering Rules","1.7 Third-Party Dependencies"]},
  {"id":"S1-C","phase":1,"name":"Storage & Hash Utilities","category":"Infrastructure","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/storage/__init__.py","backend/app/storage/s3_client.py","backend/app/storage/presigned.py","backend/app/storage/hashing.py","backend/app/storage/blocklist.py","tests/integration/test_storage.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.7 Third-Party Dependencies","1.9 Performance Targets"]},
  {"id":"S1-D","phase":1,"name":"Redis, Cache, Pub/Sub & Celery Config","category":"Real-time/Queue","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/redis/__init__.py","backend/app/redis/client.py","backend/app/redis/cache.py","backend/app/redis/pubsub.py","backend/app/workers/queues.py","backend/app/workers/base.py","tests/integration/test_redis_pubsub.py"],"complexity":"M","specSections":["1.11 Cross-Session Runtime Patterns","1.8 Technology Stack"]},
  {"id":"S1-E","phase":1,"name":"Analytics Emitter (PostHog)","category":"Infrastructure","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/analytics/__init__.py","backend/app/analytics/posthog_client.py","backend/app/analytics/events.py","backend/app/analytics/dead_letter.py","tests/integration/test_analytics.py"],"complexity":"S","specSections":["1.10 Analytics Event Contracts"]},
  {"id":"S1-F","phase":1,"name":"Frontend Shared Infrastructure","category":"Frontend","prerequisites":["S0-A","S0-B"],"ownedFiles":["frontend/src/api/client.ts","frontend/src/api/endpoints.ts","frontend/src/auth/AuthContext.tsx","frontend/src/auth/useAuth.ts","frontend/src/auth/supabaseClient.ts","frontend/src/hooks/useSSE.ts","frontend/src/hooks/usePolling.ts","frontend/src/components/Layout.tsx","frontend/src/components/Nav.tsx","frontend/src/components/GraceBanner.tsx","frontend/src/components/ProtectedRoute.tsx","frontend/src/lib/storage.ts","frontend/src/lib/analytics.ts","frontend/src/styles/globals.css"],"complexity":"M","specSections":["1.1 Shared Contracts","1.6 Route Manifest","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-A","phase":2,"name":"Auth Endpoints","category":"Auth/Contracts","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/auth.py","backend/app/services/auth_service.py","backend/app/services/password_reset.py","tests/integration/test_auth_endpoints.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.6 Route Manifest","1.13 Feature Scope"]},
  {"id":"S2-B","phase":2,"name":"Drawings Endpoints + SSE Status","category":"Backend API","prerequisites":["S1-A","S1-B","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/drawings.py","backend/app/services/drawing_service.py","backend/app/services/hash_check_service.py","backend/app/services/upload_complete_service.py","backend/app/services/drawing_state_machine.py","backend/app/services/free_tier_counter.py","backend/app/sse/drawing_status.py","tests/integration/test_drawings_api.py","tests/integration/test_drawings_sse.py"],"complexity":"L","specSections":["1.3 State Machines and Permission Matrices","1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.6 Route Manifest","1.10 Analytics Event Contracts","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-C","phase":2,"name":"Symbols & Corrections Endpoints","category":"Backend API","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/symbols.py","backend/app/services/symbol_service.py","backend/app/services/correction_service.py","tests/integration/test_symbols_api.py"],"complexity":"M","specSections":["1.1 Shared Contracts","1.4 Critical Ordering Rules","1.10 Analytics Event Contracts","1.13 Feature Scope"]},
  {"id":"S2-D","phase":2,"name":"Export Endpoints + Sync Path","category":"Backend API","prerequisites":["S1-A","S1-B","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/exports.py","backend/app/services/export_service.py","backend/app/services/export_generators.py","tests/integration/test_exports_api.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.6 Route Manifest","1.9 Performance Targets","1.10 Analytics Event Contracts"]},
  {"id":"S2-E","phase":2,"name":"Subscription + Stripe Webhook","category":"Backend API","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/subscription.py","backend/app/api/routers/stripe_webhook.py","backend/app/services/stripe_client.py","backend/app/services/subscription_service.py","backend/app/services/billing_state_machine.py","backend/app/services/stripe_event_idempotency.py","tests/integration/test_subscription.py","tests/integration/test_stripe_webhook.py"],"complexity":"L","specSections":["1.3 State Machines and Permission Matrices","1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.7 Third-Party Dependencies","1.10 Analytics Event Contracts"]},
  {"id":"S2-F","phase":2,"name":"Account, Consent & GDPR Init Endpoints","category":"Backend API","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/account.py","backend/app/services/account_service.py","backend/app/services/consent_service.py","backend/app/services/gdpr_init_service.py","tests/integration/test_account.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.13 Feature Scope"]},
  {"id":"S2-G","phase":2,"name":"Entity Classes & Misc Endpoints","category":"Backend API","prerequisites":["S1-A","S1-D"],"ownedFiles":["backend/app/api/routers/entity_classes.py","backend/app/services/entity_class_service.py","tests/integration/test_entity_classes.py"],"complexity":"S","specSections":["1.6 Route Manifest","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-H","phase":2,"name":"Ingest Worker","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/ingest/__init__.py","backend/app/workers/ingest/tasks.py","backend/app/workers/ingest/oda_converter.py","backend/app/workers/ingest/hash_reverify.py","backend/app/workers/ingest/format_detect.py","tests/integration/test_ingest_worker.py"],"complexity":"L","specSections":["1.4 Critical Ordering Rules","1.7 Third-Party Dependencies","1.11 Cross-Session Runtime Patterns","1.13 Feature Scope"]},
  {"id":"S2-I","phase":2,"name":"Scan Worker (ClamAV)","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/scan/__init__.py","backend/app/workers/scan/tasks.py","backend/app/workers/scan/clamav_client.py","tests/integration/test_scan_worker.py"],"complexity":"S","specSections":["1.7 Third-Party Dependencies","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-J","phase":2,"name":"ML Worker","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/ml/__init__.py","backend/app/workers/ml/tasks.py","backend/app/workers/ml/inference.py","backend/app/workers/ml/model_loader.py","backend/app/workers/ml/result_persistence.py","tests/integration/test_ml_worker.py"],"complexity":"L","specSections":["1.1 Shared Contracts","1.4 Critical Ordering Rules","1.9 Performance Targets","1.10 Analytics Event Contracts","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-K","phase":2,"name":"Export Worker (Async)","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/export/__init__.py","backend/app/workers/export/tasks.py","tests/integration/test_export_worker.py"],"complexity":"M","specSections":["1.9 Performance Targets","1.11 Cross-Session Runtime Patterns","1.13 Feature Scope"]},
  {"id":"S2-L","phase":2,"name":"GDPR Erasure Worker","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D"],"ownedFiles":["backend/app/workers/gdpr/__init__.py","backend/app/workers/gdpr/tasks.py","backend/app/workers/gdpr/anonymizer.py","tests/integration/test_gdpr_worker.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.11 Cross-Session Runtime Patterns","1.12 Environment Variable Schema","1.13 Feature Scope"]},
  {"id":"S2-M","phase":2,"name":"Notification Worker (SendGrid)","category":"Real-time/Queue","prerequisites":["S1-A","S1-D"],"ownedFiles":["backend/app/workers/notification/__init__.py","backend/app/workers/notification/tasks.py","backend/app/workers/notification/sendgrid_client.py","backend/app/workers/notification/templates.py","tests/integration/test_notification_worker.py"],"complexity":"M","specSections":["1.3 State Machines and Permission Matrices","1.7 Third-Party Dependencies","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S3-A","phase":3,"name":"Frontend: Auth Pages","category":"Frontend","prerequisites":["S1-F","S2-A"],"ownedFiles":["frontend/src/pages/auth/Register.tsx","frontend/src/pages/auth/Login.tsx","frontend/src/pages/auth/VerifyEmail.tsx","frontend/src/pages/auth/PasswordResetRequest.tsx","frontend/src/pages/auth/PasswordResetConfirm.tsx","frontend/src/pages/auth/OAuthCallback.tsx","frontend/src/pages/auth/AccountLinkPrompt.tsx"],"complexity":"M","specSections":["1.6 Route Manifest","1.13 Feature Scope"]},
  {"id":"S3-B","phase":3,"name":"Frontend: Drawing Library","category":"Frontend","prerequisites":["S1-F","S2-B"],"ownedFiles":["frontend/src/pages/Dashboard.tsx","frontend/src/features/library/DrawingList.tsx","frontend/src/features/library/DrawingRow.tsx","frontend/src/features/library/StatusBadge.tsx","frontend/src/features/library/SearchFilter.tsx","frontend/src/features/library/Pagination.tsx","frontend/src/features/library/useDrawings.ts"],"complexity":"M","specSections":["1.6 Route Manifest","1.9 Performance Targets","1.13 Feature Scope"]},
  {"id":"S3-C","phase":3,"name":"Frontend: Upload Flow","category":"Frontend","prerequisites":["S1-F","S2-B"],"ownedFiles":["frontend/src/pages/Upload.tsx","frontend/src/features/upload/DropZone.tsx","frontend/src/features/upload/hashClient.ts","frontend/src/features/upload/uploadOrchestrator.ts","frontend/src/features/upload/UploadProgress.tsx"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.13 Feature Scope"]},
  {"id":"S3-D","phase":3,"name":"Frontend: Review Canvas (Konva)","category":"Frontend","prerequisites":["S1-F","S2-B","S2-C"],"ownedFiles":["frontend/src/pages/Review.tsx","frontend/src/features/canvas/Canvas.tsx","frontend/src/features/canvas/SymbolLayer.tsx","frontend/src/features/canvas/BoundingBox.tsx","frontend/src/features/canvas/PageNav.tsx","frontend/src/features/canvas/InspectionPanel.tsx","frontend/src/features/canvas/ManualAnnotate.tsx","frontend/src/features/canvas/CorrectionStore.ts","frontend/src/features/canvas/useCanvasShortcuts.ts"],"complexity":"L","specSections":["1.6 Route Manifest","1.8 Technology Stack","1.9 Performance Targets","1.11 Cross-Session Runtime Patterns","1.13 Feature Scope"]},
  {"id":"S3-E","phase":3,"name":"Frontend: Account & Consent","category":"Frontend","prerequisites":["S1-F","S2-F"],"ownedFiles":["frontend/src/pages/Account.tsx","frontend/src/features/account/ProfileForm.tsx","frontend/src/features/account/ConsentToggle.tsx","frontend/src/features/account/DeleteAccount.tsx"],"complexity":"S","specSections":["1.6 Route Manifest","1.13 Feature Scope"]},
  {"id":"S3-F","phase":3,"name":"Frontend: Subscription & Upgrade","category":"Frontend","prerequisites":["S1-F","S2-E"],"ownedFiles":["frontend/src/pages/Subscription.tsx","frontend/src/features/subscription/TierCard.tsx","frontend/src/features/subscription/CheckoutRedirect.tsx","frontend/src/features/subscription/UpgradePrompt.tsx","frontend/src/features/subscription/PendingState.tsx"],"complexity":"M","specSections":["1.3 State Machines and Permission Matrices","1.6 Route Manifest","1.9 Performance Targets","1.13 Feature Scope"]},
  {"id":"S3-G","phase":3,"name":"Frontend: Exports UI + Notifications","category":"Frontend","prerequisites":["S1-F","S2-D"],"ownedFiles":["frontend/src/features/exports/ExportButton.tsx","frontend/src/features/exports/ExportModal.tsx","frontend/src/features/exports/useExportStatus.ts","frontend/src/features/notifications/InAppNotifications.tsx","frontend/src/features/notifications/notificationsStore.ts"],"complexity":"M","specSections":["1.9 Performance Targets","1.13 Feature Scope"]},
  {"id":"S3-H","phase":3,"name":"Marketing Site (Next.js)","category":"Frontend","prerequisites":["S0-A"],"ownedFiles":["marketing/app/(marketing)/page.tsx","marketing/app/pricing/page.tsx","marketing/app/about/page.tsx","marketing/app/contact/page.tsx","marketing/components/Hero.tsx","marketing/components/PricingTable.tsx","marketing/components/Footer.tsx","marketing/public/robots.txt","marketing/public/sitemap.xml"],"complexity":"M","specSections":["1.8 Technology Stack"]},
  {"id":"S4-A","phase":4,"name":"E2E Integration Tests","category":"Testing/Hardening","prerequisites":["S2-A","S2-B","S2-C","S2-D","S2-E","S2-F","S2-G","S2-H","S2-I","S2-J","S2-K","S2-L","S2-M","S3-A","S3-B","S3-C","S3-D","S3-E","S3-F","S3-G"],"ownedFiles":["tests/integration/e2e/test_upload_to_complete.py","tests/integration/e2e/test_correction_flow.py","tests/integration/e2e/test_export_sync_and_async.py","tests/integration/e2e/test_stripe_lifecycle.py","tests/integration/e2e/test_gdpr_erasure.py","tests/integration/e2e/test_blocklist_two_gate.py","tests/integration/e2e/test_free_tier_limit.py"],"complexity":"L","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.10 Analytics Event Contracts","1.13 Feature Scope"]}
]
```

Total: 30 sessions across 5 phases
```

---

### build-plan-out-of-band [primary]

**System Prompt:**
```
You are identifying out-of-band validation tasks for an autonomous build plan. These are tasks that must complete before specific sessions can safely start but are NOT themselves Claude Code sessions.

Using the distilled spec and session table provided, identify every technical spike, third-party confirmation, environment setup, or device test needed.

For each task:
- **Name**: what needs to be validated
- **Gates**: which session(s) cannot start until this passes
- **Pass condition**: the exact observable outcome that constitutes a pass
- **Fail condition**: what "blocked" looks like
- **Fallback architecture**: the alternative implementation approach if this fails, and which session briefs need to change

Common out-of-band tasks include: database provisioning, API key procurement, third-party API access confirmation, CI/CD pipeline setup, DNS configuration, SSL certificate provisioning, environment variable configuration, external service sandbox access.

If the project has no out-of-band tasks (e.g., a self-contained library), state "No out-of-band tasks identified" and explain why.
```

**User Message:**
```
# Distilled Specification — PID Analyzer

---

## 1.1 Shared Contracts

```typescript
// [CRITICAL BOUNDARY] — ML Inference Job Payload
// Written by: FastAPI (API layer at enqueue time)
// Read by: ML Worker, Ingest Worker (for job context), analytics emitters
interface MLInferenceJobPayload {
  storage_reference: string;       // S3 object key
  drawing_id: string;              // UUID
  user_id: string;                 // UUID — MUST be set at enqueue time by API layer
  page_range?: [number, number];   // optional, 1-based inclusive
}

// ML Inference Service Response
interface MLInferenceResult {
  drawing_id: string;
  symbols: DetectedSymbolResult[];
  tables: TableRegionResult[];
}

interface DetectedSymbolResult {
  entity_class_id: string;
  subtype: string;
  tag_label: string | null;
  confidence: number;              // 0.0–1.0
  bbox: BoundingBox;
  page_number: number;
}

interface TableRegionResult {
  bbox: BoundingBox;
  page_number: number;
  cells: TableCellResult[];
}

interface TableCellResult {
  row_label: string;
  column_label: string;
  bbox: BoundingBox;
  extracted_value: string;
}

interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
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

// Subscription Billing State
type BillingState = 'Active' | 'Grace' | 'Canceled';

// Tier IDs
type TierId = 'free' | 'pro' | 'team';

// User Role
type UserRole = 'user' | 'team_member' | 'team_admin';

// Symbol Source
type SymbolSource = 'ml' | 'manual';

// Correction Type
type CorrectionType = 'reclassify' | 'reject' | 'restore' | 'manual_add';

// Export Format
type ExportFormat = 'csv' | 'xlsx';

// Export Status
type ExportStatus = 'Queued' | 'Generating' | 'Complete' | 'Failed';

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

// SSE Drawing Status Event (Redis pub/sub → client)
interface DrawingStatusSSEEvent {
  drawing_id: string;
  state: DrawingProcessingState;
  timestamp: string;               // ISO 8601 UTC
}

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
```

---

## 1.2 Database Schema

```sql
-- EXTENSIONS
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- TIER
CREATE TABLE tier (
  id          VARCHAR PRIMARY KEY,   -- 'free' | 'pro' | 'team'
  name        VARCHAR NOT NULL,
  monthly_drawing_limit  INTEGER,    -- NULL = unlimited
  team_features          BOOLEAN NOT NULL DEFAULT FALSE,
  api_access             BOOLEAN NOT NULL DEFAULT FALSE
);

-- TEAM
CREATE TABLE team (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            VARCHAR NOT NULL,
  licensed_seats  INTEGER NOT NULL
);

-- USER
CREATE TABLE "user" (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email                  VARCHAR NOT NULL,
  display_name           VARCHAR NOT NULL,
  password_hash          VARCHAR,
  email_verified         BOOLEAN NOT NULL DEFAULT FALSE,
  team_id                UUID REFERENCES team(id),
  role                   VARCHAR NOT NULL CHECK (role IN ('user','team_member','team_admin')),
  deleted_at             TIMESTAMPTZ,
  anonymous_id           VARCHAR,                     -- HMAC-SHA256(user_id||server_secret), set on first erasure run
  token_invalidated_at   TIMESTAMPTZ,
  CONSTRAINT user_email_unique UNIQUE (email)
);

CREATE INDEX idx_user_team ON "user"(team_id);
CREATE INDEX idx_user_email ON "user"(email);

-- SUBSCRIPTION
CREATE TABLE subscription (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                 UUID REFERENCES "user"(id),
  team_id                 UUID REFERENCES team(id),
  tier_id                 VARCHAR NOT NULL REFERENCES tier(id),
  billing_state           VARCHAR NOT NULL CHECK (billing_state IN ('Active','Grace','Canceled')),
  grace_period_start      TIMESTAMPTZ,
  stripe_subscription_id  VARCHAR,
  stripe_customer_id      VARCHAR,
  current_period_end      TIMESTAMPTZ,
  CONSTRAINT subscription_user_or_team CHECK (
    (user_id IS NOT NULL AND team_id IS NULL) OR
    (user_id IS NULL AND team_id IS NOT NULL)
  )
);

CREATE INDEX idx_subscription_user ON subscription(user_id);
CREATE INDEX idx_subscription_team ON subscription(team_id);

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

CREATE INDEX idx_stored_file_hash ON stored_file(sha256_hash);

-- FILE_HASH_BLOCKLIST
CREATE TABLE file_hash_blocklist (
  sha256_hash  VARCHAR PRIMARY KEY,
  blocked_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reason       VARCHAR NOT NULL
);

-- DRAWING
CREATE TABLE drawing (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id          UUID REFERENCES "user"(id),
  owner_team_id          UUID REFERENCES team(id),
  filename               VARCHAR NOT NULL,
  revision_label         VARCHAR,
  processing_state       VARCHAR NOT NULL CHECK (processing_state IN (
    'Pending','Queued','Scanning','Processing','Complete','Under_Review','Failed','Scan_Failed'
  )),
  page_count             INTEGER,
  estimated_symbol_count INTEGER,
  uploaded_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  processed_at           TIMESTAMPTZ,
  stored_file_id         UUID REFERENCES stored_file(id),
  CONSTRAINT drawing_owner CHECK (
    (owner_user_id IS NOT NULL AND owner_team_id IS NULL) OR
    (owner_user_id IS NULL AND owner_team_id IS NOT NULL)
  )
);

CREATE INDEX idx_drawing_team_state_date ON drawing(owner_team_id, processing_state, uploaded_at DESC);
CREATE INDEX idx_drawing_user ON drawing(owner_user_id);
CREATE INDEX idx_drawing_fts ON drawing USING GIN (to_tsvector('english', filename || ' ' || COALESCE(revision_label, '')));

-- ENTITY_CLASS
CREATE TABLE entity_class (
  id           VARCHAR PRIMARY KEY,  -- EntityClassId values
  name         VARCHAR NOT NULL,
  parent_class VARCHAR,
  color_hex    VARCHAR NOT NULL
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

CREATE INDEX idx_detected_symbol_drawing_rejected_class ON detected_symbol(drawing_id, rejected, entity_class_id);
CREATE INDEX idx_detected_symbol_drawing_page ON detected_symbol(drawing_id, page_number);

-- TABLE_CELL
CREATE TABLE table_cell (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  drawing_id                  UUID NOT NULL REFERENCES drawing(id) ON DELETE CASCADE,
  page_number                 INTEGER NOT NULL,
  row_label                   VARCHAR NOT NULL,
  column_label                VARCHAR NOT NULL,
  bbox                        JSONB NOT NULL,
  extracted_value             VARCHAR,
  corrected_value             VARCHAR,
  correction_training_consent BOOLEAN,
  corrected_at                TIMESTAMPTZ,
  corrected_by_user_id        UUID REFERENCES "user"(id)
);

CREATE INDEX idx_table_cell_drawing_page ON table_cell(drawing_id, page_number);

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

CREATE INDEX idx_user_correction_symbol ON user_correction(detected_symbol_id);
CREATE INDEX idx_user_correction_cell ON user_correction(table_cell_id);
CREATE INDEX idx_user_correction_consent ON user_correction(training_consent) WHERE training_consent = TRUE;

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

-- REVISION_COMPARISON
CREATE TABLE revision_comparison (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  drawing_a_id        UUID NOT NULL REFERENCES drawing(id),
  drawing_b_id        UUID NOT NULL REFERENCES drawing(id),
  match_result        JSONB,
  computed_at         TIMESTAMPTZ,
  last_correction_at  TIMESTAMPTZ
);

-- AUDIT_LOG (partitioned by month, 2-year retention)
CREATE TABLE audit_log (
  id            UUID NOT NULL DEFAULT gen_random_uuid(),
  user_id       UUID REFERENCES "user"(id),
  action_type   VARCHAR NOT NULL,
  entity_id     UUID,
  entity_type   VARCHAR,
  occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata      JSONB
) PARTITION BY RANGE (occurred_at);

CREATE INDEX idx_audit_log_user_date ON audit_log(user_id, occurred_at DESC);
-- Monthly partitions created as: audit_log_YYYY_MM

-- RLS POLICIES (representative — enforce ownership server-side in middleware as primary control)
ALTER TABLE drawing ENABLE ROW LEVEL SECURITY;
ALTER TABLE detected_symbol ENABLE ROW LEVEL SECURITY;
ALTER TABLE table_cell ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_correction ENABLE ROW LEVEL SECURITY;
ALTER TABLE export_record ENABLE ROW LEVEL SECURITY;
```

---

## 1.3 State Machines and Permission Matrices

```typescript
// Drawing Processing State Transitions
const DRAWING_STATE_TRANSITIONS: Record<DrawingProcessingState, DrawingProcessingState[]> = {
  Pending:      ['Queued', 'Failed'],           // Pending → Queued after hash-check pass; → Failed on pre-check error
  Queued:       ['Scanning', 'Failed'],
  Scanning:     ['Processing', 'Scan_Failed', 'Failed'],
  Processing:   ['Complete', 'Failed'],
  Complete:     ['Under_Review', 'Queued'],     // → Under_Review on first correction action; → Queued on retry (shouldn't occur)
  Under_Review: ['Queued'],                     // → Queued on retry (edge case)
  Failed:       ['Queued'],                     // → Queued on user retry (re-uses stored file)
  Scan_Failed:  [],                             // Terminal — no retry permitted
} as const;

// Under_Review trigger: first user correction action (reclassify, reject, manual_add) — NOT canvas open
// Retry: re-uses existing StoredFile; no new file written to S3

// Subscription Billing State Transitions
const BILLING_STATE_TRANSITIONS: Record<BillingState, BillingState[]> = {
  Active: ['Grace', 'Canceled'],
  Grace:  ['Active', 'Canceled'],   // → Active on payment resolved; → Canceled on grace expiry (downgrade to Free)
  Canceled: ['Active'],             // → Active on resubscribe
} as const;

// Grace period: 7 days from first invoice.payment_failed Stripe event
// Grace period day-1 email on entry; day-6 reminder email

// Role-Permission Matrix
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

// Feature-Tier Gate Matrix
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

---

## 1.4 Critical Ordering Rules

1. **Hash check before pre-signed URL issuance.** "Client calls `POST /drawings/hash-check` with `{sha256_hash, filename, size_bytes}`. Server checks `FILE_HASH_BLOCKLIST`. If the hash is present, returns `409 Conflict` — no Drawing record is created, no S3 URL is issued." A `POST /drawings` without a valid prior hash-check pass returns `400`.

2. **Pre-signed URL issued only after hash-check pass.** "The upload flow enforces FR-17 AC-2 (no blocked file byte reaches S3) through a mandatory hash pre-check before pre-signed URL issuance."

3. **Server-side SHA-256 re-verification after storage.** "Ingest Worker performs a server-side SHA-256 verification of the stored object against the client-supplied hash... hash is also checked a second time against the blocklist to handle newly-added entries between steps 3 and 7."

4. **Upload-complete idempotency check before enqueue.** "`POST /drawings/{id}/upload-complete` is idempotent. If the Drawing record is already in `Queued` or any later processing state, the endpoint returns `200` without re-enqueuing the ingest job."

5. **user_id written into job payload at enqueue time by API layer.** "The user ID must be written into the job payload at enqueue time (by the API layer that has authenticated session context) so that worker processes can include it in emitted events without requiring a database lookup or session access. This is mandatory for `processing_complete` and `processing_failed` events."

6. **training_consent snapshotted at correction creation time.** "Each correction save sends... the resolved `training_consent` value... at time of creation; the consent value must be snapshotted at correction time, not resolved lazily."

7. **Team-level consent evaluated server-side.** "Team-level consent resolution must be evaluated server-side to prevent client-side bypass; the resolved value is not a client-supplied field."

8. **Free-tier monthly counter incremented at job enqueue, not completion.** "The counter increment must occur at the point processing is initiated (job enqueued), not at job completion, to prevent race conditions from concurrent uploads."

9. **Stripe webhook state changes via webhook only, never inline after redirect.** "The subscription state in the application database must be updated exclusively via Stripe webhook events (not inline after the payment redirect) to ensure consistency and idempotency."

10. **Stripe webhook idempotency via stored event ID before any state mutation.** "Idempotency enforced via Stripe event ID stored in DB before any state mutation."

11. **GDPR erasure: anonymous_id written before any records updated.** "On first erasure job execution, the computed anonymous ID is written to `USER.anonymous_id` before any records are updated. All subsequent erasure job retries... read `USER.anonymous_id` directly."

12. **Password reset: all sessions invalidated before token_invalidated_at updated.** "On password reset, all tokens are invalidated via Supabase Auth's `admin.signOut(userId)` call; `USER.token_invalidated_at` is simultaneously updated."

13. **Under_Review transition triggered by first correction action, not canvas open.** "The drawing transitions from `Complete` to `Under_Review` on the user's first correction action (e.g., accepting, rejecting, or editing a detected symbol), not on canvas open."

14. **ML job must be enqueued via persistent queue (never in-memory).** "ML job must be enqueued via a persistent queue (not in-memory) to satisfy NFR-7's requirement that queued jobs survive server restarts."

15. **Async export threshold evaluated server-side.** "The 1,000-symbol threshold for triggering async vs. synchronous export (FR-4 AC-3) must be evaluated server-side at job creation time, not client-side, to prevent bypass."

---

## 1.5 HTTP Status Code Contracts

| Condition | Required code | Must never return |
|---|---|---|
| Hash blocked on `POST /drawings/hash-check` | `409 Conflict` | `200`, `400` |
| `POST /drawings` without valid prior hash-check pass | `400` | `200`, `201` |
| `POST /drawings/{id}/upload-complete` when Drawing already in `Queued` or later state (idempotent) | `200` | `201`, `409` |
| `POST /drawings/{id}/upload-complete` initial success (job enqueued) | `202` | `200`, `201` |
| Drawing deletion success | `204` | `200` |
| Auth logout success | `204` | `200` |
| Password reset request success | `204` | `200` |
| Password reset confirm success | `204` | `200` |
| Account deletion initiation success | `204` | `200` |
| Stripe webhook received and processed | `200` | `4xx`, `5xx` |
| Stripe duplicate webhook (already processed, idempotent) | `200` | `4xx` |
| Unauthenticated request to protected endpoint | `401` | `403`, `200` |
| Authenticated user accessing resource they do not own | `403` | `404`, `200` |

---

## 1.6 Route Manifest

### Backend API Endpoints

```
POST   /auth/register
POST   /auth/login
POST   /auth/oauth/google
POST   /auth/refresh
POST   /auth/logout
POST   /auth/password-reset/request
POST   /auth/password-reset/confirm
POST   /drawings/hash-check
GET    /drawings
POST   /drawings
GET    /drawings/{id}
PATCH  /drawings/{id}
DELETE /drawings/{id}
POST   /drawings/{id}/retry
GET    /drawings/{id}/status              (SSE stream)
GET    /drawings/{id}/symbols
PATCH  /symbols/{id}
POST   /drawings/{id}/symbols
POST   /drawings/{id}/exports
GET    /exports/{id}
POST   /drawings/{id}/upload-complete
GET    /account
PATCH  /account
DELETE /account
GET    /account/consent
PATCH  /account/consent
GET    /subscription
POST   /subscription/checkout
POST   /webhooks/stripe
GET    /entity-classes
```

### P1 Backend Endpoints

```
GET    /teams
POST   /teams
GET    /teams/{id}/members
POST   /teams/{id}/members
DELETE /teams/{id}/members/{user_id}
GET    /teams/{id}/consent
PATCH  /teams/{id}/consent
POST   /drawings/compare
GET    /comparisons/{id}
GET    /drawings/{id}/tables
PATCH  /table-cells/{id}
GET    /exports/{id}/comparison-csv
```

### Frontend Page Routes

```
/                          (marketing/landing — Next.js)
/register
/login
/verify-email
/dashboard                 (Drawing Library)
/upload                    (File Upload Drop Zone)
/drawings/{id}/review      (Drawing Review Canvas)
/account                   (Account Settings)
/subscription              (Subscription & Upgrade)
```

### P1 Frontend Page Routes

```
/teams
/teams/{id}/members
/teams/invite/accept
/comparisons/{id}
```

---

## 1.7 Third-Party Dependencies

| Service | Auth Mechanism | Known Quota Limits | Risk Flags |
|---|---|---|---|
| **Supabase Auth** | JWT RS256; Google OAuth 2.0 via Supabase; `admin.signOut(userId)` API for session revocation | Varies by plan | Self-hostable; Postgres-native; alternative is Auth0 if managed SLA preferred |
| **Stripe Billing** | `Stripe-Signature` header (HMAC) on webhooks; API key for server calls | Standard Stripe rate limits | Webhook delivery retries require idempotency enforcement; event ID must be stored before any state mutation; `checkout.session.completed` and `customer.subscription.updated` events required |
| **SendGrid** | API key (Bearer) | Standard SendGrid send limits | Transactional only: verification, password reset, invitations, payment notifications (day-1 and day-6 grace period emails) |
| **PostHog** | API key | Self-hostable; no hard quota | GDPR-compliant; self-hostable |
| **ODA File Converter** | Commercial server-side license | N/A | **Highest risk**: success rate on complex DWGs unknown; 50-file prototype required before engineering; license expiry must be monitored with 30-day alert; commercial license must be procured before any DWG processing; fallback: LibreCAD/ezdxf for DXF path |
| **ClamAV** | Self-hosted sidecar on ingest worker | N/A | No per-scan cost; adequate for engineering file types; alternative: Trend Micro File Security for enterprise compliance certification |
| **Google OAuth 2.0** | OAuth 2.0 authorization code flow | Standard Google quotas | Account-link prompt required when OAuth email matches existing password account; never silent merge |
| **AWS S3 / S3-Compatible** | IAM role (ML workers); pre-signed URLs (clients, 15-min expiry) | Standard S3 quotas | Never publicly accessible; SSE-S3 or SSE-KMS encryption required; no CDN for export files (confidential) |
| **AWS CloudFront** | Standard CDN | N/A | Static SPA assets only; content-hash cache busting |

---

## 1.8 Technology Stack — Selected Choices Only

| Layer | Selected Technology | Architecturally Irreversible Because |
|---|---|---|
| **Frontend SPA** | React + Vite | Canvas rendering via Konva.js requires rich ecosystem; pure SPA sufficient for authenticated views; changing post-build would require full frontend rewrite |
| **Marketing/Landing** | Next.js (separate deployment) | SSR required for NFR-17 SEO; separate from SPA to avoid complexity bleed |
| **Canvas Rendering** | Konva.js (or Fabric.js) | Virtualized canvas with layer isolation is the chosen approach to meet <200ms NFR-19 with 500+ symbols; SVG overlay on top of rasterized DWG/PDF output |
| **API Server** | FastAPI (Python) | Unifies language with ML worker codebase, eliminating cross-service interface surface; Python-first ML ecosystem |
| **Async Workers** | Celery on Redis broker | Durable persistent queue (NFR-7); Redis already required for cache + SSE; Celery retry/timeout/priority support; changing broker requires worker rewrite |
| **Database** | PostgreSQL (RDS/Aurora) | ACID, JSONB for bbox payloads, RLS, mature GDPR tooling, all entities have relational structure; schema migrations via Alembic |
| **Queue / Cache / SSE pub-sub** | Redis (ElastiCache) | Three-in-one: Celery broker, subscription feature flag cache, SSE pub/sub for drawing status push; single operational dependency |
| **Object Storage** | AWS S3-compatible | Pre-signed URL pattern, IAM role scoping, SSE encryption, lifecycle policies; client-direct upload pattern avoids API byte-proxy |
| **Auth** | Supabase Auth (self-hosted) | JWT RS256, Google OAuth, session invalidation via `admin.signOut(userId)`, Postgres-native; selected over Auth0 to reduce vendor lock-in |
| **Payments** | Stripe Billing (Checkout + Customer Portal + Webhooks) | Entire subscription state machine is Stripe-webhook-driven; changing would require rebuilding billing state machine |
| **Email** | SendGrid | Transactional email integration; webhook-driven notification scheduling |
| **Analytics** | PostHog | Self-hostable, GDPR-compliant, named events with properties |
| **DWG Parsing** | ODA File Converter (server-side, licensed) | Only viable server-side DWG-to-raster/PDF/SVG converter for AutoCAD 2010–2024; runs in isolated Docker sandbox with no network egress |
| **Malware Scanning** | ClamAV (self-hosted sidecar) | Eliminates per-scan cost; runs on ingest worker |
| **Deployment** | Docker on ECS Fargate (API + CPU workers); EC2 G4dn (GPU ML workers) | GPU instance type selection is irreversible at infrastructure provisioning time |
| **Connection Pooling** | PgBouncer | From Phase 1; required before scaling |

---

## 1.9 Performance Targets

| Metric | Target Value | Hard SLA or Monitoring Target | Responsible Component |
|---|---|---|---|
| Dashboard (Drawing Library) load | <2s P95 | Monitoring target | FastAPI + PostgreSQL (paginated 25 records, indexed queries) |
| Canvas load (symbol fetch) | <3s P95 | Monitoring target | FastAPI `GET /drawings/{id}/symbols` + PostgreSQL JSONB bbox storage; correction history co-loaded in same response |
| Canvas interaction (symbol select + panel open) | <200ms P95 | **Hard SLA (NFR-19)** | React SPA; correction history pre-loaded at canvas init — no additional network fetch on panel open |
| Export (<1,000 symbols) | <30s P95 | Monitoring target | Export Worker (synchronous generation); pre-signed URL returned on poll completion |
| ML inference timeout before Failed state | 20 minutes max | Hard SLA | ML Worker; 1 automatic retry before `Failed` transition |
| Pre-signed S3 URL expiry | 15 minutes | Hard constraint (security) | FastAPI URL generation |
| Stripe tier activation after Checkout redirect | <30 seconds | Monitoring target | Stripe webhook handler + subscription update |
| Status push to client during processing | ≤10 second polling fallback | Monitoring target | SSE via Redis pub/sub; 10s polling fallback for proxied connections |
| ML accuracy (symbol detection F1) | ≥85% F1 on external dataset (≥20 drawings, ≥3 companies) | **Pre-launch gate** | ML model (pre-engineering validation required) |
| Table cell extraction accuracy | ≥75% cell-level accuracy on test dataset | Monitoring target | ML inference (table detection model) |
| Brute-force lockout | After 5 failed attempts, 15-minute lockout | Hard constraint (security) | Redis TTL-based counter |
| Symbol pagination default / max | 200 default / 500 max per page | Hard constraint | `GET /drawings/{id}/symbols` |
| Async export threshold | >1,000 symbols triggers async path | Hard constraint | Export Worker; evaluated server-side |

---

## 1.10 Analytics Event Contracts

All nine events must be instrumented. Events must be non-blocking and asynchronous. Analytics failure must not surface to users. Server-side retry queue (dead-letter) recommended.

| Event Name | Payload Shape | Code Surface That Fires It | Trigger Condition | Must NOT have happened yet | Must NEVER fire from |
|---|---|---|---|---|---|
| `drawing_uploaded` | `{ event: 'drawing_uploaded', timestamp: string (UTC ISO8601), user_id: string, drawing_id: string }` | FastAPI — `POST /drawings/{id}/upload-complete` handler | Drawing transitions to `Queued` state after upload-complete signal | Drawing must not already be in `Queued` or later state | Browser client; ML worker |
| `processing_complete` | `{ event: 'processing_complete', timestamp: string, user_id: string, drawing_id: string }` | ML Worker (user_id from job payload) | Drawing transitions to `Complete` state | `processing_failed` for same drawing_id in same job run | Browser client; must not resolve user_id via DB lookup in worker |
| `processing_failed` | `{ event: 'processing_failed', timestamp: string, user_id: string, drawing_id: string }` | ML Worker (user_id from job payload) | Drawing transitions to `Failed` state (after 1 automatic retry exhausted) | `processing_complete` for same drawing_id in same job run | Browser client |
| `correction_action` | `{ event: 'correction_action', timestamp: string, user_id: string, drawing_id: string, symbol_id: string }` | FastAPI — `PATCH /symbols/{id}` and `POST /drawings/{id}/symbols` handlers | User submits a reclassify, reject, restore, or manual_add correction | None specified | Browser client directly; must fire server-side on persistence |
| `export_initiated` | `{ event: 'export_initiated', timestamp: string, user_id: string, drawing_id: string, export_id: string, format: ExportFormat }` | FastAPI — `POST /drawings/{id}/exports` handler | Export job created (both sync and async paths) | Export file generated | Export Worker; browser client |
| `export_downloaded` | `{ event: 'export_downloaded', timestamp: string, user_id: string, drawing_id: string, export_id: string }` | FastAPI — pre-signed URL access or download endpoint | User accesses pre-signed download URL | None specified | Export Worker |
| `free_limit_reached` | `{ event: 'free_limit_reached', timestamp: string, user_id: string, drawing_id: string, subscription_id: string }` | FastAPI — processing initiation handler | Free tier user attempts to initiate processing of drawing that would exceed 3/month limit | Processing job must not be queued | Browser client; must fire before upgrade prompt is shown |
| `subscription_upgraded` | `{ event: 'subscription_upgraded', timestamp: string, user_id: string, subscription_id: string, previous_tier: TierId, new_tier: TierId }` | FastAPI — Stripe webhook handler (`customer.subscription.updated`) | Subscription tier increases | Tier change applied before event fires | Browser client; Stripe redirect handler inline |
| `subscription_downgraded` | `{ event: 'subscription_downgraded', timestamp: string, user_id: string, subscription_id: string, previous_tier: TierId, new_tier: TierId }` | FastAPI — Stripe webhook handler or downgrade confirmation handler | Subscription tier decreases (fires immediately at confirmation, not at period end) | None specified | Browser client |

---

## 1.11 Cross-Session Runtime Patterns

### Redis Cache Keys

| Key Pattern | Written By | Read By | TTL |
|---|---|---|---|
| `subscription:flags:{user_id}` | FastAPI on login / Stripe webhook handler | FastAPI middleware (every authenticated request, feature-gate evaluation) | 5 minutes; invalidated on webhook receipt |
| `entity_classes:taxonomy` | FastAPI admin update | FastAPI `GET /entity-classes`; React SPA (via API) | Indefinite; invalidated on admin update |
| `brute_force:{email}` | FastAPI login handler | FastAPI login handler | 15-minute TTL |

### Redis Pub/Sub Channels (SSE)

| Channel Pattern | Published By | Consumed By | Payload Shape |
|---|---|---|---|
| `drawing:status:{drawing_id}` | Ingest Worker, Scan Worker, ML Worker (on each state transition) | FastAPI SSE handler (`GET /drawings/{id}/status`) → client | `DrawingStatusSSEEvent` (see §1.1) |

### Celery Job Queue Names

| Queue | Workers | Job Types |
|---|---|---|
| `ingest` | Ingest Worker (CPU) | DWG-to-raster conversion, format detection, post-storage hash verification |
| `scan` | Scan Worker (ClamAV sidecar, CPU) | Malware scan |
| `ml_inference` | ML Worker (GPU — G4dn) | Symbol detection + table extraction |
| `export` | Export Worker (CPU) | CSV/XLSX generation |
| `gdpr_erasure` | GDPR Worker (CPU, scheduled) | PII purge, anonymization |
| `notification` | Notification Worker (CPU) | SendGrid email dispatch |

### Browser Storage Keys

| Key | Storage Type | Written By | Read By | Purpose |
|---|---|---|---|---|
| `correction_state:{drawing_id}` | localStorage (≤2MB cap) | Canvas review SPA | Canvas review SPA on reload | Unsaved correction state flush; server-saved state takes precedence if timestamps conflict |
| `graceBannerDismissed` | sessionStorage | Drawing Library / global nav component | Global nav component | Session-scoped suppression of grace period banner; resets on new session |

---

## 1.12 Environment Variable Schema

| Variable | Type | Valid Values | Default if Absent | Startup Behavior if Invalid | Startup Behavior if Absent |
|---|---|---|---|---|---|
| `DATABASE_URL` | string | PostgreSQL connection URI | None | Refuse to start | Refuse to start |
| `REDIS_URL` | string | Redis connection URI | None | Refuse to start | Refuse to start |
| `S3_BUCKET_NAME` | string | Any non-empty string | None | Refuse to start | Refuse to start |
| `S3_REGION` | string | AWS region code (e.g., `eu-central-1`, `us-east-1`) | None | Refuse to start | Refuse to start |
| `AWS_ACCESS_KEY_ID` | string | Any non-empty string | None (uses IAM role) | Warn | Use IAM role |
| `AWS_SECRET_ACCESS_KEY` | string | Any non-empty string | None (uses IAM role) | Warn | Use IAM role |
| `SUPABASE_URL` | string | HTTPS URL | None | Refuse to start | Refuse to start |
| `SUPABASE_SERVICE_ROLE_KEY` | string | Any non-empty string | None | Refuse to start | Refuse to start |
| `JWT_RS256_PUBLIC_KEY` | string | PEM-encoded RSA public key | None | Refuse to start | Refuse to start |
| `STRIPE_SECRET_KEY` | string | `sk_live_*` or `sk_test_*` | None | Refuse to start | Refuse to start |
| `STRIPE_WEBHOOK_SECRET` | string | `whsec_*` | None | Refuse to start | Refuse to start |
| `SENDGRID_API_KEY` | string | Any non-empty string | None | Refuse to start | Refuse to start |
| `POSTHOG_API_KEY` | string | Any non-empty string | None | Log warning; analytics disabled | Log warning; analytics disabled |
| `POSTHOG_HOST` | string | HTTPS URL | `https://app.posthog.com` | Warn; use default | Use default |
| `HMAC_SERVER_SECRET` | string | Any non-empty high-entropy string | None | Refuse to start | Refuse to start (used for anonymous_id derivation) |
| `ML_MODEL_S3_KEY` | string | S3 object key path | None | Refuse to start | Refuse to start |
| `ML_MODEL_VERSION` | string | Semver string | None | Log warning | Log warning; use latest in bucket |
| `ODA_CONVERTER_PATH` | string | Absolute filesystem path | None | Refuse to start | Refuse to start |
| `ODA_LICENSE_EXPIRY_DATE` | string | `YYYY-MM-DD` | None | Log warning | Log warning (30-day alert threshold) |
| `MAX_UPLOAD_SIZE_BYTES` | integer | Positive integer | `104857600` (100MB) | Use default | Use default |
| `PRESIGNED_URL_EXPIRY_SECONDS` | integer | Positive integer | `900` (15 min) | Use default | Use default |
| `ML_JOB_TIMEOUT_SECONDS` | integer | Positive integer | `1200` (20 min) | Use default | Use default |
| `CELERY_BROKER_URL` | string | Redis connection URI | Falls back to `REDIS_URL` | Refuse to start | Falls back to `REDIS_URL` |
| `DATA_REGION` | string | `eu-central-1` \| `us-east-1` | `eu-central-1` | Refuse to start | Use `eu-central-1` |
| `ENVIRONMENT` | string | `development` \| `staging` \| `production` | `production` | Log warning | Use `production` |

---

## 1.13 Feature Scope — P0 vs P1

### P0 (MVP — First Release)

- US-001: User registration and email verification
- US-002: Email/password and Google OAuth login with account linking and brute-force lockout
- US-003: PDF and DWG file upload with format, size, raster, DWG version, and blocklist validation
- US-004: ML training consent management and account settings (display name, email)
- US-005: Account deletion and GDPR erasure pipeline (30-day async, anonymous_id persistence)
- US-006: Drawing Library with pagination, status badges, revision labels
- US-007: Drawing Library search (filename/revision) and filter (status, date range)
- US-008: Processing state machine (Pending → Queued → Scanning → Processing → Complete/Failed/Scan_Failed) with live SSE/poll status updates and in-app notifications
- US-009: Retry failed processing jobs; delete drawings with confirmation (including mid-processing cancellation)
- US-010: All nine structured analytics events (drawing_uploaded, processing_complete, processing_failed, correction_action, export_initiated, export_downloaded, free_limit_reached, subscription_upgraded, subscription_downgraded)
- US-011: Automatic ML processing trigger after upload; detection results with confidence scores display
- US-012: Color-coded bounding box overlays on canvas (Pipe/Valve/Instrument); multi-page PDF navigation; Under_Review transition on first correction action
- US-013: Symbol inspection panel; reclassify (predefined list only); reject; undo rejection; server persistence with optimistic save indicator
- US-014: Manual annotation (draw bounding box, assign entity class, optional tag_label, confidence 1.0, source=manual)
- US-015: Session-restore for corrections (server-persistent); training consent gating at correction creation (server-side); team-level consent override
- US-016: CSV and XLSX export (synchronous path, <1,000 symbols); pre-signed download URL; re-export without overwriting prior exports
- US-017: Async export queue for >1,000 symbols; in-app notification when ready; async export failure with retry
- US-018: Free tier 3-drawing/month limit enforcement; upgrade prompt on limit hit; tier-gated features visible but inaccessible
- US-019: Stripe Checkout upgrade (Pro and Team tiers); downgrade deferred to period end; pending state with 30s webhook resolution timeout
- US-020: Grace period handling (7-day, day-1 and day-6 emails); Stripe cancellation (access until period end); idempotent webhook processing
- Pre-storage SHA-256 blocklist enforcement (two-gate: hash-check endpoint + Ingest Worker re-verification)
- JWT middleware token_invalidated_at check on every authenticated request
- DWG parsing in isolated Docker sandbox (no network egress, non-root, read-only filesystem)
- Malware scanning via ClamAV sidecar on Ingest Worker
- PgBouncer connection pooling from Phase 1
- SSE via Redis pub/sub with 10-second polling fallback

### P1 (Post-MVP — v1.0)

- US-021: ML instrument table region detection and cell extraction (≥75% cell accuracy)
- US-022: Table cell review and editing on canvas with training consent; exported in separate section
- US-023: Team workspace — invite by email (72-hour link, seat-limited), member removal, seat release, team-level ML consent override
- US-024: Shared team library with role-based permissions (Members cannot delete; Admin can); drawing attribution; removed-member drawing reassignment
- US-025: Revision comparison — spatial proximity (centroid ≤2% canvas dimension) + tag label fallback matching; Added/Removed highlights; comparison CSV export; stale flag (`last_correction_at > computed_at`); Free tier gate
- Team API endpoints (`/teams`, `/teams/{id}/members`, `/teams/{id}/consent`)
- Table API endpoints (`/drawings/{id}/tables`, `/PATCH /table-cells/{id}`)
- Comparison API endpoints (`POST /drawings/compare`, `GET /comparisons/{id}`, `GET /exports/{id}/comparison-csv`)
- FR-11 API key access (1,000 req/min per key)
- Read replica for drawing library queries (Phase 2)
- Autoscaling ML worker pool (CloudWatch queue depth trigger, scale-out at >5 jobs)
- Redis Cluster (Phase 2)
- CDN for export file delivery (Phase 2, if applicable)
- Multi-AZ PostgreSQL with WAL streaming (Phase 3)
- Cross-region S3 replication for US region (Phase 3)
- Background job monitoring via Flower/Grafana (Phase 2)
- Confidence score filter/sort for low-confidence symbols (David safety use case, Phase 2 enhancement)
- GPU Spot instances with Celery task checkpointing (cost optimization, Phase 2+)
- S3 lifecycle archival policies (Intelligent-Tiering after 30 days; Glacier after 90 days)
- Offline ML training pipeline consuming UserCorrection records with training_consent=true (not in MVP scope)
- ML model versioning service (Phase 3)
```

---

### build-plan-gate-checklists [primary]

**System Prompt:**
```
You are generating gate verification checklists for an autonomous build plan. For each phase transition, produce a flat checklist of specific observable outcomes a human must verify before starting the next phase.

Each item must name an exact command, endpoint, or observable behavior — not a general description.

Minimum per gate:
- One compilation or type-check verification (e.g., `npx tsc --noEmit` exits 0)
- One connectivity check per external dependency (database, cache, queues) if applicable
- One security verification (correct HTTP status code for an unauthorized request) if applicable
- One functional smoke test for the phase's primary deliverable

Format each gate as:

### Gate: Phase N → Phase N+1

Required sessions: [list]
Non-blocking: [list or "none"]

- [ ] [Specific verifiable check]
- [ ] [Specific verifiable check]
...
```

**User Message:**
```
# PID Analyzer — Session Decomposition

| ID | Name | Category | Phase | Prerequisites | Owned files (exhaustive) | Complexity |
| -- | ---- | -------- | ----- | ------------- | ------------------------ | ---------- |
| S0-A | Scaffold & Shared Stubs | Infrastructure | 0 | — | `backend/app/main.py`, `backend/app/config.py`, `backend/app/db/base.py`, `backend/app/db/session.py`, `backend/app/api/__init__.py`, `backend/app/api/routers/__init__.py` (all router include stubs), `backend/app/api/routers/_stubs.py` (placeholder endpoints for every route in §1.6 P0+P1), `backend/app/workers/celery_app.py`, `backend/app/workers/__init__.py`, `backend/app/schemas/contracts.py` (pydantic mirrors of §1.1), `backend/app/schemas/__init__.py`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/Dockerfile`, `backend/Dockerfile.worker`, `backend/Dockerfile.ml`, `frontend/index.html`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/router.tsx` (lazy route stubs for all SPA pages), `frontend/src/pages/_stubs.tsx`, `frontend/src/types/contracts.ts`, `marketing/next.config.js`, `marketing/tsconfig.json`, `marketing/app/layout.tsx`, `marketing/app/page.tsx`, `docker-compose.yml`, `docker-compose.test.yml`, `.env.example`, `README.md`, `ops/oda-sandbox/Dockerfile`, `ops/clamav/Dockerfile` | L |
| S0-B | Integration Harness & Manifests | Testing/Hardening | 0 | — | `package.json` (root workspace), `backend/pyproject.toml`, `backend/poetry.lock`, `frontend/package.json`, `marketing/package.json`, `tests/integration/conftest.py`, `tests/integration/docker-compose.fixtures.yml`, `tests/integration/fixtures/db.py`, `tests/integration/fixtures/redis.py`, `tests/integration/fixtures/s3.py`, `tests/integration/smoke/test_smoke.py`, `tests/integration/README.md`, `scripts/test-integration.sh`, `.github/workflows/integration.yml` | M |
| S1-A | DB Models & Migrations | Infrastructure | 1 | S0-A, S0-B | `backend/app/db/models/__init__.py`, `backend/app/db/models/user.py`, `backend/app/db/models/team.py`, `backend/app/db/models/tier.py`, `backend/app/db/models/subscription.py`, `backend/app/db/models/stored_file.py`, `backend/app/db/models/file_hash_blocklist.py`, `backend/app/db/models/drawing.py`, `backend/app/db/models/entity_class.py`, `backend/app/db/models/detected_symbol.py`, `backend/app/db/models/table_cell.py`, `backend/app/db/models/user_correction.py`, `backend/app/db/models/export_record.py`, `backend/app/db/models/ml_training_consent.py`, `backend/app/db/models/revision_comparison.py`, `backend/app/db/models/audit_log.py`, `backend/app/db/models/stripe_event.py`, `backend/alembic/versions/0001_initial_schema.py`, `backend/alembic/versions/0002_rls_policies.py`, `backend/alembic/versions/0003_audit_partitions.py`, `backend/app/db/seed_tiers.py`, `backend/app/db/seed_entity_classes.py` | L |
| S1-B | Auth Middleware & Supabase Client | Auth/Contracts | 1 | S0-A, S0-B | `backend/app/auth/__init__.py`, `backend/app/auth/supabase_client.py`, `backend/app/auth/jwt_verifier.py`, `backend/app/auth/middleware.py`, `backend/app/auth/dependencies.py`, `backend/app/auth/permissions.py` (role matrix from §1.3), `backend/app/auth/brute_force.py`, `tests/integration/test_auth_middleware.py` | M |
| S1-C | Storage & Hash Utilities | Infrastructure | 1 | S0-A, S0-B | `backend/app/storage/__init__.py`, `backend/app/storage/s3_client.py`, `backend/app/storage/presigned.py`, `backend/app/storage/hashing.py`, `backend/app/storage/blocklist.py`, `tests/integration/test_storage.py` | M |
| S1-D | Redis, Cache, Pub/Sub & Celery Config | Real-time/Queue | 1 | S0-A, S0-B | `backend/app/redis/__init__.py`, `backend/app/redis/client.py`, `backend/app/redis/cache.py` (subscription flags, entity taxonomy), `backend/app/redis/pubsub.py` (drawing:status channels), `backend/app/workers/queues.py` (queue routing config), `backend/app/workers/base.py` (Task base class with retry policy), `tests/integration/test_redis_pubsub.py` | M |
| S1-E | Analytics Emitter (PostHog) | Infrastructure | 1 | S0-A, S0-B | `backend/app/analytics/__init__.py`, `backend/app/analytics/posthog_client.py`, `backend/app/analytics/events.py` (typed emitters for all 9 events §1.10), `backend/app/analytics/dead_letter.py`, `tests/integration/test_analytics.py` | S |
| S1-F | Frontend Shared Infrastructure | Frontend | 1 | S0-A, S0-B | `frontend/src/api/client.ts`, `frontend/src/api/endpoints.ts`, `frontend/src/auth/AuthContext.tsx`, `frontend/src/auth/useAuth.ts`, `frontend/src/auth/supabaseClient.ts`, `frontend/src/hooks/useSSE.ts`, `frontend/src/hooks/usePolling.ts`, `frontend/src/components/Layout.tsx`, `frontend/src/components/Nav.tsx`, `frontend/src/components/GraceBanner.tsx`, `frontend/src/components/ProtectedRoute.tsx`, `frontend/src/lib/storage.ts` (localStorage/sessionStorage helpers), `frontend/src/lib/analytics.ts`, `frontend/src/styles/globals.css` | M |
| S2-A | Auth Endpoints | Auth/Contracts | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/auth.py`, `backend/app/services/auth_service.py`, `backend/app/services/password_reset.py`, `tests/integration/test_auth_endpoints.py` | M |
| S2-B | Drawings Endpoints + SSE Status | Backend API | 2 | S1-A, S1-B, S1-C, S1-D, S1-E | `backend/app/api/routers/drawings.py`, `backend/app/services/drawing_service.py`, `backend/app/services/hash_check_service.py`, `backend/app/services/upload_complete_service.py`, `backend/app/services/drawing_state_machine.py`, `backend/app/services/free_tier_counter.py`, `backend/app/sse/drawing_status.py`, `tests/integration/test_drawings_api.py`, `tests/integration/test_drawings_sse.py` | L |
| S2-C | Symbols & Corrections Endpoints | Backend API | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/symbols.py`, `backend/app/services/symbol_service.py`, `backend/app/services/correction_service.py` (training_consent snapshot, Under_Review trigger), `tests/integration/test_symbols_api.py` | M |
| S2-D | Export Endpoints + Sync Path | Backend API | 2 | S1-A, S1-B, S1-C, S1-D, S1-E | `backend/app/api/routers/exports.py`, `backend/app/services/export_service.py` (sync <1000 path, threshold gate), `backend/app/services/export_generators.py` (CSV/XLSX), `tests/integration/test_exports_api.py` | M |
| S2-E | Subscription + Stripe Webhook | Backend API | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/subscription.py`, `backend/app/api/routers/stripe_webhook.py`, `backend/app/services/stripe_client.py`, `backend/app/services/subscription_service.py`, `backend/app/services/billing_state_machine.py`, `backend/app/services/stripe_event_idempotency.py`, `tests/integration/test_subscription.py`, `tests/integration/test_stripe_webhook.py` | L |
| S2-F | Account, Consent & GDPR Init Endpoints | Backend API | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/account.py`, `backend/app/services/account_service.py`, `backend/app/services/consent_service.py` (server-side team consent resolution), `backend/app/services/gdpr_init_service.py`, `tests/integration/test_account.py` | M |
| S2-G | Entity Classes & Misc Endpoints | Backend API | 2 | S1-A, S1-D | `backend/app/api/routers/entity_classes.py`, `backend/app/services/entity_class_service.py`, `tests/integration/test_entity_classes.py` | S |
| S2-H | Ingest Worker | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/ingest/__init__.py`, `backend/app/workers/ingest/tasks.py`, `backend/app/workers/ingest/oda_converter.py`, `backend/app/workers/ingest/hash_reverify.py`, `backend/app/workers/ingest/format_detect.py`, `tests/integration/test_ingest_worker.py` | L |
| S2-I | Scan Worker (ClamAV) | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/scan/__init__.py`, `backend/app/workers/scan/tasks.py`, `backend/app/workers/scan/clamav_client.py`, `tests/integration/test_scan_worker.py` | S |
| S2-J | ML Worker | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/ml/__init__.py`, `backend/app/workers/ml/tasks.py`, `backend/app/workers/ml/inference.py`, `backend/app/workers/ml/model_loader.py`, `backend/app/workers/ml/result_persistence.py`, `tests/integration/test_ml_worker.py` | L |
| S2-K | Export Worker (Async) | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/export/__init__.py`, `backend/app/workers/export/tasks.py`, `tests/integration/test_export_worker.py` | M |
| S2-L | GDPR Erasure Worker | Real-time/Queue | 2 | S1-A, S1-C, S1-D | `backend/app/workers/gdpr/__init__.py`, `backend/app/workers/gdpr/tasks.py`, `backend/app/workers/gdpr/anonymizer.py` (anonymous_id HMAC, idempotent), `tests/integration/test_gdpr_worker.py` | M |
| S2-M | Notification Worker (SendGrid) | Real-time/Queue | 2 | S1-A, S1-D | `backend/app/workers/notification/__init__.py`, `backend/app/workers/notification/tasks.py`, `backend/app/workers/notification/sendgrid_client.py`, `backend/app/workers/notification/templates.py` (verification, reset, invite, grace day-1/6), `tests/integration/test_notification_worker.py` | M |
| S3-A | Frontend: Auth Pages | Frontend | 3 | S1-F, S2-A | `frontend/src/pages/auth/Register.tsx`, `frontend/src/pages/auth/Login.tsx`, `frontend/src/pages/auth/VerifyEmail.tsx`, `frontend/src/pages/auth/PasswordResetRequest.tsx`, `frontend/src/pages/auth/PasswordResetConfirm.tsx`, `frontend/src/pages/auth/OAuthCallback.tsx`, `frontend/src/pages/auth/AccountLinkPrompt.tsx` | M |
| S3-B | Frontend: Drawing Library | Frontend | 3 | S1-F, S2-B | `frontend/src/pages/Dashboard.tsx`, `frontend/src/features/library/DrawingList.tsx`, `frontend/src/features/library/DrawingRow.tsx`, `frontend/src/features/library/StatusBadge.tsx`, `frontend/src/features/library/SearchFilter.tsx`, `frontend/src/features/library/Pagination.tsx`, `frontend/src/features/library/useDrawings.ts` | M |
| S3-C | Frontend: Upload Flow | Frontend | 3 | S1-F, S2-B | `frontend/src/pages/Upload.tsx`, `frontend/src/features/upload/DropZone.tsx`, `frontend/src/features/upload/hashClient.ts`, `frontend/src/features/upload/uploadOrchestrator.ts`, `frontend/src/features/upload/UploadProgress.tsx` | M |
| S3-D | Frontend: Review Canvas (Konva) | Frontend | 3 | S1-F, S2-B, S2-C | `frontend/src/pages/Review.tsx`, `frontend/src/features/canvas/Canvas.tsx`, `frontend/src/features/canvas/SymbolLayer.tsx`, `frontend/src/features/canvas/BoundingBox.tsx`, `frontend/src/features/canvas/PageNav.tsx`, `frontend/src/features/canvas/InspectionPanel.tsx`, `frontend/src/features/canvas/ManualAnnotate.tsx`, `frontend/src/features/canvas/CorrectionStore.ts`, `frontend/src/features/canvas/useCanvasShortcuts.ts` | L |
| S3-E | Frontend: Account & Consent | Frontend | 3 | S1-F, S2-F | `frontend/src/pages/Account.tsx`, `frontend/src/features/account/ProfileForm.tsx`, `frontend/src/features/account/ConsentToggle.tsx`, `frontend/src/features/account/DeleteAccount.tsx` | S |
| S3-F | Frontend: Subscription & Upgrade | Frontend | 3 | S1-F, S2-E | `frontend/src/pages/Subscription.tsx`, `frontend/src/features/subscription/TierCard.tsx`, `frontend/src/features/subscription/CheckoutRedirect.tsx`, `frontend/src/features/subscription/UpgradePrompt.tsx`, `frontend/src/features/subscription/PendingState.tsx` | M |
| S3-G | Frontend: Exports UI + Notifications | Frontend | 3 | S1-F, S2-D | `frontend/src/features/exports/ExportButton.tsx`, `frontend/src/features/exports/ExportModal.tsx`, `frontend/src/features/exports/useExportStatus.ts`, `frontend/src/features/notifications/InAppNotifications.tsx`, `frontend/src/features/notifications/notificationsStore.ts` | M |
| S3-H | Marketing Site (Next.js) | Frontend | 3 | S0-A | `marketing/app/(marketing)/page.tsx`, `marketing/app/pricing/page.tsx`, `marketing/app/about/page.tsx`, `marketing/app/contact/page.tsx`, `marketing/components/Hero.tsx`, `marketing/components/PricingTable.tsx`, `marketing/components/Footer.tsx`, `marketing/public/robots.txt`, `marketing/public/sitemap.xml` | M |
| S4-A | E2E Integration Tests | Testing/Hardening | 4 | All Phase 2 + Phase 3 | `tests/integration/e2e/test_upload_to_complete.py`, `tests/integration/e2e/test_correction_flow.py`, `tests/integration/e2e/test_export_sync_and_async.py`, `tests/integration/e2e/test_stripe_lifecycle.py`, `tests/integration/e2e/test_gdpr_erasure.py`, `tests/integration/e2e/test_blocklist_two_gate.py`, `tests/integration/e2e/test_free_tier_limit.py` | L |

---

## Gate Definitions

**Phase 0 → Phase 1 gate** (must merge): `S0-A`, `S0-B`. Both required: scaffold provides stubs every Phase 1 session imports; harness provides the green integration baseline (`npm run test:integration` exits 0).

**Phase 1 → Phase 2 gate** (must merge): `S1-A`, `S1-B`, `S1-C`, `S1-D`, `S1-E`. Non-blocking for Phase 2 backend work: `S1-F` (frontend-only; gates Phase 3 only).

**Phase 2 → Phase 3 gate** (must merge per frontend session): each Phase 3 session depends only on its specific Phase 2 endpoint(s) — see prerequisites column. Marketing (`S3-H`) needs only Phase 0.

**Phase 3 → Phase 4 gate** (must merge): all Phase 2 + Phase 3 sessions.

---

## Intra-Phase Dependencies

None within Phase 1 (all five core infra sessions are parallel; they only import from S0-A stubs).

None within Phase 2 — workers and API routers own disjoint files. They communicate only through Celery queues / Redis channels / DB tables defined in Phase 1.

None within Phase 3 — each frontend feature owns its own subdirectory.

---

## Early-Start Optimizations

- **S1-F (frontend shared)** depends only on `S0-A`/`S0-B` — can start with Phase 1 even though it gates Phase 3 frontends.
- **S3-H (marketing site)** depends only on `S0-A` — can start as early as Phase 1.
- **S2-G (entity classes)** needs only `S1-A` + `S1-D`, can start as soon as those two merge (before S1-B/C/E).
- **S2-L (GDPR worker)** and **S2-M (notification worker)** don't need `S1-E` analytics — can start once `S1-A`/`S1-C`/`S1-D` clear.
- **S3-A (auth pages)** can begin as soon as `S2-A` clears, regardless of other Phase 2 progress.

---

## Critical Path

`S0-A` → `S1-A` (DB models) → `S2-B` (Drawings API + SSE) → `S3-D` (Review canvas — largest frontend) → `S4-A` (E2E tests)

Length: 5 sessions, complexity L → L → L → L → L ≈ 15 hrs of Claude execution on the longest chain.

---

```json
[
  {"id":"S0-A","phase":0,"name":"Scaffold & Shared Stubs","category":"Infrastructure","prerequisites":[],"ownedFiles":["backend/app/main.py","backend/app/config.py","backend/app/db/base.py","backend/app/db/session.py","backend/app/api/__init__.py","backend/app/api/routers/__init__.py","backend/app/api/routers/_stubs.py","backend/app/workers/celery_app.py","backend/app/workers/__init__.py","backend/app/schemas/contracts.py","backend/app/schemas/__init__.py","backend/alembic.ini","backend/alembic/env.py","backend/alembic/script.py.mako","backend/Dockerfile","backend/Dockerfile.worker","backend/Dockerfile.ml","frontend/index.html","frontend/vite.config.ts","frontend/tsconfig.json","frontend/src/main.tsx","frontend/src/App.tsx","frontend/src/router.tsx","frontend/src/pages/_stubs.tsx","frontend/src/types/contracts.ts","marketing/next.config.js","marketing/tsconfig.json","marketing/app/layout.tsx","marketing/app/page.tsx","docker-compose.yml","docker-compose.test.yml",".env.example","README.md","ops/oda-sandbox/Dockerfile","ops/clamav/Dockerfile"],"complexity":"L","specSections":["1.1 Shared Contracts","1.6 Route Manifest","1.8 Technology Stack","1.12 Environment Variable Schema"]},
  {"id":"S0-B","phase":0,"name":"Integration Harness & Manifests","category":"Testing/Hardening","prerequisites":[],"ownedFiles":["package.json","backend/pyproject.toml","backend/poetry.lock","frontend/package.json","marketing/package.json","tests/integration/conftest.py","tests/integration/docker-compose.fixtures.yml","tests/integration/fixtures/db.py","tests/integration/fixtures/redis.py","tests/integration/fixtures/s3.py","tests/integration/smoke/test_smoke.py","tests/integration/README.md","scripts/test-integration.sh",".github/workflows/integration.yml"],"complexity":"M","specSections":["1.8 Technology Stack","1.12 Environment Variable Schema"]},
  {"id":"S1-A","phase":1,"name":"DB Models & Migrations","category":"Infrastructure","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/db/models/__init__.py","backend/app/db/models/user.py","backend/app/db/models/team.py","backend/app/db/models/tier.py","backend/app/db/models/subscription.py","backend/app/db/models/stored_file.py","backend/app/db/models/file_hash_blocklist.py","backend/app/db/models/drawing.py","backend/app/db/models/entity_class.py","backend/app/db/models/detected_symbol.py","backend/app/db/models/table_cell.py","backend/app/db/models/user_correction.py","backend/app/db/models/export_record.py","backend/app/db/models/ml_training_consent.py","backend/app/db/models/revision_comparison.py","backend/app/db/models/audit_log.py","backend/app/db/models/stripe_event.py","backend/alembic/versions/0001_initial_schema.py","backend/alembic/versions/0002_rls_policies.py","backend/alembic/versions/0003_audit_partitions.py","backend/app/db/seed_tiers.py","backend/app/db/seed_entity_classes.py"],"complexity":"L","specSections":["1.2 Database Schema","1.3 State Machines and Permission Matrices"]},
  {"id":"S1-B","phase":1,"name":"Auth Middleware & Supabase Client","category":"Auth/Contracts","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/auth/__init__.py","backend/app/auth/supabase_client.py","backend/app/auth/jwt_verifier.py","backend/app/auth/middleware.py","backend/app/auth/dependencies.py","backend/app/auth/permissions.py","backend/app/auth/brute_force.py","tests/integration/test_auth_middleware.py"],"complexity":"M","specSections":["1.3 State Machines and Permission Matrices","1.4 Critical Ordering Rules","1.7 Third-Party Dependencies"]},
  {"id":"S1-C","phase":1,"name":"Storage & Hash Utilities","category":"Infrastructure","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/storage/__init__.py","backend/app/storage/s3_client.py","backend/app/storage/presigned.py","backend/app/storage/hashing.py","backend/app/storage/blocklist.py","tests/integration/test_storage.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.7 Third-Party Dependencies","1.9 Performance Targets"]},
  {"id":"S1-D","phase":1,"name":"Redis, Cache, Pub/Sub & Celery Config","category":"Real-time/Queue","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/redis/__init__.py","backend/app/redis/client.py","backend/app/redis/cache.py","backend/app/redis/pubsub.py","backend/app/workers/queues.py","backend/app/workers/base.py","tests/integration/test_redis_pubsub.py"],"complexity":"M","specSections":["1.11 Cross-Session Runtime Patterns","1.8 Technology Stack"]},
  {"id":"S1-E","phase":1,"name":"Analytics Emitter (PostHog)","category":"Infrastructure","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/analytics/__init__.py","backend/app/analytics/posthog_client.py","backend/app/analytics/events.py","backend/app/analytics/dead_letter.py","tests/integration/test_analytics.py"],"complexity":"S","specSections":["1.10 Analytics Event Contracts"]},
  {"id":"S1-F","phase":1,"name":"Frontend Shared Infrastructure","category":"Frontend","prerequisites":["S0-A","S0-B"],"ownedFiles":["frontend/src/api/client.ts","frontend/src/api/endpoints.ts","frontend/src/auth/AuthContext.tsx","frontend/src/auth/useAuth.ts","frontend/src/auth/supabaseClient.ts","frontend/src/hooks/useSSE.ts","frontend/src/hooks/usePolling.ts","frontend/src/components/Layout.tsx","frontend/src/components/Nav.tsx","frontend/src/components/GraceBanner.tsx","frontend/src/components/ProtectedRoute.tsx","frontend/src/lib/storage.ts","frontend/src/lib/analytics.ts","frontend/src/styles/globals.css"],"complexity":"M","specSections":["1.1 Shared Contracts","1.6 Route Manifest","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-A","phase":2,"name":"Auth Endpoints","category":"Auth/Contracts","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/auth.py","backend/app/services/auth_service.py","backend/app/services/password_reset.py","tests/integration/test_auth_endpoints.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.6 Route Manifest","1.13 Feature Scope"]},
  {"id":"S2-B","phase":2,"name":"Drawings Endpoints + SSE Status","category":"Backend API","prerequisites":["S1-A","S1-B","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/drawings.py","backend/app/services/drawing_service.py","backend/app/services/hash_check_service.py","backend/app/services/upload_complete_service.py","backend/app/services/drawing_state_machine.py","backend/app/services/free_tier_counter.py","backend/app/sse/drawing_status.py","tests/integration/test_drawings_api.py","tests/integration/test_drawings_sse.py"],"complexity":"L","specSections":["1.3 State Machines and Permission Matrices","1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.6 Route Manifest","1.10 Analytics Event Contracts","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-C","phase":2,"name":"Symbols & Corrections Endpoints","category":"Backend API","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/symbols.py","backend/app/services/symbol_service.py","backend/app/services/correction_service.py","tests/integration/test_symbols_api.py"],"complexity":"M","specSections":["1.1 Shared Contracts","1.4 Critical Ordering Rules","1.10 Analytics Event Contracts","1.13 Feature Scope"]},
  {"id":"S2-D","phase":2,"name":"Export Endpoints + Sync Path","category":"Backend API","prerequisites":["S1-A","S1-B","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/exports.py","backend/app/services/export_service.py","backend/app/services/export_generators.py","tests/integration/test_exports_api.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.6 Route Manifest","1.9 Performance Targets","1.10 Analytics Event Contracts"]},
  {"id":"S2-E","phase":2,"name":"Subscription + Stripe Webhook","category":"Backend API","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/subscription.py","backend/app/api/routers/stripe_webhook.py","backend/app/services/stripe_client.py","backend/app/services/subscription_service.py","backend/app/services/billing_state_machine.py","backend/app/services/stripe_event_idempotency.py","tests/integration/test_subscription.py","tests/integration/test_stripe_webhook.py"],"complexity":"L","specSections":["1.3 State Machines and Permission Matrices","1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.7 Third-Party Dependencies","1.10 Analytics Event Contracts"]},
  {"id":"S2-F","phase":2,"name":"Account, Consent & GDPR Init Endpoints","category":"Backend API","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/account.py","backend/app/services/account_service.py","backend/app/services/consent_service.py","backend/app/services/gdpr_init_service.py","tests/integration/test_account.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.13 Feature Scope"]},
  {"id":"S2-G","phase":2,"name":"Entity Classes & Misc Endpoints","category":"Backend API","prerequisites":["S1-A","S1-D"],"ownedFiles":["backend/app/api/routers/entity_classes.py","backend/app/services/entity_class_service.py","tests/integration/test_entity_classes.py"],"complexity":"S","specSections":["1.6 Route Manifest","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-H","phase":2,"name":"Ingest Worker","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/ingest/__init__.py","backend/app/workers/ingest/tasks.py","backend/app/workers/ingest/oda_converter.py","backend/app/workers/ingest/hash_reverify.py","backend/app/workers/ingest/format_detect.py","tests/integration/test_ingest_worker.py"],"complexity":"L","specSections":["1.4 Critical Ordering Rules","1.7 Third-Party Dependencies","1.11 Cross-Session Runtime Patterns","1.13 Feature Scope"]},
  {"id":"S2-I","phase":2,"name":"Scan Worker (ClamAV)","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/scan/__init__.py","backend/app/workers/scan/tasks.py","backend/app/workers/scan/clamav_client.py","tests/integration/test_scan_worker.py"],"complexity":"S","specSections":["1.7 Third-Party Dependencies","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-J","phase":2,"name":"ML Worker","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/ml/__init__.py","backend/app/workers/ml/tasks.py","backend/app/workers/ml/inference.py","backend/app/workers/ml/model_loader.py","backend/app/workers/ml/result_persistence.py","tests/integration/test_ml_worker.py"],"complexity":"L","specSections":["1.1 Shared Contracts","1.4 Critical Ordering Rules","1.9 Performance Targets","1.10 Analytics Event Contracts","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-K","phase":2,"name":"Export Worker (Async)","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/export/__init__.py","backend/app/workers/export/tasks.py","tests/integration/test_export_worker.py"],"complexity":"M","specSections":["1.9 Performance Targets","1.11 Cross-Session Runtime Patterns","1.13 Feature Scope"]},
  {"id":"S2-L","phase":2,"name":"GDPR Erasure Worker","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D"],"ownedFiles":["backend/app/workers/gdpr/__init__.py","backend/app/workers/gdpr/tasks.py","backend/app/workers/gdpr/anonymizer.py","tests/integration/test_gdpr_worker.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.11 Cross-Session Runtime Patterns","1.12 Environment Variable Schema","1.13 Feature Scope"]},
  {"id":"S2-M","phase":2,"name":"Notification Worker (SendGrid)","category":"Real-time/Queue","prerequisites":["S1-A","S1-D"],"ownedFiles":["backend/app/workers/notification/__init__.py","backend/app/workers/notification/tasks.py","backend/app/workers/notification/sendgrid_client.py","backend/app/workers/notification/templates.py","tests/integration/test_notification_worker.py"],"complexity":"M","specSections":["1.3 State Machines and Permission Matrices","1.7 Third-Party Dependencies","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S3-A","phase":3,"name":"Frontend: Auth Pages","category":"Frontend","prerequisites":["S1-F","S2-A"],"ownedFiles":["frontend/src/pages/auth/Register.tsx","frontend/src/pages/auth/Login.tsx","frontend/src/pages/auth/VerifyEmail.tsx","frontend/src/pages/auth/PasswordResetRequest.tsx","frontend/src/pages/auth/PasswordResetConfirm.tsx","frontend/src/pages/auth/OAuthCallback.tsx","frontend/src/pages/auth/AccountLinkPrompt.tsx"],"complexity":"M","specSections":["1.6 Route Manifest","1.13 Feature Scope"]},
  {"id":"S3-B","phase":3,"name":"Frontend: Drawing Library","category":"Frontend","prerequisites":["S1-F","S2-B"],"ownedFiles":["frontend/src/pages/Dashboard.tsx","frontend/src/features/library/DrawingList.tsx","frontend/src/features/library/DrawingRow.tsx","frontend/src/features/library/StatusBadge.tsx","frontend/src/features/library/SearchFilter.tsx","frontend/src/features/library/Pagination.tsx","frontend/src/features/library/useDrawings.ts"],"complexity":"M","specSections":["1.6 Route Manifest","1.9 Performance Targets","1.13 Feature Scope"]},
  {"id":"S3-C","phase":3,"name":"Frontend: Upload Flow","category":"Frontend","prerequisites":["S1-F","S2-B"],"ownedFiles":["frontend/src/pages/Upload.tsx","frontend/src/features/upload/DropZone.tsx","frontend/src/features/upload/hashClient.ts","frontend/src/features/upload/uploadOrchestrator.ts","frontend/src/features/upload/UploadProgress.tsx"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.13 Feature Scope"]},
  {"id":"S3-D","phase":3,"name":"Frontend: Review Canvas (Konva)","category":"Frontend","prerequisites":["S1-F","S2-B","S2-C"],"ownedFiles":["frontend/src/pages/Review.tsx","frontend/src/features/canvas/Canvas.tsx","frontend/src/features/canvas/SymbolLayer.tsx","frontend/src/features/canvas/BoundingBox.tsx","frontend/src/features/canvas/PageNav.tsx","frontend/src/features/canvas/InspectionPanel.tsx","frontend/src/features/canvas/ManualAnnotate.tsx","frontend/src/features/canvas/CorrectionStore.ts","frontend/src/features/canvas/useCanvasShortcuts.ts"],"complexity":"L","specSections":["1.6 Route Manifest","1.8 Technology Stack","1.9 Performance Targets","1.11 Cross-Session Runtime Patterns","1.13 Feature Scope"]},
  {"id":"S3-E","phase":3,"name":"Frontend: Account & Consent","category":"Frontend","prerequisites":["S1-F","S2-F"],"ownedFiles":["frontend/src/pages/Account.tsx","frontend/src/features/account/ProfileForm.tsx","frontend/src/features/account/ConsentToggle.tsx","frontend/src/features/account/DeleteAccount.tsx"],"complexity":"S","specSections":["1.6 Route Manifest","1.13 Feature Scope"]},
  {"id":"S3-F","phase":3,"name":"Frontend: Subscription & Upgrade","category":"Frontend","prerequisites":["S1-F","S2-E"],"ownedFiles":["frontend/src/pages/Subscription.tsx","frontend/src/features/subscription/TierCard.tsx","frontend/src/features/subscription/CheckoutRedirect.tsx","frontend/src/features/subscription/UpgradePrompt.tsx","frontend/src/features/subscription/PendingState.tsx"],"complexity":"M","specSections":["1.3 State Machines and Permission Matrices","1.6 Route Manifest","1.9 Performance Targets","1.13 Feature Scope"]},
  {"id":"S3-G","phase":3,"name":"Frontend: Exports UI + Notifications","category":"Frontend","prerequisites":["S1-F","S2-D"],"ownedFiles":["frontend/src/features/exports/ExportButton.tsx","frontend/src/features/exports/ExportModal.tsx","frontend/src/features/exports/useExportStatus.ts","frontend/src/features/notifications/InAppNotifications.tsx","frontend/src/features/notifications/notificationsStore.ts"],"complexity":"M","specSections":["1.9 Performance Targets","1.13 Feature Scope"]},
  {"id":"S3-H","phase":3,"name":"Marketing Site (Next.js)","category":"Frontend","prerequisites":["S0-A"],"ownedFiles":["marketing/app/(marketing)/page.tsx","marketing/app/pricing/page.tsx","marketing/app/about/page.tsx","marketing/app/contact/page.tsx","marketing/components/Hero.tsx","marketing/components/PricingTable.tsx","marketing/components/Footer.tsx","marketing/public/robots.txt","marketing/public/sitemap.xml"],"complexity":"M","specSections":["1.8 Technology Stack"]},
  {"id":"S4-A","phase":4,"name":"E2E Integration Tests","category":"Testing/Hardening","prerequisites":["S2-A","S2-B","S2-C","S2-D","S2-E","S2-F","S2-G","S2-H","S2-I","S2-J","S2-K","S2-L","S2-M","S3-A","S3-B","S3-C","S3-D","S3-E","S3-F","S3-G"],"ownedFiles":["tests/integration/e2e/test_upload_to_complete.py","tests/integration/e2e/test_correction_flow.py","tests/integration/e2e/test_export_sync_and_async.py","tests/integration/e2e/test_stripe_lifecycle.py","tests/integration/e2e/test_gdpr_erasure.py","tests/integration/e2e/test_blocklist_two_gate.py","tests/integration/e2e/test_free_tier_limit.py"],"complexity":"L","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.10 Analytics Event Contracts","1.13 Feature Scope"]}
]
```

Total: 30 sessions across 5 phases
```

---

### build-plan-brief-S0-A [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S0-A — Scaffold & Shared Stubs**.

Phase: 0 | Category: Infrastructure | Prerequisites: none

Owned files:
- backend/app/main.py
- backend/app/config.py
- backend/app/db/base.py
- backend/app/db/session.py
- backend/app/api/__init__.py
- backend/app/api/routers/__init__.py
- backend/app/api/routers/_stubs.py
- backend/app/workers/celery_app.py
- backend/app/workers/__init__.py
- backend/app/schemas/contracts.py
- backend/app/schemas/__init__.py
- backend/alembic.ini
- backend/alembic/env.py
- backend/alembic/script.py.mako
- backend/Dockerfile
- backend/Dockerfile.worker
- backend/Dockerfile.ml
- frontend/index.html
- frontend/vite.config.ts
- frontend/tsconfig.json
- frontend/src/main.tsx
- frontend/src/App.tsx
- frontend/src/router.tsx
- frontend/src/pages/_stubs.tsx
- frontend/src/types/contracts.ts
- marketing/next.config.js
- marketing/tsconfig.json
- marketing/app/layout.tsx
- marketing/app/page.tsx
- docker-compose.yml
- docker-compose.test.yml
- .env.example
- README.md
- ops/oda-sandbox/Dockerfile
- ops/clamav/Dockerfile

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S0-B [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S0-B — Integration Harness & Manifests**.

Phase: 0 | Category: Testing/Hardening | Prerequisites: none

Owned files:
- package.json
- backend/pyproject.toml
- backend/poetry.lock
- frontend/package.json
- marketing/package.json
- tests/integration/conftest.py
- tests/integration/docker-compose.fixtures.yml
- tests/integration/fixtures/db.py
- tests/integration/fixtures/redis.py
- tests/integration/fixtures/s3.py
- tests/integration/smoke/test_smoke.py
- tests/integration/README.md
- scripts/test-integration.sh
- .github/workflows/integration.yml

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S1-A [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S1-A — DB Models & Migrations**.

Phase: 1 | Category: Infrastructure | Prerequisites: S0-A, S0-B

Owned files:
- backend/app/db/models/__init__.py
- backend/app/db/models/user.py
- backend/app/db/models/team.py
- backend/app/db/models/tier.py
- backend/app/db/models/subscription.py
- backend/app/db/models/stored_file.py
- backend/app/db/models/file_hash_blocklist.py
- backend/app/db/models/drawing.py
- backend/app/db/models/entity_class.py
- backend/app/db/models/detected_symbol.py
- backend/app/db/models/table_cell.py
- backend/app/db/models/user_correction.py
- backend/app/db/models/export_record.py
- backend/app/db/models/ml_training_consent.py
- backend/app/db/models/revision_comparison.py
- backend/app/db/models/audit_log.py
- backend/app/db/models/stripe_event.py
- backend/alembic/versions/0001_initial_schema.py
- backend/alembic/versions/0002_rls_policies.py
- backend/alembic/versions/0003_audit_partitions.py
- backend/app/db/seed_tiers.py
- backend/app/db/seed_entity_classes.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S1-B [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S1-B — Auth Middleware & Supabase Client**.

Phase: 1 | Category: Auth/Contracts | Prerequisites: S0-A, S0-B

Owned files:
- backend/app/auth/__init__.py
- backend/app/auth/supabase_client.py
- backend/app/auth/jwt_verifier.py
- backend/app/auth/middleware.py
- backend/app/auth/dependencies.py
- backend/app/auth/permissions.py
- backend/app/auth/brute_force.py
- tests/integration/test_auth_middleware.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S1-C [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S1-C — Storage & Hash Utilities**.

Phase: 1 | Category: Infrastructure | Prerequisites: S0-A, S0-B

Owned files:
- backend/app/storage/__init__.py
- backend/app/storage/s3_client.py
- backend/app/storage/presigned.py
- backend/app/storage/hashing.py
- backend/app/storage/blocklist.py
- tests/integration/test_storage.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S1-D [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S1-D — Redis, Cache, Pub/Sub & Celery Config**.

Phase: 1 | Category: Real-time/Queue | Prerequisites: S0-A, S0-B

Owned files:
- backend/app/redis/__init__.py
- backend/app/redis/client.py
- backend/app/redis/cache.py
- backend/app/redis/pubsub.py
- backend/app/workers/queues.py
- backend/app/workers/base.py
- tests/integration/test_redis_pubsub.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S1-E [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S1-E — Analytics Emitter (PostHog)**.

Phase: 1 | Category: Infrastructure | Prerequisites: S0-A, S0-B

Owned files:
- backend/app/analytics/__init__.py
- backend/app/analytics/posthog_client.py
- backend/app/analytics/events.py
- backend/app/analytics/dead_letter.py
- tests/integration/test_analytics.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S1-F [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S1-F — Frontend Shared Infrastructure**.

Phase: 1 | Category: Frontend | Prerequisites: S0-A, S0-B

Owned files:
- frontend/src/api/client.ts
- frontend/src/api/endpoints.ts
- frontend/src/auth/AuthContext.tsx
- frontend/src/auth/useAuth.ts
- frontend/src/auth/supabaseClient.ts
- frontend/src/hooks/useSSE.ts
- frontend/src/hooks/usePolling.ts
- frontend/src/components/Layout.tsx
- frontend/src/components/Nav.tsx
- frontend/src/components/GraceBanner.tsx
- frontend/src/components/ProtectedRoute.tsx
- frontend/src/lib/storage.ts
- frontend/src/lib/analytics.ts
- frontend/src/styles/globals.css

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S2-A [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S2-A — Auth Endpoints**.

Phase: 2 | Category: Auth/Contracts | Prerequisites: S1-A, S1-B, S1-D, S1-E

Owned files:
- backend/app/api/routers/auth.py
- backend/app/services/auth_service.py
- backend/app/services/password_reset.py
- tests/integration/test_auth_endpoints.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S2-B [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S2-B — Drawings Endpoints + SSE Status**.

Phase: 2 | Category: Backend API | Prerequisites: S1-A, S1-B, S1-C, S1-D, S1-E

Owned files:
- backend/app/api/routers/drawings.py
- backend/app/services/drawing_service.py
- backend/app/services/hash_check_service.py
- backend/app/services/upload_complete_service.py
- backend/app/services/drawing_state_machine.py
- backend/app/services/free_tier_counter.py
- backend/app/sse/drawing_status.py
- tests/integration/test_drawings_api.py
- tests/integration/test_drawings_sse.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S2-C [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S2-C — Symbols & Corrections Endpoints**.

Phase: 2 | Category: Backend API | Prerequisites: S1-A, S1-B, S1-D, S1-E

Owned files:
- backend/app/api/routers/symbols.py
- backend/app/services/symbol_service.py
- backend/app/services/correction_service.py
- tests/integration/test_symbols_api.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S2-D [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S2-D — Export Endpoints + Sync Path**.

Phase: 2 | Category: Backend API | Prerequisites: S1-A, S1-B, S1-C, S1-D, S1-E

Owned files:
- backend/app/api/routers/exports.py
- backend/app/services/export_service.py
- backend/app/services/export_generators.py
- tests/integration/test_exports_api.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S2-E [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S2-E — Subscription + Stripe Webhook**.

Phase: 2 | Category: Backend API | Prerequisites: S1-A, S1-B, S1-D, S1-E

Owned files:
- backend/app/api/routers/subscription.py
- backend/app/api/routers/stripe_webhook.py
- backend/app/services/stripe_client.py
- backend/app/services/subscription_service.py
- backend/app/services/billing_state_machine.py
- backend/app/services/stripe_event_idempotency.py
- tests/integration/test_subscription.py
- tests/integration/test_stripe_webhook.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S2-F [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S2-F — Account, Consent & GDPR Init Endpoints**.

Phase: 2 | Category: Backend API | Prerequisites: S1-A, S1-B, S1-D, S1-E

Owned files:
- backend/app/api/routers/account.py
- backend/app/services/account_service.py
- backend/app/services/consent_service.py
- backend/app/services/gdpr_init_service.py
- tests/integration/test_account.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S2-G [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S2-G — Entity Classes & Misc Endpoints**.

Phase: 2 | Category: Backend API | Prerequisites: S1-A, S1-D

Owned files:
- backend/app/api/routers/entity_classes.py
- backend/app/services/entity_class_service.py
- tests/integration/test_entity_classes.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S2-H [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S2-H — Ingest Worker**.

Phase: 2 | Category: Real-time/Queue | Prerequisites: S1-A, S1-C, S1-D, S1-E

Owned files:
- backend/app/workers/ingest/__init__.py
- backend/app/workers/ingest/tasks.py
- backend/app/workers/ingest/oda_converter.py
- backend/app/workers/ingest/hash_reverify.py
- backend/app/workers/ingest/format_detect.py
- tests/integration/test_ingest_worker.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S2-I [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S2-I — Scan Worker (ClamAV)**.

Phase: 2 | Category: Real-time/Queue | Prerequisites: S1-A, S1-C, S1-D, S1-E

Owned files:
- backend/app/workers/scan/__init__.py
- backend/app/workers/scan/tasks.py
- backend/app/workers/scan/clamav_client.py
- tests/integration/test_scan_worker.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S2-J [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S2-J — ML Worker**.

Phase: 2 | Category: Real-time/Queue | Prerequisites: S1-A, S1-C, S1-D, S1-E

Owned files:
- backend/app/workers/ml/__init__.py
- backend/app/workers/ml/tasks.py
- backend/app/workers/ml/inference.py
- backend/app/workers/ml/model_loader.py
- backend/app/workers/ml/result_persistence.py
- tests/integration/test_ml_worker.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S2-K [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S2-K — Export Worker (Async)**.

Phase: 2 | Category: Real-time/Queue | Prerequisites: S1-A, S1-C, S1-D, S1-E

Owned files:
- backend/app/workers/export/__init__.py
- backend/app/workers/export/tasks.py
- tests/integration/test_export_worker.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S2-L [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S2-L — GDPR Erasure Worker**.

Phase: 2 | Category: Real-time/Queue | Prerequisites: S1-A, S1-C, S1-D

Owned files:
- backend/app/workers/gdpr/__init__.py
- backend/app/workers/gdpr/tasks.py
- backend/app/workers/gdpr/anonymizer.py
- tests/integration/test_gdpr_worker.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S2-M [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S2-M — Notification Worker (SendGrid)**.

Phase: 2 | Category: Real-time/Queue | Prerequisites: S1-A, S1-D

Owned files:
- backend/app/workers/notification/__init__.py
- backend/app/workers/notification/tasks.py
- backend/app/workers/notification/sendgrid_client.py
- backend/app/workers/notification/templates.py
- tests/integration/test_notification_worker.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S3-A [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S3-A — Frontend: Auth Pages**.

Phase: 3 | Category: Frontend | Prerequisites: S1-F, S2-A

Owned files:
- frontend/src/pages/auth/Register.tsx
- frontend/src/pages/auth/Login.tsx
- frontend/src/pages/auth/VerifyEmail.tsx
- frontend/src/pages/auth/PasswordResetRequest.tsx
- frontend/src/pages/auth/PasswordResetConfirm.tsx
- frontend/src/pages/auth/OAuthCallback.tsx
- frontend/src/pages/auth/AccountLinkPrompt.tsx

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S3-B [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S3-B — Frontend: Drawing Library**.

Phase: 3 | Category: Frontend | Prerequisites: S1-F, S2-B

Owned files:
- frontend/src/pages/Dashboard.tsx
- frontend/src/features/library/DrawingList.tsx
- frontend/src/features/library/DrawingRow.tsx
- frontend/src/features/library/StatusBadge.tsx
- frontend/src/features/library/SearchFilter.tsx
- frontend/src/features/library/Pagination.tsx
- frontend/src/features/library/useDrawings.ts

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S3-C [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S3-C — Frontend: Upload Flow**.

Phase: 3 | Category: Frontend | Prerequisites: S1-F, S2-B

Owned files:
- frontend/src/pages/Upload.tsx
- frontend/src/features/upload/DropZone.tsx
- frontend/src/features/upload/hashClient.ts
- frontend/src/features/upload/uploadOrchestrator.ts
- frontend/src/features/upload/UploadProgress.tsx

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S3-D [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S3-D — Frontend: Review Canvas (Konva)**.

Phase: 3 | Category: Frontend | Prerequisites: S1-F, S2-B, S2-C

Owned files:
- frontend/src/pages/Review.tsx
- frontend/src/features/canvas/Canvas.tsx
- frontend/src/features/canvas/SymbolLayer.tsx
- frontend/src/features/canvas/BoundingBox.tsx
- frontend/src/features/canvas/PageNav.tsx
- frontend/src/features/canvas/InspectionPanel.tsx
- frontend/src/features/canvas/ManualAnnotate.tsx
- frontend/src/features/canvas/CorrectionStore.ts
- frontend/src/features/canvas/useCanvasShortcuts.ts

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S3-E [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S3-E — Frontend: Account & Consent**.

Phase: 3 | Category: Frontend | Prerequisites: S1-F, S2-F

Owned files:
- frontend/src/pages/Account.tsx
- frontend/src/features/account/ProfileForm.tsx
- frontend/src/features/account/ConsentToggle.tsx
- frontend/src/features/account/DeleteAccount.tsx

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S3-F [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S3-F — Frontend: Subscription & Upgrade**.

Phase: 3 | Category: Frontend | Prerequisites: S1-F, S2-E

Owned files:
- frontend/src/pages/Subscription.tsx
- frontend/src/features/subscription/TierCard.tsx
- frontend/src/features/subscription/CheckoutRedirect.tsx
- frontend/src/features/subscription/UpgradePrompt.tsx
- frontend/src/features/subscription/PendingState.tsx

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S3-G [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S3-G — Frontend: Exports UI + Notifications**.

Phase: 3 | Category: Frontend | Prerequisites: S1-F, S2-D

Owned files:
- frontend/src/features/exports/ExportButton.tsx
- frontend/src/features/exports/ExportModal.tsx
- frontend/src/features/exports/useExportStatus.ts
- frontend/src/features/notifications/InAppNotifications.tsx
- frontend/src/features/notifications/notificationsStore.ts

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S3-H [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S3-H — Marketing Site (Next.js)**.

Phase: 3 | Category: Frontend | Prerequisites: S0-A

Owned files:
- marketing/app/(marketing)/page.tsx
- marketing/app/pricing/page.tsx
- marketing/app/about/page.tsx
- marketing/app/contact/page.tsx
- marketing/components/Hero.tsx
- marketing/components/PricingTable.tsx
- marketing/components/Footer.tsx
- marketing/public/robots.txt
- marketing/public/sitemap.xml

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-brief-S4-A [primary]

**System Prompt:**
```
You are generating an implementation brief for a single Claude Code session. This brief is the ONLY input the Claude Code instance will receive — it must contain everything needed for fully autonomous execution.

**The most important rule**: never summarize, paraphrase, or compress content from the specification documents. Paste the relevant sections verbatim. Claude Code works from exact original language, not interpretations.

Produce the brief using exactly this template:

---

#### {Session ID} — {Session Name}

**Phase {N} | {Category} | Needs: {prerequisite session IDs or "none"}**

##### Objective

One sentence: what this session builds and why it matters to the overall system.

##### Scope

State P0 MVP or P1 v1.0. If this session contains both P0 and P1 work, list which stories are P0 and which are P1. Claude Code must implement P0 work fully and stub P1 work as clearly marked placeholders — never silently omit P1 without a stub.

##### Technology constraints

The specific libraries and versions this session must use. State explicitly any library that must NOT be used and why. These constraints are sourced from the distilled spec Section 1.8 and are non-negotiable.

##### Performance targets

Any SLA this session is directly responsible for meeting. State the metric, the target value, and whether it is a hard SLA or a monitoring target. If this session owns no SLA directly, state "none — see downstream sessions".

##### Owned files

Every file this session creates or modifies. Exhaustive — if it is not listed here, this session must not touch it.

##### Read-only imports

Every file from other sessions this session imports. For each: the owning session ID, the file path, and the specific named exports required.

##### Do not touch

Explicit list of files this session must not modify. Always includes:
- Entry point files (app.ts, index.ts, or equivalent) — pre-stubbed by scaffold session
- Router files (routes.tsx, router.ts, or equivalent) — pre-stubbed by scaffold session
- All files owned by other sessions (list them)

##### Architecture context

Paste the relevant architecture specification sections verbatim. Include: component responsibilities, data flow, security requirements, performance targets, and any design decisions that constrain implementation choices. Do not paraphrase.

##### User stories and acceptance criteria

Paste the complete user stories this session implements, verbatim. Include every acceptance criteria scenario — happy path, edge cases, and failure cases. Do not summarize.

##### UX and design specification

Frontend sessions only. Paste the full UX specification section(s) verbatim. Include: interaction behaviors, component specs, data fields and types, state management rules, validation rules, visual specifications. Do not paraphrase. For backend-only or infrastructure sessions, state "N/A — no frontend component".

##### Critical implementation notes

Bullet list of implementation constraints Claude Code must not infer — it must be told explicitly:
- Every ordering rule that applies to this session (quote it)
- Every HTTP status code contract that applies (state it)
- Every atomicity requirement (name the tables or operations that must be in a single transaction)
- Every cross-session contract this session must honor (name the contract and the consuming session)
- Every silent failure mode — things that will appear to work but produce wrong behavior if done incorrectly
- Any approach that must be explicitly avoided and why

##### Mocking contract

**Frontend sessions**: list every API endpoint this session needs, with method, path, and exact mock response shape. The mock response shapes must match the backend brief that owns each endpoint.

**Backend sessions**: list every internal event, queue payload, or service interface this session depends on from other sessions. Include the exact payload shape.

**Infrastructure/scaffold sessions**: state "N/A — this session defines contracts, does not consume them" or list any external service contracts.

##### Acceptance criteria checklist

Convert every user story AC scenario into a flat checklist. Format:
    - [ ] [Specific verifiable outcome] [US-XXX AC-N]

Every item must be independently testable. Every AC scenario from the pasted user stories must appear here. Add technical ACs not covered by stories (e.g., transaction atomicity, RLS enforcement, correct HTTP status codes).

**Each AC line must either**:
(a) be covered by one or more `it(...)` blocks in the Independent Test (and that mapping must appear in the *AC → assertion mapping* below), OR
(b) be marked `[MANUAL]` at the end of the line, in which case it MUST also appear in the trailing JSON block's `manualAcs[]`. Manual items become PR-description checkboxes for human sign-off in the downstream runner.

##### Independent Test

This session must follow a TDD workflow — the Independent Test file is written FIRST and must fail before any implementation code is written.

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/{session-id}.test.ts` (adapt extension/path to project conventions; for non-TS projects use the project's idiomatic test path).
- **Exact CI command**: the precise shell command CI runs to execute this session's tests in isolation (e.g., `npm test -- tests/sessions/{session-id}`, `pytest tests/sessions/{session-id}.py`). For the MANDATORY Phase 0 integration-harness session ONLY, this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **AC → assertion mapping**: a table or bulleted list mapping every NON-`[MANUAL]` AC line above to one or more `it(...)` / `test(...)` block names in the test file. Format: `US-XXX AC-N → it("does the thing")`. `[MANUAL]` ACs are exempt and surface in the trailing JSON `manualAcs[]` instead.
- **Fixtures / test doubles**: every fixture, factory, or mock used. Mock shapes MUST match the Mocking contract section above — same response shapes, same field names, same types.
- **Pre-conditions**: any migrations, seed data, environment variables, or service spin-up the test depends on.
- **Isolation rule**: the test MUST pass when this session's PR is the only one merged in its wave — no sibling session in the same wave needs to have merged first. If the test cannot pass in isolation, this is a planning bug — flag it instead of writing a brittle test.

##### Checkpoint

- **One-sentence observable outcome** after this session's PR is merged. Describe a user-facing or system-facing behavior an operator could verify without reading the diff (e.g., "Logged-in users land on /dashboard after submitting the login form", "`GET /healthz` returns 200 with `db:ok`").
- **Shippability claim**: state explicitly — "this PR is independently mergeable to main even if no other session in the same wave has merged." If that statement is NOT true, name the blocking session ID and treat this as a planning bug surfaced for the reviewer to resolve (not a brief defect to paper over).

##### Output and handoff

What this session produces that downstream sessions depend on:
- List every file, function, type, or event contract that other sessions will import
- For each: name the consuming session(s)
- Flag any export that is load-bearing (must not change after merge) with `[LOAD-BEARING]`

---

After the closing `---` of the brief above, append a REQUIRED trailing structured JSON block. The Track B build runner consumes this as typed data — it MUST be present, well-formed, and match this exact shape:

```json
{
  "test": { "cmd": "npm test -- tests/sessions/<session-id>", "file": "tests/sessions/<session-id>.test.ts" },
  "checkpoint": "One-sentence observable outcome (mirrors the Checkpoint section above).",
  "manualAcs": [
    { "id": "US-XXX-AC-N", "text": "Verbatim text of the [MANUAL] AC line." }
  ],
  "exports": [
    { "kind": "type", "name": "TypeName", "shape": "{ field: string; other: number }" },
    { "kind": "function", "name": "fnName", "shape": "(arg: string) => Promise<Result>" },
    { "kind": "module", "name": "path/to/module", "shape": "src/path/to/module.ts" }
  ]
}
```

Field rules:
- **`test.cmd`** — the exact CI command from the Independent Test section. For the Phase 0 integration-harness session this MUST be the project-level integration command (e.g., `npm run test:integration`).
- **`test.file`** — the test file path from the Independent Test section.
- **`checkpoint`** — a machine-readable copy of the Checkpoint one-sentence observable outcome (do NOT duplicate the shippability claim into this field).
- **`manualAcs[]`** — one entry for every AC line marked `[MANUAL]` in the checklist. `id` is the `US-XXX-AC-N` tag; `text` is the AC text without the `[MANUAL]` marker. Empty array `[]` if none.
- **`exports[]`** — every named export this session produces that another session may import. For `kind: "type"` or `"function"`, `shape` is a TS-style type signature. For `kind: "module"`, `shape` is the module path. Used by `validateIntraWaveExports` to detect hidden cross-session contract dependencies at plan time. Empty array `[]` only if this session genuinely produces no shared exports (rare — most sessions export at least one symbol).

The JSON block MUST be the final content in the brief — nothing after the closing ```. Fill in every section above completely; do not leave any section empty or with placeholder text. If a non-JSON section is not applicable (e.g., UX spec for a backend session), state "N/A" with a brief reason.
```

**User Message:**
```
Generate the implementation brief for session **S4-A — E2E Integration Tests**.

Phase: 4 | Category: Testing/Hardening | Prerequisites: S2-A, S2-B, S2-C, S2-D, S2-E, S2-F, S2-G, S2-H, S2-I, S2-J, S2-K, S2-L, S2-M, S3-A, S3-B, S3-C, S3-D, S3-E, S3-F, S3-G

Owned files:
- tests/integration/e2e/test_upload_to_complete.py
- tests/integration/e2e/test_correction_flow.py
- tests/integration/e2e/test_export_sync_and_async.py
- tests/integration/e2e/test_stripe_lifecycle.py
- tests/integration/e2e/test_gdpr_erasure.py
- tests/integration/e2e/test_blocklist_two_gate.py
- tests/integration/e2e/test_free_tier_limit.py

Use the specification context provided in the system blocks to fill in all sections of the brief completely.
```

---

### build-plan-consistency-check [primary]

**System Prompt:**
```
You are auditing an autonomous build plan for semantic consistency. You receive: brief summaries, the distilled specification, the session table, and results from automated programmatic checks.

The programmatic checks have already verified:
- File ownership (no file in >1 session)
- Dependency graph (no cycles, valid prereq IDs, phase consistency)
- Declared dependencies (imports from prior-phase sessions only)
- Route coverage (every route owned by exactly one session)

Focus your audit on semantic issues the code cannot catch. Run the following checks and report PASS or FAIL per check. For every FAIL: state the session ID, the field, and the specific violation.

**CHECK 1 — Mock/backend alignment** For every endpoint referenced in any frontend session: does the mock response shape match the response type defined in the owning backend session's brief? Pass: no shape mismatches.

**CHECK 2 — Ordering rule propagation** For every critical ordering rule in the distilled spec Section 1.4: does it appear in the Critical Implementation Notes of every session brief whose owned files touch the relevant code surface? Pass: every ordering rule covered in every applicable brief.

**CHECK 3 — Analytics event firing consistency** Does each analytics event from Section 1.10 appear as a firing point in exactly one session brief? Does any brief incorrectly instruct firing an analytics event from a prohibited surface? Pass: each event fires from exactly one place. If no analytics events exist, PASS.

**CHECK 4 — Technology stack compliance** Does every session brief that specifies a technology match the selected stack from Section 1.8? Pass: no alternative technology choices present in any brief.

**CHECK 5 — Cross-session runtime pattern consistency** Does every brief that reads or writes a cache key, message queue event, real-time event, or browser storage key use the exact pattern from Section 1.11? Pass: all runtime patterns consistent. If no cross-session patterns exist, PASS.

**CHECK 6 — Full story coverage** List every user story ID from the distilled spec. List every user story ID referenced in any brief checklist. Report any story ID present in the spec but absent from all briefs. Pass: no orphaned stories.

**CHECK 7 — Entry point exclusion** Do all non-scaffold session briefs list entry point and router files in "Do not touch"? Pass: yes for all non-scaffold sessions.

Report a summary: N/7 checks passed. List all failures with specific details.
```

**User Message:**
```
## Programmatic Check Results

File Ownership: PASS
Dependency Graph: PASS
Declared Dependencies: PASS
Route Coverage: PASS
undefined: PASS
undefined: PASS
undefined: PASS

---

## Session Table

# PID Analyzer — Session Decomposition

| ID | Name | Category | Phase | Prerequisites | Owned files (exhaustive) | Complexity |
| -- | ---- | -------- | ----- | ------------- | ------------------------ | ---------- |
| S0-A | Scaffold & Shared Stubs | Infrastructure | 0 | — | `backend/app/main.py`, `backend/app/config.py`, `backend/app/db/base.py`, `backend/app/db/session.py`, `backend/app/api/__init__.py`, `backend/app/api/routers/__init__.py` (all router include stubs), `backend/app/api/routers/_stubs.py` (placeholder endpoints for every route in §1.6 P0+P1), `backend/app/workers/celery_app.py`, `backend/app/workers/__init__.py`, `backend/app/schemas/contracts.py` (pydantic mirrors of §1.1), `backend/app/schemas/__init__.py`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/Dockerfile`, `backend/Dockerfile.worker`, `backend/Dockerfile.ml`, `frontend/index.html`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/router.tsx` (lazy route stubs for all SPA pages), `frontend/src/pages/_stubs.tsx`, `frontend/src/types/contracts.ts`, `marketing/next.config.js`, `marketing/tsconfig.json`, `marketing/app/layout.tsx`, `marketing/app/page.tsx`, `docker-compose.yml`, `docker-compose.test.yml`, `.env.example`, `README.md`, `ops/oda-sandbox/Dockerfile`, `ops/clamav/Dockerfile` | L |
| S0-B | Integration Harness & Manifests | Testing/Hardening | 0 | — | `package.json` (root workspace), `backend/pyproject.toml`, `backend/poetry.lock`, `frontend/package.json`, `marketing/package.json`, `tests/integration/conftest.py`, `tests/integration/docker-compose.fixtures.yml`, `tests/integration/fixtures/db.py`, `tests/integration/fixtures/redis.py`, `tests/integration/fixtures/s3.py`, `tests/integration/smoke/test_smoke.py`, `tests/integration/README.md`, `scripts/test-integration.sh`, `.github/workflows/integration.yml` | M |
| S1-A | DB Models & Migrations | Infrastructure | 1 | S0-A, S0-B | `backend/app/db/models/__init__.py`, `backend/app/db/models/user.py`, `backend/app/db/models/team.py`, `backend/app/db/models/tier.py`, `backend/app/db/models/subscription.py`, `backend/app/db/models/stored_file.py`, `backend/app/db/models/file_hash_blocklist.py`, `backend/app/db/models/drawing.py`, `backend/app/db/models/entity_class.py`, `backend/app/db/models/detected_symbol.py`, `backend/app/db/models/table_cell.py`, `backend/app/db/models/user_correction.py`, `backend/app/db/models/export_record.py`, `backend/app/db/models/ml_training_consent.py`, `backend/app/db/models/revision_comparison.py`, `backend/app/db/models/audit_log.py`, `backend/app/db/models/stripe_event.py`, `backend/alembic/versions/0001_initial_schema.py`, `backend/alembic/versions/0002_rls_policies.py`, `backend/alembic/versions/0003_audit_partitions.py`, `backend/app/db/seed_tiers.py`, `backend/app/db/seed_entity_classes.py` | L |
| S1-B | Auth Middleware & Supabase Client | Auth/Contracts | 1 | S0-A, S0-B | `backend/app/auth/__init__.py`, `backend/app/auth/supabase_client.py`, `backend/app/auth/jwt_verifier.py`, `backend/app/auth/middleware.py`, `backend/app/auth/dependencies.py`, `backend/app/auth/permissions.py` (role matrix from §1.3), `backend/app/auth/brute_force.py`, `tests/integration/test_auth_middleware.py` | M |
| S1-C | Storage & Hash Utilities | Infrastructure | 1 | S0-A, S0-B | `backend/app/storage/__init__.py`, `backend/app/storage/s3_client.py`, `backend/app/storage/presigned.py`, `backend/app/storage/hashing.py`, `backend/app/storage/blocklist.py`, `tests/integration/test_storage.py` | M |
| S1-D | Redis, Cache, Pub/Sub & Celery Config | Real-time/Queue | 1 | S0-A, S0-B | `backend/app/redis/__init__.py`, `backend/app/redis/client.py`, `backend/app/redis/cache.py` (subscription flags, entity taxonomy), `backend/app/redis/pubsub.py` (drawing:status channels), `backend/app/workers/queues.py` (queue routing config), `backend/app/workers/base.py` (Task base class with retry policy), `tests/integration/test_redis_pubsub.py` | M |
| S1-E | Analytics Emitter (PostHog) | Infrastructure | 1 | S0-A, S0-B | `backend/app/analytics/__init__.py`, `backend/app/analytics/posthog_client.py`, `backend/app/analytics/events.py` (typed emitters for all 9 events §1.10), `backend/app/analytics/dead_letter.py`, `tests/integration/test_analytics.py` | S |
| S1-F | Frontend Shared Infrastructure | Frontend | 1 | S0-A, S0-B | `frontend/src/api/client.ts`, `frontend/src/api/endpoints.ts`, `frontend/src/auth/AuthContext.tsx`, `frontend/src/auth/useAuth.ts`, `frontend/src/auth/supabaseClient.ts`, `frontend/src/hooks/useSSE.ts`, `frontend/src/hooks/usePolling.ts`, `frontend/src/components/Layout.tsx`, `frontend/src/components/Nav.tsx`, `frontend/src/components/GraceBanner.tsx`, `frontend/src/components/ProtectedRoute.tsx`, `frontend/src/lib/storage.ts` (localStorage/sessionStorage helpers), `frontend/src/lib/analytics.ts`, `frontend/src/styles/globals.css` | M |
| S2-A | Auth Endpoints | Auth/Contracts | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/auth.py`, `backend/app/services/auth_service.py`, `backend/app/services/password_reset.py`, `tests/integration/test_auth_endpoints.py` | M |
| S2-B | Drawings Endpoints + SSE Status | Backend API | 2 | S1-A, S1-B, S1-C, S1-D, S1-E | `backend/app/api/routers/drawings.py`, `backend/app/services/drawing_service.py`, `backend/app/services/hash_check_service.py`, `backend/app/services/upload_complete_service.py`, `backend/app/services/drawing_state_machine.py`, `backend/app/services/free_tier_counter.py`, `backend/app/sse/drawing_status.py`, `tests/integration/test_drawings_api.py`, `tests/integration/test_drawings_sse.py` | L |
| S2-C | Symbols & Corrections Endpoints | Backend API | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/symbols.py`, `backend/app/services/symbol_service.py`, `backend/app/services/correction_service.py` (training_consent snapshot, Under_Review trigger), `tests/integration/test_symbols_api.py` | M |
| S2-D | Export Endpoints + Sync Path | Backend API | 2 | S1-A, S1-B, S1-C, S1-D, S1-E | `backend/app/api/routers/exports.py`, `backend/app/services/export_service.py` (sync <1000 path, threshold gate), `backend/app/services/export_generators.py` (CSV/XLSX), `tests/integration/test_exports_api.py` | M |
| S2-E | Subscription + Stripe Webhook | Backend API | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/subscription.py`, `backend/app/api/routers/stripe_webhook.py`, `backend/app/services/stripe_client.py`, `backend/app/services/subscription_service.py`, `backend/app/services/billing_state_machine.py`, `backend/app/services/stripe_event_idempotency.py`, `tests/integration/test_subscription.py`, `tests/integration/test_stripe_webhook.py` | L |
| S2-F | Account, Consent & GDPR Init Endpoints | Backend API | 2 | S1-A, S1-B, S1-D, S1-E | `backend/app/api/routers/account.py`, `backend/app/services/account_service.py`, `backend/app/services/consent_service.py` (server-side team consent resolution), `backend/app/services/gdpr_init_service.py`, `tests/integration/test_account.py` | M |
| S2-G | Entity Classes & Misc Endpoints | Backend API | 2 | S1-A, S1-D | `backend/app/api/routers/entity_classes.py`, `backend/app/services/entity_class_service.py`, `tests/integration/test_entity_classes.py` | S |
| S2-H | Ingest Worker | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/ingest/__init__.py`, `backend/app/workers/ingest/tasks.py`, `backend/app/workers/ingest/oda_converter.py`, `backend/app/workers/ingest/hash_reverify.py`, `backend/app/workers/ingest/format_detect.py`, `tests/integration/test_ingest_worker.py` | L |
| S2-I | Scan Worker (ClamAV) | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/scan/__init__.py`, `backend/app/workers/scan/tasks.py`, `backend/app/workers/scan/clamav_client.py`, `tests/integration/test_scan_worker.py` | S |
| S2-J | ML Worker | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/ml/__init__.py`, `backend/app/workers/ml/tasks.py`, `backend/app/workers/ml/inference.py`, `backend/app/workers/ml/model_loader.py`, `backend/app/workers/ml/result_persistence.py`, `tests/integration/test_ml_worker.py` | L |
| S2-K | Export Worker (Async) | Real-time/Queue | 2 | S1-A, S1-C, S1-D, S1-E | `backend/app/workers/export/__init__.py`, `backend/app/workers/export/tasks.py`, `tests/integration/test_export_worker.py` | M |
| S2-L | GDPR Erasure Worker | Real-time/Queue | 2 | S1-A, S1-C, S1-D | `backend/app/workers/gdpr/__init__.py`, `backend/app/workers/gdpr/tasks.py`, `backend/app/workers/gdpr/anonymizer.py` (anonymous_id HMAC, idempotent), `tests/integration/test_gdpr_worker.py` | M |
| S2-M | Notification Worker (SendGrid) | Real-time/Queue | 2 | S1-A, S1-D | `backend/app/workers/notification/__init__.py`, `backend/app/workers/notification/tasks.py`, `backend/app/workers/notification/sendgrid_client.py`, `backend/app/workers/notification/templates.py` (verification, reset, invite, grace day-1/6), `tests/integration/test_notification_worker.py` | M |
| S3-A | Frontend: Auth Pages | Frontend | 3 | S1-F, S2-A | `frontend/src/pages/auth/Register.tsx`, `frontend/src/pages/auth/Login.tsx`, `frontend/src/pages/auth/VerifyEmail.tsx`, `frontend/src/pages/auth/PasswordResetRequest.tsx`, `frontend/src/pages/auth/PasswordResetConfirm.tsx`, `frontend/src/pages/auth/OAuthCallback.tsx`, `frontend/src/pages/auth/AccountLinkPrompt.tsx` | M |
| S3-B | Frontend: Drawing Library | Frontend | 3 | S1-F, S2-B | `frontend/src/pages/Dashboard.tsx`, `frontend/src/features/library/DrawingList.tsx`, `frontend/src/features/library/DrawingRow.tsx`, `frontend/src/features/library/StatusBadge.tsx`, `frontend/src/features/library/SearchFilter.tsx`, `frontend/src/features/library/Pagination.tsx`, `frontend/src/features/library/useDrawings.ts` | M |
| S3-C | Frontend: Upload Flow | Frontend | 3 | S1-F, S2-B | `frontend/src/pages/Upload.tsx`, `frontend/src/features/upload/DropZone.tsx`, `frontend/src/features/upload/hashClient.ts`, `frontend/src/features/upload/uploadOrchestrator.ts`, `frontend/src/features/upload/UploadProgress.tsx` | M |
| S3-D | Frontend: Review Canvas (Konva) | Frontend | 3 | S1-F, S2-B, S2-C | `frontend/src/pages/Review.tsx`, `frontend/src/features/canvas/Canvas.tsx`, `frontend/src/features/canvas/SymbolLayer.tsx`, `frontend/src/features/canvas/BoundingBox.tsx`, `frontend/src/features/canvas/PageNav.tsx`, `frontend/src/features/canvas/InspectionPanel.tsx`, `frontend/src/features/canvas/ManualAnnotate.tsx`, `frontend/src/features/canvas/CorrectionStore.ts`, `frontend/src/features/canvas/useCanvasShortcuts.ts` | L |
| S3-E | Frontend: Account & Consent | Frontend | 3 | S1-F, S2-F | `frontend/src/pages/Account.tsx`, `frontend/src/features/account/ProfileForm.tsx`, `frontend/src/features/account/ConsentToggle.tsx`, `frontend/src/features/account/DeleteAccount.tsx` | S |
| S3-F | Frontend: Subscription & Upgrade | Frontend | 3 | S1-F, S2-E | `frontend/src/pages/Subscription.tsx`, `frontend/src/features/subscription/TierCard.tsx`, `frontend/src/features/subscription/CheckoutRedirect.tsx`, `frontend/src/features/subscription/UpgradePrompt.tsx`, `frontend/src/features/subscription/PendingState.tsx` | M |
| S3-G | Frontend: Exports UI + Notifications | Frontend | 3 | S1-F, S2-D | `frontend/src/features/exports/ExportButton.tsx`, `frontend/src/features/exports/ExportModal.tsx`, `frontend/src/features/exports/useExportStatus.ts`, `frontend/src/features/notifications/InAppNotifications.tsx`, `frontend/src/features/notifications/notificationsStore.ts` | M |
| S3-H | Marketing Site (Next.js) | Frontend | 3 | S0-A | `marketing/app/(marketing)/page.tsx`, `marketing/app/pricing/page.tsx`, `marketing/app/about/page.tsx`, `marketing/app/contact/page.tsx`, `marketing/components/Hero.tsx`, `marketing/components/PricingTable.tsx`, `marketing/components/Footer.tsx`, `marketing/public/robots.txt`, `marketing/public/sitemap.xml` | M |
| S4-A | E2E Integration Tests | Testing/Hardening | 4 | All Phase 2 + Phase 3 | `tests/integration/e2e/test_upload_to_complete.py`, `tests/integration/e2e/test_correction_flow.py`, `tests/integration/e2e/test_export_sync_and_async.py`, `tests/integration/e2e/test_stripe_lifecycle.py`, `tests/integration/e2e/test_gdpr_erasure.py`, `tests/integration/e2e/test_blocklist_two_gate.py`, `tests/integration/e2e/test_free_tier_limit.py` | L |

---

## Gate Definitions

**Phase 0 → Phase 1 gate** (must merge): `S0-A`, `S0-B`. Both required: scaffold provides stubs every Phase 1 session imports; harness provides the green integration baseline (`npm run test:integration` exits 0).

**Phase 1 → Phase 2 gate** (must merge): `S1-A`, `S1-B`, `S1-C`, `S1-D`, `S1-E`. Non-blocking for Phase 2 backend work: `S1-F` (frontend-only; gates Phase 3 only).

**Phase 2 → Phase 3 gate** (must merge per frontend session): each Phase 3 session depends only on its specific Phase 2 endpoint(s) — see prerequisites column. Marketing (`S3-H`) needs only Phase 0.

**Phase 3 → Phase 4 gate** (must merge): all Phase 2 + Phase 3 sessions.

---

## Intra-Phase Dependencies

None within Phase 1 (all five core infra sessions are parallel; they only import from S0-A stubs).

None within Phase 2 — workers and API routers own disjoint files. They communicate only through Celery queues / Redis channels / DB tables defined in Phase 1.

None within Phase 3 — each frontend feature owns its own subdirectory.

---

## Early-Start Optimizations

- **S1-F (frontend shared)** depends only on `S0-A`/`S0-B` — can start with Phase 1 even though it gates Phase 3 frontends.
- **S3-H (marketing site)** depends only on `S0-A` — can start as early as Phase 1.
- **S2-G (entity classes)** needs only `S1-A` + `S1-D`, can start as soon as those two merge (before S1-B/C/E).
- **S2-L (GDPR worker)** and **S2-M (notification worker)** don't need `S1-E` analytics — can start once `S1-A`/`S1-C`/`S1-D` clear.
- **S3-A (auth pages)** can begin as soon as `S2-A` clears, regardless of other Phase 2 progress.

---

## Critical Path

`S0-A` → `S1-A` (DB models) → `S2-B` (Drawings API + SSE) → `S3-D` (Review canvas — largest frontend) → `S4-A` (E2E tests)

Length: 5 sessions, complexity L → L → L → L → L ≈ 15 hrs of Claude execution on the longest chain.

---

```json
[
  {"id":"S0-A","phase":0,"name":"Scaffold & Shared Stubs","category":"Infrastructure","prerequisites":[],"ownedFiles":["backend/app/main.py","backend/app/config.py","backend/app/db/base.py","backend/app/db/session.py","backend/app/api/__init__.py","backend/app/api/routers/__init__.py","backend/app/api/routers/_stubs.py","backend/app/workers/celery_app.py","backend/app/workers/__init__.py","backend/app/schemas/contracts.py","backend/app/schemas/__init__.py","backend/alembic.ini","backend/alembic/env.py","backend/alembic/script.py.mako","backend/Dockerfile","backend/Dockerfile.worker","backend/Dockerfile.ml","frontend/index.html","frontend/vite.config.ts","frontend/tsconfig.json","frontend/src/main.tsx","frontend/src/App.tsx","frontend/src/router.tsx","frontend/src/pages/_stubs.tsx","frontend/src/types/contracts.ts","marketing/next.config.js","marketing/tsconfig.json","marketing/app/layout.tsx","marketing/app/page.tsx","docker-compose.yml","docker-compose.test.yml",".env.example","README.md","ops/oda-sandbox/Dockerfile","ops/clamav/Dockerfile"],"complexity":"L","specSections":["1.1 Shared Contracts","1.6 Route Manifest","1.8 Technology Stack","1.12 Environment Variable Schema"]},
  {"id":"S0-B","phase":0,"name":"Integration Harness & Manifests","category":"Testing/Hardening","prerequisites":[],"ownedFiles":["package.json","backend/pyproject.toml","backend/poetry.lock","frontend/package.json","marketing/package.json","tests/integration/conftest.py","tests/integration/docker-compose.fixtures.yml","tests/integration/fixtures/db.py","tests/integration/fixtures/redis.py","tests/integration/fixtures/s3.py","tests/integration/smoke/test_smoke.py","tests/integration/README.md","scripts/test-integration.sh",".github/workflows/integration.yml"],"complexity":"M","specSections":["1.8 Technology Stack","1.12 Environment Variable Schema"]},
  {"id":"S1-A","phase":1,"name":"DB Models & Migrations","category":"Infrastructure","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/db/models/__init__.py","backend/app/db/models/user.py","backend/app/db/models/team.py","backend/app/db/models/tier.py","backend/app/db/models/subscription.py","backend/app/db/models/stored_file.py","backend/app/db/models/file_hash_blocklist.py","backend/app/db/models/drawing.py","backend/app/db/models/entity_class.py","backend/app/db/models/detected_symbol.py","backend/app/db/models/table_cell.py","backend/app/db/models/user_correction.py","backend/app/db/models/export_record.py","backend/app/db/models/ml_training_consent.py","backend/app/db/models/revision_comparison.py","backend/app/db/models/audit_log.py","backend/app/db/models/stripe_event.py","backend/alembic/versions/0001_initial_schema.py","backend/alembic/versions/0002_rls_policies.py","backend/alembic/versions/0003_audit_partitions.py","backend/app/db/seed_tiers.py","backend/app/db/seed_entity_classes.py"],"complexity":"L","specSections":["1.2 Database Schema","1.3 State Machines and Permission Matrices"]},
  {"id":"S1-B","phase":1,"name":"Auth Middleware & Supabase Client","category":"Auth/Contracts","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/auth/__init__.py","backend/app/auth/supabase_client.py","backend/app/auth/jwt_verifier.py","backend/app/auth/middleware.py","backend/app/auth/dependencies.py","backend/app/auth/permissions.py","backend/app/auth/brute_force.py","tests/integration/test_auth_middleware.py"],"complexity":"M","specSections":["1.3 State Machines and Permission Matrices","1.4 Critical Ordering Rules","1.7 Third-Party Dependencies"]},
  {"id":"S1-C","phase":1,"name":"Storage & Hash Utilities","category":"Infrastructure","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/storage/__init__.py","backend/app/storage/s3_client.py","backend/app/storage/presigned.py","backend/app/storage/hashing.py","backend/app/storage/blocklist.py","tests/integration/test_storage.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.7 Third-Party Dependencies","1.9 Performance Targets"]},
  {"id":"S1-D","phase":1,"name":"Redis, Cache, Pub/Sub & Celery Config","category":"Real-time/Queue","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/redis/__init__.py","backend/app/redis/client.py","backend/app/redis/cache.py","backend/app/redis/pubsub.py","backend/app/workers/queues.py","backend/app/workers/base.py","tests/integration/test_redis_pubsub.py"],"complexity":"M","specSections":["1.11 Cross-Session Runtime Patterns","1.8 Technology Stack"]},
  {"id":"S1-E","phase":1,"name":"Analytics Emitter (PostHog)","category":"Infrastructure","prerequisites":["S0-A","S0-B"],"ownedFiles":["backend/app/analytics/__init__.py","backend/app/analytics/posthog_client.py","backend/app/analytics/events.py","backend/app/analytics/dead_letter.py","tests/integration/test_analytics.py"],"complexity":"S","specSections":["1.10 Analytics Event Contracts"]},
  {"id":"S1-F","phase":1,"name":"Frontend Shared Infrastructure","category":"Frontend","prerequisites":["S0-A","S0-B"],"ownedFiles":["frontend/src/api/client.ts","frontend/src/api/endpoints.ts","frontend/src/auth/AuthContext.tsx","frontend/src/auth/useAuth.ts","frontend/src/auth/supabaseClient.ts","frontend/src/hooks/useSSE.ts","frontend/src/hooks/usePolling.ts","frontend/src/components/Layout.tsx","frontend/src/components/Nav.tsx","frontend/src/components/GraceBanner.tsx","frontend/src/components/ProtectedRoute.tsx","frontend/src/lib/storage.ts","frontend/src/lib/analytics.ts","frontend/src/styles/globals.css"],"complexity":"M","specSections":["1.1 Shared Contracts","1.6 Route Manifest","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-A","phase":2,"name":"Auth Endpoints","category":"Auth/Contracts","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/auth.py","backend/app/services/auth_service.py","backend/app/services/password_reset.py","tests/integration/test_auth_endpoints.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.6 Route Manifest","1.13 Feature Scope"]},
  {"id":"S2-B","phase":2,"name":"Drawings Endpoints + SSE Status","category":"Backend API","prerequisites":["S1-A","S1-B","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/drawings.py","backend/app/services/drawing_service.py","backend/app/services/hash_check_service.py","backend/app/services/upload_complete_service.py","backend/app/services/drawing_state_machine.py","backend/app/services/free_tier_counter.py","backend/app/sse/drawing_status.py","tests/integration/test_drawings_api.py","tests/integration/test_drawings_sse.py"],"complexity":"L","specSections":["1.3 State Machines and Permission Matrices","1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.6 Route Manifest","1.10 Analytics Event Contracts","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-C","phase":2,"name":"Symbols & Corrections Endpoints","category":"Backend API","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/symbols.py","backend/app/services/symbol_service.py","backend/app/services/correction_service.py","tests/integration/test_symbols_api.py"],"complexity":"M","specSections":["1.1 Shared Contracts","1.4 Critical Ordering Rules","1.10 Analytics Event Contracts","1.13 Feature Scope"]},
  {"id":"S2-D","phase":2,"name":"Export Endpoints + Sync Path","category":"Backend API","prerequisites":["S1-A","S1-B","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/exports.py","backend/app/services/export_service.py","backend/app/services/export_generators.py","tests/integration/test_exports_api.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.6 Route Manifest","1.9 Performance Targets","1.10 Analytics Event Contracts"]},
  {"id":"S2-E","phase":2,"name":"Subscription + Stripe Webhook","category":"Backend API","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/subscription.py","backend/app/api/routers/stripe_webhook.py","backend/app/services/stripe_client.py","backend/app/services/subscription_service.py","backend/app/services/billing_state_machine.py","backend/app/services/stripe_event_idempotency.py","tests/integration/test_subscription.py","tests/integration/test_stripe_webhook.py"],"complexity":"L","specSections":["1.3 State Machines and Permission Matrices","1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.7 Third-Party Dependencies","1.10 Analytics Event Contracts"]},
  {"id":"S2-F","phase":2,"name":"Account, Consent & GDPR Init Endpoints","category":"Backend API","prerequisites":["S1-A","S1-B","S1-D","S1-E"],"ownedFiles":["backend/app/api/routers/account.py","backend/app/services/account_service.py","backend/app/services/consent_service.py","backend/app/services/gdpr_init_service.py","tests/integration/test_account.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.13 Feature Scope"]},
  {"id":"S2-G","phase":2,"name":"Entity Classes & Misc Endpoints","category":"Backend API","prerequisites":["S1-A","S1-D"],"ownedFiles":["backend/app/api/routers/entity_classes.py","backend/app/services/entity_class_service.py","tests/integration/test_entity_classes.py"],"complexity":"S","specSections":["1.6 Route Manifest","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-H","phase":2,"name":"Ingest Worker","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/ingest/__init__.py","backend/app/workers/ingest/tasks.py","backend/app/workers/ingest/oda_converter.py","backend/app/workers/ingest/hash_reverify.py","backend/app/workers/ingest/format_detect.py","tests/integration/test_ingest_worker.py"],"complexity":"L","specSections":["1.4 Critical Ordering Rules","1.7 Third-Party Dependencies","1.11 Cross-Session Runtime Patterns","1.13 Feature Scope"]},
  {"id":"S2-I","phase":2,"name":"Scan Worker (ClamAV)","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/scan/__init__.py","backend/app/workers/scan/tasks.py","backend/app/workers/scan/clamav_client.py","tests/integration/test_scan_worker.py"],"complexity":"S","specSections":["1.7 Third-Party Dependencies","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-J","phase":2,"name":"ML Worker","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/ml/__init__.py","backend/app/workers/ml/tasks.py","backend/app/workers/ml/inference.py","backend/app/workers/ml/model_loader.py","backend/app/workers/ml/result_persistence.py","tests/integration/test_ml_worker.py"],"complexity":"L","specSections":["1.1 Shared Contracts","1.4 Critical Ordering Rules","1.9 Performance Targets","1.10 Analytics Event Contracts","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S2-K","phase":2,"name":"Export Worker (Async)","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D","S1-E"],"ownedFiles":["backend/app/workers/export/__init__.py","backend/app/workers/export/tasks.py","tests/integration/test_export_worker.py"],"complexity":"M","specSections":["1.9 Performance Targets","1.11 Cross-Session Runtime Patterns","1.13 Feature Scope"]},
  {"id":"S2-L","phase":2,"name":"GDPR Erasure Worker","category":"Real-time/Queue","prerequisites":["S1-A","S1-C","S1-D"],"ownedFiles":["backend/app/workers/gdpr/__init__.py","backend/app/workers/gdpr/tasks.py","backend/app/workers/gdpr/anonymizer.py","tests/integration/test_gdpr_worker.py"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.11 Cross-Session Runtime Patterns","1.12 Environment Variable Schema","1.13 Feature Scope"]},
  {"id":"S2-M","phase":2,"name":"Notification Worker (SendGrid)","category":"Real-time/Queue","prerequisites":["S1-A","S1-D"],"ownedFiles":["backend/app/workers/notification/__init__.py","backend/app/workers/notification/tasks.py","backend/app/workers/notification/sendgrid_client.py","backend/app/workers/notification/templates.py","tests/integration/test_notification_worker.py"],"complexity":"M","specSections":["1.3 State Machines and Permission Matrices","1.7 Third-Party Dependencies","1.11 Cross-Session Runtime Patterns"]},
  {"id":"S3-A","phase":3,"name":"Frontend: Auth Pages","category":"Frontend","prerequisites":["S1-F","S2-A"],"ownedFiles":["frontend/src/pages/auth/Register.tsx","frontend/src/pages/auth/Login.tsx","frontend/src/pages/auth/VerifyEmail.tsx","frontend/src/pages/auth/PasswordResetRequest.tsx","frontend/src/pages/auth/PasswordResetConfirm.tsx","frontend/src/pages/auth/OAuthCallback.tsx","frontend/src/pages/auth/AccountLinkPrompt.tsx"],"complexity":"M","specSections":["1.6 Route Manifest","1.13 Feature Scope"]},
  {"id":"S3-B","phase":3,"name":"Frontend: Drawing Library","category":"Frontend","prerequisites":["S1-F","S2-B"],"ownedFiles":["frontend/src/pages/Dashboard.tsx","frontend/src/features/library/DrawingList.tsx","frontend/src/features/library/DrawingRow.tsx","frontend/src/features/library/StatusBadge.tsx","frontend/src/features/library/SearchFilter.tsx","frontend/src/features/library/Pagination.tsx","frontend/src/features/library/useDrawings.ts"],"complexity":"M","specSections":["1.6 Route Manifest","1.9 Performance Targets","1.13 Feature Scope"]},
  {"id":"S3-C","phase":3,"name":"Frontend: Upload Flow","category":"Frontend","prerequisites":["S1-F","S2-B"],"ownedFiles":["frontend/src/pages/Upload.tsx","frontend/src/features/upload/DropZone.tsx","frontend/src/features/upload/hashClient.ts","frontend/src/features/upload/uploadOrchestrator.ts","frontend/src/features/upload/UploadProgress.tsx"],"complexity":"M","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.13 Feature Scope"]},
  {"id":"S3-D","phase":3,"name":"Frontend: Review Canvas (Konva)","category":"Frontend","prerequisites":["S1-F","S2-B","S2-C"],"ownedFiles":["frontend/src/pages/Review.tsx","frontend/src/features/canvas/Canvas.tsx","frontend/src/features/canvas/SymbolLayer.tsx","frontend/src/features/canvas/BoundingBox.tsx","frontend/src/features/canvas/PageNav.tsx","frontend/src/features/canvas/InspectionPanel.tsx","frontend/src/features/canvas/ManualAnnotate.tsx","frontend/src/features/canvas/CorrectionStore.ts","frontend/src/features/canvas/useCanvasShortcuts.ts"],"complexity":"L","specSections":["1.6 Route Manifest","1.8 Technology Stack","1.9 Performance Targets","1.11 Cross-Session Runtime Patterns","1.13 Feature Scope"]},
  {"id":"S3-E","phase":3,"name":"Frontend: Account & Consent","category":"Frontend","prerequisites":["S1-F","S2-F"],"ownedFiles":["frontend/src/pages/Account.tsx","frontend/src/features/account/ProfileForm.tsx","frontend/src/features/account/ConsentToggle.tsx","frontend/src/features/account/DeleteAccount.tsx"],"complexity":"S","specSections":["1.6 Route Manifest","1.13 Feature Scope"]},
  {"id":"S3-F","phase":3,"name":"Frontend: Subscription & Upgrade","category":"Frontend","prerequisites":["S1-F","S2-E"],"ownedFiles":["frontend/src/pages/Subscription.tsx","frontend/src/features/subscription/TierCard.tsx","frontend/src/features/subscription/CheckoutRedirect.tsx","frontend/src/features/subscription/UpgradePrompt.tsx","frontend/src/features/subscription/PendingState.tsx"],"complexity":"M","specSections":["1.3 State Machines and Permission Matrices","1.6 Route Manifest","1.9 Performance Targets","1.13 Feature Scope"]},
  {"id":"S3-G","phase":3,"name":"Frontend: Exports UI + Notifications","category":"Frontend","prerequisites":["S1-F","S2-D"],"ownedFiles":["frontend/src/features/exports/ExportButton.tsx","frontend/src/features/exports/ExportModal.tsx","frontend/src/features/exports/useExportStatus.ts","frontend/src/features/notifications/InAppNotifications.tsx","frontend/src/features/notifications/notificationsStore.ts"],"complexity":"M","specSections":["1.9 Performance Targets","1.13 Feature Scope"]},
  {"id":"S3-H","phase":3,"name":"Marketing Site (Next.js)","category":"Frontend","prerequisites":["S0-A"],"ownedFiles":["marketing/app/(marketing)/page.tsx","marketing/app/pricing/page.tsx","marketing/app/about/page.tsx","marketing/app/contact/page.tsx","marketing/components/Hero.tsx","marketing/components/PricingTable.tsx","marketing/components/Footer.tsx","marketing/public/robots.txt","marketing/public/sitemap.xml"],"complexity":"M","specSections":["1.8 Technology Stack"]},
  {"id":"S4-A","phase":4,"name":"E2E Integration Tests","category":"Testing/Hardening","prerequisites":["S2-A","S2-B","S2-C","S2-D","S2-E","S2-F","S2-G","S2-H","S2-I","S2-J","S2-K","S2-L","S2-M","S3-A","S3-B","S3-C","S3-D","S3-E","S3-F","S3-G"],"ownedFiles":["tests/integration/e2e/test_upload_to_complete.py","tests/integration/e2e/test_correction_flow.py","tests/integration/e2e/test_export_sync_and_async.py","tests/integration/e2e/test_stripe_lifecycle.py","tests/integration/e2e/test_gdpr_erasure.py","tests/integration/e2e/test_blocklist_two_gate.py","tests/integration/e2e/test_free_tier_limit.py"],"complexity":"L","specSections":["1.4 Critical Ordering Rules","1.5 HTTP Status Code Contracts","1.10 Analytics Event Contracts","1.13 Feature Scope"]}
]
```

Total: 30 sessions across 5 phases

---

## Brief Summaries

### S0-A — Scaffold & Shared Stubs
Owned files: (exactly as listed in the prompt — exhaustive, do not touch anything else)
Imports: None — this is the root session.

### S0-B — Integration Harness & Manifests
Owned files: - `package.json` (root workspace; defines `test:integration` script)
- `backend/pyproject.toml`
- `backend/poetry.lock`
- `frontend/package.json`
- `marketing/package.json`
- `tests/integration/conftest.py`
- `tests/integration/docker-compose.fixtures.yml`
- `tests/integration/fixtures/db.py`
- `tests/integration/fixtures/redis.py`
- `tests/integration/fixtures/s3.py`
- `tests/integration/smoke/test_smoke.py`
- `tests/integration/README.md`
- `scripts/test-integration.sh`
- `.github/workflows/integration.yml`
Imports: None. This session runs before any source code exists (S0-A is a sibling that owns app scaffolding; this session must NOT import from `backend/app/*` or `frontend/src/*` because S0-B and S0-A may merge in either order).

The smoke test verifies infrastructure only (DB reachable, Redis reachable, MinIO reachable) — it does NOT import application code.

### S1-A — DB Models & Migrations
Owned files: - `backend/app/db/models/__init__.py`
- `backend/app/db/models/user.py`
- `backend/app/db/models/team.py`
- `backend/app/db/models/tier.py`
- `backend/app/db/models/subscription.py`
- `backend/app/db/models/stored_file.py`
- `backend/app/db/models/file_hash_blocklist.py`
- `backend/app/db/models/drawing.py`
- `backend/app/db/models/entity_class.py`
- `backend/app/db/models/detected_symbol.py`
- `backend/app/db/models/table_cell.py`
- `backend/app/db/models/user_correction.py`
- `backend/app/db/models/export_record.py`
- `backend/app/db/models/ml_training_consent.py`
- `backend/app/db/models/revision_comparison.py`
- `backend/app/db/models/audit_log.py`
- `backend/app/db/models/stripe_event.py`
- `backend/alembic/versions/0001_initial_schema.py`
- `backend/alembic/versions/0002_rls_policies.py`
- `backend/alembic/versions/0003_audit_partitions.py`
- `backend/app/db/seed_tiers.py`
- `backend/app/db/seed_entity_classes.py`
Imports: From **S0-A**:
- `backend/app/db/base.py` — `Base` (SQLAlchemy declarative base)
- `backend/app/db/session.py` — `engine`, `SessionLocal`, `get_db`
- `backend/app/config.py` — `settings` (for `DATABASE_URL`, `ENVIRONMENT`)
- `backend/alembic/env.py` — already wired to import `Base.metadata`; new migrations are autogenerated against the metadata this session populates.
- `backend/app/schemas/contracts.py` — `EntityClassId` literal (for seed validation), `DrawingProcessingState`, `BillingState`, `TierId`, `UserRole`, `SymbolSource`, `CorrectionType`, `ExportFormat`, `ExportStatus`.

From **S0-B**:
- `tests/integration/conftest.py` — `db_session`, `clean_db` fixtures
- `tests/integration/fixtures/db.py` — `migrate_to_head()`, `drop_all()` helpers

### S1-B — Auth Middleware & Supabase Client
Owned files: - `backend/app/auth/__init__.py`
- `backend/app/auth/supabase_client.py`
- `backend/app/auth/jwt_verifier.py`
- `backend/app/auth/middleware.py`
- `backend/app/auth/dependencies.py`
- `backend/app/auth/permissions.py`
- `backend/app/auth/brute_force.py`
- `tests/integration/test_auth_middleware.py`
Imports: - From **S0-A**:
  - `backend/app/config.py` — settings object exposing `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `JWT_RS256_PUBLIC_KEY`, `REDIS_URL`, `ENVIRONMENT`.
  - `backend/app/schemas/contracts.py` — `UserRole` type alias matching `'user' | 'team_member' | 'team_admin'`.
  - `backend/app/db/session.py` — async session factory `get_db()` (for `token_invalidated_at` lookup).
- From **S0-B**:
  - `tests/integration/conftest.py` — pytest fixtures (`db`, `redis`, `app_client`).
  - `tests/integration/fixtures/redis.py` — `redis_client` fixture.

### S1-C — Storage & Hash Utilities
Owned files: - `backend/app/storage/__init__.py`
- `backend/app/storage/s3_client.py`
- `backend/app/storage/presigned.py`
- `backend/app/storage/hashing.py`
- `backend/app/storage/blocklist.py`
- `tests/integration/test_storage.py`
Imports: - **From S0-A**:
  - `backend/app/config.py` — settings object exposing `S3_BUCKET_NAME`, `S3_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `PRESIGNED_URL_EXPIRY_SECONDS`, `MAX_UPLOAD_SIZE_BYTES`.
  - `backend/app/db/session.py` — DB session factory (for blocklist queries).
  - `backend/app/schemas/contracts.py` — `HashCheckRequest`, `HashCheckResponse` pydantic models.
- **From S0-B**:
  - `tests/integration/conftest.py` — pytest fixtures.
  - `tests/integration/fixtures/db.py` — DB fixture.
  - `tests/integration/fixtures/s3.py` — moto/localstack-backed S3 fixture.

### S1-D — Redis, Cache, Pub/Sub & Celery Config
Owned files: - `backend/app/redis/__init__.py`
- `backend/app/redis/client.py`
- `backend/app/redis/cache.py`
- `backend/app/redis/pubsub.py`
- `backend/app/workers/queues.py`
- `backend/app/workers/base.py`
- `tests/integration/test_redis_pubsub.py`
Imports: - From **S0-A** `backend/app/config.py`: settings object exposing `REDIS_URL`, `CELERY_BROKER_URL`, `ENVIRONMENT`.
- From **S0-A** `backend/app/workers/celery_app.py`: the `celery_app` instance (this session configures its queue routing and task base class but does not redefine the app).
- From **S0-A** `backend/app/schemas/contracts.py`: `DrawingStatusSSEEvent`, `DrawingProcessingState`, `TierId`, `BillingState`.
- From **S0-B** `tests/integration/conftest.py`: redis fixture (`redis_client`), event loop fixture.
- From **S0-B** `tests/integration/fixtures/redis.py`: ephemeral Redis container fixture.

### S1-E — Analytics Emitter (PostHog)
Owned files: - `backend/app/analytics/__init__.py`
- `backend/app/analytics/posthog_client.py`
- `backend/app/analytics/events.py`
- `backend/app/analytics/dead_letter.py`
- `tests/integration/test_analytics.py`
Imports: - From **S0-A**: `backend/app/config.py` — env var accessors (`POSTHOG_API_KEY`, `POSTHOG_HOST`, `ENVIRONMENT`); `backend/app/schemas/contracts.py` — types `TierId`, `ExportFormat` (for typed event signatures).
- From **S0-B**: `tests/integration/conftest.py` — pytest fixtures (db, redis container handles) for the test file.

Note: S1-D (Redis client) is **not** a prerequisite per the session plan. This session must therefore use the raw `REDIS_URL` env var directly via `redis-py` for its dead-letter queue, and not import from `backend/app/redis/*` (which is owned by S1-D and may not exist when this session runs in isolation). If S1-D has merged, callers may later inject its client, but this session's code must function standalone.

### S1-F — Frontend Shared Infrastructure
Owned files: - `frontend/src/api/client.ts`
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
Imports: - From **S0-A**:
  - `frontend/src/types/contracts.ts` — all TS types defined in §1.1 (`DrawingProcessingState`, `DrawingStatusSSEEvent`, `HashCheckRequest`, `HashCheckResponse`, `SymbolsPageResponse`, `BillingState`, `TierId`, `UserRole`, `SymbolSource`, `CorrectionType`, `ExportFormat`, `ExportStatus`, `EntityClassId`, `SymbolRecord`, `CorrectionRecord`, `BoundingBox`, etc.)
  - `frontend/src/router.tsx` — only for understanding route names; do not modify.

### S2-A — Auth Endpoints
Owned files: ```
backend/app/api/routers/auth.py
backend/app/services/auth_service.py
backend/app/services/password_reset.py
tests/integration/test_auth_endpoints.py
```
Imports: | Owning Session | File Path | Named Exports Required |
|---|---|---|
| S0-A | `backend/app/schemas/contracts.py` | Pydantic mirrors of §1.1 shared contracts (used for response shaping) |
| S0-A | `backend/app/api/routers/__init__.py` | Router include stubs (do not modify; import only) |
| S1-A | `backend/app/db/models/user.py` | `User` ORM model |
| S1-A | `backend/app/db/models/subscription.py` | `Subscription` ORM model |
| S1-A | `backend/app/db/models/audit_log.py` | `AuditLog` ORM model |
| S1-B | `backend/app/auth/supabase_client.py` | `get_supabase_client`, `get_supabase_admin_client` |
| S1-B | `backend/app/auth/jwt_verifier.py` | `verify_jwt_token`, `decode_jwt_claims` |
| S1-B | `backend/app/auth/dependencies.py` | `get_current_user` FastAPI dependency |
| S1-B | `backend/app/auth/brute_force.py` | `check_brute_force_lockout`, `increment_brute_force_counter`, `reset_brute_force_counter` |
| S1-D | `backend/app/redis/client.py` | `get_redis_client` |
| S1-D | `backend/app/workers/queues.py` | `NOTIFICATION_QUEUE` queue name constant |
| S1-D | `backend/app/workers/base.py` | `BaseTask` Celery task base class |
| S1-E | `backend/app/analytics/posthog_client.py` | `get_posthog_client` (imported but not called in auth; present for consistent wiring pattern) |
| S0-A | `backend/app/db/session.py` | `get_db` async session dependency |

### S2-B — Drawings Endpoints + SSE Status
Owned files: ```
backend/app/api/routers/drawings.py
backend/app/services/drawing_service.py
backend/app/services/hash_check_service.py
backend/app/services/upload_complete_service.py
backend/app/services/drawing_state_machine.py
backend/app/services/free_tier_counter.py
backend/app/sse/drawing_status.py
tests/integration/test_drawings_api.py
tests/integration/test_drawings_sse.py
```
Imports: | Session | File | Named exports required |
|---|---|---|
| S0-A | `backend/app/api/routers/__init__.py` | Router registration pattern |
| S0-A | `backend/app/schemas/contracts.py` | `HashCheckRequest`, `HashCheckResponse`, `DrawingProcessingState`, `MLInferenceJobPayload`, `DrawingStatusSSEEvent`, `BoundingBox` |
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` |
| S1-A | `backend/app/db/models/drawing.py` | `Drawing` |
| S1-A | `backend/app/db/models/stored_file.py` | `StoredFile` |
| S1-A | `backend/app/db/models/file_hash_blocklist.py` | `FileHashBlocklist` |
| S1-A | `backend/app/db/models/subscription.py` | `Subscription` |
| S1-A | `backend/app/db/models/tier.py` | `Tier` |
| S1-A | `backend/app/db/models/user.py` | `User` |
| S1-A | `backend/app/db/session.py` | `get_db` |
| S1-B | `backend/app/auth/dependencies.py` | `get_current_user`, `require_authenticated` |
| S1-B | `backend/app/auth/permissions.py` | `ROLE_PERMISSIONS`, `assert_drawing_access`, `assert_drawing_delete` |
| S1-C | `backend/app/storage/presigned.py` | `generate_upload_presigned_url`, `generate_download_presigned_url` |
| S1-C | `backend/app/storage/s3_client.py` | `get_s3_client` |
| S1-C | `backend/app/storage/blocklist.py` | `is_hash_blocked` |
| S1-D | `backend/app/redis/client.py` | `get_redis_client` |
| S1-D | `backend/app/redis/pubsub.py` | `subscribe_drawing_status`, `DRAWING_STATUS_CHANNEL` |
| S1-D | `backend/app/workers/queues.py` | `INGEST_QUEUE` |
| S1-E | `backend/app/analytics/events.py` | `emit_drawing_uploaded`, `emit_free_limit_reached` |

### S2-C — Symbols & Corrections Endpoints
Owned files: ```
backend/app/api/routers/symbols.py
backend/app/services/symbol_service.py
backend/app/services/correction_service.py
tests/integration/test_symbols_api.py
```

All Pydantic request/response schemas specific to this session are defined within `symbols.py` (router file). No new schema module is created — load-bearing shared types are already in `backend/app/schemas/contracts.py` (S0-A).

---
Imports: | Session | File | Named exports required |
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

### S2-D — Export Endpoints + Sync Path
Owned files: ```
backend/app/api/routers/exports.py
backend/app/services/export_service.py
backend/app/services/export_generators.py
tests/integration/test_exports_api.py
```

---
Imports: | Owning Session | File Path | Named Exports Required |
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

### S2-E — Subscription + Stripe Webhook
Owned files: - `backend/app/api/routers/subscription.py`
- `backend/app/api/routers/stripe_webhook.py`
- `backend/app/services/stripe_client.py`
- `backend/app/services/subscription_service.py`
- `backend/app/services/billing_state_machine.py`
- `backend/app/services/stripe_event_idempotency.py`
- `tests/integration/test_subscription.py`
- `tests/integration/test_stripe_webhook.py`

---
Imports: | Owning Session | File Path | Required Named Exports |
|---|---|---|
| S1-A | `backend/app/db/models/subscription.py` | `Subscription` |
| S1-A | `backend/app/db/models/stripe_event.py` | `StripeEvent` |
| S1-A | `backend/app/db/models/user.py` | `User` |
| S1-A | `backend/app/db/models/tier.py` | `Tier` |
| S1-B | `backend/app/auth/dependencies.py` | `get_current_user` |
| S1-D | `backend/app/redis/client.py` | `get_redis` |
| S1-D | `backend/app/redis/cache.py` | `invalidate_subscription_flags`, `set_subscription_flags` |
| S1-E | `backend/app/analytics/events.py` | `emit_subscription_upgraded`, `emit_subscription_downgraded` |
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` |
| S0-A | `backend/app/schemas/contracts.py` | `BillingState`, `TierId` |

---

### S2-F — Account, Consent & GDPR Init Endpoints
Owned files: - `backend/app/api/routers/account.py`
- `backend/app/services/account_service.py`
- `backend/app/services/consent_service.py`
- `backend/app/services/gdpr_init_service.py`
- `tests/integration/test_account.py`

---
Imports: | Owning Session | File Path | Named Exports Required |
|---|---|---|
| S0-A | `backend/app/schemas/contracts.py` | All Pydantic contract types; `DrawingProcessingState`, `BillingState`, `TierId`, `UserRole` |
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` (Celery application instance) |
| S0-A | `backend/app/config.py` | `settings` (for `settings.ENVIRONMENT`, `settings.HMAC_SERVER_SECRET`) |
| S1-A | `backend/app/db/models/user.py` | `User` (ORM model with fields: `id`, `email`, `display_name`, `email_verified`, `role`, `team_id`, `deleted_at`, `token_invalidated_at`, `anonymous_id`) |
| S1-A | `backend/app/db/models/ml_training_consent.py` | `MLTrainingConsent` (ORM model with fields: `id`, `user_id`, `team_id`, `opted_in`, `updated_at`) |
| S1-A | `backend/app/db/session.py` | `get_async_session` (FastAPI dependency providing `AsyncSession`) |
| S1-B | `backend/app/auth/dependencies.py` | `get_current_user` (FastAPI dependency returning authenticated `User` instance; raises `HTTPException(401)` if token invalid, expired, or `token_invalidated_at` check fails; raises `HTTPException(401)` if `user.deleted_at` is set) |
| S1-B | `backend/app/auth/supabase_client.py` | `supabase_admin_client` (initialized Supabase client with service role key) |
| S1-D | `backend/app/redis/cache.py` | `invalidate_subscription_flags(user_id: str) -> None` (deletes `subscription:flags:{user_id}` Redis key) |
| S1-E | `backend/app/analytics/events.py` | (imported for structural completeness; no analytics events are fired from account/consent endpoints per §1.10 event table — none of the nine events originate from this session's handlers) |

---

### S2-G — Entity Classes & Misc Endpoints
Owned files: - `backend/app/api/routers/entity_classes.py`
- `backend/app/services/entity_class_service.py`
- `tests/integration/test_entity_classes.py`

---
Imports: | Owning session | File path | Specific named exports required |
|---|---|---|
| S0-A | `backend/app/schemas/contracts.py` | `EntityClassId` (Pydantic-equivalent literal or `Literal` type), base schema helpers |
| S0-A | `backend/app/api/routers/__init__.py` | Router registration pattern (read for consistency; do not modify) |
| S1-A | `backend/app/db/models/entity_class.py` | `EntityClass` SQLAlchemy model |
| S1-A | `backend/app/db/session.py` | `get_db` async session dependency |
| S1-D | `backend/app/redis/cache.py` | `get_cached`, `set_cached`, `invalidate_cached` (or equivalent cache CRUD helpers) |
| S1-D | `backend/app/redis/client.py` | `get_redis_client` dependency |

---

### S2-H — Ingest Worker
Owned files: ```
backend/app/workers/ingest/__init__.py
backend/app/workers/ingest/tasks.py
backend/app/workers/ingest/oda_converter.py
backend/app/workers/ingest/hash_reverify.py
backend/app/workers/ingest/format_detect.py
tests/integration/test_ingest_worker.py
```

---
Imports: | Owning Session | File Path | Named Exports Required |
|---|---|---|
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` (Celery application instance) |
| S0-A | `backend/app/config.py` | `settings` (Settings object with all env vars from §1.12) |
| S1-A | `backend/app/db/session.py` | `get_db_session` (context manager / dependency) |
| S1-A | `backend/app/db/models/drawing.py` | `Drawing` (SQLAlchemy model) |
| S1-A | `backend/app/db/models/stored_file.py` | `StoredFile` (SQLAlchemy model) |
| S1-A | `backend/app/db/models/file_hash_blocklist.py` | `FileHashBlocklist` (SQLAlchemy model) |
| S1-C | `backend/app/storage/s3_client.py` | `get_s3_client`, `download_object_bytes`, `upload_object_bytes` |
| S1-C | `backend/app/storage/hashing.py` | `compute_sha256` |
| S1-C | `backend/app/storage/blocklist.py` | `is_hash_blocked` |
| S1-D | `backend/app/redis/pubsub.py` | `publish_drawing_status` |
| S1-D | `backend/app/workers/queues.py` | `INGEST_QUEUE`, `SCAN_QUEUE` (queue name constants) |
| S1-D | `backend/app/workers/base.py` | `BaseTaskWithRetry` (base Celery task class with retry policy) |
| S1-E | `backend/app/analytics/events.py` | `emit_event` (for P1 stubs — imported but not called in P0) |

---

### S2-I — Scan Worker (ClamAV)
Owned files: - `backend/app/workers/scan/__init__.py`
- `backend/app/workers/scan/tasks.py`
- `backend/app/workers/scan/clamav_client.py`
- `tests/integration/test_scan_worker.py`

---
Imports: | Owning Session | File | Named Exports Required |
|---|---|---|
| S0-A | `backend/app/schemas/contracts.py` | `MLInferenceJobPayload`, `DrawingStatusSSEEvent`, `DrawingProcessingState` |
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` |
| S1-A | `backend/app/db/models/drawing.py` | `Drawing` |
| S1-A | `backend/app/db/models/stored_file.py` | `StoredFile` |
| S1-A | `backend/app/db/session.py` | `SessionLocal` (or `get_db`) |
| S1-C | `backend/app/storage/s3_client.py` | `get_s3_client` |
| S1-D | `backend/app/redis/pubsub.py` | `publish_drawing_status` |
| S1-D | `backend/app/workers/queues.py` | `Queues` (queue name constants) |
| S1-D | `backend/app/workers/base.py` | `BaseTask` |
| S1-E | `backend/app/analytics/events.py` | *(available but not invoked — no analytics events are fired by the scan worker per §1.10; this import exists only for awareness)* |

---

### S2-J — ML Worker
Owned files: ```
backend/app/workers/ml/__init__.py
backend/app/workers/ml/tasks.py
backend/app/workers/ml/inference.py
backend/app/workers/ml/model_loader.py
backend/app/workers/ml/result_persistence.py
tests/integration/test_ml_worker.py
```

---
Imports: | Owning session | File path | Required named exports |
|---|---|---|
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` |
| S0-A | `backend/app/schemas/contracts.py` | `MLInferenceJobPayload`, `MLInferenceResult`, `DetectedSymbolResult`, `TableRegionResult`, `BoundingBox`, `DrawingStatusSSEEvent`, `DrawingProcessingState` |
| S0-A | `backend/app/config.py` | `settings` (env var access: `ML_MODEL_S3_KEY`, `ML_MODEL_VERSION`, `ML_JOB_TIMEOUT_SECONDS`, `S3_BUCKET_NAME`) |
| S1-A | `backend/app/db/models/drawing.py` | `Drawing` |
| S1-A | `backend/app/db/models/detected_symbol.py` | `DetectedSymbol` |
| S1-A | `backend/app/db/models/table_cell.py` | `TableCell` (for P1 stub reference only) |
| S1-A | `backend/app/db/session.py` | `SessionLocal`, `get_db` |
| S1-C | `backend/app/storage/s3_client.py` | `download_file_bytes`, `get_s3_client` |
| S1-D | `backend/app/redis/pubsub.py` | `publish_drawing_status` |
| S1-D | `backend/app/workers/base.py` | `BaseTask` |
| S1-D | `backend/app/workers/queues.py` | `ML_INFERENCE_QUEUE` |
| S1-E | `backend/app/analytics/events.py` | `emit_processing_complete`, `emit_processing_failed` |

---

### S2-K — Export Worker (Async)
Owned files: - `backend/app/workers/export/__init__.py`
- `backend/app/workers/export/tasks.py`
- `tests/integration/test_export_worker.py`

---
Imports: | Owning Session | File Path | Named Exports Required |
|---|---|---|
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` (Celery application instance) |
| S0-A | `backend/app/config.py` | `settings` (S3_BUCKET_NAME, REDIS_URL, DATABASE_URL, etc.) |
| S1-A | `backend/app/db/models/export_record.py` | `ExportRecord` (SQLAlchemy model) |
| S1-A | `backend/app/db/models/stored_file.py` | `StoredFile` (SQLAlchemy model) |
| S1-A | `backend/app/db/models/detected_symbol.py` | `DetectedSymbol` (SQLAlchemy model) |
| S1-A | `backend/app/db/models/drawing.py` | `Drawing` (SQLAlchemy model) |
| S1-A | `backend/app/db/session.py` | `SessionLocal` (SQLAlchemy session factory) |
| S1-C | `backend/app/storage/s3_client.py` | `upload_bytes`, `get_s3_client` |
| S1-C | `backend/app/storage/hashing.py` | `sha256_bytes` (compute SHA-256 of bytes in memory) |
| S1-D | `backend/app/redis/pubsub.py` | `publish_event` (publishes JSON payload to Redis channel) |
| S1-D | `backend/app/redis/client.py` | `get_redis_client` |
| S1-E | `backend/app/analytics/events.py` | Not required — no analytics events fire from this worker (see §1.10) |

---

### S2-L — GDPR Erasure Worker
Owned files: - `backend/app/workers/gdpr/__init__.py`
- `backend/app/workers/gdpr/tasks.py`
- `backend/app/workers/gdpr/anonymizer.py`
- `tests/integration/test_gdpr_worker.py`

---
Imports: | Owning Session | File Path | Named Exports Required |
|---|---|---|
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` (Celery application instance) |
| S0-A | `backend/app/config.py` | `settings` (env var access, including `HMAC_SERVER_SECRET`, `DATABASE_URL`, `REDIS_URL`) |
| S1-A | `backend/app/db/models/user.py` | `User` (SQLAlchemy model) |
| S1-A | `backend/app/db/models/audit_log.py` | `AuditLog` (SQLAlchemy model) |
| S1-A | `backend/app/db/models/ml_training_consent.py` | `MLTrainingConsent` (SQLAlchemy model) |
| S1-A | `backend/app/db/models/user_correction.py` | `UserCorrection` (SQLAlchemy model) |
| S1-A | `backend/app/db/models/drawing.py` | `Drawing` (SQLAlchemy model; for orphaned drawing ownership logic if needed) |
| S1-A | `backend/app/db/session.py` | `get_db_session` (session factory / context manager) |
| S1-C | `backend/app/storage/s3_client.py` | `S3Client` (for future S3 deletion stubs — import only, not called in P0) |
| S1-D | `backend/app/workers/queues.py` | `GDPR_ERASURE_QUEUE` (queue routing constant) |
| S1-D | `backend/app/workers/base.py` | `BaseTask` (base Celery task class with retry policy) |

---

### S2-M — Notification Worker (SendGrid)
Owned files: ```
backend/app/workers/notification/__init__.py
backend/app/workers/notification/tasks.py
backend/app/workers/notification/sendgrid_client.py
backend/app/workers/notification/templates.py
tests/integration/test_notification_worker.py
```
Imports: | Owning Session | File Path | Named Exports Required |
|---|---|---|
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` (Celery application instance) |
| S0-A | `backend/app/config.py` | `settings` (Settings object exposing `SENDGRID_API_KEY`, `ENVIRONMENT`) |
| S1-A | `backend/app/db/session.py` | `get_db_session` (sync session factory for worker use) |
| S1-A | `backend/app/db/models/user.py` | `User` (ORM model — for any required email lookup fallback) |
| S1-D | `backend/app/workers/base.py` | `BaseTask` (Celery Task base class with retry policy hooks) |
| S1-D | `backend/app/workers/queues.py` | `NOTIFICATION_QUEUE` (queue name constant — `"notification"`) |

### S3-A — Frontend: Auth Pages
Owned files: - `frontend/src/pages/auth/Register.tsx`
- `frontend/src/pages/auth/Login.tsx`
- `frontend/src/pages/auth/VerifyEmail.tsx`
- `frontend/src/pages/auth/PasswordResetRequest.tsx`
- `frontend/src/pages/auth/PasswordResetConfirm.tsx`
- `frontend/src/pages/auth/OAuthCallback.tsx`
- `frontend/src/pages/auth/AccountLinkPrompt.tsx`
Imports: | Owning Session | File | Named exports required |
|---|---|---|
| S1-F | `frontend/src/api/client.ts` | `apiClient` |
| S1-F | `frontend/src/api/endpoints.ts` | `AUTH_ENDPOINTS` |
| S1-F | `frontend/src/auth/AuthContext.tsx` | `AuthContext` |
| S1-F | `frontend/src/auth/useAuth.ts` | `useAuth` |
| S1-F | `frontend/src/auth/supabaseClient.ts` | `supabase` |
| S1-F | `frontend/src/components/Layout.tsx` | `Layout` |
| S1-F | `frontend/src/components/ProtectedRoute.tsx` | `ProtectedRoute` |
| S1-F | `frontend/src/lib/analytics.ts` | `trackEvent` (imported but not used for analytics events — only available for future use; see Critical notes) |
| S0-A | `frontend/src/types/contracts.ts` | `UserRole` |

### S3-B — Frontend: Drawing Library
Owned files: ```
frontend/src/pages/Dashboard.tsx
frontend/src/features/library/DrawingList.tsx
frontend/src/features/library/DrawingRow.tsx
frontend/src/features/library/StatusBadge.tsx
frontend/src/features/library/SearchFilter.tsx
frontend/src/features/library/Pagination.tsx
frontend/src/features/library/useDrawings.ts
```

---
Imports: | Owning Session | File | Named Exports Required |
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

### S3-C — Frontend: Upload Flow
Owned files: ```
frontend/src/pages/Upload.tsx
frontend/src/features/upload/DropZone.tsx
frontend/src/features/upload/hashClient.ts
frontend/src/features/upload/uploadOrchestrator.ts
frontend/src/features/upload/UploadProgress.tsx
```
Imports: | Owning session | File path | Named exports required |
|---|---|---|
| S1-F | `frontend/src/api/client.ts` | `apiClient` (Axios / fetch wrapper with auth headers) |
| S1-F | `frontend/src/api/endpoints.ts` | `ENDPOINTS` (URL constants for all API routes) |
| S1-F | `frontend/src/auth/AuthContext.tsx` | `AuthContext` |
| S1-F | `frontend/src/auth/useAuth.ts` | `useAuth` (returns `user`, `session`, `loading`) |
| S1-F | `frontend/src/components/Layout.tsx` | `Layout` |
| S1-F | `frontend/src/components/ProtectedRoute.tsx` | `ProtectedRoute` |
| S0-A | `frontend/src/types/contracts.ts` | `HashCheckRequest`, `HashCheckResponse`, `DrawingProcessingState` |

### S3-D — Frontend: Review Canvas (Konva)
Owned files: ```
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
Imports: | Owning session | File path | Named exports required |
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

### S3-E — Frontend: Account & Consent
Owned files: ```
frontend/src/pages/Account.tsx
frontend/src/features/account/ProfileForm.tsx
frontend/src/features/account/ConsentToggle.tsx
frontend/src/features/account/DeleteAccount.tsx
```

---
Imports: | Owning Session | File Path | Named Exports Required |
|---|---|---|
| S1-F | `frontend/src/api/client.ts` | `apiClient` |
| S1-F | `frontend/src/api/endpoints.ts` | `ACCOUNT_URL`, `ACCOUNT_CONSENT_URL` (or equivalent endpoint constants) |
| S1-F | `frontend/src/auth/useAuth.ts` | `useAuth` |
| S1-F | `frontend/src/auth/AuthContext.tsx` | `AuthContext` |
| S1-F | `frontend/src/auth/supabaseClient.ts` | `supabase` |
| S1-F | `frontend/src/components/Layout.tsx` | `Layout` |
| S1-F | `frontend/src/components/ProtectedRoute.tsx` | `ProtectedRoute` |
| S1-F | `frontend/src/types/contracts.ts` | `UserRole`, `BillingState`, `TierId` |
| S0-A | `frontend/src/router.tsx` | Read-only — do not modify; the `/account` route stub is pre-wired here |

---

### S3-F — Frontend: Subscription & Upgrade
Owned files: ```
frontend/src/pages/Subscription.tsx
frontend/src/features/subscription/TierCard.tsx
frontend/src/features/subscription/CheckoutRedirect.tsx
frontend/src/features/subscription/UpgradePrompt.tsx
frontend/src/features/subscription/PendingState.tsx
```

---
Imports: | Owning Session | File | Named Exports Required |
|---|---|---|
| S1-F | `frontend/src/api/client.ts` | `apiClient` (Axios instance or equivalent) |
| S1-F | `frontend/src/api/endpoints.ts` | `ENDPOINTS.subscription`, `ENDPOINTS.subscriptionCheckout` |
| S1-F | `frontend/src/auth/AuthContext.tsx` | `useAuth` (or re-exported from `useAuth.ts`) |
| S1-F | `frontend/src/auth/useAuth.ts` | `useAuth` |
| S1-F | `frontend/src/components/Layout.tsx` | `Layout` |
| S1-F | `frontend/src/components/GraceBanner.tsx` | `GraceBanner` |
| S1-F | `frontend/src/components/ProtectedRoute.tsx` | `ProtectedRoute` |
| S1-F | `frontend/src/lib/analytics.ts` | `trackEvent` (or equivalent wrapper) |
| S1-F | `frontend/src/lib/storage.ts` | `getSessionItem`, `setSessionItem` (sessionStorage helpers) |
| S1-F | `frontend/src/types/contracts.ts` | `TierId`, `BillingState`, `SubscriptionRecord` (if defined), `ExportFormat` |
| S0-A | `frontend/src/router.tsx` | Route definitions (read-only — do not modify) |

---

### S3-G — Frontend: Exports UI + Notifications
Owned files: ```
frontend/src/features/exports/ExportButton.tsx
frontend/src/features/exports/ExportModal.tsx
frontend/src/features/exports/useExportStatus.ts
frontend/src/features/notifications/InAppNotifications.tsx
frontend/src/features/notifications/notificationsStore.ts
```

---
Imports: | Owning Session | File | Named Exports Required |
|---|---|---|
| S1-F | `frontend/src/api/client.ts` | `apiClient` (typed fetch wrapper) |
| S1-F | `frontend/src/api/endpoints.ts` | `ENDPOINTS.exports.create(drawingId)`, `ENDPOINTS.exports.get(exportId)` |
| S1-F | `frontend/src/hooks/usePolling.ts` | `usePolling` |
| S1-F | `frontend/src/auth/useAuth.ts` | `useAuth` (for current user context) |
| S0-A | `frontend/src/types/contracts.ts` | `ExportFormat`, `ExportStatus`, `ExportRecord` |

---

### S3-H — Marketing Site (Next.js)
Owned files: ```
marketing/app/(marketing)/page.tsx       # Landing/home page (route: /)
marketing/app/pricing/page.tsx           # Pricing page (route: /pricing)
marketing/app/about/page.tsx             # About page (route: /about)
marketing/app/contact/page.tsx           # Contact page (route: /contact)
marketing/components/Hero.tsx            # Hero section component
marketing/components/PricingTable.tsx    # Tier comparison table component
marketing/components/Footer.tsx          # Site-wide footer
marketing/public/robots.txt              # SEO crawl rules
marketing/public/sitemap.xml             # SEO URL index
```

---
Imports: | Owning Session | File | Named Exports Required |
|---|---|---|
| S0-A | `marketing/app/layout.tsx` | Default layout wrapper (consumed implicitly by Next.js App Router — not imported directly, but must not conflict) |
| S0-A | `marketing/next.config.js` | Consumed by Next.js build system — not imported in code |
| S0-A | `marketing/tsconfig.json` | Consumed by TypeScript compiler — not imported in code |

No runtime imports from other sessions are required. This session is self-contained.

---

### S4-A — E2E Integration Tests
Owned files: Every file this session creates or modifies:

```
tests/integration/e2e/test_upload_to_complete.py
tests/integration/e2e/test_correction_flow.py
tests/integration/e2e/test_export_sync_and_async.py
tests/integration/e2e/test_stripe_lifecycle.py
tests/integration/e2e/test_gdpr_erasure.py
tests/integration/e2e/test_blocklist_two_gate.py
tests/integration/e2e/test_free_tier_limit.py
```

This session does NOT create a `conftest.py` — that is owned by S0-B. If shared E2E fixtures are needed that are not already in `tests/integration/conftest.py`, they must be defined as module-level fixtures inside the individual test files or as a new `tests/integration/e2e/conftest.py` (acceptable only if it contains no logic already owned by S0-B).

---
Imports: | Owning Session | File path | Specific named exports required |
|---|---|---|
| S0-B | `tests/integration/conftest.py` | `db_session`, `redis_client`, `s3_client`, `test_app`, `async_client` |
| S0-B | `tests/integration/fixtures/db.py` | `db_session`, `apply_migrations`, `seed_tiers`, `seed_entity_classes` |
| S0-B | `tests/integration/fixtures/redis.py` | `redis_client`, `pubsub_listener` |
| S0-B | `tests/integration/fixtures/s3.py` | `s3_client`, `s3_bucket` |
| S1-A | `backend/app/db/models/drawing.py` | `Drawing` (ORM model — for direct DB assertions) |
| S1-A | `backend/app/db/models/user.py` | `User` |
| S1-A | `backend/app/db/models/subscription.py` | `Subscription` |
| S1-A | `backend/app/db/models/detected_symbol.py` | `DetectedSymbol` |
| S1-A | `backend/app/db/models/user_correction.py` | `UserCorrection` |
| S1-A | `backend/app/db/models/export_record.py` | `ExportRecord` |
| S1-A | `backend/app/db/models/stripe_event.py` | `StripeEvent` |
| S1-A | `backend/app/db/models/stored_file.py` | `StoredFile` |
| S1-A | `backend/app/db/models/file_hash_blocklist.py` | `FileHashBlocklist` |
| S1-A | `backend/app/db/seed_tiers.py` | `seed_tiers` |
| S1-A | `backend/app/db/seed_entity_classes.py` | `seed_entity_classes` |
| S1-B | `backend/app/auth/jwt_verifier.py` | `create_test_token` (or equivalent test helper) |
| S1-C | `backend/app/storage/hashing.py` | `compute_sha256` |
| S1-D | `backend/app/redis/pubsub.py` | `DRAWING_STATUS_CHANNEL` |
| S1-E | `backend/app/analytics/events.py` | All typed emitter functions (for mock-capture assertions) |
| S0-A | `backend/app/schemas/contracts.py` | `MLInferenceJobPayload`, `MLInferenceResult`, `DetectedSymbolResult`, `DrawingStatusSSEEvent`, `SymbolsPageResponse`, `HashCheckResponse` |
| S2-H | `backend/app/workers/ingest/tasks.py` | `ingest_drawing` (Celery task — for direct task invocation in tests) |
| S2-I | `backend/app/workers/scan/tasks.py` | `scan_drawing` |
| S2-J | `backend/app/workers/ml/tasks.py` | `run_ml_inference` |
| S2-K | `backend/app/workers/export/tasks.py` | `generate_export` |
| S2-L | `backend/app/workers/gdpr/tasks.py` | `run_gdpr_erasure` |

---
```

---

### build-plan-dry-run [primary]

**System Prompt:**
```
You are generating a dry-run verification procedure for an autonomous build plan. This procedure must pass before any Phase 1 session begins.

You receive extracted export/import tables from Phase 0 and Phase 1 briefs — not full briefs. Use these to produce a compact verification procedure.

## Step 1 — Run Phase 0

Run the Phase 0 scaffold session in isolation with only its brief. Capture its complete output. Extract an export manifest: one row per named export across all output files.

## Step 2 — Consolidated import table

Produce a single table of every import that any Phase 1 session expects from Phase 0:

| Session | File Path | Export Name | Expected Type/Shape |
|---------|-----------|-------------|---------------------|

Derive this from the import tables provided. Do not repeat the full brief content — one row per import.

## Step 3 — Mismatch report (failures only)

Cross-reference the Phase 0 output table against Step 2. Report **only mismatches and missing items** — do not list successful matches. For each issue, include the fix inline:

| Session | File | Expected Export | Issue | Fix (which brief section to update) |
|---------|------|-----------------|-------|--------------------------------------|

If zero mismatches: state "All imports verified — dry run PASS" and stop.

## Step 4 — Ambiguous items

List any imports whose shape cannot be verified from the brief text alone (e.g., the brief says "import X" but doesn't specify the type). These require Step 1 output inspection:

| # | Session | File | What to verify |
|---|---------|------|----------------|

**The dry run must achieve a full match before any Phase 1 session begins.** This is the lowest-cost moment to catch contract mismatches.
```

**User Message:**
```
## Phase 0 and Phase 1 — Export/Import Extracts

### S0-A — Scaffold & Shared Stubs (Phase 0)
**Owned files:**
(exactly as listed in the prompt — exhaustive, do not touch anything else)

**Output/exports:**
N/A

**Read-only imports:**
None — this is the root session.

---

### S0-B — Integration Harness & Manifests (Phase 0)
**Owned files:**
- `package.json` (root workspace; defines `test:integration` script)
- `backend/pyproject.toml`
- `backend/poetry.lock`
- `frontend/package.json`
- `marketing/package.json`
- `tests/integration/conftest.py`
- `tests/integration/docker-compose.fixtures.yml`
- `tests/integration/fixtures/db.py`
- `tests/integration/fixtures/redis.py`
- `tests/integration/fixtures/s3.py`
- `tests/integration/smoke/test_smoke.py`
- `tests/integration/README.md`
- `scripts/test-integration.sh`
- `.github/workflows/integration.yml`

**Output/exports:**
N/A

**Read-only imports:**
None. This session runs before any source code exists (S0-A is a sibling that owns app scaffolding; this session must NOT import from `backend/app/*` or `frontend/src/*` because S0-B and S0-A may merge in either order).

The smoke test verifies infrastructure only (DB reachable, Redis reachable, MinIO reachable) — it does NOT import application code.

---

### S1-A — DB Models & Migrations (Phase 1)
**Owned files:**
- `backend/app/db/models/__init__.py`
- `backend/app/db/models/user.py`
- `backend/app/db/models/team.py`
- `backend/app/db/models/tier.py`
- `backend/app/db/models/subscription.py`
- `backend/app/db/models/stored_file.py`
- `backend/app/db/models/file_hash_blocklist.py`
- `backend/app/db/models/drawing.py`
- `backend/app/db/models/entity_class.py`
- `backend/app/db/models/detected_symbol.py`
- `backend/app/db/models/table_cell.py`
- `backend/app/db/models/user_correction.py`
- `backend/app/db/models/export_record.py`
- `backend/app/db/models/ml_training_consent.py`
- `backend/app/db/models/revision_comparison.py`
- `backend/app/db/models/audit_log.py`
- `backend/app/db/models/stripe_event.py`
- `backend/alembic/versions/0001_initial_schema.py`
- `backend/alembic/versions/0002_rls_policies.py`
- `backend/alembic/versions/0003_audit_partitions.py`
- `backend/app/db/seed_tiers.py`
- `backend/app/db/seed_entity_classes.py`

**Output/exports:**
N/A

**Read-only imports:**
From **S0-A**:
- `backend/app/db/base.py` — `Base` (SQLAlchemy declarative base)
- `backend/app/db/session.py` — `engine`, `SessionLocal`, `get_db`
- `backend/app/config.py` — `settings` (for `DATABASE_URL`, `ENVIRONMENT`)
- `backend/alembic/env.py` — already wired to import `Base.metadata`; new migrations are autogenerated against the metadata this session populates.
- `backend/app/schemas/contracts.py` — `EntityClassId` literal (for seed validation), `DrawingProcessingState`, `BillingState`, `TierId`, `UserRole`, `SymbolSource`, `CorrectionType`, `ExportFormat`, `ExportStatus`.

From **S0-B**:
- `tests/integration/conftest.py` — `db_session`, `clean_db` fixtures
- `tests/integration/fixtures/db.py` — `migrate_to_head()`, `drop_all()` helpers

---

### S1-B — Auth Middleware & Supabase Client (Phase 1)
**Owned files:**
- `backend/app/auth/__init__.py`
- `backend/app/auth/supabase_client.py`
- `backend/app/auth/jwt_verifier.py`
- `backend/app/auth/middleware.py`
- `backend/app/auth/dependencies.py`
- `backend/app/auth/permissions.py`
- `backend/app/auth/brute_force.py`
- `tests/integration/test_auth_middleware.py`

**Output/exports:**
N/A

**Read-only imports:**
- From **S0-A**:
  - `backend/app/config.py` — settings object exposing `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `JWT_RS256_PUBLIC_KEY`, `REDIS_URL`, `ENVIRONMENT`.
  - `backend/app/schemas/contracts.py` — `UserRole` type alias matching `'user' | 'team_member' | 'team_admin'`.
  - `backend/app/db/session.py` — async session factory `get_db()` (for `token_invalidated_at` lookup).
- From **S0-B**:
  - `tests/integration/conftest.py` — pytest fixtures (`db`, `redis`, `app_client`).
  - `tests/integration/fixtures/redis.py` — `redis_client` fixture.

---

### S1-C — Storage & Hash Utilities (Phase 1)
**Owned files:**
- `backend/app/storage/__init__.py`
- `backend/app/storage/s3_client.py`
- `backend/app/storage/presigned.py`
- `backend/app/storage/hashing.py`
- `backend/app/storage/blocklist.py`
- `tests/integration/test_storage.py`

**Output/exports:**
N/A

**Read-only imports:**
- **From S0-A**:
  - `backend/app/config.py` — settings object exposing `S3_BUCKET_NAME`, `S3_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `PRESIGNED_URL_EXPIRY_SECONDS`, `MAX_UPLOAD_SIZE_BYTES`.
  - `backend/app/db/session.py` — DB session factory (for blocklist queries).
  - `backend/app/schemas/contracts.py` — `HashCheckRequest`, `HashCheckResponse` pydantic models.
- **From S0-B**:
  - `tests/integration/conftest.py` — pytest fixtures.
  - `tests/integration/fixtures/db.py` — DB fixture.
  - `tests/integration/fixtures/s3.py` — moto/localstack-backed S3 fixture.

---

### S1-D — Redis, Cache, Pub/Sub & Celery Config (Phase 1)
**Owned files:**
- `backend/app/redis/__init__.py`
- `backend/app/redis/client.py`
- `backend/app/redis/cache.py`
- `backend/app/redis/pubsub.py`
- `backend/app/workers/queues.py`
- `backend/app/workers/base.py`
- `tests/integration/test_redis_pubsub.py`

**Output/exports:**
N/A

**Read-only imports:**
- From **S0-A** `backend/app/config.py`: settings object exposing `REDIS_URL`, `CELERY_BROKER_URL`, `ENVIRONMENT`.
- From **S0-A** `backend/app/workers/celery_app.py`: the `celery_app` instance (this session configures its queue routing and task base class but does not redefine the app).
- From **S0-A** `backend/app/schemas/contracts.py`: `DrawingStatusSSEEvent`, `DrawingProcessingState`, `TierId`, `BillingState`.
- From **S0-B** `tests/integration/conftest.py`: redis fixture (`redis_client`), event loop fixture.
- From **S0-B** `tests/integration/fixtures/redis.py`: ephemeral Redis container fixture.

---

### S1-E — Analytics Emitter (PostHog) (Phase 1)
**Owned files:**
- `backend/app/analytics/__init__.py`
- `backend/app/analytics/posthog_client.py`
- `backend/app/analytics/events.py`
- `backend/app/analytics/dead_letter.py`
- `tests/integration/test_analytics.py`

**Output/exports:**
N/A

**Read-only imports:**
- From **S0-A**: `backend/app/config.py` — env var accessors (`POSTHOG_API_KEY`, `POSTHOG_HOST`, `ENVIRONMENT`); `backend/app/schemas/contracts.py` — types `TierId`, `ExportFormat` (for typed event signatures).
- From **S0-B**: `tests/integration/conftest.py` — pytest fixtures (db, redis container handles) for the test file.

Note: S1-D (Redis client) is **not** a prerequisite per the session plan. This session must therefore use the raw `REDIS_URL` env var directly via `redis-py` for its dead-letter queue, and not import from `backend/app/redis/*` (which is owned by S1-D and may not exist when this session runs in isolation). If S1-D has merged, callers may later inject its client, but this session's code must function standalone.

---

### S1-F — Frontend Shared Infrastructure (Phase 1)
**Owned files:**
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

**Output/exports:**
N/A

**Read-only imports:**
- From **S0-A**:
  - `frontend/src/types/contracts.ts` — all TS types defined in §1.1 (`DrawingProcessingState`, `DrawingStatusSSEEvent`, `HashCheckRequest`, `HashCheckResponse`, `SymbolsPageResponse`, `BillingState`, `TierId`, `UserRole`, `SymbolSource`, `CorrectionType`, `ExportFormat`, `ExportStatus`, `EntityClassId`, `SymbolRecord`, `CorrectionRecord`, `BoundingBox`, etc.)
  - `frontend/src/router.tsx` — only for understanding route names; do not modify.
```

---

## Token Usage

| Agent | # | Input | Output | Cache Read | Cache Write | Cost |
|-------|--:|------:|-------:|-----------:|------------:|------|
| build-plan-distilled-spec [primary] | 1 | 22 | 11,860 | 0 | 60,614 | $0.5416 |
| build-plan-session-table [primary] | 1 | 48 | 16,836 | 0 | 19,445 | $0.6156 |
| build-plan-build-order [primary] | 1 | 10,963 | 13,467 | 0 | 0 | $0.2349 |
| build-plan-mermaid-diagram [primary] | 1 | 11,200 | 7,872 | 0 | 0 | $0.1517 |
| build-plan-ownership-table [primary] | 1 | 10,956 | 25,966 | 0 | 0 | $0.4224 |
| build-plan-build-summary [primary] | 1 | 10,973 | 5,403 | 0 | 0 | $0.1140 |
| build-plan-out-of-band [primary] | 1 | 12,050 | 7,872 | 0 | 0 | $0.1542 |
| build-plan-gate-checklists [primary] | 1 | 10,990 | 12,534 | 0 | 0 | $0.2210 |
| build-plan-brief-S0-A [primary] | 1 | 564 | 8,419 | 0 | 35,974 | $0.5730 |
| build-plan-brief-S0-B [primary] | 1 | 291 | 6,186 | 0 | 35,974 | $0.5158 |
| build-plan-brief-S1-A [primary] | 1 | 501 | 16,768 | 0 | 35,974 | $0.7814 |
| build-plan-brief-S1-B [primary] | 1 | 246 | 8,235 | 0 | 35,974 | $0.5668 |
| build-plan-brief-S1-C [primary] | 1 | 201 | 7,429 | 35,974 | 0 | $0.2047 |
| build-plan-brief-S1-D [primary] | 1 | 226 | 8,505 | 35,974 | 0 | $0.2317 |
| build-plan-brief-S1-E [primary] | 1 | 194 | 7,444 | 35,974 | 0 | $0.2051 |
| build-plan-brief-S1-F [primary] | 1 | 361 | 8,288 | 35,974 | 0 | $0.2270 |
| build-plan-brief-S2-A [primary] | 1 | 135 | 19,748 | 0 | 24,949 | $0.4463 |
| build-plan-brief-S2-B [primary] | 1 | 218 | 23,349 | 24,949 | 0 | $0.3584 |
| build-plan-brief-S2-C [primary] | 1 | 137 | 22,905 | 24,949 | 0 | $0.3515 |
| build-plan-brief-S2-D [primary] | 1 | 142 | 15,603 | 24,949 | 0 | $0.2420 |
| build-plan-brief-S2-E [primary] | 1 | 197 | 29,117 | 24,949 | 0 | $0.4448 |
| build-plan-brief-S2-F [primary] | 1 | 155 | 32,247 | 24,949 | 0 | $0.4917 |
| build-plan-brief-S2-G [primary] | 1 | 118 | 8,971 | 24,949 | 0 | $0.1424 |
| build-plan-brief-S2-H [primary] | 1 | 176 | 27,765 | 24,949 | 0 | $0.4245 |
| build-plan-brief-S2-I [primary] | 1 | 145 | 25,784 | 24,949 | 0 | $0.3947 |
| build-plan-brief-S2-J [primary] | 1 | 164 | 13,842 | 24,949 | 0 | $0.2156 |
| build-plan-brief-S2-K [primary] | 1 | 125 | 17,192 | 24,949 | 0 | $0.2657 |
| build-plan-brief-S2-L [primary] | 1 | 139 | 13,291 | 24,949 | 0 | $0.2073 |
| build-plan-brief-S2-M [primary] | 1 | 146 | 14,763 | 24,949 | 0 | $0.2294 |
| build-plan-brief-S3-A [primary] | 1 | 180 | 31,037 | 24,949 | 0 | $0.4736 |
| build-plan-brief-S3-B [primary] | 1 | 170 | 19,591 | 24,949 | 0 | $0.3019 |
| build-plan-brief-S3-C [primary] | 1 | 144 | 15,888 | 24,949 | 0 | $0.2462 |
| build-plan-brief-S3-D [primary] | 1 | 216 | 23,219 | 24,949 | 0 | $0.3564 |
| build-plan-brief-S3-E [primary] | 1 | 127 | 17,521 | 24,949 | 0 | $0.2707 |
| build-plan-brief-S3-F [primary] | 1 | 150 | 15,113 | 24,949 | 0 | $0.2346 |
| build-plan-brief-S3-G [primary] | 1 | 152 | 18,224 | 24,949 | 0 | $0.2813 |
| build-plan-brief-S3-H [primary] | 1 | 161 | 10,773 | 24,949 | 0 | $0.1696 |
| build-plan-brief-S4-A [primary] | 1 | 297 | 26,947 | 24,949 | 0 | $0.4126 |
| build-plan-consistency-check [primary] | 1 | 25,075 | 8,916 | 0 | 0 | $0.2090 |
| build-plan-dry-run [primary] | 1 | 3,275 | 8,446 | 0 | 0 | $0.1365 |
| **TOTAL** | **40** | **101,730** | **633,336** | **667,825** | **248,904** | **$13.0675** |

---

## Warnings

*(none)*

---

## Errors

*(none)*

---

## Next Steps

*(not captured)*

---

## Debug: API Call Details

### build-plan-distilled-spec [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 3m 30s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 22 (— used)
- Output — budget: — | actual: 11,860 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: No (60,614 tokens written to cache)

---

### build-plan-session-table [primary]

**Request Parameters:**
- model: claude-opus-4-7
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-opus-4-7
- duration: 2m 41s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 48 (— used)
- Output — budget: — | actual: 16,836 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: No (19,445 tokens written to cache)

---

### build-plan-build-order [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 16000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 3m 26s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 10,963 (— used)
- Output — budget: — | actual: 13,467 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: No (0 tokens written to cache)

---

### build-plan-mermaid-diagram [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 32000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 1m 38s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 11,200 (— used)
- Output — budget: — | actual: 7,872 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: No (0 tokens written to cache)

---

### build-plan-ownership-table [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 32000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 5m 34s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 10,956 (— used)
- Output — budget: — | actual: 25,966 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: No (0 tokens written to cache)

---

### build-plan-build-summary [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 24000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 1m 24s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 10,973 (— used)
- Output — budget: — | actual: 5,403 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: No (0 tokens written to cache)

---

### build-plan-out-of-band [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 24000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 2m 37s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 12,050 (— used)
- Output — budget: — | actual: 7,872 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: No (0 tokens written to cache)

---

### build-plan-gate-checklists [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 16000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 3m 0s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 10,990 (— used)
- Output — budget: — | actual: 12,534 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: No (0 tokens written to cache)

---

### build-plan-brief-S0-A [primary]

**Request Parameters:**
- model: claude-opus-4-7
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-opus-4-7
- duration: 1m 48s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 564 (— used)
- Output — budget: — | actual: 8,419 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: No (35,974 tokens written to cache)

---

### build-plan-brief-S0-B [primary]

**Request Parameters:**
- model: claude-opus-4-7
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-opus-4-7
- duration: 1m 19s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 291 (— used)
- Output — budget: — | actual: 6,186 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: No (35,974 tokens written to cache)

---

### build-plan-brief-S1-A [primary]

**Request Parameters:**
- model: claude-opus-4-7
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-opus-4-7
- duration: 2m 60s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 501 (— used)
- Output — budget: — | actual: 16,768 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: No (35,974 tokens written to cache)

---

### build-plan-brief-S1-B [primary]

**Request Parameters:**
- model: claude-opus-4-7
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-opus-4-7
- duration: 1m 43s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 246 (— used)
- Output — budget: — | actual: 8,235 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: No (35,974 tokens written to cache)

---

### build-plan-brief-S1-C [primary]

**Request Parameters:**
- model: claude-opus-4-7
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-opus-4-7
- duration: 1m 28s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 201 (— used)
- Output — budget: — | actual: 7,429 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (35,974 read, 0 written)

---

### build-plan-brief-S1-D [primary]

**Request Parameters:**
- model: claude-opus-4-7
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-opus-4-7
- duration: 1m 39s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 226 (— used)
- Output — budget: — | actual: 8,505 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (35,974 read, 0 written)

---

### build-plan-brief-S1-E [primary]

**Request Parameters:**
- model: claude-opus-4-7
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-opus-4-7
- duration: 1m 29s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 194 (— used)
- Output — budget: — | actual: 7,444 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (35,974 read, 0 written)

---

### build-plan-brief-S1-F [primary]

**Request Parameters:**
- model: claude-opus-4-7
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-opus-4-7
- duration: 1m 41s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 361 (— used)
- Output — budget: — | actual: 8,288 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (35,974 read, 0 written)

---

### build-plan-brief-S2-A [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 5m 23s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 135 (— used)
- Output — budget: — | actual: 19,748 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: No (24,949 tokens written to cache)

---

### build-plan-brief-S2-B [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 6m 31s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 218 (— used)
- Output — budget: — | actual: 23,349 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S2-C [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 6m 3s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 137 (— used)
- Output — budget: — | actual: 22,905 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S2-D [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 4m 10s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 142 (— used)
- Output — budget: — | actual: 15,603 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S2-E [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 8m 5s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 197 (— used)
- Output — budget: — | actual: 29,117 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S2-F [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 8m 56s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 155 (— used)
- Output — budget: — | actual: 32,247 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S2-G [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 2m 47s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 118 (— used)
- Output — budget: — | actual: 8,971 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S2-H [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 7m 58s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 176 (— used)
- Output — budget: — | actual: 27,765 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S2-I [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 7m 16s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 145 (— used)
- Output — budget: — | actual: 25,784 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S2-J [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 3m 59s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 164 (— used)
- Output — budget: — | actual: 13,842 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S2-K [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 4m 54s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 125 (— used)
- Output — budget: — | actual: 17,192 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S2-L [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 3m 49s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 139 (— used)
- Output — budget: — | actual: 13,291 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S2-M [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 3m 59s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 146 (— used)
- Output — budget: — | actual: 14,763 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S3-A [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 8m 22s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 180 (— used)
- Output — budget: — | actual: 31,037 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S3-B [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 5m 21s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 170 (— used)
- Output — budget: — | actual: 19,591 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S3-C [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 4m 36s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 144 (— used)
- Output — budget: — | actual: 15,888 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S3-D [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 6m 36s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 216 (— used)
- Output — budget: — | actual: 23,219 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S3-E [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 4m 45s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 127 (— used)
- Output — budget: — | actual: 17,521 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S3-F [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 4m 17s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 150 (— used)
- Output — budget: — | actual: 15,113 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S3-G [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 5m 13s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 152 (— used)
- Output — budget: — | actual: 18,224 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S3-H [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 3m 8s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 161 (— used)
- Output — budget: — | actual: 10,773 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-brief-S4-A [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 64000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 7m 41s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 297 (— used)
- Output — budget: — | actual: 26,947 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: Yes (24,949 read, 0 written)

---

### build-plan-consistency-check [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 16000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 2m 39s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 25,075 (— used)
- Output — budget: — | actual: 8,916 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: No (0 tokens written to cache)

---

### build-plan-dry-run [primary]

**Request Parameters:**
- model: claude-sonnet-4-6
- max_tokens: 32000
- thinking: adaptive

**Response Metadata:**
- stop_reason: end_turn
- model (returned by API): claude-sonnet-4-6
- duration: 1m 51s

**Token Budget vs Actual:**
- Input  — budget: — | actual: 3,275 (— used)
- Output — budget: — | actual: 8,446 (— used)
- Budget exceeded: No

**Cache:**
- Cache hit: No (0 tokens written to cache)

---

## Debug: User Stories Sub-call Timing

*(user stories not run)*

---

## Debug: Memory / Learnings

*(no learnings recorded)*