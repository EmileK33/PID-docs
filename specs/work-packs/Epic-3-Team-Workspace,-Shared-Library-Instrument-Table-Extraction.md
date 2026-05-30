# Epic 3: Team Workspace, Shared Library & Instrument Table Extraction — Implementation Context

> **Stories**: US-021 through US-025
> **Token budget**: ~11K tokens (leave ~160K for codebase + conversation)
> **Shared context**: Load `shared-context.md` from this directory for tech stack, database schema, API patterns, and cross-cutting requirements.

## Instructions for Claude Code

You are building this epic under human supervision. The human approves plans and resolves ambiguities — you write all the code.

1. **Load shared context** — Load `shared-context.md` from this directory for tech stack, database schema, API patterns, and cross-cutting requirements.
2. **Confirm the story** — Check the CURRENT STORY marker below. Ask: "The active story is [US-XXX: Title] — correct, or switch?" Wait for confirmation.
3. **Plan first** — Read acceptance criteria + related architecture/UX sections. Present 2-3 implementation approaches with trade-offs. Write a detailed plan (files, functions, data flow, how each AC is satisfied). Flag any spec ambiguities for the human to resolve.
4. **Wait for approval** — Do not write code until the human says "go", "approved", or "proceed".
5. **Implement** — Write production-quality code satisfying every Given/When/Then scenario in the acceptance criteria. Run tests after each story.
6. **Stay in scope** — Implement ONLY the current story. Other stories in this file are context only — do not implement them.

## CURRENT STORY: US-021
> Change this marker when switching to a different story.

---

# Stories in This Epic

## US-021: Detect and extract instrument table regions from P&ID drawings (Large) ← ACTIVE

#### US-021: Detect and extract instrument table regions from P&ID drawings
**Epic**: Team Workspace, Shared Library & Instrument Table Extraction
**Priority**: Should-have
**Complexity**: Large

**User Story**:
As a Process Safety Engineer (David),
I want the system to automatically detect and extract structured instrument/valve data tables embedded in a P&ID drawing during ML processing,
So that I receive a complete structured dataset — both symbol detections and tabular instrument indexes — without performing any manual table transcription.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Table detected and extracted)**:
  - Given a drawing has completed malware scanning and ML processing has begun
  - When the drawing contains one or more rectangular vector table regions (e.g., instrument index, line list, valve list)
  - Then the system identifies those regions as data tables distinct from symbol detections, extracts cell text content mapped to rows and columns, and makes the structured table data available alongside symbol results when processing completes

- **Scenario 2 (Happy Path — Table data included in export)**:
  - Given a drawing with extracted table data is in `Complete` or `Under_Review` state
  - When David initiates an export in CSV or XLSX format
  - Then the exported file includes a separate worksheet or clearly labeled section containing the extracted table rows and columns, with a page/sheet identifier for multi-page PDFs

- **Scenario 3 (Accuracy threshold met)**:
  - Given the ML model is evaluated against the internal test dataset containing drawings with known instrument tables
  - When cell-level extraction results are compared to ground-truth labels
  - Then the system achieves ≥ 75% cell-level accuracy on tabular data extraction across the test dataset

- **Scenario 4 (No tables present)**:
  - Given a drawing that contains only symbol geometry with no rectangular table regions
  - When ML processing completes
  - Then no table section is included in the results and no error or warning is surfaced to the user regarding table extraction

- **Scenario 5 (Drawing contains raster-embedded table)**:
  - Given a drawing where a table region is rendered as a raster image rather than vector geometry
  - When ML processing completes
  - Then the raster table is not extracted, and the system does not include it in the structured output; no processing failure is triggered

**Technical Notes**:
- Table detection runs as part of the same ML inference pass as symbol detection; the inference service request/response schema must accommodate both `symbols` and `tables` arrays in the response payload — Architecture Agent to extend the interface defined in Section 8.
- Table region classification must produce bounding box coordinates at the table level and at the individual cell level to support in-canvas editing in US-022.
- This story depends on the ML inference service (Section 8 integration); the 20-minute processing timeout and 1 automatic retry policy apply equally to jobs containing table extraction.

**Related Requirements**: FR-7

**Dependencies**: None (ML inference pipeline established in P0 epic covering FR-2)

---

## US-022: Review and edit extracted instrument table cell values before export (Medium)

#### US-022: Review and edit extracted instrument table cell values before export
**Epic**: Team Workspace, Shared Library & Instrument Table Extraction
**Priority**: Should-have
**Complexity**: Medium

