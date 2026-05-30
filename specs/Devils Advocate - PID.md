# Devil's Advocate Report: PID Analyzer
*Generated: 2025-01-31*

## Verdict Summary
The downstream documents are largely coherent with the PRD but contain three categories of genuine gaps: the UX defers all P1 screens and the registration/login screens without verifying those "pre-built patterns" meet the PRD's specific acceptance criteria; the Architecture has a critical upload-flow race condition and an anonymization strategy that breaks its own stated guarantee; and the User Stories contain a dependency inversion between US-013 and US-015 that makes neither story independently shippable. Left unresolved, these will produce rework mid-sprint.

```json
{
  "criticalIssues": [
    {
      "location": "Architecture > Section 5 — Upload Protocol & POST /drawings",
      "issue": "SHA-256 blocklist check is specified server-side on the stored object, but the file is already written to S3 before the check runs.",
      "why": "A blocklisted file reaches object storage before rejection, violating FR-17 AC-2 which requires rejection before any byte is written to storage.",
      "suggestion": "Hash must be computed on the upload stream before S3 write, or the pre-signed URL flow must be replaced with a proxied upload for the hash-check step."
    },
    {
      "location": "User Stories > Epic 3 > US-013 — Non-Goal boundary vs. US-015 dependency",
      "issue": "US-013 explicitly marks server persistence as out of scope and declares the story incomplete without US-015, creating an unshippable unit.",
      "why": "If US-013 ships in a sprint without US-015, corrections are lost on refresh; the non-goal boundary makes this a guaranteed regression if sprints are split.",
      "suggestion": "Merge US-013 and US-015 into a single story or remove the non-goal boundary and require both in the same sprint as a bundled acceptance criterion."
    },
    {
      "location": "Architecture > Section 4 — Anonymization Strategy (HMAC includes deletion_timestamp)",
      "issue": "The anonymous ID is HMAC of user_id plus deletion_timestamp, making it non-deterministic if the erasure job retries on a different day.",
      "why": "A retry on day 2 produces a different anonymous ID than the run on day 1, leaving some records with ID-A and others with ID-B, violating FR-14 AC-3 cross-table consistency.",
      "suggestion": "Use only user_id plus server_secret in the HMAC, recording the anonymous ID to the User row on first erasure job execution and reusing it on retry."
    },
    {
      "location": "UX Design > Deferred Screens — Registration & Login marked as pre-built patterns",
      "issue": "Registration and Login screens are deferred with no prototype, but FR-5 specifies 9 distinct acceptance criteria including account-linking prompt and lockout UI that are not pre-built patterns.",
      "why": "The account-linking prompt (FR-5 AC-2) and 15-minute lockout message (FR-5 AC-6) are product-specific flows; marking them as standard patterns means they will ship without UX review.",
      "suggestion": "Produce at minimum a wireframe for the account-linking prompt and lockout state; these are not covered by any auth library out of the box."
    },
    {
      "location": "Architecture > Section 5 — POST /drawings returns upload_url but no explicit blocklist pre-check",
      "issue": "The API issues a pre-signed S3 PUT URL before computing the SHA-256 hash, so the blocklist is checked after the file is already in S3.",
      "why": "This is the same race as Critical Issue 1 restated at the API contract level — the endpoint design structurally prevents pre-storage hash gating.",
      "suggestion": "Add a mandatory POST /drawings/hash-check step before issuing the pre-signed URL, or require the client to supply a client-computed hash that is verified server-side before the URL is issued."
    },
    {
      "location": "User Stories > Epic 4 > US-019 — Stripe webhook-only state update with no inline confirmation",
      "issue": "Subscription tier is updated exclusively on webhook receipt, but the Stripe Checkout redirect returns to the app before the webhook arrives, leaving the user on a stale Free tier UI.",
      "why": "Webhook delivery can lag 5-30 seconds; the user sees no tier change immediately after payment, creating a broken post-upgrade experience with no loading or pending state defined.",
      "suggestion": "Define a pending subscription state shown after Checkout redirect that resolves when the webhook arrives, with a maximum 30-second polling timeout and a fallback message."
    },
    {
      "location": "Architecture > Section 6 — DETECTED_SYMBOL missing instrument table cell entity type",
      "issue": "Table cells extracted by FR-7 are not represented in the data model; DETECTED_SYMBOL has no table_cell subtype or separate entity.",
      "why": "US-022 requires real-time editing of table cell values, but there is no entity to store the edited value or its training_consent flag, making FR-7 and FR-13 unimplementable as specced.",
      "suggestion": "Add a TABLE_CELL entity with FK to DRAWING, cell coordinates, extracted value, and corrected value fields, with training_consent captured per correction."
    },
    {
      "location": "User Stories > Epic 2 > US-010 — Analytics events emitted by backend workers lack user_id context",
      "issue": "processing_complete and processing_failed are emitted by the ML worker, which has no authenticated user session and may not have the user_id readily available.",
      "why": "FR-16 AC-1 requires user_id in every event payload; worker jobs carry drawing_id but user_id must be explicitly passed or looked up, and the story does not specify this.",
      "suggestion": "Require the job payload to include user_id at enqueue time and mandate that worker-emitted events read user_id from the job payload, not from session context."
    }
  ],
  "warnings": [
    {
      "location": "UX Design > Node 6 — Account Settings ML consent toggle default state",
      "concern": "The prototype shows the ML consent toggle as checked/true by default, directly contradicting FR-13 AC-1 which mandates opted-out as the default.",
      "why": "A toggle defaulting to opted-in silently enrolls users in training data contribution, violating the GDPR constraint in Section 17 of the PRD.",
      "suggestion": "Correct the prototype default to unchecked/false and add a note in the design rationale confirming the opted-out default is intentional per FR-13."
    },
    {
      "location": "Architecture > Section 5 — GET /drawings/{id}/symbols has no pagination parameter for large drawings",
      "concern": "The endpoint returns all symbols for a page in one query, but a drawing with 500 symbols on one page sends a large payload with no pagination.",
      "why": "NFR-1 requires canvas load under 3 seconds at P95; a 500-symbol JSONB payload with bounding boxes could exceed this on slower connections without pagination or streaming.",
      "suggestion": "Add optional limit and offset parameters to the symbols endpoint and define a recommended default page size in the architecture spec."
    },
    {
      "location": "UX Design > Node 3 — Drawing Review Canvas missing loading state",
      "concern": "The canvas flow shows no loading state between opening a drawing and bounding boxes rendering; large drawings may take seconds to fetch symbols.",
      "why": "A blank or partially rendered canvas with no progress indicator will appear broken to engineers opening a drawing with 500 symbols on a slow connection.",
      "suggestion": "Add a skeleton or spinner state to the canvas blueprint that displays while GET /drawings/{id}/symbols is in-flight."
    },
    {
      "location": "User Stories > Epic 5 > US-025 — Revision comparison gated to Pro/Team but Free tier UI behavior unspecified",
      "concern": "US-025 technical notes state the feature is tier-gated but do not specify what the Free tier user sees when navigating to comparison from the library.",
      "why": "FR-9 AC-3 requires tier-gated features to show an upgrade CTA; without a story AC covering this state, the gating UI will be inconsistent with the upgrade prompt pattern.",
      "suggestion": "Add a scenario to US-025 covering the Free tier access attempt and its upgrade CTA, consistent with US-018 Scenario 5 pattern."
    },
    {
      "location": "Architecture > Section 5 — No endpoint defined for POST /drawings/{id}/upload-complete idempotency",
      "concern": "If the client calls upload-complete twice (network retry), the ingest job is enqueued twice, processing the same file twice and creating duplicate Drawing state transitions.",
      "why": "The upload-complete endpoint is not documented as idempotent; duplicate calls would produce duplicate Celery jobs and duplicate DetectedSymbol records.",
      "suggestion": "Specify that upload-complete is idempotent by checking Drawing state; if already in Queued or later state, return 200 without re-enqueuing."
    },
    {
      "location": "UX Design > Node 7 — Subscription page grace period banner described as persistent but no spec for non-subscription pages",
      "concern": "The grace period banner is defined on the Subscription page but FR-15 and US-020 imply users should see billing warnings on all authenticated pages.",
      "why": "A user who never visits the Subscription page during a 7-day grace period will miss both in-app warnings and rely solely on email, reducing payment resolution rate.",
      "suggestion": "Specify that the grace period banner appears in the top navigation bar on all authenticated pages, not only the Subscription page."
    },
    {
      "location": "User Stories > Epic 1 > US-003 — Pre-2010 DWG rejection not covered by any scenario",
      "concern": "Technical notes mention DWG version detection for pre-2010 files but no acceptance criteria scenario covers the user-facing error for an unsupported DWG version.",
      "why": "Without a defined error message and state for pre-2010 DWG uploads, implementation will produce an inconsistent error or a generic 400 that violates FR-1 AC-3.",
      "suggestion": "Add Scenario 7 to US-003 covering pre-2010 DWG rejection with a descriptive error naming the supported version range (2010-2024)."
    },
    {
      "location": "Architecture > Section 12b — Revision comparison staleness after post-comparison corrections",
      "concern": "The open question on materialized REVISION_COMPARISON storage is unresolved but the data model already includes it as a concrete entity with jsonb match_result.",
      "why": "If corrections are made after a comparison is computed, the stored match_result is stale and will produce incorrect change summaries without any staleness indicator.",
      "suggestion": "Add a computed_after_correction boolean or last_correction_at timestamp to REVISION_COMPARISON so the UI can warn users when the comparison predates recent corrections."
    },
    {
      "location": "UX Design > Node 5 — Export Modal previous exports list hardcoded to 5 with no link to ExportRecord retention policy",
      "concern": "The modal caps previous exports at 5 displayed entries, but ExportRecord retention is 2 years per the data model; older exports are accessible via API but not surfaced.",
      "why": "A user who exported a drawing 6 times will assume the 6th oldest export is gone, but it is retrievable — creating a support burden when engineers cannot find a prior export.",
      "suggestion": "Add a 'View all exports' link below the 5-entry list that routes to a full export history view, or document the 5-entry cap as a deliberate design decision with rationale."
    },
    {
      "location": "User Stories > Epic 3 > US-012 — Under_Review state transition trigger left unresolved",
      "concern": "The clarification section notes this is unresolved, but US-012 technical notes state the transition must be recorded, creating an implementation dependency on an open product decision.",
      "why": "Developers will make an arbitrary choice at implementation time; if canvas-open triggers Under_Review, Marcus sees drawings listed as Under_Review in the library without any active correction work.",
      "suggestion": "Product Owner must resolve this before US-012 enters a sprint; suggested answer is first correction action triggers Under_Review, keeping Under_Review semantically meaningful."
    },
    {
      "location": "Architecture > Section 7 — Canvas interaction 200ms target attributed to local state lookup but symbol panel requires server data",
      "concern": "The architecture claims 200ms is achievable because symbol selection is a local state lookup, but the inspection panel may need to fetch correction history from the server for the selected symbol.",
      "why": "If UserCorrection records are not pre-loaded with the symbol bulk fetch, the panel open triggers a network round-trip that breaks the 200ms NFR-19 target on any latency above ~100ms.",
      "suggestion": "Specify that correction history is included in the GET /drawings/{id}/symbols response payload to ensure the panel can open from local state with no additional fetch."
    },
    {
      "location": "UX Design > Node 2 — File Upload missing state for drawings in Processing when Free limit is reached mid-upload",
      "concern": "The upload flow checks Free tier limit after upload completes, but if a drawing is uploaded and the in-progress 3rd job completes mid-upload of a 4th, the counter increments concurrently.",
      "why": "US-018 Scenario 3 covers in-progress jobs at the moment of limit but the UX flow does not show what happens if the limit is reached after the file transfer but before job queuing.",
      "suggestion": "Add a state to the upload flow user story showing the file-retained-but-not-queued outcome when the limit is hit post-transfer, with clear messaging that the file is safe."
    },
    {
      "location": "Architecture > Section 3 — Supabase Auth token_version counter invalidation on password reset",
      "concern": "The architecture uses a token_version counter on the User record to invalidate all tokens on password reset, but Supabase Auth manages JWT issuance and may not honor application-level token_version checks.",
      "why": "If Supabase Auth validates tokens independently of the application DB, the token_version approach requires a middleware check on every request that may conflict with Supabase's own session management.",
      "suggestion": "Verify that Supabase Auth supports server-side session invalidation by user ID; if not, document the middleware hook that checks token_version on every authenticated request."
    }
  ],
  "questions": [
    "Who owns the ODA File Converter commercial license procurement decision and what is the lead time — this blocks FR-1 DWG support entirely and is not assigned to any team member?",
    "When the grace period banner appears only on the Subscription page, how does a user in Grace state who never visits that page receive the day-6 in-app warning required by US-020 Scenario 2?",
    "If two team members simultaneously reclassify the same symbol to different entity classes and both saves succeed via last-write-wins, does the audit log record both corrections and which one does the export reflect?"
  ]
}
```