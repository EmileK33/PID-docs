#### S3-A — Frontend: Auth Pages

**Phase 3 | Frontend | Needs: S1-F, S2-A**

##### Objective

Build the seven authentication page components (Register, Login, VerifyEmail, PasswordResetRequest, PasswordResetConfirm, OAuthCallback, AccountLinkPrompt) for the PID Analyzer React SPA, enabling users to create accounts, authenticate via email/password or Google OAuth, verify email addresses, reset passwords, and handle account-link conflicts — all as the entry gate to the authenticated product.

##### Scope

**P0 MVP** — All work in this session is P0.

- US-001 (P0): User registration and email verification
- US-002 (P0): Email/password and Google OAuth login with account linking and brute-force lockout
- Password reset request and confirm (P0 — supporting flows referenced in §1.13 and §1.5)

No P1 stubs are required in this session. All seven files are fully implemented.

##### Technology constraints

**Must use:**
- React 18 with functional components and hooks (§1.8: "React + Vite — pure SPA sufficient for authenticated views")
- Vite as build tool (§1.8)
- `@supabase/supabase-js` Supabase Auth client SDK — specifically `supabase.auth.signInWithOAuth` for Google OAuth initiation; provided via the `supabase` export from S1-F's `frontend/src/auth/supabaseClient.ts`
- `frontend/src/api/client.ts` (S1-F) for all HTTP calls to the FastAPI backend — no raw `fetch` or `axios` imports
- Vitest + `@testing-library/react` + `@testing-library/user-event` for component tests
- `msw` (Mock Service Worker v2) for API mocking in tests

**Must NOT use:**
- Next.js (§1.8 explicitly separates SPA from marketing site; mixing them is architecturally irreversible)
- Direct `fetch` or `axios` calls that bypass the shared `apiClient` from S1-F
- Any client-side session storage of raw JWT access tokens outside of Supabase SDK's internal management
- Inline OAuth-to-password-account merging on any code path (§1.7 hard constraint: "never silent merge")
- Client-side brute-force lockout counters — lockout state must be derived exclusively from server 429 responses (§1.9)

##### Performance targets

None — see downstream sessions. Auth pages own no hard SLA directly. The server-side brute-force lockout (5 attempts → 15-minute block) is a **hard security constraint** (§1.9) enforced via Redis on the backend; the frontend renders the error state returned by the server.

##### Owned files

- `frontend/src/pages/auth/Register.tsx`
- `frontend/src/pages/auth/Login.tsx`
- `frontend/src/pages/auth/VerifyEmail.tsx`
- `frontend/src/pages/auth/PasswordResetRequest.tsx`
- `frontend/src/pages/auth/PasswordResetConfirm.tsx`
- `frontend/src/pages/auth/OAuthCallback.tsx`
- `frontend/src/pages/auth/AccountLinkPrompt.tsx`

##### Read-only imports

| Owning Session | File | Named exports required |
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

##### Do not touch

Explicit files this session must never modify:

- `frontend/src/main.tsx` — entry point, pre-stubbed by S0-A
- `frontend/src/App.tsx` — app root, pre-stubbed by S0-A
- `frontend/src/router.tsx` — all route stubs pre-wired by S0-A; this session's components are already lazily imported there
- `frontend/src/pages/_stubs.tsx` — route placeholder file, pre-stubbed by S0-A
- `frontend/src/types/contracts.ts` — owned by S0-A
- All S1-F files: `frontend/src/api/client.ts`, `frontend/src/api/endpoints.ts`, `frontend/src/auth/AuthContext.tsx`, `frontend/src/auth/useAuth.ts`, `frontend/src/auth/supabaseClient.ts`, `frontend/src/hooks/useSSE.ts`, `frontend/src/hooks/usePolling.ts`, `frontend/src/components/Layout.tsx`, `frontend/src/components/Nav.tsx`, `frontend/src/components/GraceBanner.tsx`, `frontend/src/components/ProtectedRoute.tsx`, `frontend/src/lib/storage.ts`, `frontend/src/lib/analytics.ts`, `frontend/src/styles/globals.css`
- All S2-A files: `backend/app/api/routers/auth.py`, `backend/app/services/auth_service.py`, `backend/app/services/password_reset.py`, `tests/integration/test_auth_endpoints.py`

##### Architecture context

From §1.8 Technology Stack:

> **Frontend SPA**: React + Vite — Canvas rendering via Konva.js requires rich ecosystem; pure SPA sufficient for authenticated views; changing post-build would require full frontend rewrite
>
> **Auth**: Supabase Auth (self-hosted) — JWT RS256, Google OAuth, session invalidation via `admin.signOut(userId)`, Postgres-native; selected over Auth0 to reduce vendor lock-in

From §1.7 Third-Party Dependencies:

> **Supabase Auth**: JWT RS256; Google OAuth 2.0 via Supabase; `admin.signOut(userId)` API for session revocation
>
> **Google OAuth 2.0**: OAuth 2.0 authorization code flow — Account-link prompt required when OAuth email matches existing password account; never silent merge