**User Story**:
As a Process Safety Engineer (David),
I want to review extracted instrument table cell values on the drawing canvas and correct any misread text before exporting,
So that the exported instrument index accurately reflects the drawing content and I can trust it as input for HAZOP preparation without manually cross-checking every cell.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Cell value edited and saved)**:
  - Given a drawing is in `Complete` or `Under_Review` state and contains at least one extracted instrument table
  - When David clicks a table cell on the drawing canvas and modifies its text value
  - Then the updated value is saved in real time, persists across browser sessions, and is reflected in the next export of that drawing

- **Scenario 2 (Happy Path — Edited table cell exported correctly)**:
  - Given David has edited one or more table cell values and initiates a CSV or XLSX export
  - When the export file is generated
  - Then the exported table section contains David's corrected cell values, not the original ML-extracted values

- **Scenario 3 (Table region visible and distinct on canvas)**:
  - Given a drawing with detected table regions is opened in the review canvas
  - When the canvas renders
  - Then table regions are visually distinguished from symbol bounding boxes, and individual cells are selectable by clicking within the table boundary

- **Scenario 4 (No table detected — edit UI not shown)**:
  - Given a drawing that completed processing with no detected table regions
  - When David opens the review canvas
  - Then no table editing panel or table cell overlay is displayed, and the canvas shows only symbol detections

- **Scenario 5 (Concurrent symbol and table corrections preserved)**:
  - Given David has made both symbol corrections (via FR-3) and table cell edits on the same drawing
  - When David closes and re-opens the review canvas
  - Then both symbol corrections and table cell edits are fully preserved without either overwriting the other

**Technical Notes**:
- Cell-level bounding boxes produced by US-021 are the prerequisite for click-target hit detection in the canvas; this story has a hard dependency on US-021's cell-level coordinate output.
- Table cell edit state should be stored using the same real-time persistence mechanism used for UserCorrections in FR-3 to avoid introducing a second persistence path — Architecture Agent to confirm data model extension.
- ML training consent rules from FR-13 apply to table cell corrections in the same way they apply to symbol corrections; the `training_consent` flag must be captured at correction-record creation time.

**Related Requirements**: FR-7

**Dependencies**: US-021

---

## US-023: Invite team members and manage seat-limited team workspace (Medium)

#### US-023: Invite team members and manage seat-limited team workspace
**Epic**: Team Workspace, Shared Library & Instrument Table Extraction
**Priority**: Should-have
**Complexity**: Medium

**User Story**:
As a CAD/Document Control Manager (Marcus),
I want to invite engineers to a shared team workspace by email and enforce the licensed seat count,
So that all project engineers access drawings from one centralized library without exceeding the subscription we have paid for.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Invitation sent within seat limit)**:
  - Given Marcus is a Team Admin and the team has at least one available licensed seat
  - When Marcus submits a valid email address to invite a new member
  - Then the system sends the invitee an email containing an accept link valid for 72 hours and records a pending invitation against the seat count

- **Scenario 2 (Seat limit reached — invitation blocked)**:
  - Given the team has consumed all licensed seats (including pending invitations)
  - When Marcus attempts to invite an additional member
  - Then the system blocks the invitation, displays a seat-limit error with an upgrade call-to-action, and does not send an invitation email

- **Scenario 3 (Invitee accepts within 72 hours)**:
  - Given a pending invitation email has been sent and the accept link has not expired
  - When the invitee clicks the accept link and completes account registration or login
  - Then the invitee is added to the team as a Member, gains access to the shared library, and the seat is marked as occupied

- **Scenario 4 (Accept link expired)**:
  - Given an invitation accept link that was issued more than 72 hours ago
  - When the invitee attempts to use the link
  - Then the page displays an expiry message, the invitation is invalidated, and the reserved seat is released back to the available count

- **Scenario 5 (Member removed — seat released)**:
  - Given Marcus removes an existing team member from the workspace
  - When the removal is confirmed
  - Then the member loses immediate access to the shared library, their drawings are reassigned to the Team Admin, the occupied seat is released, and the team's available seat count increases by one

- **Scenario 6 (Team-level ML training consent set by Admin)**:
  - Given Marcus is a Team Admin viewing team settings
  - When Marcus sets the team-level ML training data contribution preference
  - Then the preference is applied to all current team members immediately and individual members cannot override it from their own account settings

**Technical Notes**:
- Invitation emails are delivered via the SendGrid integration (Section 8); the accept link must encode a signed token to prevent enumeration of pending invitations.
- Pending invitations should count against the seat limit to prevent over-invitation races; the seat reservation is released on expiry (Scenario 4) and on removal (Scenario 5).
- FR-13 AC-3 requires team-level consent to override individual member settings; the consent preference set here propagates to all UserCorrection records created after the change — Architecture Agent to confirm propagation mechanism.

