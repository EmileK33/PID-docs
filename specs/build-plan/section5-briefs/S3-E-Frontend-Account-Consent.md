---

#### S3-E — Frontend: Account & Consent

**Phase 3 | Frontend | Needs: S1-F, S2-F**

---

##### Objective

Build the `/account` page that lets authenticated users update their display name and email, toggle ML training consent (with server-enforced team-override visibility), and initiate account deletion with a GDPR erasure confirmation flow.

---

##### Scope

**P0 MVP** — all work in this session is P0.

- US-004: Account settings (display name, email) and ML training consent management — **P0**
- US-005: Account deletion initiation and GDPR erasure pipeline UI — **P0**

No P1 stubs are required for this session; all owned files are fully implemented.

---

##### Technology constraints

Sourced from §1.8 Technology Stack:

| Layer | Constraint |
|---|---|
| **Frontend SPA** | React + Vite (TypeScript). **Must NOT use Next.js** — that is the marketing site only. |
| **Canvas** | Konva.js is irrelevant to this session — must NOT be imported. |
| **Auth** | Supabase Auth client via `supabaseClient.ts` (from S1-F). Must use the shared `useAuth` hook for session and user context; must never instantiate a second Supabase client. |
| **API calls** | All HTTP calls must go through the shared `apiClient` from `frontend/src/api/client.ts` (S1-F) — never raw `fetch` or a new axios instance. |
| **Test runner** | Vitest + `@testing-library/react` + `msw` (Mock Service Worker) for API mocking in tests. |
| **Styling** | Must import `frontend/src/styles/globals.css` (owned by S1-F) via the Layout component; must not introduce a separate CSS framework. |

---

##### Performance targets

No hard SLA is directly owned by this session. The account page is a low-traffic, user-initiated flow. No P95 latency target is specified in §1.9 for account settings.

Loading states for all three API interactions (profile load, consent load, save operations) must be handled so the UI never appears frozen, but no specific millisecond target applies.

---

##### Owned files

```
frontend/src/pages/Account.tsx
frontend/src/features/account/ProfileForm.tsx
frontend/src/features/account/ConsentToggle.tsx
frontend/src/features/account/DeleteAccount.tsx
```

---

##### Read-only imports

| Owning Session | File Path | Named Exports Required |
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

##### Do not touch

- `frontend/src/router.tsx` — pre-stubbed by S0-A; route for `/account` already points to `Account.tsx`
- `frontend/src/main.tsx` — entry point, pre-stubbed by S0-A
- `frontend/src/App.tsx` — pre-stubbed by S0-A
- `frontend/src/pages/_stubs.tsx` — S0-A scaffold stubs; Account.tsx replaces the stub, do not edit the stubs file
- `frontend/src/api/client.ts` — owned by S1-F
- `frontend/src/api/endpoints.ts` — owned by S1-F
- `frontend/src/auth/AuthContext.tsx` — owned by S1-F
- `frontend/src/auth/useAuth.ts` — owned by S1-F
- `frontend/src/auth/supabaseClient.ts` — owned by S1-F
- `frontend/src/components/Layout.tsx` — owned by S1-F
- `frontend/src/components/Nav.tsx` — owned by S1-F
- `frontend/src/components/GraceBanner.tsx` — owned by S1-F
- `frontend/src/components/ProtectedRoute.tsx` — owned by S1-F
- `frontend/src/lib/storage.ts` — owned by S1-F
- `frontend/src/lib/analytics.ts` — owned by S1-F
- `frontend/src/styles/globals.css` — owned by S1-F
- `frontend/src/types/contracts.ts` — owned by S1-F
- All `backend/` files — owned by S2-F and other backend sessions
- All `tests/integration/` files — owned by respective backend sessions

---

##### Architecture context

The following sections are quoted verbatim from the distilled specification:

**From §1.3 — Role-Permission Matrix (relevant rows):**

```typescript
const ROLE_PERMISSIONS = {
  user: {
    // ...
    billing_manage:          true,      // personal subscription
    gdpr_delete_account:     true,
  },
  team_member: {
    // ...
    billing_manage:          false,
    gdpr_delete_account:     true,
  },
  team_admin: {
    // ...
    billing_manage:          true,      // team subscription
    gdpr_delete_account:     true,
  },
} as const;
```

**From §1.4 — Critical Ordering Rules:**