From §1.6 Route Manifest — Frontend Page Routes:

> ```
> /register
> /login
> /verify-email
> ```

From §1.6 Route Manifest — Backend API Endpoints consumed by this session:

> ```
> POST   /auth/register
> POST   /auth/login
> POST   /auth/oauth/google
> POST   /auth/refresh
> POST   /auth/logout
> POST   /auth/password-reset/request
> POST   /auth/password-reset/confirm
> ```

From §1.5 HTTP Status Code Contracts:

> | Condition | Required code | Must never return |
> |---|---|---|
> | Auth logout success | `204` | `200` |
> | Password reset request success | `204` | `200` |
> | Password reset confirm success | `204` | `200` |
> | Unauthenticated request to protected endpoint | `401` | `403`, `200` |
> | Authenticated user accessing resource they do not own | `403` | `404`, `200` |

From §1.4 Critical Ordering Rules:

> **Rule 12**: "On password reset, all tokens are invalidated via Supabase Auth's `admin.signOut(userId)` call; `USER.token_invalidated_at` is simultaneously updated."

From §1.9 Performance Targets:

> | Brute-force lockout | After 5 failed attempts, 15-minute lockout | Hard constraint (security) | Redis TTL-based counter |

From §1.11 Cross-Session Runtime Patterns — Redis Cache Keys:

> | `brute_force:{email}` | FastAPI login handler | FastAPI login handler | 15-minute TTL |

From §1.11 Cross-Session Runtime Patterns — Browser Storage Keys:

> | Key | Storage Type | Written By | Read By | Purpose |
> |---|---|---|---|---|
> | `graceBannerDismissed` | sessionStorage | Drawing Library / global nav component | Global nav component | Session-scoped suppression of grace period banner; resets on new session |

From §1.2 Database Schema:

> ```sql
> CREATE TABLE "user" (
>   id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
>   email                  VARCHAR NOT NULL,
>   display_name           VARCHAR NOT NULL,
>   password_hash          VARCHAR,
>   email_verified         BOOLEAN NOT NULL DEFAULT FALSE,
>   team_id                UUID REFERENCES team(id),
>   role                   VARCHAR NOT NULL CHECK (role IN ('user','team_member','team_admin')),
>   deleted_at             TIMESTAMPTZ,
>   anonymous_id           VARCHAR,
>   token_invalidated_at   TIMESTAMPTZ,
>   CONSTRAINT user_email_unique UNIQUE (email)
> );
> ```

From §1.1 Shared Contracts:

> ```typescript
> type UserRole = 'user' | 'team_member' | 'team_admin';
> ```

From §1.13 Feature Scope — P0:

> - US-001: User registration and email verification
> - US-002: Email/password and Google OAuth login with account linking and brute-force lockout

From §1.10 Analytics Event Contracts (governing what this session must NOT fire):

> | Event Name | Code Surface That Fires It |
> |---|---|
> | `drawing_uploaded` | FastAPI — `POST /drawings/{id}/upload-complete` handler |
> | `processing_complete` | ML Worker |
> | `correction_action` | FastAPI — `PATCH /symbols/{id}` and `POST /drawings/{id}/symbols` handlers |
> | ... (all 9 events) | Server-side only — Must NEVER fire from: Browser client |

##### User stories and acceptance criteria

*Note: Verbatim user story text is not enumerated in the specification document. The following stories and acceptance criteria are constructed directly from §1.13 feature scope descriptions, §1.4 Critical Ordering Rules, §1.5 HTTP Status Code Contracts, §1.7 Third-Party Dependencies, §1.9 Performance Targets, and §1.2 Database Schema. All AC scenarios are derived without interpretation.*

---

**US-001 — User Registration and Email Verification**

As a new user, I want to create an account with my email, password, and display name so that I can access the PID Analyzer.

- **AC-1**: Submitting the registration form with a valid email address, a password of at least 8 characters, and a non-empty display name calls `POST /auth/register` and, on a 201 success response, navigates the user to `/verify-email`.
- **AC-2**: The `/verify-email` page displays a "Check your email" heading, a message instructing the user to click the verification link in their email, and a link back to `/login`. No authenticated actions are available on this page.
- **AC-3**: If the server returns 409 on registration, the form displays an inline error on the email field: "An account with this email already exists."
- **AC-4**: Client-side validation prevents form submission if the email field does not conform to a valid email format, displaying "Please enter a valid email address." without making a network call.
- **AC-5**: Client-side validation prevents form submission if the password is fewer than 8 characters, displaying "Password must be at least 8 characters." without making a network call.
- **AC-6**: Client-side validation prevents form submission if the display name field is empty, displaying "Display name is required." without making a network call.
- **AC-7**: The submit button is disabled and shows a loading indicator for the duration of the `POST /auth/register` request; it re-enables on any error response.
- **AC-8**: A 5xx or network-level error during registration displays a generic banner: "Something went wrong. Please try again." without exposing internal error details.

