# 0. Platform Declaration

**Platform**: Web App
**Platform Rationale**: A web application provides platform-agnostic access for engineering teams working across different OS environments and removes the friction of local software installation for large DWG/PDF file processing.
**Platform Assumptions**: Web = responsive desktop-primary (1280px+ optimized); no PWA or offline mode required; file processing performed server-side; no mobile breakpoint support in v1; REST API backend consumed by browser SPA frontend.

---

## 1. Executive Summary (PRD Only)
PID Analyzer is a web application that uses machine learning to automatically identify and extract pipes, valves, and instrument tables from Process and Instrumentation Diagram (P&ID) files uploaded in PDF or AutoCAD DWG format. It is built for process engineers and instrumentation teams in oil & gas, chemical, and industrial facilities who currently spend days manually digitizing P&ID drawings into structured data. By automating symbol recognition and extraction, PID Analyzer eliminates the "Manual Digitization Trap" and reduces the time to produce structured P&ID data from days to minutes, enabling downstream tasks such as asset management, HAZOP studies, and equipment inventories to begin sooner.

---

## 2. Problem Statement (PRD Only)
**The Manual Digitization Trap**
Engineers receive P&ID drawings as PDFs or DWG files and must manually identify, count, and catalog every valve, pipe segment, and instrument tag in a spreadsheet. A single P&ID sheet can contain hundreds of symbols. This process takes 4–16 hours per drawing sheet and introduces human error rates of 5–15%.

**The Version Confusion Problem**
P&IDs are revised frequently during the design lifecycle. Engineers lose track of which revision was last digitized, resulting in duplicate work and inconsistent asset registers when a newer revision replaces an older one.

**The Tool Fragmentation Problem**
Engineers switch between AutoCAD (to view DWGs), Adobe Acrobat (to view PDFs), and Excel (to record data) to complete a single digitization task. There is no unified workspace for viewing, extracting, and validating P&ID data.

**Why existing solutions are inadequate:**
- **AutoCAD Electrical / Plant 3D**: Requires the original editable DWG source file with intelligence embedded; does not process scanned or exported PDFs and costs $3,000+/seat/year
- **SmartPlant P&ID (Hexagon)**: Enterprise-only ($100K+ deployment), requires weeks of configuration, and targets new-build projects — not existing drawing libraries
- **PDF extraction tools (Adobe Acrobat, Bluebeam)**: Extract text only; cannot recognize vector engineering symbols (valves, sensors, actuators)
- **Manual Excel templates**: Unscalable, error-prone, and provide no visual confirmation that the correct symbol was identified
- **General-purpose ML vision tools (AWS Rekognition, Google Vision)**: Not trained on engineering P&ID symbol sets; produce high error rates on domain-specific notation

---

## 3. Goals & Objectives (PRD Only)
**Business Goals** (stack-ranked):
- Achieve 60+ paying engineering teams within 12 months of launch, validating willingness to pay for automated P&ID digitization
- Reach ≥ 70% annual subscription renewal rate by providing measurable time savings that justify per-seat pricing
- Establish ML model accuracy (≥ 85% symbol recognition F1-score) as primary competitive moat within 6 months of launch
- Generate sufficient labeled extraction data from user corrections to continuously improve ML model accuracy without additional manual labeling cost

**User Goals** (stack-ranked by frequency × pain severity):
- "I want to upload a P&ID drawing and receive a structured list of all valves, pipes, and instruments in under 10 minutes, without manual counting"
- "I want to visually confirm which symbols were detected and correct any misidentifications before exporting"
- "I want to export the structured data to CSV or Excel so I can import it into our asset register or HAZOP template"
- "I want to manage multiple drawing revisions and know which version was last processed"

---

## 4. Target Audience

**Persona 1 — Priya, Instrumentation Engineer**
Mid-career engineer (32–45) at an EPC contractor or operating company, working on brownfield P&ID digitization projects for plant expansions or safety studies.
- **Pain Points**: Spends 2–3 days per project manually counting instruments across 20–50 drawing sheets; frequently finds errors after submission; has no budget for enterprise software
- **Usage Pattern**: Project-triggered, 2–5 sessions per week, 30–90 min per session; session begins when a new drawing revision arrives from the client
- **Willingness to Pay**: $50–$150/month per seat; decision driven by billable-hour savings on digitization tasks

**Persona 2 — David, Process Safety Engineer**
Senior engineer (40–55) at a chemical manufacturer or refinery, responsible for HAZOP facilitation and P&ID accuracy verification before safety reviews.
- **Pain Points**: Cannot start a HAZOP study until the P&ID is fully digitized; current manual process delays HAZOP preparation by 1–2 weeks; needs high confidence in completeness (missed valves create safety risk)
- **Usage Pattern**: Event-triggered (pre-HAZOP, pre-PSSR), 1–3 sessions per week during study preparation phase, 60–120 min per session
- **Willingness to Pay**: $150–$400/month; decision driven by compliance urgency and risk reduction, approved at team/department level