> **Rule 6:** "Each correction save sends... the resolved `training_consent` value... at time of creation; the consent value must be snapshotted at correction time, not resolved lazily."

> **Rule 7:** "Team-level consent resolution must be evaluated server-side to prevent client-side bypass; the resolved value is not a client-supplied field."

**From §1.5 — HTTP Status Code Contracts:**

| Condition | Required code | Must never return |
|---|---|---|
| Account deletion initiation success | `204` | `200` |
| Unauthenticated request to protected endpoint | `401` | `403`, `200` |
| Authenticated user accessing resource they do not own | `403` | `404`, `200` |

**From §1.6 — Route Manifest (relevant endpoints):**

```
GET    /account
PATCH  /account
DELETE /account
GET    /account/consent
PATCH  /account/consent
```

**From §1.11 — Browser Storage Keys:**

| Key | Storage Type | Written By | Read By | Purpose |
|---|---|---|---|---|
| `graceBannerDismissed` | sessionStorage | Drawing Library / global nav component | Global nav component | Session-scoped suppression of grace period banner; resets on new session |

> Note: `graceBannerDismissed` is read by `Nav.tsx` (S1-F) — S3-E must not touch this key.

**From §1.13 — P0 Feature Scope (relevant items):**

> - US-004: ML training consent management and account settings (display name, email)
> - US-005: Account deletion and GDPR erasure pipeline (30-day async, anonymous_id persistence)
> - JWT middleware token_invalidated_at check on every authenticated request

**From §1.4 — Rule 11 (GDPR erasure, server-side):**

> "On first erasure job execution, the computed anonymous ID is written to `USER.anonymous_id` before any records are updated. All subsequent erasure job retries... read `USER.anonymous_id` directly."

> Note: This is entirely server-side (owned by S2-L GDPR Worker). S3-E only initiates the deletion by calling `DELETE /account`; it does not implement the erasure logic.

**From §1.2 — Relevant Schema:**

