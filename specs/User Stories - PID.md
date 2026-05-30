# User Stories: PID Analyzer

## Overview
PID Analyzer is a web application that automates extraction of pipes, valves, and instrument data from P&ID drawings (PDF/DWG) using ML-based symbol detection. These stories cover the full product from secure file ingestion through ML processing, interactive validation, export, team collaboration, subscription management, and compliance — scoped for a desktop-primary browser SPA with a server-side ML inference pipeline. Personas are drawn directly from Section 4: **Instrumentation Engineer (Priya)**, **Process Safety Engineer (David)**, and **CAD/Document Control Manager (Marcus)**.

---

---

### Epic 2 — Drawing Library Management & Processing State
**Priority**: P0 — Must-have for MVP
**Requirements Covered**: FR-6, FR-16
**Description**: Provides the persistent drawing workspace that engineers return to across sessions. Covers the library list view (status, revision labels, search/filter), the full processing state machine (Queued → Scanning → Processing → Complete/Failed/Scan_Failed), retry flows, and analytics event instrumentation for all user actions. This epic is the operational backbone that all other epics depend on for drawing context.
**Story ID Range**: US-006 – US-010

---

### Epic 3 — ML Symbol Detection & Interactive Review Canvas
**Priority**: P0 — Must-have for MVP
**Requirements Covered**: FR-2, FR-3
**Description**: Delivers the core value proposition: automated ML symbol detection with confidence scores, and the interactive drawing canvas where engineers validate, correct, reclassify, and manually add detections. Covers both the ML trigger/status flow and the full human-in-the-loop correction interface with real-time persistence and training-consent-gated feedback recording.
**Story ID Range**: US-011 – US-015

---

### Epic 4 — Structured Data Export & Subscription Billing
**Priority**: P0 — Must-have for MVP
**Requirements Covered**: FR-4, FR-9, FR-15
**Description**: Closes the end-to-end workflow by delivering validated extraction data as CSV/XLSX downloads, and enforces the subscription tier model (Free/Pro/Team limits, upgrade prompts, Stripe webhook handling for payment failures and cancellations, grace periods). These two capabilities are coupled at the access-control boundary: export availability and processing allowance are both gated by subscription state.
**Story ID Range**: US-016 – US-020

---

### Epic 5 — Team Workspace, Shared Library & Instrument Table Extraction
**Priority**: P1 — Should-have for v1.0
**Requirements Covered**: FR-7, FR-8, FR-10
**Description**: Extends the platform for multi-user team workflows (shared drawing library, role-based Admin/Member access, seat-limited invitations) and adds instrument table detection and extraction as a P1 ML capability. Revision comparison is included here as it depends on the shared library model and is primarily consumed by Marcus's document control workflow.
**Story ID Range**: US-021 – US-025

---

## Required UI Contexts

| UI Context | Type | P0 Stories | Key Fields |
|---|---|---|---|
| Registration & Email Verification Form | Form | US-001, US-002 | email, password, ML training consent opt-in, email verification status |
| Login Form | Form | US-001, US-002 | email, password, Google OAuth button, account-link prompt, lockout message |
| File Upload Drop Zone | Form | US-003, US-017 | file picker, drag-and-drop target, progress indicator, format/size error messages |
| Drawing Library | Screen | US-006, US-007, US-008 | filename, upload date, processing status badge, revision label, search/filter controls |
| Processing Status Detail | Screen | US-007, US-008 | state indicator (Queued/Scanning/Processing/Complete/Failed), retry CTA, error message |
| Drawing Review Canvas | Screen | US-011, US-012, US-013, US-014 | bounding box overlays, entity class color codes, confidence score, tag label, classification panel |
| Symbol Detail & Reclassification Panel | Modal | US-012, US-013, US-014 | entity class selector, confidence score, tag/label field, reject/accept action |
| Manual Annotation Tool | Modal | US-014 | bounding box draw tool, entity class assignment, save action |
| Export Download Modal | Modal | US-016, US-017 | format selector (CSV/XLSX), download link, async-ready status, re-export option |
| Account Settings | Screen | US-002, US-004, US-005 | display name, email, password reset, ML training consent toggle, account deletion CTA |
| Subscription & Upgrade Prompt | Screen | US-018, US-019, US-020 | current tier, usage counter, upgrade CTA, pricing info, grace period notice |

### P1 UI Contexts

| UI Context | Type | P1 Stories | Key Fields |
|---|---|---|---|
| Team Management Screen | Screen | US-023, US-024 | member list, invite by email, seat count, role badge, remove member action |
| Team Invitation Accept Page | Screen | US-023 | invite link, accept/decline CTA, team name |
| Revision Comparison Canvas | Screen | US-025 | drawing selector (A vs B), addition/removal highlights, summary panel, export comparison CSV |
| Instrument Table Review Panel | Modal | US-021, US-022 | table region highlight, extracted cell values, editable cell fields, export inclusion toggle |

---

## User Stories

### Secure File Upload, Auth & Account Compliance (Must-have for MVP)
**Requirements Covered**: FR-1, FR-5, FR-13, FR-14, FR-17
**Description**: Establishes the authenticated entry point for all user workflows. Covers registration, login (email/password + Google OAuth), session management, file upload with drag-and-drop/browser picker, malware hash blocklist enforcement, ML training consent, and GDPR account deletion. Without this epic, no other feature can be accessed or attributed to a user.
**User Stories**: US-001 – US-005

---

#### US-001: Register account and verify email
**Epic**: Secure File Upload, Auth & Account Compliance
**Priority**: Must-have
**Complexity**: Medium

**User Story**:
As Priya, an Instrumentation Engineer,
I want to register for an account using my email and password and verify my email address,
So that my drawings and extraction data are securely attributed to my identity and I can begin uploading P&ID files.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Successful Registration)**:
  - Given I am an unauthenticated visitor on the registration page
  - When I submit a valid email address, a password meeting complexity requirements, and my display name
  - Then my account is created in an unverified state, a verification email is sent to the provided address, and the page displays a confirmation message instructing me to check my email before I can upload drawings

- **Scenario 2 (Email Verification Completes Registration)**:
  - Given I have registered and received a verification email containing a unique time-limited link
  - When I click the verification link within its valid window
  - Then my account is marked as verified, I am redirected to the application dashboard, and I am permitted to upload my first drawing

- **Scenario 3 (Duplicate Email Rejected)**:
  - Given an account already exists for a given email address
  - When I attempt to register using that same email address
  - Then the form displays an error stating that an account with this email already exists, and no new account is created

- **Scenario 4 (Upload Blocked Until Verified)**:
  - Given I have registered but have not yet clicked the verification link
  - When I attempt to upload a drawing
  - Then the system blocks the upload and displays a message stating that email verification is required, with an option to resend the verification email

- **Scenario 5 (Expired Verification Link)**:
  - Given I have registered and my verification email link has expired
  - When I click the expired link
  - Then the page displays an error stating the link has expired and offers a resend option that generates a new valid verification link

**Technical Notes**:
- Password complexity requirements (minimum length, character classes) should be defined by the Architecture Agent and enforced consistently on both client and server.
- Verification link expiry window should be defined by the Architecture Agent; the resend flow must invalidate any previously issued unclicked verification tokens for the same account.
- The unverified account state must be represented in the data model so the upload gate in FR-1 can query it.

**Related Requirements**: FR-5

**Dependencies**: None

---

#### US-002: Log in via email/password and Google OAuth with account linking
**Epic**: Secure File Upload, Auth & Account Compliance
**Priority**: Must-have
**Complexity**: Medium

**User Story**:
As Priya, an Instrumentation Engineer,
I want to log in with my email and password or via my Google account, with clear handling when both methods share the same email,
So that I can access my drawing library securely without being locked out or silently assigned a duplicate account.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Email/Password Login)**:
  - Given I am a verified, registered user on the login page
  - When I submit my correct email address and password
  - Then I am authenticated, a session is created, and I am redirected to my drawing library dashboard

- **Scenario 2 (Happy Path — Google OAuth Login for New Account)**:
  - Given I have no existing account and I choose to log in with Google
  - When I complete Google OAuth consent and Google returns a verified email address
  - Then a new verified account is created using the Google-provided email, I am authenticated, and I am redirected to the drawing library dashboard

- **Scenario 3 (Account Linking Prompt — OAuth Email Matches Existing Password Account)**:
  - Given I have an existing password-registered account for a given email address
  - When I attempt to log in via Google OAuth using that same email address
  - Then the system does not create a duplicate account or silently merge, and instead presents a prompt explaining that an account with this email already exists and asking me to confirm account linking by authenticating with my existing password