**Persona 3 — Marcus, CAD/Document Control Manager** *(Secondary)*
Document controller (35–50) at an EPC or owner-operator, responsible for managing drawing libraries and ensuring revision tracking across hundreds of P&ID sheets.
- **Pain Points**: No automated way to detect what changed between two P&ID revisions; manually comparing drawings sheet-by-sheet; responsible for accuracy but not an engineer
- **Usage Pattern**: Ongoing, 3–5 sessions per week, 15–30 min per session for upload and status review
- **Willingness to Pay**: $30–$80/seat/month; decision typically bundled with team license

---

## 5. Functional Requirements
### P0 — Must Have for MVP

**FR-1: Upload P&ID Drawing File**
- **Description**: Users upload a PDF or AutoCAD DWG file containing a P&ID drawing. Addresses the "Tool Fragmentation Problem" by providing a single entry point regardless of source file format.
- **Priority**: P0
- **Category**: File Ingestion
- **Acceptance Criteria**:
  1. System accepts PDF (single or multi-page) and DWG (AutoCAD 2010–2024 format) file uploads via drag-and-drop or file browser
  2. System rejects files exceeding 100MB with a user-visible error message specifying the limit
  3. System rejects non-PDF, non-DWG file types and displays a descriptive error naming the accepted formats
  4. Upload progress is visible to the user in real time until server acknowledgment is received
  5. System generates a unique Drawing record upon successful upload and associates it with the authenticated user's account
  6. System detects raster-only PDF uploads (no vector geometry) and displays a descriptive error explaining that scanned PDFs are not supported; for multi-page PDFs with mixed vector/raster pages, raster pages are skipped and the user is notified of which pages were excluded
- **Related Learnings / Rationale**: Priya's workflow alternates between client-supplied PDFs and DWG exports; supporting both formats removes a gatekeeping step that would otherwise cause her to abandon the tool.

---

**FR-2: ML-Based Symbol Detection & Extraction**
- **Description**: The system automatically analyzes the uploaded vector drawing using ML and identifies all pipes (line segments), valves (standard ISA 5.1 symbols), and instrument bubbles/tags. Directly solves the "Manual Digitization Trap" — the core value proposition.
- **Priority**: P0
- **Category**: ML Processing
- **Acceptance Criteria**:
  1. System initiates ML processing automatically upon successful file upload and notifies the user when processing is complete
  2. System detects and classifies pipes (line segments), valves (gate, globe, ball, butterfly, check, and control valve types), and instrument bubbles as separate entity classes
  3. System achieves ≥ 85% F1-score on symbol detection measured against both the internal test dataset and a held-out external customer dataset of ≥ 20 real P&ID drawings from ≥ 3 companies; both thresholds must be met before FR-2 is considered complete
  4. Each detected symbol is assigned a confidence score (0.0–1.0) visible to the user
  5. System processes a single A1-size drawing sheet containing ≤ 500 symbols in ≤ 10 minutes; when a drawing is estimated to contain > 500 symbols, the user is warned before processing begins that extended processing time may apply and the 10-minute SLA does not apply
  6. System surfaces a processing failure status with a user-visible error if ML inference does not complete within 20 minutes
- **Related Learnings / Rationale**: David's HAZOP preparation requires completeness confidence; the confidence score and F1 target are the minimum signals needed for him to trust the output without re-checking manually.

---

**FR-3: Interactive Extraction Review & Correction**
- **Description**: Users view the drawing with detected symbols overlaid as bounding boxes or highlights, and can accept, reject, or reclassify individual detections. Addresses the "Manual Digitization Trap" error-correction gap and enables human-in-the-loop validation for high-stakes use cases.
- **Priority**: P0
- **Category**: Review & Validation
- **Acceptance Criteria**:
  1. Detected symbols are overlaid on the drawing canvas with color-coded bounding boxes differentiated by entity class (pipe, valve, instrument)
  2. User can click a detected symbol to view its classification, confidence score, and tag/label (if extracted)
  3. User can reclassify a detected symbol to a different entity class from a predefined list
  4. User can mark a detected symbol as rejected (false positive), removing it from the extraction output
  5. User can manually add a bounding box over an undetected symbol and assign it an entity class (false negative correction)
  6. All user corrections are saved in real time and persist across browser sessions
  7. Correction actions are recorded as labeled training feedback only for users and teams who have explicitly opted in to ML training data contribution (see FR-13); corrections from opted-out users are saved for their own review but are excluded from model training pipelines
- **Related Learnings / Rationale**: Priya's 5–15% manual error rate concern means she will not trust a tool that offers no correction mechanism; David's safety context makes false negatives (missed valves) unacceptable without a manual fallback.

---

**FR-4: Structured Data Export**
- **Description**: Users export the validated extraction results as a structured CSV or Excel file containing entity class, tag, location, confidence score, and revision metadata per detected symbol. Solves the final step of the "Tool Fragmentation Problem" by eliminating manual transcription into spreadsheets.
- **Priority**: P0
- **Category**: Export
- **Acceptance Criteria**:
  1. System exports all non-rejected detected symbols to CSV and XLSX formats, selectable by the user
  2. Each exported row includes: entity class, subtype, tag label (if detected), bounding box coordinates, confidence score, drawing filename, and revision identifier
  3. Export file is delivered as a pre-signed download URL available within 30 seconds of the user initiating the export action for drawings with ≤ 1,000 symbols; for larger drawings, the system queues generation asynchronously and notifies the user in-app when the download is ready
  4. Multi-page PDF drawings export a single consolidated file with a sheet/page identifier column
  5. User can re-export after making corrections without losing the previous export file