```sql
CREATE TABLE "user" (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email                  VARCHAR NOT NULL,
  display_name           VARCHAR NOT NULL,
  -- ...
  role                   VARCHAR NOT NULL CHECK (role IN ('user','team_member','team_admin')),
  -- ...
);

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

---

##### User stories and acceptance criteria

The distilled spec (§1.13) does not include verbatim user story text; the following ACs are derived from §1.13 descriptions, §1.4 ordering rules, §1.5 HTTP contracts, and §1.3 permission matrices. They constitute the binding contract for this session.

---

**US-004 — Account Settings & ML Training Consent**

*As an authenticated user, I want to update my display name and email and manage my ML training consent preference so that my account reflects correct information and my data rights are respected.*

**Profile Management ACs:**

- **US-004 AC-1:** On page load, the profile form is pre-populated with the current `display_name` and `email` values from `GET /account`.
- **US-004 AC-2:** When the user changes the display name and clicks Save, `PATCH /account` is called with `{ display_name: "<new value>" }`. On 200 response, a success message is displayed and the form retains the new value.
- **US-004 AC-3:** When the user changes the email field and clicks Save, `PATCH /account` is called with `{ email: "<new value>" }`. On 200 response, a success message is displayed.
- **US-004 AC-4:** If `display_name` is empty on submit, a client-side validation error is shown ("Display name is required") and no API call is made.
- **US-004 AC-5:** If `email` does not match a valid email format on submit, a client-side validation error is shown ("Enter a valid email address") and no API call is made.
- **US-004 AC-6:** While the `PATCH /account` call is in-flight, the Save button shows a loading indicator and is disabled to prevent duplicate submissions.
- **US-004 AC-7:** If `PATCH /account` returns a non-2xx response, an error message is displayed inline (e.g., "Failed to update profile. Please try again.") and the form values revert to the last successfully saved state.

**ML Training Consent ACs:**

- **US-004 AC-8:** On page load, the consent toggle reflects the current `opted_in` value from `GET /account/consent`.
- **US-004 AC-9:** When the user toggles the consent switch, `PATCH /account/consent` is called immediately with `{ opted_in: <new boolean> }`. On 200 response, the toggle stays in its new position.
- **US-004 AC-10:** While the consent `PATCH` call is in-flight, the toggle is disabled to prevent race conditions.
- **US-004 AC-11:** If `PATCH /account/consent` returns a non-2xx response, the toggle reverts to its previous position and an error message is displayed.
- **US-004 AC-12:** When `GET /account/consent` returns `is_team_override: true`, the toggle is rendered as disabled with a visible label such as "Managed by your team" and the user cannot interact with it. The displayed value shows `effective_opted_in`.
- **US-004 AC-13:** The consent section includes explanatory text describing what ML training consent means (that user corrections may be used to improve the model).

---

**US-005 — Account Deletion & GDPR Erasure**

*As an authenticated user, I want to permanently delete my account so that my data is erased in accordance with GDPR within 30 days.*

- **US-005 AC-1:** A "Delete Account" button is visible in a clearly marked "Danger Zone" or equivalent destructive-action section on the Account page.
- **US-005 AC-2:** Clicking "Delete Account" opens a confirmation modal. No API call is made at this point.
- **US-005 AC-3:** The confirmation modal displays a warning explaining that the action is permanent and that personal data will be erased within 30 days.
- **US-005 AC-4:** The confirmation modal has a "Cancel" button. Clicking "Cancel" closes the modal without making any API call and the user remains on the account page.
- **US-005 AC-5:** The confirmation modal has a "Delete My Account" confirm button (styled as a destructive/danger action).
- **US-005 AC-6:** Clicking "Delete My Account" calls `DELETE /account`. While the call is in-flight, the button shows a loading indicator and is disabled.
- **US-005 AC-7:** On a `204` response from `DELETE /account`, the Supabase session is signed out (via `supabase.auth.signOut()`) and the user is navigated to `/`.
- **US-005 AC-8:** If `DELETE /account` returns a non-2xx response, an error message is shown inside the modal (e.g., "Failed to delete account. Please try again.") and the modal remains open.
- **US-005 AC-9:** The account page is accessible only to authenticated users. Unauthenticated access to `/account` redirects to `/login` (enforced by `ProtectedRoute` from S1-F).

---

##### UX and design specification

The spec does not contain a dedicated UX mockup document. The following specification is derived from functional requirements in §1.13, the permission matrix in §1.3, and the ordering rules in §1.4.

---

**Page: `/account` — Account.tsx**

- **Layout:** Wrapped in `<Layout>` (S1-F) which includes the global `<Nav>` and `<GraceBanner>`. Also wrapped in `<ProtectedRoute>` (S1-F) to enforce authentication.
- **Page title (document):** "Account Settings — PID Analyzer"
- **Page heading (visual):** "Account Settings"
- **Section structure (top to bottom):**
  1. **Profile** — contains `<ProfileForm />`
  2. **ML Training Consent** — contains `<ConsentToggle />`
  3. **Danger Zone** — contains `<DeleteAccount />`

- **State managed in Account.tsx:**
  - `accountData: AccountResponse | null` — loaded from `GET /account`; passed as prop to `<ProfileForm>`
  - `consentData: ConsentResponse | null` — loaded from `GET /account/consent`; passed as prop to `<ConsentToggle>`
  - `isLoadingAccount: boolean` — shows skeleton/loading state for profile section
  - `isLoadingConsent: boolean` — shows skeleton/loading state for consent section
  - `loadError: string | null` — if initial load fails, show page-level error with retry

- **Initial data load:** Both `GET /account` and `GET /account/consent` are fetched on mount (parallel, via `Promise.all` or separate `useEffect` calls). Loading states are shown independently per section.

---

**Component: ProfileForm.tsx**

**Props:**
```typescript
interface ProfileFormProps {
  initialData: AccountResponse;
  onSaveSuccess: (updated: AccountResponse) => void;
}
```

**Form fields:**
| Field | Input type | Label | Validation | Max length |
|---|---|---|---|---|
| `display_name` | `text` | "Display Name" | Required; non-empty after trim | 100 chars |
| `email` | `email` | "Email Address" | Required; valid email format (RFC-standard) | 254 chars |

**Interaction rules:**
- Form is pre-populated from `initialData` on mount.
- The Save button is **disabled** when: (a) the call is in-flight, or (b) neither field has changed from the last saved value (dirty-check).
- On submit (Save button click or form `onSubmit`):
  1. Run client-side validation. If invalid, show per-field error messages and abort.
  2. Build a partial PATCH body containing only changed fields.
  3. Call `PATCH /account`.
  4. On success: call `onSaveSuccess(response)`, show success message (inline, e.g., green text "Profile updated.").
  5. On error: show inline error message, revert form to last-saved values.
- While in-flight: Save button shows spinner text ("Saving…") and is `disabled`.
- No page navigation occurs on save.

**Data types (local to this component — do not export):**
```typescript
type ProfileFormState = {
  display_name: string;
  email: string;
};
```

---

**Component: ConsentToggle.tsx**

**Props:**
```typescript
interface ConsentToggleProps {
  initialData: ConsentResponse;
  onConsentChange?: (updated: ConsentResponse) => void;
}
```

**Interaction rules:**
- Renders a toggle switch (HTML `<input type="checkbox">` or equivalent accessible role `switch`).
- The toggle value reflects `effective_opted_in` (not `opted_in`) — this is the server-resolved value.
- If `is_team_override === true`:
  - Toggle is `disabled`.
  - A label reads: "Managed by your team" (exact text).
  - No `PATCH /account/consent` call is ever made.
- If `is_team_override === false`:
  - Toggle is interactive.
  - On change: immediately disable the toggle, call `PATCH /account/consent` with `{ opted_in: <new value> }`.
  - On success: update toggle to new value, re-enable.
  - On error: revert toggle to original value, re-enable, show inline error text ("Failed to update consent preference.").
- Explanatory text beneath the toggle (always visible):
  > "When enabled, your symbol corrections and reclassifications may be used to improve the ML model. You can change this at any time."

**Data types:**
```typescript
type ConsentToggleState = {
  isSaving: boolean;
  currentOptedIn: boolean;
};
```

---

**Component: DeleteAccount.tsx**

**Props:**
```typescript
interface DeleteAccountProps {
  onDeleteSuccess?: () => void; // called after sign-out; caller can optionally navigate
}
```

**Interaction rules:**

- Renders a "Delete Account" button styled as a destructive action (red background or red text, visually distinct from primary actions).
- Section heading: "Danger Zone" or "Delete Account".
- Short description above the button: "Permanently delete your account and all associated data. This action cannot be undone."

**Confirmation modal state:**
```typescript
type DeleteModalState = {
  isOpen: boolean;
  isDeleting: boolean;
  error: string | null;
};
```

**Modal content (shown when `isOpen === true`):**
- Heading: "Delete Your Account"
- Body text:
  > "This will permanently delete your account. Your personal data will be erased within 30 days in accordance with GDPR. This action cannot be undone."
- "Cancel" button (secondary/neutral style): closes modal, no API call.
- "Delete My Account" button (destructive/red style): triggers deletion flow.

**Deletion flow:**
1. Set `isDeleting: true`, disable both buttons.
2. Call `DELETE /account`.
3. On `204`: call `supabase.auth.signOut()`, then navigate to `/`.
4. On error: set `error: "Failed to delete account. Please try again."`, set `isDeleting: false`, modal remains open.

**Accessibility requirements:**
- Modal must trap focus while open.
- Modal must be dismissible via `Escape` key (equivalent to clicking Cancel).
- The "Delete My Account" button must have `aria-label="Confirm delete my account"`.

---

##### Critical implementation notes

- **`DELETE /account` returns `204 No Content`** (§1.5). The frontend must not interpret `204` as an error. After receiving `204`, call `supabase.auth.signOut()` before navigating. Never check for a response body on `204`.

- **`is_team_override: true` means the toggle is display-only** (§1.4 Rule 7: "Team-level consent resolution must be evaluated server-side to prevent client-side bypass; the resolved value is not a client-supplied field"). The component must read `effective_opted_in` for display and must never call `PATCH /account/consent` when `is_team_override` is true, even if code reaches that branch somehow.

- **training_consent snapshotted at correction time, not on toggle** (§1.4 Rule 6). The `ConsentToggle` component only sets the user's preference. The actual training consent flag applied to a given correction is evaluated by the server at the time the correction is submitted (owned by S2-C). S3-E has no responsibility for snapshotting — it just saves the preference.

- **No analytics events are fired from S3-E directly.** The nine required analytics events in §1.10 do not include account settings changes. The server-side `correction_action` event (fired by S2-C) uses the consent value stored in the DB at the time of correction. S3-E must NOT call `frontend/src/lib/analytics.ts` for any account page interaction.

- **Profile PATCH body must be a partial object.** If only `display_name` changes, send `{ display_name: "…" }` only. Do not send unchanged fields — this avoids triggering email re-verification flows unnecessarily on the server.

- **On `PATCH /account` email change**, the server may return a message indicating re-verification is needed (exact shape determined by S2-F). If the response includes an `email_verified: false` field, the form should show an informational message: "A verification email has been sent to your new address." The form should not treat this as an error.

- **ProtectedRoute must wrap Account.tsx** at the page level (§1.13: unauthenticated access returns `401` from the API; the frontend redirect must happen at the route level before any API calls are made). Use `<ProtectedRoute>` from S1-F as the outermost wrapper in `Account.tsx`.

- **Do not use `localStorage` for account/consent form state.** The `correction_state:{drawing_id}` localStorage key (§1.11) is for the canvas. Account settings are always server-sourced on page load — no local persistence required.

- **After account deletion, call `supabase.auth.signOut()` first** before navigating. Calling `signOut()` invalidates the Supabase session token client-side. If navigation happens before `signOut()`, the auth token may persist in memory for the remainder of the tab session. The sequence must be: `DELETE /account` → `204` → `supabase.auth.signOut()` → `navigate('/')`.

- **Silent failure mode to avoid:** If the `ConsentToggle` component optimistically updates the UI before the API call completes and then fails to revert on error, the displayed state will be out of sync with the server. Always revert to the pre-call value on API error.

- **Silent failure mode to avoid:** If `ProfileForm` sends both `display_name` and `email` in every PATCH (even when only one changed), the server may trigger an email re-verification on every save. Always diff against `initialData` before building the PATCH body.

---

##### Mocking contract

This session consumes the following API endpoints. Mock response shapes are defined here for use in tests (MSW handlers). These shapes must match what S2-F implements.

---

**`GET /account`**

```typescript
// Response 200
interface AccountResponse {
  id: string;                             // UUID
  email: string;
  display_name: string;
  email_verified: boolean;
  role: 'user' | 'team_member' | 'team_admin';
  team_id: string | null;                 // null for individual users
}