**Related Requirements**: FR-10, FR-13

**Dependencies**: None (FR-5 authentication epic covers account creation)

---

## US-024: Access, upload, and manage drawings in shared team library with role-based permissions (Medium)

#### US-024: Access, upload, and manage drawings in shared team library with role-based permissions
**Epic**: Team Workspace, Shared Library & Instrument Table Extraction
**Priority**: Should-have
**Complexity**: Medium

**User Story**:
As a CAD/Document Control Manager (Marcus),
I want all team members to view and work with drawings in a single shared library while restricting destructive actions to Admins only,
So that engineers have full access to the latest drawing data and I retain control over what is permanently removed from the team's record.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Member views and opens shared drawing)**:
  - Given a team Member is logged in and drawings have been uploaded to the shared team library
  - When the Member navigates to the Drawing Library
  - Then all drawings in the shared library are visible with filename, upload date, processing status, revision label, and the name of the team member who uploaded each drawing

- **Scenario 2 (Happy Path — Any member uploads a drawing to shared library)**:
  - Given a team Member or Admin is logged in
  - When they upload a PDF or DWG file
  - Then the drawing is added to the shared team library, is immediately visible to all team members, and the uploader's name is attributed to the drawing record

- **Scenario 3 (Member attempts to delete a drawing — blocked)**:
  - Given a team Member (non-Admin) is viewing the shared library
  - When the Member attempts to delete a drawing
  - Then the delete action is unavailable (control is not presented or is disabled with a permissions indicator) and no deletion occurs

- **Scenario 4 (Admin deletes a drawing from shared library)**:
  - Given Marcus is a Team Admin and selects a drawing for deletion
  - When Marcus confirms the deletion prompt
  - Then the drawing and all its associated extraction data are permanently removed from the shared library and are no longer accessible to any team member

- **Scenario 5 (Removed member's drawings reassigned)**:
  - Given a team member who uploaded drawings is removed from the team (via US-023)
  - When Marcus views the shared library after the removal
  - Then drawings previously attributed to the removed member remain in the shared library under Team Admin ownership, and the removed member's name is replaced with the Team Admin's name in the attribution field

**Technical Notes**:
- Role enforcement (Admin vs. Member) must be validated server-side on every delete request; client-side hiding of the delete control is a UX convenience only and is not the security boundary.
- Drawing ownership reassignment on member removal (Scenario 5) should be an atomic operation triggered by the same event that removes the member from the team — Architecture Agent to define the transaction boundary.
- The shared library drawing list should apply the same search, filter, and pagination behavior defined in FR-6 (filename, revision label, processing status, upload date range).

**Related Requirements**: FR-10, FR-6

**Dependencies**: US-023

---

## US-025: Compare Two Drawing Revisions and Export Symbol Change Summary (Large)

#### US-025: Compare Two Drawing Revisions and Export Symbol Change Summary
**Epic**: Team Workspace, Shared Library & Instrument Table Extraction
**Priority**: Should-have
**Complexity**: Large

**User Story**:
As a CAD/Document Control Manager (Marcus),
I want to select two processed revisions of the same drawing and see which symbols were added or removed between them,
So that I can produce a verified change summary for the engineering record without manually comparing two drawing sheets side by side.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Comparison Initiated on Two Complete Drawings)**:
  - Given Marcus selects two drawings from the library that have both reached `Complete` processing state
  - When Marcus initiates a revision comparison
  - Then the system matches symbols between the two revisions using spatial proximity (bounding box centroid within 2% of drawing canvas dimensions) as the primary heuristic, falling back to tag label match for symbols without spatial overlap, and produces a comparison result

- **Scenario 2 (Happy Path — Changes Highlighted on Canvas and Summarised)**:
  - Given a comparison result has been generated
  - When Marcus views the comparison
  - Then added symbols are highlighted with a distinct color, removed symbols are highlighted with a different distinct color, and a summary panel lists each changed symbol with its entity class, tag, and change type (Added / Removed)

- **Scenario 3 (Change Summary Exported as CSV)**:
  - Given Marcus is viewing a completed revision comparison
  - When Marcus initiates a CSV export of the comparison summary
  - Then the downloaded file contains one row per changed symbol with columns for entity class, subtype, tag, and change type (Added / Removed), and includes the drawing filename and revision labels for both compared versions

- **Scenario 4 (Comparison Blocked — One or Both Drawings Not Complete)**:
  - Given Marcus attempts to compare two drawings where at least one has a processing status other than `Complete`
  - When the comparison is initiated
  - Then the system displays an error message stating that both drawings must have completed processing before comparison is available, and no comparison job is started