- **Scenario 4 (Brute-Force Lockout)**:
  - Given I am on the login page and have submitted incorrect credentials 5 consecutive times for a given email
  - When I attempt a 6th login within the 15-minute lockout window
  - Then the login is rejected, the UI displays a message stating the account is temporarily locked and indicates when I may try again, and no further attempts are processed until the lockout expires

- **Scenario 5 (Session Expiry Redirect)**:
  - Given I am an authenticated user whose session has been inactive for 8 hours
  - When I attempt to navigate to any authenticated page
  - Then my session is invalidated, I am redirected to the login page, and the page displays a session-expiry notification

**Technical Notes**:
- The 5-minute pre-expiry warning modal referenced in NFR-18 is a session management UX behavior; the Architecture Agent should implement the server-side inactivity timer that feeds the frontend countdown.
- Account linking must be implemented as an explicit confirmation flow — never as an automatic silent merge — to prevent account takeover via OAuth.
- Lockout state (attempt count, lockout timestamp) must persist server-side; client-side-only enforcement is insufficient.
- Google OAuth integration requires a registered OAuth client with the Google Cloud Console; this is an Architecture concern.

**Related Requirements**: FR-5

**Dependencies**: US-001

---

#### US-003: Upload PDF or DWG file with format, size, and raster validation
**Epic**: Secure File Upload, Auth & Account Compliance
**Priority**: Must-have
**Complexity**: Large

**User Story**:
As Priya, an Instrumentation Engineer,
I want to upload my P&ID drawing file via drag-and-drop or a file browser picker with immediate feedback on whether the file is accepted,
So that I know my drawing has been received and queued for processing without switching to another application to verify format compatibility.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Valid PDF Upload)**:
  - Given I am an authenticated, verified user on the drawing upload surface
  - When I drag and drop a PDF file that is ≤ 100MB and contains vector geometry
  - Then a real-time upload progress indicator is displayed, and upon server acknowledgment a unique Drawing record is created, associated with my account, placed in `Queued` state, and the drawing appears in my library with status `Queued`

- **Scenario 2 (Happy Path — Valid DWG Upload via File Browser)**:
  - Given I am an authenticated, verified user
  - When I use the file browser picker to select an AutoCAD DWG file (versions 2010–2024) that is ≤ 100MB
  - Then the same upload progress and Drawing record creation behavior occurs as Scenario 1, with the drawing entering `Queued` state in my library

- **Scenario 3 (File Size Limit Exceeded)**:
  - Given I attempt to upload a file larger than 100MB
  - When the file is submitted via drag-and-drop or file browser
  - Then the upload is rejected before the file is transferred in full, and the page displays an error message specifying the 100MB limit and the actual file size

- **Scenario 4 (Unsupported File Type Rejected)**:
  - Given I attempt to upload a file that is neither a PDF nor a DWG (e.g., a JPEG, DOCX, or DXF)
  - When the file is submitted
  - Then the upload is rejected and the page displays an error naming the accepted formats (PDF and DWG)

- **Scenario 5 (Raster-Only PDF Rejected; Mixed PDF Partially Accepted)**:
  - Given I upload a PDF that contains only raster (scanned) pages with no vector geometry
  - When the system processes the upload
  - Then the Drawing record enters a terminal error state and the library displays a descriptive error explaining that scanned PDFs without vector geometry are not supported; if instead the PDF contains a mix of vector and raster pages, the Drawing record is created, raster pages are skipped, and I am notified in the library view of which page numbers were excluded

- **Scenario 6 (Blocklisted File Hash Rejected)**:
  - Given a file whose SHA-256 hash matches an entry in the FileHashBlocklist
  - When I attempt to upload that file
  - Then the upload is rejected with a security error message that does not reveal the reason is malware-related, and no file data is written to object storage

- **Scenario 7 (Pre-2010 DWG Version Rejected)**:
  - Given I attempt to upload a DWG file created in AutoCAD version 2009 or earlier
  - When the file is submitted via drag-and-drop or file browser
  - Then the upload is rejected before the Drawing record is created, and the page displays an error message stating that only DWG files from AutoCAD 2010–2024 are supported, naming the detected version where determinable

**Technical Notes**:
- SHA-256 hash computation (FR-17) must occur before the file is written to object storage; the blocklist check must be the first server-side gate after authentication and size/type validation.
- Raster-vs-vector detection for PDFs requires server-side parsing; the Architecture Agent should determine the appropriate library (e.g., pdfminer, PyMuPDF) and define the vector geometry threshold.
- DWG version detection (to reject pre-2010 files, Scenario 7) must be implemented server-side; the client-side picker must not be the sole enforcement point.
- Upload progress visibility requires a chunked or multipart upload mechanism; the Architecture Agent should define the upload protocol.

**Related Requirements**: FR-1, FR-17

**Dependencies**: US-001, US-002
---

#### US-004: Manage ML Training Consent and Configure Account Settings
**Epic**: Secure File Upload, Auth & Account Compliance
**Priority**: Must-have
**Complexity**: Small

**User Story**:
As Priya, an Instrumentation Engineer,
I want to explicitly choose whether my correction actions contribute to ML model training,
So that I retain control over how my proprietary drawing data is used.

As Priya, an Instrumentation Engineer,
I also want to update my display name and email address from account settings,
So that my account details remain accurate and attributable to me.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Opt-In Consent Prompt at Registration and First Upload)**:
  - Given I am completing registration or uploading my first drawing
  - When the ML training consent prompt is presented
  - Then the prompt clearly states that drawing geometry and correction labels (not raw drawing files) are used for training, the default selection is opted-out, and I must take an explicit action to opt in; my preference is saved to my account immediately upon selection

- **Scenario 2 (Changing Consent Preference from Account Settings)**:
  - Given I am an authenticated user on the account settings page
  - When I toggle my ML training data contribution preference from opted-out to opted-in (or vice versa)
  - Then the new preference is saved immediately and applies to all correction actions I perform from that point forward; existing correction records are not retroactively altered

- **Scenario 3 (Opted-Out Corrections Excluded from Training Pipeline)**:
  - Given my training consent preference is set to opted-out
  - When I perform correction actions on a drawing (reclassify, reject, or manually add a symbol)
  - Then the correction is saved and visible in my review canvas, but the correction record is flagged as excluded from the ML training pipeline

- **Scenario 4 (Update Display Name and Email)**:
  - Given I am an authenticated user on the account settings page
  - When I submit a new display name or a new email address
  - Then my display name is updated immediately; if I changed my email address, a verification email is sent to the new address and the old email remains active until the new one is verified

- **Scenario 5 (Team Admin Consent Override — Conditional)**:
  - Given I am a member of a Team where the Team Admin has set a team-level training consent preference
  - When I navigate to my account settings ML consent section
  - Then the setting is displayed as read-only with a message indicating it is controlled by my Team Admin, and I cannot override it

**Technical Notes**:
- The `MLTrainingConsent` entity must store the opt-in/opt-out state and timestamp; the `UserCorrection` entity must capture the `training_consent` flag at the time of creation (not at the time of pipeline execution) so that retroactive consent changes do not alter historical records.
- Team-level consent (Scenario 5) requires that the correction pipeline checks the team's consent state when a user belongs to a team, overriding the individual user's preference. **Scenario 5 is conditionally active only when the Team Workspace (Epic 5, US-023/US-024) is present in the sprint scope; if Epic 5 is excluded, Scenario 5 should be deferred to US-023.**
- Email change flow must follow the same verification pattern as registration (US-001) to prevent account hijacking via unverified email updates.

**Related Requirements**: FR-5, FR-13

**Dependencies**: US-001, US-002
---

#### US-005: Delete account and trigger GDPR erasure pipeline
**Epic**: Secure File Upload, Auth & Account Compliance
**Priority**: Must-have
**Complexity**: Medium

**User Story**:
As Priya, an Instrumentation Engineer,
I want to permanently delete my account from account settings with a clear confirmation step,
So that my personal data is removed in compliance with GDPR's right-to-erasure and I retain confidence that my proprietary drawing data is not retained after I leave.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Account Deletion Initiated)**:
  - Given I am an authenticated user on the account settings page
  - When I initiate account deletion and confirm by entering my password
  - Then my account is immediately deactivated (all active sessions are invalidated and I am redirected to the login page with a confirmation message), and an automated erasure job is scheduled to complete within 30 days