// Example mock:
{
  "id": "a1b2c3d4-0000-0000-0000-000000000001",
  "email": "jane@example.com",
  "display_name": "Jane Doe",
  "email_verified": true,
  "role": "user",
  "team_id": null
}
```

---

**`PATCH /account`**

```typescript
// Request body (partial — only changed fields)
interface PatchAccountRequest {
  display_name?: string;
  email?: string;
}

// Response 200 — same shape as AccountResponse above
// Response 422 — validation error (FastAPI standard):
{
  "detail": [{ "loc": ["body", "email"], "msg": "value is not a valid email address", "type": "value_error.email" }]
}
```

---

**`GET /account/consent`**

```typescript
// Response 200
interface ConsentResponse {
  opted_in: boolean;           // user's own setting
  effective_opted_in: boolean; // resolved value (may differ if team override applies)
  is_team_override: boolean;   // true when team policy controls consent
  updated_at: string;          // ISO 8601 UTC
}

// Example — individual user, consent off:
{
  "opted_in": false,
  "effective_opted_in": false,
  "is_team_override": false,
  "updated_at": "2024-01-15T10:30:00Z"
}

// Example — team member with team override:
{
  "opted_in": false,
  "effective_opted_in": true,
  "is_team_override": true,
  "updated_at": "2024-01-10T08:00:00Z"
}
```

---

**`PATCH /account/consent`**

```typescript
// Request body
interface PatchConsentRequest {
  opted_in: boolean;
}