- **Scenario 5 (No Differences Detected)**:
  - Given two drawings are compared and the symbol sets are spatially and tag-matched with no unmatched symbols on either side
  - When the comparison completes
  - Then the summary panel displays a message indicating no symbol differences were detected, the canvas shows no highlighted changes, and a CSV export remains available containing zero data rows (with headers only)

- **Scenario 6 (Free Tier Access Attempt — Upgrade CTA Displayed)**:
  - Given a Free tier user navigates to the revision comparison feature from the drawing library
  - When the comparison entry point is reached
  - Then the system does not initiate a comparison job, the page displays an upgrade call-to-action indicating that revision comparison is available on Pro and Team tiers, and the user is presented with a path to upgrade consistent with the pattern established in US-018 Scenario 5

**Technical Notes**:
- Spatial proximity matching (centroid within 2% of canvas dimensions) and tag label fallback are the mandated heuristics per FR-8 AC-2; the comparison algorithm must apply these consistently and the matching strategy should be documented for the Architecture Agent to implement.
- Comparison is available for any two drawings in the library regardless of whether they share a revision label; it is Marcus's responsibility to select the correct pair — the system does not enforce drawing identity matching.
- Comparison results should be stored as a derived entity (not recomputed on each canvas open) to avoid re-running the matching algorithm on repeat views; Architecture Agent to define the storage model.
- The comparison feature is gated to Pro and Team tier per FR-9 AC-3; tier enforcement must be applied server-side so that Free tier users cannot initiate a comparison job by bypassing the UI.

**Related Requirements**: FR-8, FR-9

**Dependencies**: US-023, US-024
---

## Requirements Needing Clarification

1. **FR-2 AC-3 — external dataset threshold**
   - **Issue**: Requires a held-out external customer dataset of ≥ 20 drawings from ≥ 3 companies before FR-2 is considered complete; this is a pre-launch ML validation gate, not a user-facing story. Cannot be assigned a testable story ID — must be tracked as a separate engineering acceptance criterion outside the story backlog.

2. **NFR-6 — malware scanning vendor selection**
   - **Issue**: PRD defers vendor choice (ClamAV, Trend Micro) to the Architecture Agent; the scanning SLA (60 seconds) and state transition (Scanning → Scan_Failed) are testable, but the specific integration cannot produce a fully specified story until a vendor is selected. Scanning behaviour is covered in US-008 at the state-machine level pending vendor confirmation.

---

## Summary

**Total Stories**: 25
**Breakdown by Priority**:
- Must-have: 20
- Should-have: 5
- Could-have: 0

---

# PRD — Functional Requirements

**FR-6: Drawing Library Management**
- **Description**: Users view, organize, and delete all drawings they have uploaded, including processing status and export history per drawing. Addresses the "Version Confusion Problem" by providing a persistent record of processed drawings.
- **Priority**: P0
- **Category**: Drawing Management
- **Acceptance Criteria**:
  1. Drawing library displays all uploaded drawings with filename, upload date, processing status (Queued / Scanning / Processing / Complete / Failed), and revision tag
  2. User can open any completed drawing to return to the interactive review canvas
  3. User can delete a drawing and its associated extraction data; deletion requires a confirmation step
  4. User can assign a revision label (free-text, e.g., "Rev C") to any drawing at upload time or after processing
  5. Drawing library is paginated and supports search by filename and revision label; users can additionally filter by processing status and upload date range
- **Related Learnings / Rationale**: Marcus manages hundreds of drawing sheets; without a searchable library with revision labels and status/date filters, the tool becomes unusable at scale and he reverts to folder-based file management.

---

**FR-13: ML Training Consent & Data Contribution**
- **Description**: Users and teams explicitly opt in or out of contributing their correction actions as ML training data. Required to satisfy the Section 17 regulatory constraint prohibiting use of customer drawings for model training without consent.
- **Priority**: P0
- **Category**: Compliance
- **Acceptance Criteria**:
  1. During account registration and at first drawing upload, users are presented with an explicit opt-in prompt for ML training data contribution; the default state is opted-out
  2. Users can change their training data contribution preference at any time from account settings; the change applies to all future correction actions immediately
  3. Team Admins can set a team-level training data contribution preference that applies to all team members; individual members cannot override the team-level setting
  4. Correction actions from opted-out users are stored for the user's own review and export but are excluded from all ML training pipelines
  5. The opt-in prompt clearly states that drawing geometry and correction labels (not raw drawing files) are used for training
- **Related Learnings / Rationale**: FR-3 AC-7 records corrections as training feedback; without this FR, all corrections silently violate Section 17's prohibition on using customer data for training without explicit consent.

---