- **Related Learnings / Rationale**: Both Priya and David's downstream tasks (asset register, HAZOP template) are spreadsheet-based; providing XLSX directly eliminates a conversion step that currently fragments the workflow.

---

**FR-5: User Authentication & Account Management**
- **Description**: Users register, log in, and manage their accounts with secure session handling. Required to associate drawings, corrections, and export history with individual users and enforce subscription tier limits.
- **Priority**: P0
- **Category**: Authentication
- **Acceptance Criteria**:
  1. Users register with email and password; email verification is required before first upload is permitted
  2. Users log in with email/password; OAuth login via Google is supported; if a Google OAuth email matches an existing password-registered account, the system prompts the user to link the accounts rather than creating a duplicate or silently merging
  3. Sessions expire after 8 hours of inactivity and redirect the user to the login page with a session-expiry message
  4. Users can reset their password via a time-limited email link (link expires in 24 hours); all active sessions are invalidated on password reset
  5. Users can update their display name and email address from account settings
  6. After 5 consecutive failed login attempts for a given email, the account is locked for 15 minutes; the user is notified via the login UI
- **Related Learnings / Rationale**: Marcus's document control role requires individual attribution of who uploaded or modified a drawing; session management and account identity are prerequisites for the audit trail needed in his compliance context.

---

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

**FR-14: Account Deletion & GDPR Erasure**
- **Description**: Users can permanently delete their account, triggering removal of PII within 30 days and anonymization of retained records that have independent retention value (billing, model training).
- **Priority**: P0
- **Category**: Compliance
- **Acceptance Criteria**:
  1. Account deletion is accessible from account settings and requires password confirmation before executing
  2. On deletion, user PII (email, name, password hash) is purged within 30 days via an automated scheduled job
  3. UserCorrection records attributed to the deleted user are anonymized (user ID replaced with a non-reversible anonymous ID) rather than deleted, preserving training utility while removing re-identifiability; anonymization occurs within 30 days
  4. ExportRecord and audit log entries retain the action and entity IDs but replace user-identifying fields with the anonymous ID
  5. Drawing files uploaded solely by the deleted user (no team context) are permanently deleted from object storage within 30 days; drawings in a team library are retained under team ownership
- **Related Learnings / Rationale**: NFR-10 mandates GDPR right-to-erasure; UserCorrections retained 5 years for training value must be anonymized rather than deleted to satisfy both the retention policy and erasure right simultaneously.

---

**FR-15: Subscription Billing State & Payment Failure Handling**
- **Description**: The system handles Stripe webhook events for payment failures, subscription cancellations, and renewals, applying grace periods and user notifications to prevent abrupt access loss.
- **Priority**: P0
- **Category**: Billing & Access Control
- **Acceptance Criteria**:
  1. On payment failure, the system enters a 7-day grace period during which the user retains full access; the user receives an email notification on day 1 and day 6 of the grace period
  2. If payment is not resolved within the grace period, the subscription downgrades to Free tier; existing drawings and data are retained per FR-9 AC-5
  3. On subscription cancellation via Stripe webhook, access continues until the end of the paid billing period; the system does not downgrade immediately
  4. Stripe webhook events are idempotent; duplicate webhook delivery for the same event does not result in duplicate state changes
  5. A quarantine file hash blocklist entry is permanent and cannot be cleared by subscription state changes
- **Related Learnings / Rationale**: FR-9 references Stripe but defines no failure handling; a failed payment with no grace period immediately locks paying users out; a missing webhook handler silently keeps canceled users active.

---

**FR-16: Analytics Event Instrumentation**
- **Description**: The system emits structured analytics events for all user actions required to measure the Section 15 success metrics.
- **Priority**: P0
- **Category**: Observability
- **Acceptance Criteria**:
  1. The following named events are emitted with timestamp and user ID on each occurrence: `drawing_uploaded`, `processing_complete`, `processing_failed`, `correction_action`, `export_initiated`, `export_downloaded`, `free_limit_reached`, `subscription_upgraded`, `subscription_downgraded`
  2. Each event payload includes the relevant entity ID (drawing ID, export record ID, subscription ID) in addition to timestamp and user ID
  3. Events are delivered to the analytics pipeline within 5 seconds of the triggering user action
  4. Event emission failures do not cause the triggering user action to fail; analytics delivery is best-effort and non-blocking
- **Related Learnings / Rationale**: Section 15 success metrics are unmeasurable without these specific named events; making this a P0 FR ensures instrumentation is implemented alongside features rather than deferred.

---