// Response 200 — same shape as ConsentResponse
// Response 403 — if team override prevents change:
{ "detail": "Consent is managed by your team." }
```

---

**`DELETE /account`**

```
// Response: 204 No Content — no response body
// Response 401 — if session expired
// Response 500 — server error
```

---

##### Acceptance criteria checklist

- [ ] Profile form displays current `display_name` on page load from `GET /account` [US-004 AC-1]
- [ ] Profile form displays current `email` on page load from `GET /account` [US-004 AC-1]
- [ ] Changing `display_name` and clicking Save calls `PATCH /account` with `{ display_name: "..." }` [US-004 AC-2]
- [ ] On successful PATCH, a success message is displayed in the profile section [US-004 AC-2]
- [ ] Changing `email` and clicking Save calls `PATCH /account` with `{ email: "..." }` [US-004 AC-3]
- [ ] Empty `display_name` on submit shows validation error "Display name is required" without API call [US-004 AC-4]
- [ ] Invalid `email` format on submit shows validation error "Enter a valid email address" without API call [US-004 AC-5]
- [ ] Save button is disabled and shows loading indicator while PATCH /account is in-flight [US-004 AC-6]
- [ ] On PATCH /account error (non-2xx), an inline error message is shown and form reverts to last-saved values [US-004 AC-7]
- [ ] Consent toggle reflects `effective_opted_in` from `GET /account/consent` on page load [US-004 AC-8]
- [ ] Toggling the consent switch calls `PATCH /account/consent` with the new boolean value [US-004 AC-9]
- [ ] Consent toggle is disabled while PATCH /account/consent is in-flight [US-004 AC-10]
- [ ] On PATCH /account/consent error, toggle reverts to its previous position and shows error message [US-004 AC-11]
- [ ] When `is_team_override: true`, consent toggle is rendered as `disabled` [US-004 AC-12]
- [ ] When `is_team_override: true`, label "Managed by your team" is visible [US-004 AC-12]
- [ ] When `is_team_override: true`, no PATCH /account/consent call is made regardless of click [US-004 AC-12]
- [ ] Consent section displays explanatory text about ML training data usage [US-004 AC-13]
- [ ] "Delete Account" button is visible on the account page [US-005 AC-1]
- [ ] Clicking "Delete Account" opens a confirmation modal without making any API call [US-005 AC-2]
- [ ] Confirmation modal contains text about permanent deletion and 30-day GDPR erasure [US-005 AC-3]
- [ ] Clicking "Cancel" in the modal closes it without making any API call [US-005 AC-4]
- [ ] Confirmation modal contains a "Delete My Account" button styled as destructive [US-005 AC-5]
- [ ] Clicking "Delete My Account" calls `DELETE /account` [US-005 AC-6]
- [ ] "Delete My Account" button shows loading state and is disabled during in-flight DELETE call [US-005 AC-6]
- [ ] On 204 response from DELETE /account, `supabase.auth.signOut()` is called and user navigates to `/` [US-005 AC-7]
- [ ] On non-2xx response from DELETE /account, error message appears in modal and modal remains open [US-005 AC-8]
- [ ] `/account` redirects unauthenticated users to `/login` (ProtectedRoute enforced) [US-005 AC-9]
- [ ] `PATCH /account` body only includes fields that have changed — unchanged fields are omitted [TECH — partial PATCH contract]
- [ ] `DELETE /account` receives a 204 and the frontend does not treat it as an error [TECH — HTTP 204 contract §1.5]
- [ ] `supabase.auth.signOut()` is called BEFORE navigation after successful account deletion [TECH — session invalidation ordering]
- [ ] No `PATCH /account/consent` call is ever made when `is_team_override: true` [TECH — Rule 7 enforcement §1.4]

---

##### Independent Test

**Test file path (TDD — written first, must fail before implementation):**
`tests/sessions/S3-E.test.tsx`

**Exact CI command:**
```sh
cd frontend && npx vitest run ../../tests/sessions/S3-E.test.tsx
```

---

**AC → assertion mapping:**

| AC | `it(...)` block name |
|---|---|
| US-004 AC-1 | `it("pre-populates display_name and email from GET /account")` |
| US-004 AC-2 | `it("calls PATCH /account with display_name when display name is changed and saved")` |
| US-004 AC-2 (success msg) | `it("shows success message after successful PATCH /account")` |
| US-004 AC-3 | `it("calls PATCH /account with email when email is changed and saved")` |
| US-004 AC-4 | `it("shows validation error and does not call API when display_name is empty")` |
| US-004 AC-5 | `it("shows validation error and does not call API when email is invalid")` |
| US-004 AC-6 | `it("disables Save button with loading indicator while PATCH /account is in-flight")` |
| US-004 AC-7 | `it("shows error message and reverts form values when PATCH /account fails")` |
| US-004 AC-8 | `it("reflects effective_opted_in from GET /account/consent in the toggle")` |
| US-004 AC-9 | `it("calls PATCH /account/consent with new opted_in value on toggle change")` |
| US-004 AC-10 | `it("disables toggle while PATCH /account/consent is in-flight")` |
| US-004 AC-11 | `it("reverts toggle and shows error when PATCH /account/consent fails")` |
| US-004 AC-12 (disabled) | `it("renders consent toggle as disabled when is_team_override is true")` |
| US-004 AC-12 (label) | `it("shows 'Managed by your team' label when is_team_override is true")` |
| US-004 AC-12 (no call) | `it("does not call PATCH /account/consent when is_team_override is true")` |
| US-004 AC-13 | `it("displays explanatory text about ML training data usage")` |
| US-005 AC-1 | `it("renders a Delete Account button on the account page")` |
| US-005 AC-2 | `it("opens confirmation modal on Delete Account click without making API call")` |
| US-005 AC-3 | `it("modal contains text about permanent deletion and 30-day GDPR erasure period")` |
| US-005 AC-4 | `it("closes modal without API call when Cancel is clicked")` |
| US-005 AC-5 | `it("confirmation modal contains a Delete My Account button")` |
| US-005 AC-6 | `it("calls DELETE /account when Delete My Account confirm button is clicked")` |
| US-005 AC-6 (loading) | `it("shows loading state and disables confirm button during DELETE /account")` |
| US-005 AC-7 | `it("signs out and navigates to / after 204 from DELETE /account")` |
| US-005 AC-8 | `it("shows error inside modal and keeps it open when DELETE /account fails")` |
| US-005 AC-9 | `it("ProtectedRoute is present wrapping the account page")` |
| TECH partial PATCH | `it("only includes changed fields in the PATCH /account request body")` |
| TECH 204 | `it("does not treat 204 No Content as an error")` |
| TECH sign-out order | `it("calls supabase.auth.signOut before navigating after deletion")` |
| TECH Rule 7 | `it("never calls PATCH /account/consent when is_team_override is true on any interaction")` |

---

**Fixtures / test doubles:**

```typescript
// MSW handlers — registered in tests/sessions/S3-E.test.tsx setup