- **Scenario 2 (PII Purged Within 30 Days)**:
  - Given my account deletion has been initiated
  - When the scheduled erasure job executes within 30 days
  - Then my email address, display name, and password hash are permanently deleted from the system and cannot be recovered or queried

- **Scenario 3 (UserCorrection Records Anonymized, Not Deleted)**:
  - Given my account deletion has been initiated and I have UserCorrection records from opted-in training sessions
  - When the erasure job executes
  - Then my user ID on all UserCorrection records is replaced with a non-reversible anonymous ID, preserving the training utility of the correction data while removing re-identifiability; no UserCorrection records are deleted

- **Scenario 4 (Personal Drawings Deleted; Team Drawings Retained)**:
  - Given my account deletion has been initiated
  - When the erasure job executes
  - Then drawing files I uploaded outside of any team context are permanently deleted from object storage within 30 days; drawings I uploaded to a team library are retained under team ownership and are not deleted

- **Scenario 5 (Audit Log and Export Records Anonymized)**:
  - Given my account deletion has been initiated
  - When the erasure job executes
  - Then ExportRecord and audit log entries retain the action type and entity IDs but replace my user-identifying fields with the same non-reversible anonymous ID used for UserCorrection records

**Technical Notes**:
- Account deactivation (session invalidation) must be synchronous and immediate; the PII purge, file deletion, and anonymization steps are asynchronous and executed by a scheduled background job within the 30-day window.
- The anonymous ID must be deterministic per deleted user (so all records for one user share the same anonymous ID) but non-reversible; the Architecture Agent should define the hashing or token strategy.
- The erasure job must be idempotent so that re-execution (e.g., after a job failure and retry) does not produce inconsistent anonymization states.
- ExportRecord StoredFiles (generated export files) for personal drawings should also be deleted from object storage as part of the personal drawing deletion step (Scenario 4).

**Related Requirements**: FR-14

**Dependencies**: US-001, US-002, US-003, US-004
### Drawing Library Management & Processing State (Must-have for MVP)
**Requirements Covered**: FR-6, FR-16
**Description**: Provides the persistent drawing workspace engineers return to across sessions. Covers the library list view (status, revision labels, search/filter/pagination), the full processing state machine (Queued → Scanning → Processing → Complete/Failed/Scan_Failed), retry flows for failed jobs, and analytics event instrumentation for all tracked user actions.
**User Stories**: US-006 – US-010

---

#### US-006: View Drawing Library with Status, Revision Labels, and Pagination
**Epic**: Drawing Library Management & Processing State
**Priority**: Must-have
**Complexity**: Medium

**User Story**:
As Marcus, CAD/Document Control Manager,
I want to view all uploaded drawings in a paginated library showing filename, upload date, processing status, and revision label,
So that I can track the state of every drawing in the team's library without switching between folders or external tracking sheets.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Library Loads with Drawing Records)**:
  - Given Marcus is authenticated and has uploaded at least one drawing
  - When he navigates to the Drawing Library page
  - Then the page displays a list of drawings, each showing: filename, upload date, processing status badge (Queued / Scanning / Processing / Complete / Failed / Scan_Failed), and revision label (if assigned)

- **Scenario 2 (Pagination)**:
  - Given Marcus has more than 25 drawings in his library
  - When the library page loads
  - Then drawings are displayed in pages of 25, with pagination controls showing current page and total page count; navigating to the next page loads the next 25 records without a full page reload

- **Scenario 3 (Revision Label — Assigned at Upload)**:
  - Given a drawing was uploaded with a revision label of "Rev C"
  - When Marcus views the library
  - Then the drawing row displays "Rev C" in the revision label column

- **Scenario 4 (Revision Label — Assigned After Upload)**:
  - Given a completed drawing has no revision label assigned
  - When Marcus assigns the label "Rev D" inline from the library view
  - Then the label is saved and immediately displayed in the drawing row without a page reload

- **Scenario 5 (Empty State)**:
  - Given Marcus has no drawings uploaded to his library
  - When he navigates to the Drawing Library page
  - Then the page displays an empty state message with a prompt to upload the first drawing

**Technical Notes**:
- Processing status badges must reflect live state; poll or use server-sent events for drawings in transient states (Queued, Scanning, Processing) so status updates without manual page refresh.
- Pagination default of 25 records per page; page size should be configurable server-side to allow future adjustment.
- Revision label inline edit must debounce and persist to server; no separate save button required, but a visible save-confirmation indicator (e.g., checkmark) is expected.

**Related Requirements**: FR-6

**Dependencies**: US-001 (file upload, which creates Drawing records)

---

#### US-007: Search and Filter Drawing Library by Filename, Status, and Date Range
**Epic**: Drawing Library Management & Processing State
**Priority**: Must-have
**Complexity**: Medium

**User Story**:
As Marcus, CAD/Document Control Manager,
I want to search the drawing library by filename and revision label, and filter by processing status and upload date range,
So that I can locate a specific drawing or set of drawings across a large library without scrolling through hundreds of records.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Filename Search)**:
  - Given Marcus has drawings with filenames including "FD-100" and "FD-200" in his library
  - When he types "FD-100" into the search field
  - Then the library displays only drawings whose filename or revision label contains "FD-100"; results update as he types with a debounce of no more than 400ms

- **Scenario 2 (Filter by Processing Status)**:
  - Given Marcus has drawings in multiple processing states
  - When he selects "Failed" from the status filter dropdown
  - Then the library displays only drawings with a processing status of "Failed"; all other drawings are hidden from the current view

- **Scenario 3 (Filter by Upload Date Range)**:
  - Given Marcus has drawings uploaded across multiple months
  - When he sets an upload date range of 1 June 2025 to 30 June 2025
  - Then only drawings uploaded within that inclusive date range are displayed

- **Scenario 4 (Combined Search and Filter)**:
  - Given Marcus has applied a filename search of "FD" and a status filter of "Complete"
  - When both are active simultaneously
  - Then the library displays only drawings whose filename or revision label contains "FD" AND whose status is "Complete"; the active filter count is indicated in the UI

- **Scenario 5 (No Results)**:
  - Given Marcus applies a search or filter combination that matches no drawings
  - When the query executes
  - Then the library displays a "No drawings match your search" message; pagination controls are hidden

**Technical Notes**:
- Search is case-insensitive substring match against filename and revision label fields.
- Status filter should support multi-select to allow filtering on more than one status simultaneously.
- Active search/filter state should be preserved in the URL query string so Marcus can bookmark or share a filtered view.

**Related Requirements**: FR-6

**Dependencies**: US-006

---

#### US-008: Track Drawing Through Processing State Machine and Surface Terminal States
**Epic**: Drawing Library Management & Processing State
**Priority**: Must-have
**Complexity**: Large

**User Story**:
As Priya, Instrumentation Engineer,
I want to see my drawing's processing status update in real time as it moves through each stage — from upload through scanning to ML analysis — and receive clear notifications when processing completes or fails,
So that I know exactly when results are ready to review or when I need to take corrective action, without manually refreshing the page.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Full Successful Transition)**:
  - Given Priya has uploaded a valid vector PDF drawing
  - When the system processes the drawing
  - Then the library status badge transitions sequentially through: Queued → Scanning → Processing → Complete; each transition is reflected in the UI without a manual page refresh; on reaching Complete, an in-app notification is displayed indicating the drawing is ready to review

- **Scenario 2 (Scan_Failed Terminal State)**:
  - Given the malware scan service returns a failed result for a drawing
  - When the scan completes
  - Then the drawing status is set to Scan_Failed; the library displays a Scan_Failed badge; the drawing detail surface shows an explanation that the file could not be processed for security reasons without exposing malware scan details or blocklist contents; no retry option is presented

- **Scenario 3 (Processing Failed Terminal State)**:
  - Given ML inference does not complete within 20 minutes or the model returns an error
  - When the timeout or error occurs
  - Then the drawing status is set to Failed; an in-app notification informs Priya that processing could not be completed; a one-click retry action is visible on the drawing record in the library

- **Scenario 4 (Raster-Only PDF Detection)**:
  - Given Priya uploads a PDF that contains only raster images with no vector geometry
  - When the system evaluates the file during Scanning
  - Then the drawing transitions to a terminal rejection state; the UI displays an error message stating that scanned PDFs without vector geometry are not supported; no retry option is presented