**FR-7: Instrument Table Detection & Extraction**
- **Description**: The ML pipeline identifies structured instrument/valve data tables embedded in P&ID drawings (e.g., line lists, instrument indexes) and extracts their tabular content as structured rows. Addresses the "Manual Digitization Trap" for table-format data that symbols alone do not capture.
- **Priority**: P1
- **Category**: ML Processing
- **Acceptance Criteria**:
  1. System identifies rectangular table regions in the drawing and classifies them as data tables distinct from symbol detections
  2. System extracts table cell content (text strings) and maps rows and columns to a structured output format
  3. Extracted table data is included in the export file as a separate worksheet or section
  4. User can review and edit extracted table cell values in the review canvas before export
  5. System achieves ≥ 75% cell-level accuracy on tabular data extraction against the internal test dataset
- **Related Learnings / Rationale**: David's HAZOP preparation requires instrument index tables as well as symbol counts; omitting table extraction means he still performs partial manual work, reducing perceived time savings.

---

**FR-8: Revision Comparison**
- **Description**: Users select two versions of the same drawing and the system highlights symbols added, removed, or reclassified between revisions. Directly solves the "Version Confusion Problem" for Marcus and reduces re-digitization effort for Priya.
- **Priority**: P1
- **Category**: Drawing Management
- **Acceptance Criteria**:
  1. User can select any two drawings from the library and initiate a revision comparison
  2. System matches symbols between revisions using spatial proximity (bounding box centroid within 2% of drawing canvas dimensions) as primary heuristic, falling back to tag label match for symbols without spatial overlap; the matching strategy is applied consistently across all comparisons
  3. Additions and removals are highlighted in the drawing canvas with distinct colors and listed in a summary panel
  4. Comparison summary is exportable as a CSV showing entity class, tag, and change type (Added / Removed)
  5. Comparison is available only for drawings that have both completed ML processing
- **Related Learnings / Rationale**: Marcus spends significant time manually comparing drawing revisions; this feature makes his session trigger (new revision arrival) produce actionable output without re-digitizing the full drawing.

---

**FR-9: Subscription Tier Enforcement**
- **Description**: The system enforces usage limits by subscription tier (Free, Pro, Team), restricts access to tier-gated features, and provides upgrade prompts when limits are reached. Required to support the business model and revenue generation.
- **Priority**: P1
- **Category**: Billing & Access Control
- **Acceptance Criteria**:
  1. Free tier: maximum 3 drawings processed per calendar month (counter resets on the 1st of each month UTC); Pro tier: unlimited drawings; Team tier: unlimited drawings with multi-seat access up to the licensed seat count
  2. When a Free tier user attempts to process a 4th drawing in the same calendar month, the system blocks the action, emits `free_limit_reached`, and displays an upgrade prompt with pricing information; in-progress jobs at the moment of downgrade are allowed to complete
  3. Pro and Team tier features (revision comparison, team library) are visually indicated and inaccessible to Free tier users with an upgrade call-to-action
  4. Users can upgrade their subscription from within the application; downgrade takes effect at the end of the current billing period
  5. On downgrade, drawings and extraction data are retained but new processing jobs are blocked until the next calendar month's counter allows it; the user is shown their remaining free processing slots
  6. Team tier seat count is defined at subscription time; the Team Admin cannot invite members beyond the licensed seat count without upgrading; the system displays a seat-limit error and upgrade prompt when the limit is reached
- **Related Learnings / Rationale**: The 3-drawing Free tier limit is sufficient for Priya to evaluate the tool on a real project without requiring upfront commitment; the hard block with upgrade prompt converts evaluation to paid subscription.

---

**FR-10: Team Workspace & Shared Library**
- **Description**: Team-tier accounts can invite members, and all members share a single drawing library with role-based access (Admin, Member). Addresses Marcus's document control need to manage drawings on behalf of multiple engineers.
- **Priority**: P1
- **Category**: Collaboration
- **Acceptance Criteria**:
  1. Team Admin can invite users by email up to the licensed seat count; invitees receive an email with an accept link valid for 72 hours
  2. All team members can view, open, and export any drawing in the shared library
  3. Only Team Admins can delete drawings from the shared library
  4. Team Admin can remove members; removed members lose access to the shared library immediately; drawings uploaded by the removed member are reassigned to the Team Admin and remain in the shared library
  5. Drawing upload and correction actions display the initiating member's name in the library view
- **Related Learnings / Rationale**: Marcus's document control role requires centralized visibility over who uploaded what and when; without a shared library, each engineer maintains a separate silo that reintroduces the fragmentation problem.

---

### P2 — Future Versions

# Architecture

## 6. Security & Compliance Architecture