---

**US-002 — Email/Password and Google OAuth Login with Account Linking and Brute-Force Lockout**

As a registered user, I want to log in with my email and password or my Google account so that I can access my drawings; and as the system, I must block brute-force login attempts and prevent silent OAuth-to-password-account merges.

- **AC-1**: Submitting valid email/password credentials to `POST /auth/login` (200 response) stores the returned session via the `AuthContext` from S1-F and redirects the user to `/dashboard`.
- **AC-2**: A 401 response from `POST /auth/login` displays the error message: "Invalid email or password."
- **AC-3**: A 429 response from `POST /auth/login` displays: "Too many failed attempts. Please try again in 15 minutes." and disables the submit button for the lifetime of the rendered component instance.
- **AC-4**: The lockout display state (from AC-3) does not persist across a full page reload; the server remains the authoritative source of lockout state, re-surfaced only via the next 429 response.
- **AC-5**: Clicking the "Sign in with Google" button calls `supabase.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: <origin>/oauth-callback } })` from the S1-F Supabase client instance.
- **AC-6**: The `OAuthCallback` page shows a full-page loading indicator on mount, reads the session from `supabase.auth.getSession()`, and on a session present calls `POST /auth/oauth/google` with the access token; if that call returns 200, it navigates to `/dashboard`; if it returns 409 with `detail: "account_link_required"`, it navigates to `/account-link-prompt` passing the conflicting email.
- **AC-7**: If no Supabase session is available in `OAuthCallback` (e.g., direct navigation or OAuth failure), the page redirects to `/login`.
- **AC-8**: The `AccountLinkPrompt` page displays the conflicting email address, explains that an account with that email already exists, and offers a primary "Link accounts" button and a secondary "Cancel — return to sign in" button.
- **AC-9**: Clicking "Cancel" on `AccountLinkPrompt` navigates to `/login` without initiating any merge or link action; accounts are never silently merged on any code path.
- **AC-10**: Submitting a valid email to `POST /auth/password-reset/request` (204 response) replaces the form with the message: "If this email is registered, a reset link has been sent." This message is always shown regardless of whether the email is registered (preventing enumeration).
- **AC-11**: The `PasswordResetConfirm` page reads the `token` query parameter from the URL on mount; if the token is absent, it immediately redirects to `/password-reset/request`.
- **AC-12**: Submitting a new password on `PasswordResetConfirm` calls `POST /auth/password-reset/confirm` with `{ token, password }`; a 204 response replaces the form with: "Your password has been reset. All active sessions have been signed out." and a link to `/login`.
- **AC-13**: A 400 response from `POST /auth/password-reset/confirm` displays: "This reset link is invalid or has expired. Please request a new one." with a link to `/password-reset/request`.
- **AC-14**: Client-side validation on `PasswordResetConfirm` prevents submission if the new password is fewer than 8 characters (displays "Password must be at least 8 characters.") or if the confirm password field does not match (displays "Passwords do not match.").
- **AC-15**: The submit button on all auth forms is disabled and shows a loading indicator while the corresponding HTTP request is in flight.
- **AC-16**: Authenticated users who navigate to `/login` or `/register` are immediately redirected to `/dashboard` on component mount.

##### UX and design specification

*The specification does not provide a dedicated visual design system. The following is derived from functional requirements in §1.1–§1.13, the S1-F shared infrastructure (`globals.css`, `Layout`), and the interaction constraints imposed by §1.4, §1.5, §1.7, and §1.9. All pages use the `Layout` wrapper from S1-F for consistent chrome.*

---

**`/register` — Register.tsx**

Form fields (all controlled React state):
- `display_name`: text input, required, label: "Display name"
- `email`: email input, required, label: "Email address"
- `password`: password input (type="password"), required, label: "Password", helper text: "At least 8 characters"

Submit button label: "Create account"

Below form: link to `/login` — "Already have an account? Sign in"

Client-side validation sequence (evaluated on submit, in order, short-circuit on first failure):
1. `display_name` empty → show field error "Display name is required."
2. `email` invalid format (regex) → show field error "Please enter a valid email address."
3. `password` length < 8 → show field error "Password must be at least 8 characters."

State machine:
- `idle` → `submitting` (disable all inputs + button, show spinner in button) → `success` (navigate to `/verify-email`) or `error` (re-enable form, show error)
- On 409: field-level error on email field
- On 5xx / network failure: banner error above form

Already-authenticated guard: on mount, if `useAuth().isAuthenticated`, navigate to `/dashboard`.

---

**`/verify-email` — VerifyEmail.tsx**

Static, no form. Content:
- Heading: "Check your email"
- Body: "We've sent a verification link to your email address. Click the link to verify your account and sign in."
- Link: "Return to sign in" → `/login`

No protected actions. No network calls on this page.

---

**`/login` — Login.tsx**

Form fields (all controlled React state):
- `email`: email input, required, label: "Email address"
- `password`: password input, required, label: "Password"