**FR-17: Security File Hash Blocklist**
- **Description**: The system maintains a blocklist of quarantined file hashes and permanently rejects re-uploads of any file matching a blocked hash.
- **Priority**: P0
- **Category**: Security
- **Acceptance Criteria**:
  1. On `Scan_Failed`, the SHA-256 hash of the rejected file is recorded in a persistent blocklist
  2. At upload time, the system computes the SHA-256 hash of the incoming file and rejects it with a security error if the hash matches any blocklist entry, before the file is written to object storage
  3. The rejection message does not expose the reason (malware detection) or blocklist contents to the user
  4. Blocklist entries are permanent and cannot be removed via the user interface
- **Related Learnings / Rationale**: Section 9 prohibits retry for Scan_Failed drawings but no mechanism prevents re-upload of the identical file under a different filename.

---

### P1 — Should Have for v1.0

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

**FR-11: API Access for Programmatic Integration**
- **Description**: Expose a REST API that allows external systems (asset management platforms, HAZOP tools) to submit drawings and retrieve extraction results programmatically.
- **Priority**: P2
- **Category**: Integration
- **Acceptance Criteria**:
  1. API supports authenticated file submission, processing status polling, and results retrieval
  2. API returns results in JSON matching the export data schema
  3. API rate limits are enforced per API key per subscription tier

**FR-12: Custom Symbol Library Training**
- **Description**: Users upload a set of custom or non-ISA symbols with labels to fine-tune the ML model for company-specific or regional P&ID conventions.
- **Priority**: P2
- **Category**: ML Configuration
- **Acceptance Criteria**:
  1. User can upload a minimum of 20 labeled symbol examples per custom class
  2. System fine-tunes the detection model and makes the custom class available within 48 hours
  3. Custom symbol classes appear alongside standard classes in the review and correction interface

---
## 6. Conceptual Data Model
| Entity | Relationships | PII? | Retention |
|---|---|---|---|
| User | HAS-MANY Drawings (personal); BELONGS-TO Team (optional); HAS-ONE Subscription | Yes — email, name | Account lifetime + 30 days post-deletion; PII purged within 30 days of deletion |
| Team | HAS-MANY Users; HAS-MANY Drawings (shared library) | No | Account lifetime + 30 days post-deletion |
| Subscription | BELONGS-TO User or Team; HAS-ONE active Tier; HAS-ONE billing state (Active / Grace / Canceled) | No | 7 years (billing records) |
| Tier | HAS-MANY Subscriptions; defines limits, seat counts, and feature gates | No | Indefinite |
| Drawing | BELONGS-TO User or Team; HAS-MANY DetectedSymbols; HAS-MANY Revisions; HAS-ONE StoredFile | No | User-controlled; deletion removes all child entities — deletion dependency, see Architecture |
| Revision | BELONGS-TO Drawing; HAS-MANY DetectedSymbols | No | Inherits from Drawing |
| StoredFile | BELONGS-TO Drawing (source file) or ExportRecord (generated file); holds object storage bucket reference and SHA-256 hash | No | Inherits from parent Drawing or ExportRecord; hash retained in FileHashBlocklist on Scan_Failed |
| FileHashBlocklist | Standalone; stores SHA-256 hashes of quarantined files | No | Permanent |
| DetectedSymbol | BELONGS-TO Drawing; HAS-ONE EntityClass; HAS-MANY UserCorrections | No | Inherits from Drawing |
| EntityClass | HAS-MANY DetectedSymbols; defines taxonomy (Pipe, Valve subtype, Instrument) | No | Indefinite |
| UserCorrection | BELONGS-TO DetectedSymbol; BELONGS-TO User (nullable after anonymization); flagged with training_consent at time of creation | No | 5 years; user ID anonymized within 30 days of account deletion — see Architecture for anonymization job |
| MLTrainingConsent | BELONGS-TO User or Team; records opt-in/opt-out state and timestamp | No | Account lifetime + 30 days |
| ExportRecord | BELONGS-TO Drawing; BELONGS-TO User (nullable after anonymization); HAS-ONE StoredFile | No | 2 years |

---
## 7. Non-Functional Requirements
#### Universal

**NFR-1: Page Load Performance**
- **Category**: Performance
- Primary drawing review canvas loads in < 3 seconds at P95 on a 100Mbps desktop connection; initial dashboard (Drawing Library) loads in < 2 seconds at P95

**NFR-2: ML Processing Throughput**
- **Category**: Performance
- Single A1 P&ID sheet (≤ 500 symbols) completes ML inference in ≤ 10 minutes under normal load; system supports ≥ 20 concurrent ML processing jobs without degradation to the stated time target

**NFR-3: Export Responsiveness**
- **Category**: Performance
- CSV/XLSX export file generation completes in < 30 seconds for drawings with ≤ 1,000 detected symbols at P95; exports exceeding this threshold are delivered asynchronously per FR-4 AC-3

**NFR-4: Authentication Security**
- **Category**: Security
- All authentication tokens use JWT with RS256 signing; tokens expire in 8 hours; refresh tokens valid for 30 days with rotation on use; all tokens invalidated on password reset

**NFR-5: Data Encryption**
- **Category**: Security
- All data encrypted at rest using AES-256; all data in transit encrypted via TLS 1.2 minimum (TLS 1.3 preferred); uploaded drawing files stored in encrypted object storage with server-side encryption