**Authentication Flow**: Supabase Auth issues RS256 JWTs. Google OAuth account-linking requires password confirmation before merging OAuth identity to existing account. Brute-force: 5 failed attempts → 15-minute server-side lockout (stored in Redis with TTL). Password reset invalidates all active sessions via Supabase Auth `admin.signOut(userId)` and updates `USER.token_invalidated_at`; middleware rejects any token with `iat` before this timestamp.

**Authorization Model**: RBAC with three roles — `user` (personal library), `team_member` (shared library read + upload), `team_admin` (shared library full control + billing). Role evaluated server-side on every request; never derived from JWT claims alone.

**Data Encryption**:
- At rest: AES-256 via S3 SSE-S3 or SSE-KMS; PostgreSQL encrypted EBS volumes.
- In transit: TLS 1.3 required for all external connections; TLS 1.2 minimum for legacy clients.
- DWG parsing sandbox: isolated Docker container with no network egress, read-only filesystem except for temp output directory; process runs as non-root user.

**Security Boundaries**:
- Object storage: never publicly accessible; all access via pre-signed URLs with 15-minute expiry.
- Blocklist enforcement: `POST /drawings/hash-check` gates pre-signed URL issuance; no blocked file hash is ever admitted to the S3 upload flow. Ingest Worker performs a second-pass server-side hash verification post-storage as a defense-in-depth check.
- ML worker: reads from S3 via IAM role; no internet egress; writes results only to PostgreSQL.
- Stripe webhooks: verified via `Stripe-Signature` header before any state mutation.

**GDPR Compliance**:
- EU region default (Frankfurt `eu-central-1`); US region optional (Virginia `us-east-1`).
- Right-to-erasure: 30-day async job; HMAC-based deterministic anonymous ID (`HMAC-SHA256(user_id || server_secret)`); anonymous ID persisted to `USER.anonymous_id` on first job execution and reused on retry, ensuring cross-table consistency.
- UserCorrections anonymized not deleted; training utility preserved post-deletion.
- DPA available for Team tier; consent captured at registration with opt-out default.
- Audit logs append-only; retained 2 years; anonymized on user deletion.

**OWASP Top 10 Mitigations**:
- Injection: SQLAlchemy ORM parameterized queries; no raw SQL construction from user input.
- Broken Access Control: server-side ownership check on every drawing/symbol/table-cell endpoint; team role enforcement in middleware.
- IDOR: all resource IDs are UUIDs; ownership validated before response.
- File Upload: type validation + malware scan + two-gate blocklist check (pre-URL + post-storage verification) before processing; DWG parsed in sandbox.
- Sensitive Data Exposure: PII fields encrypted at column level for email in audit logs; pre-signed URLs short-TTL.

---

## 7. Scalability & Performance

**Critical Data Flow — Drawing Processing**:

```mermaid
sequenceDiagram
    participant U as Browser
    participant API as FastAPI
    participant S3 as Object Storage
    participant Q as Redis Queue
    participant IW as Ingest Worker
    participant SW as Scan Worker
    participant ML as ML Worker
    participant SSE as SSE Stream

    U->>U: Compute SHA-256 of file (client-side)
    U->>API: POST /drawings/hash-check {sha256_hash}
    API->>PG: Check FILE_HASH_BLOCKLIST
    alt Hash blocked
        API-->>U: 409 Conflict -- upload rejected
    else Hash allowed
        API-->>U: {allowed: true, drawing_id}
        U->>API: POST /drawings {drawing_id, filename}
        API->>S3: Generate pre-signed PUT URL
        API-->>U: {drawing_id, upload_url}
        U->>S3: PUT file (direct upload)
        U->>API: POST /drawings/{id}/upload-complete
        API->>PG: Drawing state = Queued (idempotent check)
        API->>Q: Enqueue ingest job
        API-->>U: 202 Accepted
        U->>API: GET /drawings/{id}/status (SSE)
        Q->>IW: Dequeue ingest job
        IW->>S3: Fetch file; verify SHA-256 server-side
        IW->>PG: Second-pass blocklist check; state = Scanning
        SSE-->>U: state: Scanning
        IW->>Q: Enqueue scan job
        Q->>SW: Dequeue scan job
        SW->>SW: ClamAV scan
        SW->>PG: Update state = Processing
        SSE-->>U: state: Processing
        SW->>Q: Enqueue ML job
        Q->>ML: Dequeue ML job
        ML->>S3: Fetch file / raster output
        ML->>ML: GPU inference (symbol + table)
        ML->>PG: Insert DetectedSymbols + TableCells; state = Complete
        SSE-->>U: state: Complete
        API->>Q: Enqueue notification job
    end
```