**Technical Notes**:
- State transitions must be persisted in the Drawing record before the UI is notified; use server-sent events (SSE) or WebSocket for live status push to the browser; polling is an acceptable fallback with a maximum 10-second interval for drawings in transient states.
- The 20-minute ML inference timeout and 1 automatic retry before marking `Failed` are handled server-side (see Section 8 ML Inference Service spec); the UI only surfaces the terminal `Failed` state after the retry is exhausted.
- Raster page skipping for mixed vector/raster multi-page PDFs (per FR-1 AC-6) is a sub-case of this state machine; skipped pages must be recorded and surfaced in the drawing detail alongside the processing notification.
- The large-drawing symbol-count warning (> 500 symbols) is owned exclusively by US-011 Scenario 4 and is not duplicated here.

**Related Requirements**: FR-6, FR-16
*(Note: FR-2 is a triggering dependency via the ML inference service but is not a requirement covered by this story; FR-6 is the primary requirement and FR-16 governs the `processing_complete` and `processing_failed` events emitted at state transitions.)*

**Dependencies**: US-001 (file upload initiates state machine)
---

#### US-009: Retry Failed Processing Job and Delete Drawing with Confirmation
**Epic**: Drawing Library Management & Processing State
**Priority**: Must-have
**Complexity**: Small

**User Story**:
As Priya, Instrumentation Engineer,
I want to retry a failed processing job with a single click and permanently delete drawings I no longer need after confirming my intent,
So that I can recover from transient ML failures without re-uploading files and keep my library uncluttered without risking accidental data loss.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Retry Failed Job)**:
  - Given a drawing is in the Failed state (ML inference failure, not Scan_Failed)
  - When Priya clicks the retry action on that drawing record
  - Then the drawing status resets to Queued and re-enters the processing state machine using the existing stored file, without requiring a new file upload; the retry action is no longer visible while the drawing is in a transient state

- **Scenario 2 (Scan_Failed — No Retry Available)**:
  - Given a drawing is in the Scan_Failed state
  - When Priya views the drawing record in the library
  - Then no retry action is displayed; the drawing record shows only the Scan_Failed status and the security explanation message

- **Scenario 3 (Happy Path — Delete Drawing with Confirmation)**:
  - Given Priya has a drawing in any state in her library
  - When she initiates deletion and confirms the action in the confirmation dialog
  - Then the drawing, its associated DetectedSymbols, UserCorrections, and ExportRecords are permanently removed; the drawing no longer appears in the library; the StoredFile in object storage is marked for deletion

- **Scenario 4 (Deletion Cancelled)**:
  - Given Priya initiates deletion of a drawing
  - When she dismisses the confirmation dialog without confirming
  - Then the drawing remains in the library unchanged

- **Scenario 5 (Delete Drawing in Processing State)**:
  - Given a drawing is currently in Queued, Scanning, or Processing state
  - When Priya confirms deletion
  - Then the in-progress job is cancelled server-side and the drawing and all associated data are deleted; a brief status message confirms the cancellation and deletion were successful

**Technical Notes**:
- Retry must re-use the existing `StoredFile` reference; no new file is written to object storage on retry.
- Deletion of a drawing in a team context is subject to role restriction (Team Admins only per FR-10 AC-3); this story covers personal library deletion; team-library deletion enforcement is handled in the Team Workspace epic.
- The confirmation dialog must display the drawing filename so Priya can verify she is deleting the correct record.

**Related Requirements**: FR-6

**Dependencies**: US-006, US-008

---

#### US-010: Emit and Deliver Structured Analytics Events for All Tracked User Actions
**Epic**: Drawing Library Management & Processing State
**Priority**: Must-have
**Complexity**: Medium

**User Story**:
As the PID Analyzer platform,
I need all tracked user and system actions to be silently instrumented with structured analytics events,
So that the product team can measure activation, retention, and conversion metrics that reflect real usage and guide product improvements.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Named Events Emitted with Required Payload)**:
  - Given a user or system performs any of the following actions: file upload completes, processing completes, processing fails, a correction action is taken, an export is initiated, an export file is downloaded, a free tier limit is reached, a subscription is upgraded, or a subscription is downgraded
  - When each action occurs
  - Then the corresponding named event (`drawing_uploaded`, `processing_complete`, `processing_failed`, `correction_action`, `export_initiated`, `export_downloaded`, `free_limit_reached`, `subscription_upgraded`, `subscription_downgraded`) is emitted with a payload containing: event name, timestamp (UTC), user ID, and the relevant entity ID (drawing ID, export record ID, or subscription ID as applicable)

- **Scenario 2 (Worker-Emitted Events Carry User ID from Job Payload)**:
  - Given a processing job is enqueued for a drawing owned by an authenticated user
  - When the ML worker emits a `processing_complete` or `processing_failed` event upon job completion or failure
  - Then the event payload contains the user ID that was included in the job payload at enqueue time; the worker does not resolve user ID from session context and does not emit the event without a user ID present in the job payload

- **Scenario 3 (Analytics Failure Does Not Block User Action)**:
  - Given the analytics pipeline is unavailable or returns an error
  - When a tracked action occurs
  - Then the action completes successfully and the user receives no error related to analytics; the event emission failure is logged server-side for retry or investigation but does not surface to the user

- **Scenario 4 (Free Limit Reached Event — Correct Trigger Point)**:
  - Given a Free tier user has processed 3 drawings in the current calendar month
  - When they attempt to initiate processing of a 4th drawing
  - Then the `free_limit_reached` event is emitted before the upgrade prompt is displayed; the event payload includes the user ID and subscription ID; the processing job is not queued

**Technical Notes**:
- Event emission must be non-blocking and asynchronous; the user-facing request must not wait on analytics delivery to return a response.
- The user ID must be written into the job payload at enqueue time (by the API layer that has authenticated session context) so that worker processes can include it in emitted events without requiring a database lookup or session access. This is mandatory for `processing_complete` and `processing_failed` events.
- Events originating from server-side transitions (e.g., `processing_complete`, `processing_failed`) are emitted by the backend processing service, not the browser client; ensure the analytics instrumentation layer is available to all backend services, not only the web API.
- A server-side retry queue (e.g., dead-letter queue) is recommended for failed event deliveries to support eventual consistency in the analytics pipeline without surfacing failures to users.
- All nine named events in FR-16 AC-1 must be covered; no subset delivery is acceptable for this story to be considered complete.

**Related Requirements**: FR-16

**Dependencies**: US-006, US-007, US-008, US-009
---

#### US-011: Trigger ML Processing on Upload and Display Detection Results with Confidence Scores
**Epic**: ML Symbol Detection & Interactive Review Canvas
**Priority**: Must-have
**Complexity**: Medium

**User Story**:
As Priya, an Instrumentation Engineer,
I want ML processing to start automatically after my drawing uploads and to see the detection results with confidence scores when it completes,
So that I receive a structured extraction without manually initiating any analysis step.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Processing Completes Successfully)**:
  - Given Priya has successfully uploaded a PDF or DWG drawing and the file has passed the malware scan
  - When the drawing transitions from `Scanning` to `Processing` state
  - Then the system automatically enqueues the ML inference job without any additional user action, the Drawing Library displays the status as `Processing`, and upon completion the status updates to `Complete` with a visible in-app notification that results are ready

- **Scenario 2 (Results Display with Confidence Scores)**:
  - Given a drawing has reached `Complete` state with ML inference results
  - When Priya opens the drawing from the library
  - Then the review canvas displays the total count of detected symbols grouped by entity class (Pipe, Valve, Instrument), and each detected symbol entry in the results panel shows its entity class, subtype, tag label (if extracted), and a confidence score between 0.0 and 1.0

- **Scenario 3 (Processing Failure — Timeout or Model Error)**:
  - Given a drawing has been in `Processing` state for more than 20 minutes or the ML inference service returns an error
  - When the failure condition is detected by the system
  - Then the drawing status updates to `Failed`, Priya receives an in-app notification with a user-readable error message, and a one-click retry action is available that re-queues the same file without requiring re-upload

- **Scenario 4 (Large Drawing Pre-Processing Warning)**:
  - Given the system estimates a drawing contains more than 500 symbols based on initial file analysis
  - When the drawing is queued for ML processing
  - Then the page displays a warning message stating that extended processing time may apply and the standard 10-minute completion estimate does not apply, before inference begins