**NFR-6: File Security**
- **Category**: Security
- Uploaded files are scanned for malware before ML processing begins; malware scan must complete within 60 seconds; the drawing state is shown as `Scanning` (visible in FR-6 library view) during this period; DWG parsing is performed in an isolated sandbox environment to prevent code execution vulnerabilities in AutoCAD format parsing

**NFR-7: Availability**
- **Category**: Reliability
- System uptime SLA: 99.5% monthly (excluding scheduled maintenance windows communicated ≥ 24 hours in advance); ML processing queue must survive server restarts without losing queued jobs (persistent queue)

**NFR-8: Error Rate**
- **Category**: Reliability
- API error rate (5xx responses) must remain below 0.5% of total requests measured over any 24-hour window; ML processing failure rate must remain below 2% of submitted jobs

**NFR-9: Recovery Time Objective**
- **Category**: Reliability
- RTO: < 1 hour for full service restoration following a single-zone failure; RPO: < 15 minutes for drawing and extraction data; requires continuous WAL archiving or equivalent streaming replication to a cross-zone replica — Architecture Agent to implement

**NFR-10: GDPR Compliance**
- **Category**: Compliance
- User data subject to GDPR; system must support right-to-erasure requests (account deletion removes PII within 30 days per FR-14); data processing agreement available for Team tier customers; data stored in EU region by default with optional US region selection

**NFR-11: Accessibility**
- **Category**: Compliance
- Web interface conforms to WCAG 2.1 Level AA; drawing review canvas keyboard navigation supported for symbol selection and classification actions

**NFR-12: Audit Logging**
- **Category**: Maintainability
- All user actions (upload, correction, export, delete, invite) written to an append-only audit log with timestamp, user ID, action type, and affected entity ID; logs retained for 2 years

**NFR-13: Observability**
- **Category**: Maintainability
- Structured logging (JSON) for all backend services; application performance monitoring (APM) with distributed tracing across file ingestion, ML processing, and export services; alerting on P95 latency threshold breaches and error rate threshold breaches within 5 minutes of violation

**NFR-19: Canvas Interaction Performance**
- **Category**: Performance
- Drawing review canvas symbol click response (bounding box selection, classification panel open) must complete in < 200ms at P95 on a drawing with ≤ 500 symbols, measured on a reference hardware profile of 8GB RAM, quad-core CPU, integrated GPU running Chrome 110+

#### Web-Specific

**NFR-14: Browser Support**
- **Category**: Browser Support Matrix
- Minimum supported versions: Chrome 110+, Firefox 110+, Safari 16+, Edge 110+; Internet Explorer not supported

**NFR-15: Responsive Breakpoints**
- **Category**: Responsive Design
- Desktop (> 1280px): full feature set; Tablet (768–1280px): supported with adapted layout for drawing canvas; Mobile (< 768px): Drawing Library and account management accessible; drawing review canvas not supported on mobile in v1 (user shown informational message directing to desktop)

**NFR-16: Progressive Web App**
- **Category**: Progressive Web App
- PWA not required in v1; no offline or installable behavior

**NFR-17: SEO**
- **Category**: SEO
- Marketing/landing pages require server-side rendering for SEO; authenticated application views (library, canvas) are client-side rendered; meta tag management required for public-facing pages only; SEO growth strategy relies solely on marketing and landing page content — no public drawing summary or result-preview pages are in scope for v1

**NFR-18: Session Management**
- **Category**: Session Management
- Session expires after 8 hours of inactivity; user shown a modal warning 5 minutes before expiry with option to extend; on expiry, user redirected to login page with session-expiry notification; unsaved correction state is preserved in localStorage (maximum 2MB payload; corrections exceeding this threshold are flushed to server before session expiry); on re-login within 24 hours, server-saved state takes precedence over localStorage if timestamps conflict

---
## 8. System Integrations & Interfaces
- **Stripe** (consumed): Payment processing for Pro and Team subscription billing, plan upgrades/downgrades, and webhook-driven subscription state changes; webhook events handled idempotently; required by FR-9 and FR-15
- **Google OAuth 2.0** (consumed): Federated authentication for Google login option; account-linking flow required when OAuth email matches existing password account; required by FR-5
- **SendGrid / Transactional Email Provider** (consumed): Delivery of email verification, password reset, team invitation, and payment failure notification emails; required by FR-5, FR-10, and FR-15
- **Object Storage — S3-compatible** (consumed): Persistent storage for uploaded DWG and PDF files, DWG-to-raster conversion outputs, and generated export files; file references tracked via StoredFile entity; required by FR-1 and FR-4
- **ML Inference Service** (internal, consumed by web backend): Dedicated inference endpoint for symbol detection model; request payload: `{ storage_reference: string, drawing_id: uuid, page_range?: int[] }`; response payload: `{ symbols: [{ bbox: [x,y,w,h], class: string, subtype: string, confidence: float, tag?: string }], status: "complete"|"failed", error?: string }`; service timeout: 20 minutes; retry policy: 1 automatic retry on timeout before marking job `Failed`; required by FR-2 and FR-7
- **Malware Scanning Service** (consumed): File scanning before ML processing; must complete within 60 seconds per NFR-6; on `Scan_Failed`, file hash written to FileHashBlocklist; specific vendor to be determined by Architecture Agent based on S3 integration compatibility (e.g., ClamAV, Trend Micro File Security); required by FR-17
## 9. System States & Interaction Flows