// Default mock: individual user, no team override
const mockAccount: AccountResponse = {
  id: "a1b2c3d4-0000-0000-0000-000000000001",
  email: "jane@example.com",
  display_name: "Jane Doe",
  email_verified: true,
  role: "user",
  team_id: null,
};

const mockConsent: ConsentResponse = {
  opted_in: false,
  effective_opted_in: false,
  is_team_override: false,
  updated_at: "2024-01-15T10:30:00Z",
};

// Variant: team member with team override
const mockConsentTeamOverride: ConsentResponse = {
  opted_in: false,
  effective_opted_in: true,
  is_team_override: true,
  updated_at: "2024-01-10T08:00:00Z",
};

// MSW server handlers:
// GET /account → 200 mockAccount
// PATCH /account → 200 { ...mockAccount, ...patchedFields }
// PATCH /account (failure variant) → 500 { detail: "Internal server error" }
// GET /account/consent → 200 mockConsent  
// PATCH /account/consent → 200 updatedConsent
// PATCH /account/consent (failure variant) → 500
// DELETE /account → 204
// DELETE /account (failure variant) → 500

// Supabase mock:
// supabase.auth.signOut → jest.fn() resolving to { error: null }
// Wrap in vi.mock('../../frontend/src/auth/supabaseClient', () => ({
//   supabase: { auth: { signOut: vi.fn().mockResolvedValue({ error: null }) } }
// }))