- **Scenario 5 (Scan Failed — No Retry Offered)**:
  - Given a drawing has reached `Scan_Failed` terminal state
  - When Priya views the drawing in the library
  - Then the status is shown as `Scan_Failed`, no retry action is presented, and the displayed message explains the file could not be processed due to a security restriction without referencing malware detection details

**Technical Notes**:
- ML job must be enqueued via a persistent queue (not in-memory) to satisfy NFR-7's requirement that queued jobs survive server restarts.
- The inference request payload must conform to the ML Inference Service contract defined in Section 8: `{ storage_reference, drawing_id, page_range? }`; the system issues one automatic retry on timeout before transitioning to `Failed`.
- The `processing_complete` and `processing_failed` analytics events (FR-16) must be emitted at the respective state transitions; event emission must not block the state update.
- In-app notifications for `Complete` and `Failed` states may be implemented via polling or server-sent events; the architecture choice is left to the Architecture Agent.

**Related Requirements**: FR-2, FR-16

**Dependencies**: US-001 (user authentication), US-003 (file upload and malware scan initiation), US-008 (drawing processing state machine and terminal state handling)
---

#### US-012: Render Detected Symbols as Color-Coded Bounding Box Overlays on Drawing Canvas
**Epic**: ML Symbol Detection & Interactive Review Canvas
**Priority**: Must-have
**Complexity**: Large

**User Story**:
As Priya, an Instrumentation Engineer,
I want detected symbols displayed as color-coded bounding box overlays directly on top of my drawing,
So that I can visually confirm which symbols were found and immediately identify which entity class each detection belongs to before reviewing details.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Overlays Render on Canvas Load)**:
  - Given a drawing has reached `Complete` or `Under_Review` state with ML detection results
  - When Priya opens the drawing review canvas
  - Then all non-rejected detected symbols are rendered as bounding box overlays on the drawing, with each overlay color-coded by entity class (Pipe, Valve, Instrument using three visually distinct colors), and the canvas is navigable via pan and zoom

- **Scenario 2 (Color Legend is Visible)**:
  - Given the drawing canvas is loaded with bounding box overlays present
  - When Priya views the canvas
  - Then a persistent legend is displayed mapping each entity class to its corresponding bounding box color, and the legend remains visible during pan and zoom operations

- **Scenario 3 (Rejected Symbols Are Hidden from Canvas)**:
  - Given a detected symbol has been marked as rejected by Priya
  - When the drawing canvas is rendered or refreshed
  - Then the bounding box for the rejected symbol is no longer visible on the canvas, and the symbol count in the results panel decrements accordingly

- **Scenario 4 (Multi-Page PDF — Page Navigation)**:
  - Given a drawing was produced from a multi-page PDF
  - When Priya opens the review canvas
  - Then page navigation controls are available, each page renders its own bounding box overlays independently, and switching pages loads the correct set of detections for that page without losing overlay state on other pages

- **Scenario 5 (Canvas Interaction — Bounding Box Selection)**:
  - Given the drawing canvas is loaded and contains detected symbol overlays
  - When Priya clicks on a bounding box to select it
  - Then the bounding box is highlighted as selected and the classification detail panel opens for that symbol

**Technical Notes**:
- Canvas rendering must support vector overlay rendering on top of both rasterized DWG output and PDF vector content; the rendering approach (SVG overlay, Canvas 2D, WebGL) is the Architecture Agent's decision.
- Bounding box coordinates from the ML inference response are in `[x, y, w, h]` format relative to the drawing coordinate space; the frontend must transform these to viewport coordinates on zoom/pan.
- **`Under_Review` state transition trigger (resolved)**: The drawing transitions from `Complete` to `Under_Review` on the user's first correction action (e.g., accepting, rejecting, or editing a detected symbol), not on canvas open. This keeps `Under_Review` semantically meaningful — Marcus (Plant Manager) will not see drawings listed as `Under_Review` merely because Priya viewed the canvas without acting. Canvas open alone must not trigger the state transition; the first write action must.
- The interaction behavior described in Scenario 5 has an associated NFR performance target (NFR-19); the Architecture Agent owns the implementation approach to meet that target.

**Related Requirements**: FR-2, FR-3

**Dependencies**: US-011
---

#### US-013: Inspect, Reclassify, Reject, and Persist Individual Detected Symbol Corrections
**Epic**: ML Symbol Detection & Interactive Review Canvas
**Priority**: Must-have
**Complexity**: Medium

**User Story**:
As a Process Safety Engineer,
I want to click any detected symbol to inspect its details, reclassify it to the correct entity class, or reject it as a false positive, with each correction saved automatically to the server,
So that I can correct ML errors that survive a page reload or session expiry and ensure no incorrect symbols enter the asset register or HAZOP template.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Inspect Symbol Details)**:
  - Given the drawing canvas is loaded with bounding box overlays and the drawing is in `Complete` or `Under_Review` state
  - When the Process Safety Engineer clicks a bounding box on the canvas
  - Then an inspection panel opens displaying the symbol's entity class, subtype, tag label (if extracted), confidence score (0.0–1.0), and the current correction status (Accepted / Rejected / Reclassified)

- **Scenario 2 (Reclassify Symbol to Different Entity Class)**:
  - Given the inspection panel is open for a selected symbol
  - When the Process Safety Engineer selects a different entity class from the predefined classification list and confirms the reclassification
  - Then the symbol's entity class updates to the newly selected value, the bounding box color updates on the canvas to reflect the new entity class, the results panel count adjusts for both the source and target entity classes, and the correction is persisted to the server; on reloading the canvas the reclassification is present in the same state

- **Scenario 3 (Reject Symbol as False Positive)**:
  - Given the inspection panel is open for a selected symbol
  - When the Process Safety Engineer marks the symbol as rejected
  - Then the symbol's status is set to Rejected, the bounding box is removed from the canvas view, the symbol is excluded from the extraction results panel count, the rejection is persisted to the server, and a save-confirmation indicator is briefly visible

- **Scenario 4 (Undo Rejection — Restore Symbol)**:
  - Given a symbol has previously been marked as Rejected and persisted, and the Process Safety Engineer locates it via the results panel filtered to show rejected symbols
  - When the Process Safety Engineer removes the rejection flag from that symbol
  - Then the symbol's status reverts to Accepted, its bounding box reappears on the canvas with the correct entity class color, the results panel count updates accordingly, and the restored state is persisted to the server

- **Scenario 5 (Predefined Classification List is Complete)**:
  - Given the inspection panel is open for reclassification
  - When the Process Safety Engineer opens the entity class selection control
  - Then the list contains all supported entity classes and valve subtypes as defined in FR-2 AC-2 (Pipe; Valve subtypes: Gate, Globe, Ball, Butterfly, Check, Control; Instrument), and no free-text class entry is permitted

- **Scenario 6 (Persistence Failure — Non-blocking Warning)**:
  - Given the server is unavailable when a correction action is completed
  - When the correction is attempted to be saved
  - Then the canvas and results panel reflect the correction in local state, a non-blocking inline warning is displayed indicating the correction could not be saved, and the system retains the local state for retry without interrupting the engineer's correction workflow

**Technical Notes**:
- Reclassification and rejection actions must each emit a `correction_action` analytics event (FR-16 AC-1) with the drawing ID and symbol ID in the payload.
- The predefined classification list must be sourced from the EntityClass reference data (Section 6 data model) rather than hardcoded in the frontend, so new classes added server-side are reflected without a frontend deploy.
- Each correction save sends the symbol ID, correction type, new classification (if applicable), and the resolved `training_consent` value (per ML consent rules in FR-13) at time of creation; the consent value must be snapshotted at correction time, not resolved lazily. Team-level consent resolution must be evaluated server-side.
- Training feedback gating (opted-in vs. opted-out, team-level override) is enforced server-side on the corrections endpoint; the `training_consent` flag on the persisted record must reflect the resolved value, not a client-supplied value.

**Related Requirements**: FR-3, FR-13

**Dependencies**: US-012, US-014
---

#### US-014: Manually Annotate Undetected Symbols as False Negative Corrections
**Epic**: ML Symbol Detection & Interactive Review Canvas
**Priority**: Must-have
**Complexity**: Medium

**User Story**:
As David, a Process Safety Engineer,
I want to draw a bounding box over any symbol the ML missed and assign it an entity class,
So that I can ensure no valve or instrument is absent from the final extraction output, which is critical for safety completeness in HAZOP preparation.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Draw and Classify a New Bounding Box)**:
  - Given the drawing canvas is in annotation mode, activated by a visible manual-annotation control
  - When David draws a rectangular bounding box over an undetected symbol on the canvas and selects an entity class from the predefined list
  - Then a new detected symbol record is created with the assigned entity class, a confidence score of 1.0 (indicating human-confirmed), a source of `manual`, and the bounding box is rendered on the canvas using the color matching the assigned entity class