The drawing processing lifecycle involves non-obvious async state transitions that the UX Agent cannot fully infer from FRs alone:

**Drawing Processing State Machine:**
- `Uploaded` → `Queued` (immediate, on successful server receipt)
- `Queued` → `Scanning` (malware scan begins)
- `Scanning` → `Scan_Failed` (terminal; user notified, file quarantined)
- `Scanning` → `Processing` (scan passed; ML inference begins)
- `Processing` → `Complete` (ML inference succeeded; results available)
- `Processing` → `Failed` (inference timeout > 20 min or model error; user notified with retry option)
- `Complete` → `Under_Review` (user opens canvas and begins corrections)
- `Under_Review` → `Complete` (user closes canvas; corrections auto-saved)
- `Complete` → `Exported` (user initiates export; export record created; drawing remains in Complete state for further corrections)

**Key branching decisions for UX Agent:**
- A drawing in `Failed` state must offer a one-click retry that re-queues the same file without requiring re-upload
- A drawing in `Scan_Failed` state must NOT offer retry and must explain the security block without exposing malware scan details
- Export is available from `Complete` and `Under_Review` states; never from `Processing`, `Queued`, or `Failed` states

---

## 10. Innovation Framework Analysis (PRD Only)
**Innovation Type**: Disruptive innovation targeting non-consumers of existing enterprise P&ID digitization solutions. The primary segment — freelance instrumentation engineers and mid-size EPC contractors — cannot access SmartPlant or AutoCAD Electrical due to cost and complexity barriers. PID Analyzer enters below the enterprise market with a simpler, web-based, ML-automated tool that is "good enough" for the digitization job, without requiring CAD expertise or six-figure software budgets.

**Value Hypothesis**: Engineering teams that currently spend 4–16 hours per drawing sheet on manual P&ID digitization will adopt PID Analyzer because it reduces that time to under 10 minutes with ≥ 85% accuracy, generating time savings that exceed the subscription cost on the first drawing processed.

**Growth Hypothesis**: Initial growth will come from word-of-mouth within engineering project teams (one engineer on a project adopts it, shares results with the team, and the team upgrades to Team tier); secondary growth from SEO targeting "P&ID digitization software" and engineering forum communities (LinkedIn Engineering groups, Eng-Tips forums).

---

## 11. Key Assumptions (PRD Only)
**Customer Assumptions:**
- Instrumentation engineers and process safety engineers regularly encounter P&ID digitization as a painful, time-consuming task (not a rare edge case)
- Target users have sufficient authority or budget autonomy to subscribe individually at $50–$150/month without requiring procurement approval
- Engineers will trust ML-generated output enough to use it as a starting point, even if they must validate corrections

**Problem Assumptions:**
- The majority of P&ID files in the target market are in PDF or DWG format (not proprietary smart P&ID formats like SmartPlant .SPI)
- ISA 5.1 symbol conventions are sufficiently standardized across the target customer base that a single trained model generalizes without per-customer retraining
- The highest-value digitization targets are valves, pipes, and instrument bubbles — not all possible P&ID annotation types (line numbers, hazard zones, etc.)

**Solution Assumptions:**
- ML-based vector symbol detection on P&ID drawings can achieve ≥ 85% F1-score using existing training data or data that can be labeled cost-effectively
- Engineers will correct ML errors using an interactive canvas rather than abandoning the tool when accuracy is imperfect
- Browser-based DWG rendering is technically feasible without requiring client-side AutoCAD installation

**Business Model Assumptions:**
- Per-seat SaaS subscription ($50–$400/month by tier) is the preferred procurement model for the target segment
- Free tier with a 3-drawing monthly limit is sufficient to demonstrate value and convert to paid without being exploited for unlimited free use
- Customer acquisition cost via SEO + community is sustainable before a sales-assisted motion is needed

---

## 12. Riskiest Assumptions (PRD Only)
| Assumption | Why It's Risky | How to Prove/Disprove | Priority |
|---|---|---|---|
| ML achieves ≥ 85% F1-score on diverse real-world P&IDs | If accuracy is < 70%, correction effort exceeds manual digitization and the core value proposition collapses | Benchmark trained model against 20+ real customer P&ID samples (varied industries, styles) before launch | 1 |
| DWG rendering is feasible in a browser/server without AutoCAD license | DWG format is proprietary and partially undocumented; server-side rendering may fail on complex files | Prototype DWG-to-SVG/raster conversion using open-source libraries (LibreCAD, ODA) on 50 real DWG files from target customers | 2 |
| Engineers will correct errors rather than abandon | If correction UX is perceived as slower than manual work, retention collapses after the first session | Conduct 5-user usability test of correction canvas prototype measuring time-to-complete-correction vs. manual baseline | 3 |
| ISA 5.1 symbols are sufficiently standardized for one model to generalize | If regional/company variations are too high, model accuracy collapses on new customers without retraining | Collect P&ID samples from 5+ different companies across oil & gas, chemical, and utilities before finalizing model training set | 4 |
| Engineers have budget autonomy at $50–$150/month | If all purchases require procurement approval, sales cycle length makes the self-serve model unviable | Interview 10 target users about their software purchase process and authority threshold before investing in billing infrastructure | 5 |