// useAuth mock:
// vi.mock('../../frontend/src/auth/useAuth', () => ({
//   useAuth: () => ({ user: mockAccount, isAuthenticated: true, isLoading: false })
// }))

// react-router-dom mock (navigate):
// const mockNavigate = vi.fn()
// vi.mock('react-router-dom', () => ({ ...actualModule, useNavigate: () => mockNavigate }))
```

---

**Pre-conditions:**

- `frontend/package.json` must list `vitest`, `@testing-library/react`, `@testing-library/user-event`, `msw`, `@testing-library/jest-dom` as devDependencies (established by S0-B).
- `frontend/vite.config.ts` must configure `test.environment: 'jsdom'` (established by S0-A).
- The `tests/sessions/` directory must exist (established by S0-B scaffold).
- S1-F files must be importable (they are pre-stubbed by S0-A/S1-F); mocks override their runtime behavior.
- No database, Redis, or S3 connection is needed — all API calls are intercepted by MSW.

---

**Isolation rule:**

This test file mocks all API responses with MSW and mocks all S1-F imports (`useAuth`, `supabaseClient`, `ProtectedRoute`, `Layout`, `apiClient`). It passes when this session's PR is the only one merged — no backend session or other frontend session needs to have merged first.

---

##### Checkpoint

- **One-sentence observable outcome:** An authenticated user navigating to `/account` sees their display name, email, and ML consent toggle pre-populated from the API; can save profile changes with success feedback; can toggle consent (or sees a "Managed by your team" disabled state); and clicking "Delete Account" → confirming opens a GDPR-disclosure modal that on confirmation signs them out and redirects to `/`.
- **Shippability claim:** This PR is independently mergeable to main even if no other session in the same wave has merged. All API dependencies are mocked in tests; the runtime will fall back to the pre-stubbed endpoint stubs from S0-A until S2-F merges.

---

##### Output and handoff

| Export | Kind | Shape | Consuming Session(s) | Load-bearing? |
|---|---|---|---|---|
| `Account` (default export) | React component | `() => JSX.Element` — page at `/account` | S0-A router stub (already wired), S4-A E2E tests | No |
| `ProfileForm` | React component | `(props: ProfileFormProps) => JSX.Element` | S4-A E2E tests | No |
| `ConsentToggle` | React component | `(props: ConsentToggleProps) => JSX.Element` | S4-A E2E tests | No |
| `DeleteAccount` | React component | `(props: DeleteAccountProps) => JSX.Element` | S4-A E2E tests | No |
| `AccountResponse` | TypeScript interface | `{ id: string; email: string; display_name: string; email_verified: boolean; role: UserRole; team_id: string \| null }` | S4-A E2E tests; potentially S3-D, S3-B if they render user display name | **[LOAD-BEARING]** — must not rename fields after merge; S2-F backend contract must match |
| `ConsentResponse` | TypeScript interface | `{ opted_in: boolean; effective_opted_in: boolean; is_team_override: boolean; updated_at: string }` | S4-A E2E tests; S3-D (CorrectionStore reads effective consent state for display) | **[LOAD-BEARING]** — shape must match S2-F `GET /account/consent` response |

---

```json
{
  "test": {
    "cmd": "cd frontend && npx vitest run ../../tests/sessions/S3-E.test.tsx",
    "file": "tests/sessions/S3-E.test.tsx"
  },
  "checkpoint": "An authenticated user navigating to /account sees their display name, email, and ML consent toggle pre-populated from the API; can save profile changes with success feedback; can toggle consent (or sees a 'Managed by your team' disabled state); and clicking Delete Account then confirming signs them out and redirects to /.",
  "manualAcs": [],
  "exports": [
    {
      "kind": "module",
      "name": "Account",
      "shape": "frontend/src/pages/Account.tsx"
    },
    {
      "kind": "module",
      "name": "ProfileForm",
      "shape": "frontend/src/features/account/ProfileForm.tsx"
    },
    {
      "kind": "module",
      "name": "ConsentToggle",
      "shape": "frontend/src/features/account/ConsentToggle.tsx"
    },
    {
      "kind": "module",
      "name": "DeleteAccount",
      "shape": "frontend/src/features/account/DeleteAccount.tsx"
    },
    {
      "kind": "type",
      "name": "AccountResponse",
      "shape": "{ id: string; email: string; display_name: string; email_verified: boolean; role: 'user' | 'team_member' | 'team_admin'; team_id: string | null }"
    },
    {
      "kind": "type",
      "name": "ConsentResponse",
      "shape": "{ opted_in: boolean; effective_opted_in: boolean; is_team_override: boolean; updated_at: string }"
    },
    {
      "kind": "type",
      "name": "ProfileFormProps",
      "shape": "{ initialData: AccountResponse; onSaveSuccess: (updated: AccountResponse) => void }"
    },
    {
      "kind": "type",
      "name": "ConsentToggleProps",
      "shape": "{ initialData: ConsentResponse; onConsentChange?: (updated: ConsentResponse) => void }"
    },
    {
      "kind": "type",
      "name": "DeleteAccountProps",
      "shape": "{ onDeleteSuccess?: () => void }"
    }
  ]
}
```