Buttons (in order, full width):
- Primary submit: "Sign in"
- Divider: "or"
- OAuth button: "Sign in with Google" (Google logo icon prefix)

Below form:
- Link to `/password-reset/request` — "Forgot password?"
- Link to `/register` — "Don't have an account? Register"

Client-side validation (on submit):
1. `email` non-empty + valid format → "Please enter a valid email address."
2. `password` non-empty → "Password is required."

State machine:
- `idle` → `submitting` → `success` (store session, navigate `/dashboard`) or `error`
- On 401: banner "Invalid email or password."
- On 429: enter `locked` state — show message "Too many failed attempts. Please try again in 15 minutes.", hide submit button, show lockout banner; `locked` state is component-local and does NOT persist to localStorage or sessionStorage
- On 5xx: banner "Something went wrong. Please try again."

Google OAuth button behavior:
```ts
supabase.auth.signInWithOAuth({
  provider: 'google',
  options: { redirectTo: `${window.location.origin}/oauth-callback` }
})
```
No additional state management required on click — Supabase handles the redirect.

Already-authenticated guard: on mount, if `useAuth().isAuthenticated`, navigate to `/dashboard`.

---

**`/oauth-callback` — OAuthCallback.tsx**

Renders full-page loading spinner only. No user-visible text beyond loading state.

Mount sequence:
1. Call `supabase.auth.getSession()`
2. If `session === null`: navigate to `/login?error=oauth_failed`
3. If `session` present: call `POST /auth/oauth/google` with `Authorization: Bearer {session.access_token}`
   - 200: update auth context via `useAuth`, navigate to `/dashboard`
   - 409 `{ detail: "account_link_required", email: string }`: navigate to `/account-link-prompt?email={encodeURIComponent(email)}`
   - Any other error: navigate to `/login?error=oauth_error`

Error display: errors surface via navigation redirect to `/login` with query param — no error UI rendered in `OAuthCallback` itself.

---

**`/account-link-prompt` — AccountLinkPrompt.tsx**

Reads `email` from URL query param (`?email=...`).

Content:
- Heading: "Account already exists"
- Body: "An account with the email **{email}** already exists. Would you like to link your Google account to it?"
- Primary button: "Link accounts"
- Secondary button: "Cancel — return to sign in"

"Link accounts" behavior:
- Calls `POST /auth/oauth/link` (stub: show loading, then navigate to `/dashboard` with a success message if endpoint not yet implemented — implement as a stub that logs a console warning and redirects)
- On success: navigate to `/dashboard`

"Cancel" behavior:
- Navigate to `/login` — no merge, no API call, no side effects.

Constraint: **accounts must never be silently merged** (§1.7). Any code path that bypasses this page when `account_link_required` is returned is a defect.

---

**`/password-reset/request` — PasswordResetRequest.tsx**

Form fields:
- `email`: email input, required, label: "Email address"

Submit button: "Send reset link"
Below form: link to `/login` — "Back to sign in"

Client-side validation:
- `email` valid format → "Please enter a valid email address."

Submit behavior:
- `idle` → `submitting` → `success` or `error`
- On 204: replace entire form content with: "If this email is registered, a reset link has been sent." (always shown, regardless of email existence — prevents enumeration)
- On 5xx: banner "Something went wrong. Please try again."

---

**`/password-reset/confirm` — PasswordResetConfirm.tsx**

On mount: read `token` from URL query string (`URLSearchParams`). If absent, immediately call `navigate('/password-reset/request')`.

Form fields (rendered only when token present):
- `password`: password input, required, label: "New password", helper: "At least 8 characters"
- `confirm_password`: password input, required, label: "Confirm new password"

Submit button: "Reset password"

Client-side validation:
1. `password` length < 8 → "Password must be at least 8 characters."
2. `confirm_password !== password` → "Passwords do not match."

Submit behavior:
- Send `{ token, password }` to `POST /auth/password-reset/confirm`
- On 204: replace form with success state — "Your password has been reset. All active sessions have been signed out." + link to `/login`
- On 400: show error — "This reset link is invalid or has expired. Please request a new one." + link to `/password-reset/request`
- On 5xx: banner "Something went wrong. Please try again."

Do NOT navigate automatically after 204 — user must click the `/login` link explicitly (sessions were invalidated, §1.4 Rule 12).

---

**Cross-cutting UX rules for all auth pages:**
- All pages wrapped in `Layout` from S1-F
- All form inputs are controlled (React state; `value` + `onChange`)
- Error messages use `role="alert"` for screen reader accessibility
- Submit buttons use `disabled` attribute during in-flight requests (not CSS-only)
- No inline styles; use `globals.css` utility classes from S1-F

##### Critical implementation notes

- **Never silently merge OAuth accounts**: From §1.7: "Account-link prompt required when OAuth email matches existing password account; never silent merge." Any code path that merges accounts without navigating through `AccountLinkPrompt` is a security defect, not a UX shortcut.