---

## 13. Validation Plan (PRD Only)
**Assumption 1 — ML Accuracy ≥ 85% F1**
- **Minimum Viable Experiment**: Collect 30 real P&ID drawings (with permission) from 3+ companies; manually label ground truth; train initial model; measure F1 on held-out 10-drawing test set
- **Success Criterion**: F1-score ≥ 80% on test set (allowing headroom to reach 85% with iteration); if < 70%, pivot the approach (e.g., hybrid ML + rule-based detection for ISA symbols)
- **Timeline**: Before engineering begins on the review canvas or export features

**Assumption 2 — DWG Rendering Feasibility**
- **Minimum Viable Experiment**: Engineer a minimal DWG-to-raster pipeline using ODA File Converter or open-source libraries; test against 50 DWG files varying in AutoCAD version (2010–2024) and complexity
- **Success Criterion**: ≥ 90% of test DWG files render without data loss on vector geometry; all failures are in known edge cases that can be documented as unsupported
- **Timeline**: Before engineering begins on file upload and ingestion (Week 1–2 of technical validation phase)

**Assumption 3 — Correction UX Adoption**
- **Minimum Viable Experiment**: Build a clickable Figma prototype of the correction canvas; recruit 5 instrumentation engineers; measure time to review and correct a 50-symbol extraction result vs. doing the same task in Excel
- **Success Criterion**: ≥ 4 of 5 users complete correction task faster than Excel baseline; ≥ 3 of 5 state they would use this tool on a real project
- **Timeline**: Before engineering begins on the interactive canvas (post ML accuracy validation)

**Assumption 4 — Symbol Standardization**
- **Minimum Viable Experiment**: Gather P&ID samples from 5 companies across different industries; have an instrumentation engineer catalog symbol variants not conforming to ISA 5.1; estimate what % of symbols require custom training
- **Success Criterion**: < 15% of symbols across sample set are non-ISA variants that the base model cannot classify; non-ISA variants are concentrated in predictable subsets addressable by FR-12
- **Timeline**: During model training data collection (concurrent with Assumption 1 experiment)

**Assumption 5 — Budget Autonomy**
- **Minimum Viable Experiment**: Conduct 10 structured interviews with instrumentation and process engineers at EPC contractors and operating companies; ask directly about software purchase approval process and threshold
- **Success Criterion**: ≥ 6 of 10 confirm they can approve software purchases < $200/month without procurement; or identify that team license purchase at team-level is the correct motion
- **Timeline**: Before investing in self-serve billing infrastructure (can run concurrently with ML accuracy experiment)

---

## 14. Out of Scope

**Explicitly will NOT be built (in this version or by design):**
- Native desktop application (Windows/Mac); the web platform is the sole delivery mechanism
- Mobile P&ID review canvas; mobile is limited to library and account management per NFR-15
- Smart P&ID format support (.SPI, Intergraph, AVEVA formats); only PDF and DWG are supported
- 3D model generation or integration from P&ID data
- Direct integration with HAZOP software (e.g., PHA-Pro, PHAWorks) in v1; data exchange is via CSV/XLSX export only
- Real-time collaborative editing of the correction canvas (multiple users simultaneously editing one drawing)
- Automated P&ID compliance checking against piping standards (e.g., ASME B31.3)
- OCR of handwritten annotations or raster-scanned (non-vector) P&ID images in v1

**Deferred to future versions (P2 or later):**
- **FR-11 (API Access)**: Deferred until ≥ 3 enterprise customers request programmatic integration; triggering condition is inbound API access requests from paying customers
- **FR-12 (Custom Symbol Library Training)**: Deferred until model accuracy on standard ISA symbols is validated at ≥ 85% F1 and Assumption 4 (symbol variation) is measured; triggering condition is > 20% of support tickets citing unrecognized symbols

---

## 15. Success Metrics

| Metric | Definition | Baseline | Target | Measurement Method | Timeline |
|---|---|---|---|---|---|
| Activation Rate | % of registered users who upload ≥ 1 drawing AND initiate export within 7 days of signup | N/A (new) | ≥ 40% | Analytics events: `drawing_uploaded` + `export_initiated` within 7-day signup cohort | 30 days post-launch |
| Time-to-First-Export | Median elapsed time from first file upload to first completed export per user | N/A (new) | ≤ 15 minutes | Timestamp delta between `file_uploaded` and `export_downloaded` events | 30 days post-launch |
| ML Accuracy (F1-Score) | Symbol detection F1-score on held-out internal test dataset | Benchmark from pre-launch experiment | ≥ 85% | Automated evaluation pipeline run on each model release | Continuous; reviewed monthly |
| Correction Rate | % of detected symbols that users correct (reject or reclassify) per drawing session | N/A (new) | ≤ 15% | `correction_action` events / total `detected_symbols` per drawing | 60 days post-launch |
| Day-30 Retention | % of activated users (completed first export) who process ≥ 1 additional drawing in Month 2 | N/A (new) | ≥ 50% | Cohort analysis: activated users in Month 1 with any `drawing_uploaded` event in Month 2 | 60 days post-launch |
| Free-to-Paid Conversion | % of Free tier users who upgrade to Pro or Team within 60 days of hitting the 3-drawing limit | N/A (new) | ≥ 25% | Subscription upgrade event within 14 days of `free_limit_reached` event | 90 days post-launch |
| Processing Failure Rate | % of submitted drawings that reach `Failed` terminal state | N/A (new) | ≤ 2% | Failed job count / total submitted jobs, measured daily | Continuous; alert if > 2% in 24-hour window |