**Caching Strategy**:
- Redis: subscription feature flags cached per user (5-minute TTL, invalidated on webhook receipt).
- Redis: entity class taxonomy (indefinite TTL, invalidated on admin update).
- CDN: static SPA assets with content-hash cache busting; export files served via pre-signed S3 URLs (no CDN — confidential content).
- PostgreSQL: drawing library queries use read replica at Phase 2.

**Performance Targets**:
- Dashboard load: <2s P95 — achieved via paginated API (25 records), indexed queries.
- Canvas load: <3s P95 — symbol bulk-fetch endpoint returns symbols for a page with default limit of 200; bounding boxes stored as JSONB avoid joins. Correction history co-loaded in the same response; no second round-trip required for panel open.
- Canvas interaction: <200ms P95 — symbol selection and panel open operate entirely from client-side state loaded at canvas initialization; no additional network fetch is required because correction history is pre-loaded with the symbols response.
- Export (<1,000 symbols): <30s P95 — synchronous generation in Export Worker; pre-signed URL returned on job completion poll.

**Symbol Pagination on Canvas**: `GET /drawings/{id}/symbols` accepts `limit` (default 200, max 500) and `offset` parameters. The client loads all symbols for the current page using offset-based pagination on initial canvas open; subsequent pages are loaded on-demand during multi-page navigation. This bounds the initial payload to a predictable size regardless of drawing density.

**Scaling Approach**:
- ML Workers: horizontal autoscaling on GPU instances based on queue depth (CloudWatch metric); minimum 1 instance, scale-out at queue depth >5 jobs.
- API: horizontal scaling behind ALB; stateless (sessions in Redis/Supabase).
- Database: read replica at Phase 2; connection pooling via PgBouncer from Phase 1.

---

## 8. AI & Emerging Tech Assessment

**Proven Capabilities** (safe to commit):
- Vector symbol detection via CNN-based object detection (YOLO-variant or DETR) on P&ID line drawings — well-established in engineering document processing literature.
- Table region detection via layout analysis models (LayoutLM, rule-based geometric detection).
- Confidence score output — native to all object detection frameworks.

**R&D / Risk Items**:
- ≥85% F1 on diverse real-world P&IDs — validated only post-training; must be confirmed by pre-launch experiment (Section 13 of PRD).
- DWG-to-vector fidelity via ODA File Converter — success rate on complex drawings unknown; 50-file prototype required.

**ML Inference Cost Shape**:
- GPU inference: the dominant cost driver. Each A1 drawing consumes 2–8 GPU-minutes on a G4dn instance. At 20 concurrent jobs (NFR-2), minimum 2–3 GPU instances needed at peak. Cost scales directly with processing volume.
- Token costs: N/A — no LLM APIs; all inference is self-hosted model serving.

**Human-in-the-Loop**:
- FR-3 correction canvas is the primary validation layer; every export reflects human-reviewed state.
- Confidence score surfaced per symbol — David's safety use case requires ability to sort/filter by low-confidence detections as a Phase 2 enhancement.
- Fallback if ML service is unavailable: drawing transitions to `Failed` state with retry option; no silent partial results.
- Table cell corrections (FR-7, US-022) feed the same training consent pipeline as symbol corrections, via the `TABLE_CELL.correction_training_consent` field.

**Training Data Flywheel**:
- `UserCorrection` records with `training_consent = true` feed a separate offline training pipeline (not in MVP scope).
- Anonymization preserves training utility post-user-deletion — architecture supports this from day one.
- Model versioning: ML worker loads model from S3 artifact store; version pinned in worker config; new model versions deployable without API downtime.

---

## 12. Design Decisions & Open Questions

**12a. Design Decisions Made**:

- **Pre-Storage Blocklist Enforcement via Client Hash Pre-Check**: FR-17 AC-2 requires that no blocked file byte reaches storage. The pre-signed S3 URL flow cannot interpose on the byte stream between browser and S3, so the hash gate must occur before the URL is issued. Decision: client computes SHA-256 before upload; `POST /drawings/hash-check` validates against `FILE_HASH_BLOCKLIST` and is a mandatory precondition for receiving a pre-signed URL. A second server-side verification by the Ingest Worker defends against client-side hash tampering and newly-added blocklist entries. Trade-off: requires client-side SHA-256 computation (browser SubtleCrypto API), which adds latency for large files; a pre-engineering spike validates this UX impact.

- **Upload-Complete Idempotency**: Network retries on `POST /drawings/{id}/upload-complete` must not produce duplicate ingest jobs. Decision: endpoint checks the Drawing's current `processing_state`; if already `Queued` or later, returns `200` without re-enqueuing. Trade-off: adds a DB read on every call; cost is negligible given the low frequency of this endpoint.