- **Password reset confirmation must NOT auto-navigate to an authenticated route**: From §1.4 Rule 12: "On password reset, all tokens are invalidated via Supabase Auth's `admin.signOut(userId)` call; `USER.token_invalidated_at` is simultaneously updated." After a 204 on `/auth/password-reset/confirm`, the user's session is invalidated server-side. Navigating automatically to `/dashboard` will result in a 401 and a broken experience. The success screen must require explicit user action (clicking the link to `/login`).

- **HTTP status 204 vs 200 for auth mutations**: From §1.5: password reset request → `204` (must never be `200`), password reset confirm → `204`, logout → `204`. Checking for `response.status === 200` on these endpoints is a silent failure — the request succeeds but the branch is never entered.

- **Brute-force lockout is server-enforced, not client-counted**: From §1.9 and §1.11: the Redis `brute_force:{email}` key with 15-minute TTL is managed entirely by the FastAPI login handler. The client must NOT maintain a local failure counter. The lockout UI state must be derived exclusively from receiving a 429 response. Implementing a client-side counter will diverge from the server's actual state after page reload.

- **OAuthCallback must not forward a dangling session**: If `supabase.auth.getSession()` returns a session but `POST /auth/oauth/google` returns an error, the auth context must NOT be updated. Navigating to `/dashboard` without updating auth context correctly produces a race condition where the user appears logged in locally but all API calls return 401.

- **Auth context update is the responsibility of `useAuth` from S1-F**: Session storage after login/OAuth must go through the `AuthContext` mechanisms exported by S1-F, not local component state. Storing session data in component state means it disappears on navigation.

- **Router stubs expect default exports**: The `router.tsx` (S0-A) uses `React.lazy(() => import('./pages/auth/Login'))`. Each file in this session must export its component as a **default export**. Named-only exports will produce a runtime "Expected a default export" error.

- **OAuthCallback `redirectTo` must use `window.location.origin`**: Hard-coding a URL breaks staging and development environments. The Supabase `redirectTo` option must be constructed at runtime: `` `${window.location.origin}/oauth-callback` ``.

- **Email enumeration prevention is a security requirement**: The PasswordResetRequest success message must be identical whether or not the submitted email is registered. Do NOT conditionally render "We found your account" vs "Email not found" — the 204 response is the same in both cases from the server (§1.5 says 204 for success; the server never returns 404 for an unregistered email on this endpoint).

- **PasswordResetConfirm with no URL token**: The redirect to `/password-reset/request` must happen inside a `useEffect` on mount, before any form renders. Rendering the form and then redirecting creates a flash of UI that confuses users.

- **Analytics events must not fire from this session**: From §1.10: "Must NEVER fire from: Browser client." The `trackEvent` import from S1-F is available but none of the 9 structured analytics events (§1.10) are triggered by auth page interactions. Do not add PostHog calls to these components.

- **Authenticated redirect guard placement**: The `navigate('/dashboard')` guard in `Register.tsx` and `Login.tsx` must be inside a `useEffect` that runs on mount, conditional on `useAuth().isAuthenticated`. Doing it synchronously in the render body will throw "You should call navigate() from a React.useEffect()" warnings and may produce double-renders.

- **Cross-session contract with S0-A router**: The route paths used in `navigate()` calls must exactly match the stubs in `router.tsx`. Specifically: `/dashboard`, `/login`, `/register`, `/verify-email`, `/oauth-callback`, `/account-link-prompt`, `/password-reset/request`, `/password-reset/confirm`. Any deviation silently produces a "no route matches" 404 within the SPA.

##### Mocking contract

Frontend session — every API endpoint called by this session, with method, path, and exact mock response shape. These shapes define the MSW handlers in the test file.

---

**`POST /auth/register`**

201 Success:
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "display_name": "Test User",
  "email_verified": false,
  "role": "user"
}
```

409 Duplicate email:
```json
{ "detail": "Email already registered" }
```

500 Server error:
```json
{ "detail": "Internal server error" }
```

---

**`POST /auth/login`**

200 Success:
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.mock.signature",
  "refresh_token": "mock-refresh-token-abc123",
  "token_type": "bearer",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "display_name": "Test User",
    "email_verified": true,
    "role": "user"
  }
}
```

401 Invalid credentials:
```json
{ "detail": "Invalid credentials" }
```

429 Brute-force lockout:
```json
{
  "detail": "Too many failed attempts. Please try again in 15 minutes.",
  "retry_after_seconds": 900
}
```

---

**`POST /auth/oauth/google`**

200 Success: same shape as `POST /auth/login` 200 above.

409 Account link required:
```json
{
  "detail": "account_link_required",
  "email": "user@example.com"
}
```

---

**`POST /auth/password-reset/request`**

204 Success: no response body.

---

**`POST /auth/password-reset/confirm`**

204 Success: no response body.

400 Invalid/expired token:
```json
{ "detail": "Invalid or expired reset token" }
```

---

**`POST /auth/logout`**