- **Scenario 2 (Manually Added Symbol Appears in Results Panel)**:
  - Given a manually added symbol has been created with an entity class assignment
  - When David views the results panel
  - Then the manually added symbol appears in the list for its entity class, the total count for that class increments by one, and the symbol is visually distinguishable from ML-detected symbols (e.g., a distinct border style or label indicating manual origin)

- **Scenario 3 (Manually Added Symbol Can Be Inspected and Edited)**:
  - Given a manually added symbol exists on the canvas
  - When David clicks its bounding box
  - Then the inspection panel opens showing the entity class, `manual` source indicator, and an option to reclassify or delete the annotation; reclassifying updates the canvas overlay color; deleting removes the bounding box and decrements the results panel count

- **Scenario 4 (Annotation Mode Does Not Interfere with Navigation Mode)**:
  - Given the drawing canvas is in default navigation mode (pan and zoom)
  - When David has not activated the annotation mode control
  - Then drawing a drag gesture on the canvas performs a pan operation and does not create a bounding box; switching to annotation mode is a deliberate, explicit action via a dedicated UI control

- **Scenario 5 (Incomplete Bounding Box Is Discarded)**:
  - Given David has activated annotation mode and begun drawing a bounding box
  - When the drawn rectangle is smaller than a minimum viable area threshold (to prevent accidental single-click annotations)
  - Then the bounding box is discarded without creating a symbol record, and the canvas returns to annotation mode ready for the next draw action

**Non-Goal (Scope Boundary)**: Server-side persistence of manually added symbol records is explicitly out of scope for this story. All symbol creation and state changes described in the ACs above are local (in-memory / component state) only. Durable persistence to the server is owned by US-015. This story is not considered complete in isolation; it must be integrated with US-015 before manual annotations survive a page refresh.

**Technical Notes**:
- Manually added symbols must be stored as `DetectedSymbol` records with a `source` field set to `manual` to distinguish them from ML-generated detections in the data model and in export output (FR-4 AC-2).
- The minimum bounding box area threshold should be configurable server-side to allow tuning without a frontend deploy; a reasonable default is left to the Architecture Agent.
- Manual annotation actions must emit a `correction_action` analytics event (FR-16) with the drawing ID and the new symbol ID in the payload.
- Correction persistence is handled by US-015; this story covers canvas interaction, local state, and symbol record creation only.

**Related Requirements**: FR-3

**Dependencies**: US-012, US-015
---

#### US-015: Restore Corrections Across Sessions and Gate Training Feedback by ML Consent
**Epic**: ML Symbol Detection & Interactive Review Canvas
**Priority**: Must-have
**Complexity**: Medium

**User Story**:
As a Process Safety Engineer,
I want my corrections to be fully restored when I return to a drawing after a session expiry or browser crash, and to know that my drawing data is only used for ML training if I have explicitly consented,
So that I never lose validated work and my organisation's confidential P&ID data is protected from unauthorised use.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Corrections Survive Session Expiry and Re-Login)**:
  - Given the Process Safety Engineer's session expires during a review session
  - When the engineer re-authenticates within 24 hours and reopens the drawing canvas
  - Then all previously persisted corrections are restored on the canvas in the same state (reclassifications, rejections, manual annotations), with no correction data lost

- **Scenario 2 (Training Feedback Excluded for Opted-Out Users)**:
  - Given a Process Safety Engineer whose account or team has ML training data contribution set to opted-out (the default state per FR-13)
  - When that engineer performs any correction action (reclassify, reject, manual annotation)
  - Then the `UserCorrection` record is created and saved for the engineer's own review and export, the `training_consent` flag on the record is set to `false`, and the record is excluded from all ML training pipelines

- **Scenario 3 (Training Feedback Included for Opted-In Users)**:
  - Given a Process Safety Engineer whose account has ML training data contribution explicitly set to opted-in
  - When that engineer performs a correction action
  - Then the `UserCorrection` record is created with `training_consent` flag set to `true`, and the record is available to the ML training pipeline

- **Scenario 4 (Team-Level Consent Overrides Individual Preference)**:
  - Given the Process Safety Engineer belongs to a Team where the Team Admin has set the team-level training data contribution preference to opted-out
  - When the engineer performs a correction action regardless of any individual preference they may have previously set
  - Then the `UserCorrection` record is created with `training_consent` set to `false`, and the engineer cannot override the team-level setting from their individual account settings

**Technical Notes**:
- NFR-18 specifies a 2MB localStorage cap for unsaved correction state; the persistence layer must estimate payload size and flush to server proactively before approaching this threshold, not only on session expiry warning. Server-saved state takes precedence over localStorage if timestamps conflict on restore.
- Team-level consent resolution must be evaluated server-side to prevent client-side bypass; the resolved value is not a client-supplied field.
- Correction persistence failures (server unavailable) are surfaced as non-blocking inline warnings per US-013 Scenario 6; this story covers session-level restore fidelity and consent gating only.

**Related Requirements**: FR-3, FR-13

**Dependencies**: US-013, US-014

#### Requirements Needing Clarification

**US-011 — Processing Status Polling vs. Push Notification**
The PRD specifies in-app notification when processing completes (FR-2 AC-1) but does not define whether this is delivered via polling, WebSocket, or server-sent events. The choice affects whether the library page requires manual refresh or updates live. Architecture Agent should confirm the push mechanism before US-011 is built.

**US-012 — `Under_Review` State Transition Trigger**
Section 9 defines `Complete` → `Under_Review` when "user opens canvas and begins corrections," but does not specify whether opening the canvas alone triggers the transition or whether the first correction action is required. This distinction affects state reporting in the Drawing Library. Product Owner should confirm the trigger.

**US-014 — Tag Label Entry for Manually Added Symbols**
FR-3 AC-5 states users can add a bounding box and assign an entity class, but does not specify whether they can also manually enter a tag label (e.g., "FT-201") for the new symbol. If tag entry is supported, the inspection panel for manual annotations requires an additional input field. Product Owner should confirm scope for v1.

**US-015 — Correction Conflict Resolution for Team Drawings**
If two team members open the same drawing simultaneously (FR-10 allows all members to open any team drawing), the real-time persistence model may produce conflicting correction states. The PRD explicitly defers real-time collaborative editing (Section 14), but does not define a last-write-wins or conflict-detection behavior for near-simultaneous corrections. Architecture Agent should define the conflict resolution strategy before US-015 is built.
---

#### US-016: Export validated extraction results as CSV or XLSX download
**Epic**: Structured Data Export & Subscription Billing
**Priority**: Must-have
**Complexity**: Medium

**User Story**:
As Priya, an Instrumentation Engineer,
I want to export my validated extraction results as a CSV or XLSX file,
So that I can import the structured symbol data directly into our asset register or HAZOP template without manual transcription.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — CSV export)**:
  - Given Priya has a drawing in `Complete` or `Under_Review` state with at least one non-rejected detected symbol
  - When she selects CSV format and initiates the export action
  - Then the system generates a CSV file and delivers a pre-signed download URL within 30 seconds, and the file contains one row per non-rejected symbol with columns: entity class, subtype, tag label, bounding box coordinates, confidence score, drawing filename, and revision identifier

- **Scenario 2 (Happy Path — XLSX export)**:
  - Given Priya has a drawing in `Complete` state with multi-page PDF content
  - When she selects XLSX format and initiates the export action
  - Then the system delivers a pre-signed download URL within 30 seconds, and the XLSX file contains a consolidated sheet with a page/sheet identifier column for each symbol row

- **Scenario 3 (Export unavailable in ineligible state)**:
  - Given a drawing is in `Processing`, `Queued`, or `Failed` state
  - When Priya navigates to the drawing detail view
  - Then the export action is not available and the page displays a status-appropriate message explaining why export is unavailable

- **Scenario 4 (Re-export after corrections)**:
  - Given Priya has previously exported a drawing and has since made additional corrections to detected symbols
  - When she initiates a new export
  - Then the system generates a new export file reflecting the current correction state and delivers a new pre-signed download URL; the previous export file remains accessible