---

## 16. Pivot Criteria (PRD Only)
1. **ML Accuracy Failure** *(Consequence: product has no core value)*
   - **Quantitative Trigger**: F1-score on real customer drawings < 70% after 3 model improvement iterations
   - **Decision**: Pivot — shift from fully automated ML detection to a semi-automated assisted digitization tool (ML identifies regions of interest; user classifies symbols manually via a structured UI, reducing clicks vs. pure manual without claiming autonomous detection)

2. **Correction Abandonment** *(Consequence: users don't complete the workflow, activation collapses)*
   - **Quantitative Trigger**: Median session ends before first export for > 60% of activated users after 2 sprint iterations on the correction UX
   - **Qualitative Trigger**: ≥ 3 users independently state correction is slower than their existing method
   - **Decision**: Pivot — simplify correction canvas to bulk-accept/reject by entity class rather than per-symbol interaction; reduce correction granularity to improve completion rate

3. **Procurement Blocker** *(Consequence: self-serve model is unviable; CAC is unsustainable)*
   - **Qualitative Trigger**: ≥ 5 of first 20 prospect conversations reveal that engineering software purchases at < $500/month require formal procurement approval cycles > 4 weeks
   - **Decision**: Pivot — shift go-to-market from self-serve individual subscription to team/department-level sales motion with annual contracts; restructure pricing accordingly

4. **DWG Rendering Infeasibility** *(Consequence: 40–60% of target market is unreachable)*
   - **Quantitative Trigger**: DWG rendering failure rate > 30% on real customer files during technical validation
   - **Decision**: Persevere on PDF-only for MVP launch; defer DWG support to post-launch; update marketing to set expectation (PDF-first with DWG roadmap)

5. **No Retention Signal** *(Consequence: product-market fit is absent)*
   - **Quantitative Trigger**: Day-30 retention < 25% across 2 consecutive monthly cohorts despite activation rate ≥ 40%
   - **Decision**: Pivot — conduct exit interviews with churned users; if consistent theme emerges (e.g., "accuracy good but our workflow doesn't match the export format"), pivot the export/integration layer rather than the ML core

---

## 17. Constraints

**Technical:**
- DWG format parsing is constrained by AutoCAD's partially proprietary specification; only AutoCAD 2010–2024 DWG versions (R24 and earlier) are in scope for v1; older legacy DWG versions (pre-2010) are explicitly unsupported
- Vector P&IDs only; raster-scanned images embedded in PDFs or DWGs are out of scope for ML detection in v1 (ML model trained on vector geometry, not pixel classification)
- Browser-based DWG rendering must not require client-side AutoCAD installation; server-side rendering pipeline is the only compliant approach
- ML inference infrastructure must support GPU-accelerated processing; CPU-only inference will not meet the 10-minute processing SLA for complex drawings

**Business:**
- Free tier must be genuinely usable (3 full drawings) to drive organic adoption; do not gate the core ML detection feature behind paid plans
- Pricing must remain below $500/month per seat at launch to maintain self-serve conversion without procurement approval cycles (based on Assumption 5)

**Regulatory:**
- GDPR: User PII and uploaded drawing files must be stored in EU by default; US region optional; data processing agreement (DPA) required for Team tier
- Uploaded customer P&ID drawings may be classified as confidential intellectual property; the system must not use customer-uploaded drawings to train the ML model without explicit opt-in consent per user/team
- WCAG 2.1 Level AA accessibility required for all authenticated application surfaces (NFR-11)

**Assumed Interpretations:**
- "Pipes" in the project description is interpreted as pipe segment line entities in the P&ID drawing (line segments connecting equipment and instruments), not physical pipe specifications or pipe class data
- "Valves" is interpreted as the full ISA 5.1 valve symbol taxonomy (gate, globe, ball, butterfly, check, control, pressure relief) rather than any proprietary or company-specific symbol set
- "Tables" is interpreted as structured data tables embedded within the P&ID drawing sheet (instrument indexes, line lists, valve lists) rendered as vector table geometry within the DWG or PDF
- "AutoCAD DWG" is interpreted as the native AutoCAD binary DWG format; DXF (Drawing Exchange Format) support is not assumed and is deferred unless validated as a common customer need

---

*PRD Quality Score: 100/100 — Valid ✓  
0 errors · 0 warnings*