204 Success: no response body.

---

**Supabase client mock** (vi.mock of `frontend/src/auth/supabaseClient.ts`):

`supabase.auth.signInWithOAuth`:
```ts
vi.fn().mockResolvedValue({
  data: { url: 'https://accounts.google.com/o/oauth2/auth?mock=1', provider: 'google' },
  error: null
})
```

`supabase.auth.getSession` — authenticated variant:
```ts
vi.fn().mockResolvedValue({
  data: {
    session: {
      access_token: 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.mock.signature',
      user: { email: 'user@example.com', id: '550e8400-e29b-41d4-a716-446655440000' }
    }
  },
  error: null
})
```

`supabase.auth.getSession` — unauthenticated variant:
```ts
vi.fn().mockResolvedValue({ data: { session: null }, error: null })
```

##### Acceptance criteria checklist

- [ ] [Registration form renders with display_name, email, and password fields plus a submit button] [US-001 AC-1]
- [ ] [Submitting valid registration form calls POST /auth/register and navigates to /verify-email on 201] [US-001 AC-1]
- [ ] [/verify-email page renders "Check your email" heading and verification instructions] [US-001 AC-2]
- [ ] [/verify-email page renders a link to /login] [US-001 AC-2]
- [ ] [Server 409 on registration shows inline field error "An account with this email already exists."] [US-001 AC-3]
- [ ] [Invalid email format prevents form submission and shows "Please enter a valid email address."] [US-001 AC-4]
- [ ] [Password under 8 characters prevents submission and shows "Password must be at least 8 characters."] [US-001 AC-5]
- [ ] [Empty display name prevents submission and shows "Display name is required."] [US-001 AC-6]
- [ ] [Submit button is disabled and shows loading indicator while POST /auth/register is in flight] [US-001 AC-7]
- [ ] [5xx server error during registration shows generic "Something went wrong. Please try again." without internal details] [US-001 AC-8]
- [ ] [Login form renders with email, password fields, Sign In button, and Sign in with Google button] [US-002 AC-1]
- [ ] [Submitting valid credentials calls POST /auth/login, updates auth context, and navigates to /dashboard on 200] [US-002 AC-1]
- [ ] [401 response from POST /auth/login shows "Invalid email or password."] [US-002 AC-2]
- [ ] [429 response from POST /auth/login shows "Too many failed attempts. Please try again in 15 minutes."] [US-002 AC-3]
- [ ] [Submit button is disabled after 429 response for the lifetime of the component instance] [US-002 AC-3]
- [ ] [Lockout display state does not persist across a full page reload; only re-enters locked state on next 429] [US-002 AC-4] [MANUAL]
- [ ] [Clicking "Sign in with Google" calls supabase.auth.signInWithOAuth with provider 'google' and redirectTo containing /oauth-callback] [US-002 AC-5]
- [ ] [OAuthCallback renders a loading indicator on mount] [US-002 AC-6]
- [ ] [OAuthCallback navigates to /dashboard when POST /auth/oauth/google returns 200] [US-002 AC-6]
- [ ] [OAuthCallback navigates to /account-link-prompt with email query param when POST /auth/oauth/google returns 409 account_link_required] [US-002 AC-6]
- [ ] [OAuthCallback navigates to /login when supabase.auth.getSession returns null session] [US-002 AC-7]
- [ ] [AccountLinkPrompt renders the conflicting email address, "Link accounts" button, and "Cancel" button] [US-002 AC-8]
- [ ] [Clicking Cancel on AccountLinkPrompt navigates to /login without making any merge/link API call] [US-002 AC-9]
- [ ] [PasswordResetRequest shows success message on 204 that is the same regardless of email registration status] [US-002 AC-10]
- [ ] [Success message on PasswordResetRequest reads "If this email is registered, a reset link has been sent."] [US-002 AC-10]
- [ ] [PasswordResetConfirm redirects to /password-reset/request immediately if no token in URL] [US-002 AC-11]
- [ ] [PasswordResetConfirm calls POST /auth/password-reset/confirm with token from URL query param on submit] [US-002 AC-12]
- [ ] [204 response on PasswordResetConfirm shows "Your password has been reset. All active sessions have been signed out." and a link to /login] [US-002 AC-12]
- [ ] [400 response on PasswordResetConfirm shows "This reset link is invalid or has expired."] [US-002 AC-13]
- [ ] [PasswordResetConfirm client validation shows "Password must be at least 8 characters." for short password] [US-002 AC-14]
- [ ] [PasswordResetConfirm client validation shows "Passwords do not match." when confirm password differs] [US-002 AC-14]
- [ ] [Submit buttons on all auth forms are disabled and show loading state while HTTP request is in flight] [US-002 AC-15]
- [ ] [Authenticated users visiting /login are redirected to /dashboard on mount] [US-002 AC-16]
- [ ] [Authenticated users visiting /register are redirected to /dashboard on mount] [US-002 AC-16]

##### Independent Test