- **Scenario 5 (Export from Under_Review state)**:
  - Given Priya has a drawing in `Under_Review` state with corrections in progress
  - When she initiates an export
  - Then the system exports all currently non-rejected symbols (including any corrections saved to that point) and delivers a pre-signed download URL within 30 seconds

- **Scenario 6 (Drawing exceeds synchronous threshold)**:
  - Given a drawing has more than 1,000 detected symbols
  - When Priya initiates an export
  - Then the system does not attempt synchronous generation; instead it queues the export asynchronously and displays an in-app message informing her that the download will be ready shortly (handled fully in US-017)

**Technical Notes**:
- Export action must emit the `export_initiated` analytics event (FR-16) including drawing ID, export format, and user ID at the moment the action is triggered; `export_downloaded` must be emitted when the pre-signed URL is accessed.
- Pre-signed URL expiry window to be determined by Architecture Agent; the URL must remain valid long enough for the user to initiate a download within the same session.
- An `ExportRecord` entity must be created per export attempt, linked to the Drawing and User, with a reference to the generated `StoredFile`; this supports the re-export history requirement and the 2-year retention policy from the data model.
- For multi-page PDFs, the page/sheet identifier column value should correspond to the source page index (1-based) of the drawing from which the symbol was detected.

**Related Requirements**: FR-4, FR-16

**Dependencies**: US-011 (ML processing and symbol detection must be complete), US-013 (interactive review and correction state must be persisted)

---

#### US-017: Queue and deliver asynchronous export for large drawings and support re-export
**Epic**: Structured Data Export & Subscription Billing
**Priority**: Must-have
**Complexity**: Medium

**User Story**:
As Priya, an Instrumentation Engineer,
I want large drawing exports to be generated in the background and delivered as a notification when ready,
So that I can continue working in the application without waiting for a slow export to complete.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — async export queued)**:
  - Given Priya has a drawing with more than 1,000 detected symbols in `Complete` state
  - When she initiates an export in either CSV or XLSX format
  - Then the system queues the export job, immediately displays an in-app notification confirming the export is being prepared, and does not block further navigation or interaction

- **Scenario 2 (In-app notification on export ready)**:
  - Given an asynchronous export job has completed successfully
  - When Priya is viewing any page within the application
  - Then the page displays an in-app notification indicating the export is ready, and the notification contains a download link that delivers the file

- **Scenario 3 (Download link accessibility)**:
  - Given an asynchronous export has completed and Priya clicks the download link in the notification
  - When the pre-signed URL is accessed
  - Then the file downloads successfully and the `export_downloaded` analytics event is emitted

- **Scenario 4 (Async export failure)**:
  - Given an asynchronous export job encounters a generation error
  - When the job fails
  - Then the in-app notification updates to indicate the export failed and presents a retry action; the previously accessible export file (if any) is unaffected

- **Scenario 5 (Re-export does not overwrite prior export)**:
  - Given Priya has a completed async export for a drawing
  - When she initiates a second export of the same drawing after making corrections
  - Then both the original export file and the new export file are independently accessible; the new export reflects the updated correction state

**Technical Notes**:
- The async export job must be processed by a persistent, durable queue (per NFR-7) so that in-flight export jobs survive server restarts without loss.
- The 1,000-symbol threshold for triggering async vs. synchronous export (FR-4 AC-3) must be evaluated server-side at job creation time, not client-side, to prevent bypass.
- Each async export generates a new `ExportRecord` with status (`Queued` / `Generating` / `Complete` / `Failed`) and a linked `StoredFile` reference on completion; status polling or a push mechanism (WebSocket or server-sent event) is required to drive the in-app notification — Architecture Agent to select the delivery mechanism.
- `export_initiated` analytics event must be emitted when the async job is enqueued (not when it completes).

**Related Requirements**: FR-4, FR-16

**Dependencies**: US-016

---

#### US-018: Enforce Free Tier Processing Limit and Display Upgrade Prompt
**Epic**: Structured Data Export & Subscription Billing
**Priority**: Must-have
**Complexity**: Medium

**User Story**:
As Priya, an Instrumentation Engineer on the Free tier,
I want to be clearly informed when I have reached my monthly processing limit and shown a path to upgrade,
So that I understand my options and can continue working without confusion about why my drawing was blocked.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — within Free tier limit)**:
  - Given Priya is on the Free tier and has processed fewer than 3 drawings in the current calendar month
  - When she uploads a new drawing and initiates ML processing
  - Then the drawing is queued for processing normally and her remaining processing slots for the month are visible in the UI

- **Scenario 2 (Free tier limit reached — processing blocked)**:
  - Given Priya is on the Free tier and has already processed 3 drawings in the current calendar month
  - When she attempts to initiate ML processing on a 4th drawing
  - Then the system blocks the processing action, emits the `free_limit_reached` analytics event, and displays an upgrade prompt that includes current pricing information for Pro and Team tiers; the uploaded drawing file is retained so she does not need to re-upload after upgrading

- **Scenario 3 (In-progress job at moment of limit)**:
  - Given Priya's 3rd Free tier processing job is currently in-progress when the monthly counter reaches its limit
  - When that job is actively being processed
  - Then the in-progress job is allowed to complete; only subsequent new processing initiations are blocked

- **Scenario 4 (Monthly counter reset)**:
  - Given Priya is on the Free tier and has processed 3 drawings in a calendar month
  - When the calendar month rolls over (1st of the following month, UTC)
  - Then her processing counter resets to 0 and she can initiate processing on new drawings without an upgrade prompt

- **Scenario 5 (Tier-gated features visible but inaccessible)**:
  - Given Priya is on the Free tier and views the drawing library or navigation menu
  - When Pro/Team-only features (revision comparison, team library) are displayed
  - Then those features are visually indicated as tier-gated and present an upgrade call-to-action when Priya attempts to interact with them; they are never silently hidden

**Technical Notes**:
- The Free tier counter must be evaluated against calendar month boundaries in UTC; the counter increment must occur at the point processing is initiated (job enqueued), not at job completion, to prevent race conditions from concurrent uploads.
- The monthly counter and remaining slots must be surfaced via an API endpoint that the frontend queries on the drawing library and upload views; this value must not be derived solely from client-side state.
- The `free_limit_reached` event payload must include user ID, drawing ID (of the blocked drawing), and the timestamp; this event is required for the Free-to-Paid Conversion success metric (Section 15).
- Tier-gated feature visibility rules (Scenario 5) must be driven by a server-returned feature flag set on session, not hardcoded client-side, to allow tier changes to take effect without a page reload.

**Related Requirements**: FR-9, FR-16

**Dependencies**: US-001, US-002 (authenticated user with active session required to evaluate subscription state); US-019 (upgrade prompt navigates to the upgrade flow introduced by US-019; this story is blocked until US-019 provides a reachable upgrade entry point)

> **Note to Orchestrator**: The suggested fix for US-018 directed the change to US-025 (adding a Free tier access attempt and upgrade CTA scenario consistent with Scenario 5 here). US-018 itself is complete as written; no modification to this story is required. The US-025 author must add the corresponding scenario when that story is written or refined.
---

#### US-019: Upgrade and Downgrade Subscription Tier with Stripe Integration
**Epic**: Structured Data Export & Subscription Billing
**Priority**: Must-have
**Complexity**: Large

**User Story**:
As Marcus, a CAD/Document Control Manager and Team Admin,
I want to upgrade our team's subscription to Pro or Team tier from within the application and downgrade when needed,
So that I can provision the correct access level for my engineering team in time for project milestones without leaving the product to manage billing through an external portal.

> **Persona rationale**: Subscription upgrade and downgrade is a billing-owner action. Marcus is the Team Admin responsible for managing the drawing library and team access; he is the natural owner of billing decisions on behalf of a team. David (Process Safety Engineer) may trigger the upgrade prompt but would escalate billing authority to Marcus or a department manager rather than completing the purchase himself. Individual engineers such as Priya may upgrade personal Pro seats autonomously, but the Team tier seat-count scenario (AC-2) is unambiguously an admin action.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — Upgrade to Pro Tier)**:
  - Given Marcus is on the Free tier and initiates an upgrade to Pro from within the application
  - When he completes the Stripe-hosted payment flow with valid payment details and is redirected back to the application
  - Then the page displays a pending subscription state indicating the upgrade is being confirmed, the state resolves to Pro tier within 30 seconds as the Stripe webhook is received, unlimited processing becomes available, and the `subscription_upgraded` analytics event is emitted with subscription ID and new tier

