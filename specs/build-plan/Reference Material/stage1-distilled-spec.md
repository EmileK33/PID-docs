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