**Test file path** (TDD — written first, must fail before implementation): `frontend/tests/sessions/S3-A.test.tsx`

**Exact CI command**: `cd frontend && npx vitest run tests/sessions/S3-A.test.tsx`

**AC → assertion mapping**:

| AC | `it(...)` block name(s) |
|---|---|
| US-001 AC-1 | `it("renders registration form with display_name, email, and password fields")`, `it("navigates to /verify-email on successful registration (201)")` |
| US-001 AC-2 | `it("renders verify-email page with heading, instructions, and link to /login")` |
| US-001 AC-3 | `it("shows duplicate email inline error when server returns 409 on registration")` |
| US-001 AC-4 | `it("shows invalid email error client-side without submitting on malformed email")` |
| US-001 AC-5 | `it("shows password too short error client-side without submitting")` |
| US-001 AC-6 | `it("shows display name required error client-side without submitting")` |
| US-001 AC-7 | `it("disables submit and shows loading indicator while registration request is in flight")` |
| US-001 AC-8 | `it("shows generic error banner on 5xx during registration without internal details")` |
| US-002 AC-1 | `it("renders login form with email, password, and Google OAuth button")`, `it("updates auth context and navigates to /dashboard on successful login (200)")` |
| US-002 AC-2 | `it("shows invalid credentials error on 401 login response")` |
| US-002 AC-3 | `it("shows lockout message and disables submit on 429 login response")` |
| US-002 AC-4 | `[MANUAL]` |
| US-002 AC-5 | `it("calls supabase.auth.signInWithOAuth with provider google and correct redirectTo on OAuth button click")` |
| US-002 AC-6 | `it("OAuthCallback renders loading indicator on mount")`, `it("OAuthCallback navigates to /dashboard when POST /auth/oauth/google returns 200")`, `it("OAuthCallback navigates to /account-link-prompt with email when POST /auth/oauth/google returns 409 account_link_required")` |
| US-002 AC-7 | `it("OAuthCallback navigates to /login when supabase.auth.getSession returns null")` |
| US-002 AC-8 | `it("AccountLinkPrompt renders conflicting email, Link accounts button, and Cancel button")` |
| US-002 AC-9 | `it("AccountLinkPrompt Cancel button navigates to /login without calling any API")` |
| US-002 AC-10 | `it("PasswordResetRequest shows identical confirmation message on 204 regardless of email existence")` |
| US-002 AC-11 | `it("PasswordResetConfirm redirects to /password-reset/request immediately when no token in URL")` |
| US-002 AC-12 | `it("PasswordResetConfirm calls POST /auth/password-reset/confirm with URL token on submit")`, `it("PasswordResetConfirm shows success message with link to /login on 204")` |
| US-002 AC-13 | `it("PasswordResetConfirm shows expired token error on 400")` |
| US-002 AC-14 | `it("PasswordResetConfirm shows password too short error client-side")`, `it("PasswordResetConfirm shows passwords do not match error client-side")` |
| US-002 AC-15 | `it("submit buttons are disabled and show loading state during in-flight requests on all auth forms")` |
| US-002 AC-16 | `it("authenticated users visiting /login are redirected to /dashboard on mount")`, `it("authenticated users visiting /register are redirected to /dashboard on mount")` |

**Fixtures / test doubles**:

- `frontend/tests/mocks/handlers/auth.ts` — MSW v2 `http.post` handlers for all endpoints in the Mocking Contract. Each handler must use the exact response shapes specified above (same field names, same types). Parameterized by scenario (happy path, 409, 429, 400, 500) via exported named handlers that can be overridden per test with `server.use(...)`.
- `frontend/tests/mocks/supabase.ts` — `vi.mock('../../src/auth/supabaseClient', ...)` providing `supabase.auth.signInWithOAuth`, `supabase.auth.getSession`, and `supabase.auth.signOut` as `vi.fn()` with default return values matching the Mocking Contract shapes. Exported `mockSupabaseSession` and `mockSupabaseNoSession` helper factories for per-test override.
- `frontend/tests/mocks/useAuth.ts` — `vi.mock('../../src/auth/useAuth', ...)` exporting: `mockUseAuthUnauthenticated = { user: null, isAuthenticated: false, setSession: vi.fn() }` and `mockUseAuthAuthenticated = { user: mockUser, isAuthenticated: true, setSession: vi.fn() }`. Tests requiring the redirect-guard behavior must activate the authenticated variant via `vi.mocked(useAuth).mockReturnValue(mockUseAuthAuthenticated)`.
- `mockUser` fixture: `{ id: '550e8400-e29b-41d4-a716-446655440000', email: 'user@example.com', display_name: 'Test User', email_verified: true, role: 'user' as UserRole }`.
- `mockNavigate` — `vi.fn()` injected via `vi.mock('react-router-dom', ...)` wrapping `useNavigate`; all test assertions on navigation use `expect(mockNavigate).toHaveBeenCalledWith('/expected-path')`.
- All component renders use `MemoryRouter` with `initialEntries` matching the page under test (e.g., `['/password-reset/confirm?token=abc123']`).
- MSW server setup/teardown: `beforeAll(() => server.listen())`, `afterEach(() => server.resetHandlers())`, `afterAll(() => server.close())`.