- **Scenario 2 (Happy Path — Upgrade to Team Tier with Seat Count)**:
  - Given Marcus is on the Free tier and selects the Team tier upgrade option
  - When he specifies a seat count, completes the Stripe payment flow, and is redirected back to the application
  - Then the page displays a pending subscription state, which resolves to Team tier once the webhook is received; the team workspace becomes accessible and the licensed seat count is enforced per FR-9 AC-6

- **Scenario 3 (Pending State Timeout — Webhook Not Received Within 30 Seconds)**:
  - Given Marcus has completed the Stripe payment flow and been redirected back to the application
  - When 30 seconds elapse without the application receiving the corresponding Stripe webhook
  - Then the pending state resolves to a fallback message informing Marcus that his payment was received but tier activation may take a few minutes, prompting him to refresh; the subscription tier is not prematurely changed in either direction

- **Scenario 4 (Downgrade — Deferred to End of Billing Period)**:
  - Given Marcus is on the Pro tier and initiates a downgrade to Free
  - When the downgrade is confirmed
  - Then the system schedules the downgrade to take effect at the end of the current billing period; Marcus retains Pro tier access until that date; the `subscription_downgraded` analytics event is emitted immediately at confirmation

- **Scenario 5 (Post-Downgrade Data and Access Behavior)**:
  - Given Marcus's subscription has downgraded to Free at the end of the billing period
  - When he next accesses the application
  - Then all previously processed drawings and extraction data are retained and accessible; new processing jobs are subject to the Free tier monthly limit; Marcus is shown his remaining free processing slots

- **Scenario 6 (Stripe Payment Failure During Upgrade)**:
  - Given Marcus is attempting to upgrade and Stripe returns a payment failure (e.g., card declined)
  - When the Stripe payment flow returns an error
  - Then the page displays a descriptive payment error message, the subscription tier is not changed, and Marcus is prompted to retry with updated payment details

**Technical Notes**:
- Stripe Checkout or Stripe Billing Portal must be used for the payment flow; the subscription state in the application database must be updated exclusively via Stripe webhook events (not inline after the payment redirect) to ensure consistency and idempotency.
- After Checkout redirect, the application must enter a pending subscription state and poll for tier resolution (suggested interval: 3 seconds) until the webhook-triggered update is detected or the 30-second timeout elapses; the polling endpoint should return the current resolved tier without side effects.
- The application must handle the `checkout.session.completed` and `customer.subscription.updated` Stripe webhook events to apply tier changes; webhook handlers must be idempotent (per FR-15 AC-4).
- Seat count for Team tier must be stored on the `Subscription` entity and enforced server-side at invite time (FR-10 AC-1); the seat count value originates from the Stripe subscription metadata or quantity field — Architecture Agent to define the mapping.
- `subscription_upgraded` and `subscription_downgraded` analytics events must include: user ID, previous tier, new tier, subscription ID, and timestamp.

**Related Requirements**: FR-9, FR-15, FR-16

**Dependencies**: US-001, US-002 (authenticated user with active session required before subscription state can be read or modified); US-018 (upgrade prompt entry point that routes users to this flow)
---

#### US-020: Handle Stripe payment failure grace period and cancellation webhook events
**Epic**: Structured Data Export & Subscription Billing
**Priority**: Must-have
**Complexity**: Medium

**User Story**:
As David, a Process Safety Engineer,
I want the system to give me time to resolve a failed payment before my access is affected, and to accurately reflect my subscription state when I cancel,
So that a transient billing issue does not interrupt an active HAZOP preparation session and I retain access for the period I have already paid for.

**Acceptance Criteria**:
- **Scenario 1 (Happy Path — payment failure enters grace period)**:
  - Given David has an active Pro subscription and Stripe sends an `invoice.payment_failed` webhook event
  - When the webhook is received and processed
  - Then the system sets the subscription billing state to `Grace`, David retains full Pro tier access, and an email notification is sent to his registered address on day 1 of the grace period

- **Scenario 2 (Grace period reminder on day 6)**:
  - Given David's subscription is in `Grace` state and 6 days have elapsed since the payment failure
  - When the scheduled grace period check runs
  - Then a second email notification is sent to David's registered address reminding him that access will be restricted if payment is not resolved

- **Scenario 3 (Grace period expires — downgrade to Free)**:
  - Given David's subscription has been in `Grace` state for 7 days without a successful payment
  - When the grace period expiry job runs
  - Then the subscription is downgraded to Free tier; existing drawings and extraction data are retained; new processing jobs are subject to the Free tier limit; David is shown a notification in-app explaining the access change and directing him to update payment details

- **Scenario 4 (Payment resolved during grace period)**:
  - Given David's subscription is in `Grace` state and Stripe sends a `invoice.payment_succeeded` webhook event
  - When the webhook is received and processed
  - Then the subscription billing state is reset to `Active`, David's full Pro access continues uninterrupted, and no further grace period notifications are sent

- **Scenario 5 (Subscription cancellation — access until period end)**:
  - Given David has cancelled his Pro subscription via Stripe and Stripe sends a `customer.subscription.deleted` or `customer.subscription.updated` (cancel_at_period_end) webhook event
  - When the webhook is received and processed
  - Then the system does not immediately downgrade access; David retains Pro tier access until the end of the current paid billing period; the application displays a banner indicating when access will change

- **Scenario 6 (Duplicate webhook — idempotent handling)**:
  - Given Stripe delivers the same `invoice.payment_failed` webhook event more than once (retry delivery)
  - When the duplicate event is received
  - Then the system recognises the event has already been processed (by Stripe event ID) and takes no further action; the grace period start date and notification state are not reset

**Technical Notes**:
- Grace period day-1 and day-6 email notifications must be delivered via the transactional email integration (SendGrid per Section 8); notification scheduling should use a durable scheduler (e.g., delayed job or cron) rather than in-process timers to survive restarts.
- Idempotency must be enforced by storing the Stripe event ID on first receipt and checking for existence before processing; duplicate events must return a 200 response to Stripe to prevent re-delivery loops.
- The `Grace` billing state must be a first-class value on the `Subscription` entity (alongside `Active` and `Canceled`); the feature-gate evaluation logic in US-018 and US-019 must account for `Grace` state (full access retained during grace period).
- The security file hash blocklist (FR-17) must be explicitly decoupled from subscription state transitions; a blocklist entry created during a `Grace` or `Canceled` period must persist unchanged regardless of subsequent subscription state changes (FR-15 AC-5).

**Related Requirements**: FR-15, FR-16

**Dependencies**: US-019 (subscription entity and Stripe integration established)

#### Requirements Needing Clarification

**US-017 — In-app notification delivery mechanism**: FR-4 AC-3 states the system "notifies the user in-app when the download is ready" but does not specify whether the notification is push-based (WebSocket, server-sent events) or poll-based (periodic API polling). If the user navigates away and returns, the notification must still be surfaced. The delivery mechanism affects architecture choices; the Architecture Agent should specify the approach, and the UX Agent should confirm expected notification placement (toast, notification bell, banner).

**US-019 — Stripe flow type (Checkout vs. Billing Portal)**: The PRD specifies Stripe as the billing integration but does not clarify whether users manage subscriptions via Stripe-hosted Checkout/Customer Portal (redirecting away from the app) or via an embedded Stripe Elements form. This affects how Scenario 5 (payment failure during upgrade) is experienced and where the error message surfaces. The product owner should confirm the preferred Stripe integration pattern before the billing UI is built.

**US-020 — Grace period clock start event**: FR-15 AC-1 states the 7-day grace period begins "on payment failure" but does not clarify whether the clock starts on the first `invoice.payment_failed` event or after Stripe has exhausted its own retry schedule (typically 3–4 attempts over several days). If the grace period begins after Stripe retries, the effective user-facing window is 7 days post-Stripe-retry; if it begins on first failure, Stripe retries and the application grace period run concurrently, which may reduce the user's effective window. The product owner should confirm the intended trigger point.
### Team Workspace, Shared Library & Instrument Table Extraction (Should-have for v1.0)
**Requirements Covered**: FR-7, FR-8, FR-10
**Description**: Extends the platform for multi-user team workflows: shared drawing library with Admin/Member roles, seat-limited email invitations, member removal with drawing reassignment. Also adds P1 ML capabilities — instrument table detection and extraction with in-canvas cell editing — and revision comparison with spatial/tag matching, change highlighting, and CSV export of diffs.
**User Stories**: US-021 – US-025

---

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