- **TABLE_CELL as a First-Class Entity**: FR-7 table extraction and US-022 cell editing require persistent, correctable table data. Decision: `TABLE_CELL` is a distinct entity with FK to `DRAWING`, `bbox`, `extracted_value`, `corrected_value`, and `correction_training_consent`. `USER_CORRECTION` gains a nullable `table_cell_id` FK to record cell-level corrections uniformly. Trade-off: adds a join for exports that include both symbol and table data, but keeps the correction audit trail unified.

- **Correction History Pre-Loaded with Symbol Fetch**: The canvas panel open must complete within 200ms (NFR-19). A separate server round-trip for correction history breaks this target on any non-trivial network latency. Decision: `GET /drawings/{id}/symbols` returns a `corrections_by_symbol_id` map in the same response. Trade-off: increases payload size, but correction history per symbol is small (typically 0–3 records) and the payload is bounded by the per-page symbol limit.

- **Revision Comparison Staleness Tracking**: The `REVISION_COMPARISON` entity stores a `last_correction_at` timestamp that is updated whenever a correction is submitted for either drawing in the comparison. Decision: the `GET /comparisons/{id}` response includes a `stale` boolean derived from `last_correction_at > computed_at`. The UI uses this to warn users that the comparison predates recent corrections. Trade-off: `last_correction_at` requires a lightweight update on every correction write to any drawing involved in a comparison; acceptable overhead.

- **GDPR Anonymous ID Persistence**: Making the erasure anonymous ID deterministic with only `(user_id || server_secret)` and persisting it to `USER.anonymous_id` on first execution ensures retry consistency. Decision: the erasure job reads the persisted `anonymous_id` on all retries; if not yet set, computes and writes it transactionally before touching any related records. Trade-off: if `server_secret` rotates, the stored `anonymous_id` values remain valid because they are persisted — rotation only affects future deletions.

- **Upload Protocol (Client → S3 Direct)**: Client uploads directly to S3 via pre-signed PUT URL; API receives a completion signal. Trade-off: API server is never a file byte proxy, reducing memory pressure, but requires the hash-check pre-step to enforce blocklist before URL issuance.

- **DWG Parsing Sandbox**: Isolated Docker sidecar with no network egress and non-root process for all DWG parsing (NFR-6 explicit requirement). Trade-off: adds container orchestration complexity but eliminates code-execution attack surface from malicious DWG files.

- **SSE vs. WebSocket for Status Push**: Decision: Server-Sent Events (SSE) via Redis pub/sub, with 10-second polling fallback for proxied connections. Trade-off: SSE is unidirectional (sufficient for status push) and simpler to scale than WebSocket connections; polling fallback handles corporate proxy environments common in the engineering target market.

- **Celery on Redis vs. Dedicated Queue (SQS/RabbitMQ)**: Redis already required for caching and SSE pub/sub. Decision: Celery with Redis broker at MVP. Trade-off: Redis becomes a dependency for three concerns (queue, cache, SSE); SQS migration path available at Phase 3 without changing worker code.

**12b. Open Questions**:

- **`Complete → Under_Review` State Transition Trigger**: Does opening the canvas alone trigger `Under_Review`, or does the first correction action? Impact: If canvas-open triggers it, drawings that are opened but not corrected show `Under_Review` in the library, which may confuse Marcus when auditing drawing states.

- **Grace Period Clock Start**: Does the 7-day grace period begin on the first Stripe `invoice.payment_failed` event, or after Stripe has exhausted its own retry schedule (~3–4 days)? Impact: Billing notification scheduling (day 1 and day 6 emails) cannot be finalized without this decision.

- **Tag Label Entry for Manual Annotations**: Can users type a tag label (e.g., "FT-201") when manually adding a symbol (US-014)? The API and schema now support `tag_label` as an optional field; the remaining question is whether the PRD intends this as a required user input or an optional annotation. Impact: affects annotation panel UI design and export schema documentation.

- **Multi-Tenant Correction Conflict Resolution**: When two team members submit conflicting corrections for the same symbol near-simultaneously, which wins? Last-write-wins (timestamp-based) is simplest but may silently discard a correction; explicit conflict detection requires a `version` field on `DETECTED_SYMBOL`. The PRD defers real-time collaboration but does not define a conflict resolution strategy for near-simultaneous writes.

---

# Cross-Epic Dependencies

**Depends on**:
- Epic 1 (Secure File Upload, Auth & Account Compliance, US-004): FR-13
- Epic 2 (Drawing Library Management & Processing State, US-006): FR-6

**Provides to**: No later epics share FRs with this epic.