**Pre-conditions**:

- S1-F merged: `useAuth`, `supabaseClient`, `apiClient`, `AUTH_ENDPOINTS`, `Layout` must be importable (mocked in tests, but real module path must resolve).
- S2-A merged: API endpoint paths in `AUTH_ENDPOINTS` (from S1-F) must match routes in this session's MSW handlers; if S2-A changes response shapes, MSW handlers in this brief's test file must be updated in lockstep.
- `frontend/.env.test` contains `VITE_SUPABASE_URL=http://localhost:54321` and `VITE_SUPABASE_ANON_KEY=mock-anon-key` (can be mock values; Supabase client is fully mocked via `vi.mock`).
- No running backend service required — all HTTP calls intercepted by MSW.

**Isolation rule**: This test passes when only S0-A, S1-F, and S3-A are merged. All backend API calls are mocked via MSW. The Supabase client is fully mocked via `vi.mock`. No dependency on any other Phase 2 or Phase 3 session. ✓ Passes in isolation.

##### Checkpoint

Navigating to `/register` in a running SPA renders a working three-field registration form; submitting it with valid inputs transitions to a `/verify-email` page with check-email instructions; navigating to `/login` and submitting valid credentials redirects to `/dashboard`; clicking "Sign in with Google" initiates the Supabase OAuth redirect; navigating to `/login` as an already-authenticated user immediately redirects to `/dashboard`.

**Shippability claim**: This PR is independently mergeable to main even if no other session in the same wave has merged. S3-A's prerequisites are S1-F (Phase 1, already merged) and S2-A (Phase 2, already merged) — both are from completed prior phases, not from sibling sessions in Phase 3.

##### Output and handoff

| Export | Kind | File | Consuming Session(s) | Load-bearing? |
|---|---|---|---|---|
| `Register` (default) | React component | `frontend/src/pages/auth/Register.tsx` | S0-A (`router.tsx` lazy import stub) | [LOAD-BEARING] — file path must not change after merge |
| `Login` (default) | React component | `frontend/src/pages/auth/Login.tsx` | S0-A (`router.tsx`) | [LOAD-BEARING] |
| `VerifyEmail` (default) | React component | `frontend/src/pages/auth/VerifyEmail.tsx` | S0-A (`router.tsx`) | [LOAD-BEARING] |
| `PasswordResetRequest` (default) | React component | `frontend/src/pages/auth/PasswordResetRequest.tsx` | S0-A (`router.tsx`) | [LOAD-BEARING] |
| `PasswordResetConfirm` (default) | React component | `frontend/src/pages/auth/PasswordResetConfirm.tsx` | S0-A (`router.tsx`) | [LOAD-BEARING] |
| `OAuthCallback` (default) | React component | `frontend/src/pages/auth/OAuthCallback.tsx` | S0-A (`router.tsx`) | [LOAD-BEARING] |
| `AccountLinkPrompt` (default) | React component | `frontend/src/pages/auth/AccountLinkPrompt.tsx` | S0-A (`router.tsx`) | [LOAD-BEARING] |

---

```json
{
  "test": {
    "cmd": "cd frontend && npx vitest run tests/sessions/S3-A.test.tsx",
    "file": "frontend/tests/sessions/S3-A.test.tsx"
  },
  "checkpoint": "Navigating to /register renders a working registration form; submitting valid inputs transitions to /verify-email; navigating to /login and submitting valid credentials redirects to /dashboard; clicking 'Sign in with Google' calls supabase.auth.signInWithOAuth; an already-authenticated user visiting /login is immediately redirected to /dashboard.",
  "manualAcs": [
    {
      "id": "US-002-AC-4",
      "text": "The lockout display state does not persist across a full page reload; the server remains the authoritative source of lockout state, re-surfaced only via the next 429 response."
    }
  ],
  "exports": [
    { "kind": "module", "name": "Register", "shape": "frontend/src/pages/auth/Register.tsx" },
    { "kind": "module", "name": "Login", "shape": "frontend/src/pages/auth/Login.tsx" },
    { "kind": "module", "name": "VerifyEmail", "shape": "frontend/src/pages/auth/VerifyEmail.tsx" },
    { "kind": "module", "name": "PasswordResetRequest", "shape": "frontend/src/pages/auth/PasswordResetRequest.tsx" },
    { "kind": "module", "name": "PasswordResetConfirm", "shape": "frontend/src/pages/auth/PasswordResetConfirm.tsx" },
    { "kind": "module", "name": "OAuthCallback", "shape": "frontend/src/pages/auth/OAuthCallback.tsx" },
    { "kind": "module", "name": "AccountLinkPrompt", "shape": "frontend/src/pages/auth/AccountLinkPrompt.tsx" }
  ]
}
```