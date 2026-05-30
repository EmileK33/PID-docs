#### S3-F — Frontend: Subscription & Upgrade

**Phase 3 | Frontend | Needs: S1-F, S2-E**

---

##### Objective

Build the Subscription & Upgrade frontend — the `/subscription` page, tier cards, Stripe Checkout redirect, post-checkout pending state (30 s webhook polling), upgrade prompt modal, and grace/cancellation messaging — so users can view, upgrade, downgrade, and monitor their billing tier entirely from the browser.

---

##### Scope

**P0 MVP** — all work in this session is P0.

Stories covered:
- **US-018** (P0): Free tier 3-drawing/month limit enforcement; upgrade prompt on limit hit; tier-gated features visible but inaccessible
- **US-019** (P0): Stripe Checkout upgrade (Pro and Team tiers); downgrade deferred to period end; pending state with 30 s webhook resolution timeout
- **US-020** (P0): Grace period handling; Stripe cancellation with access-until-period-end messaging; billing state reflected in subscription page UI

P1 stubs required:
- Team management link from TierCard (Team tier CTA post-purchase leads to `/teams` — stub as `/* P1: team workspace navigation */`)
- API key access feature row in TierCard for team tier (`/* P1: FR-11 API key access */`)

---

##### Technology constraints

From §1.8 (verbatim, selected entries):

> **Frontend SPA** | React + Vite | Canvas rendering via Konva.js requires rich ecosystem; pure SPA sufficient for authenticated views; changing post-build would require full frontend rewrite

> **Payments** | Stripe Billing (Checkout + Customer Portal + Webhooks) | Entire subscription state machine is Stripe-webhook-driven; changing would require rebuilding billing state machine

> **Analytics** | PostHog | Self-hostable, GDPR-compliant, named events with properties

Required libraries (from stack + session dependencies):
- `react` + `react-dom` (SPA layer)
- `vite` (build)
- Axios or `fetch` via `frontend/src/api/client.ts` (S1-F) — **must use the shared API client, not raw fetch**
- `frontend/src/lib/analytics.ts` (S1-F) — **must use shared analytics wrapper, never PostHog SDK directly**
- `@testing-library/react`, `@testing-library/user-event`, `vitest`, `msw` (testing)

**Must NOT use:**
- `@stripe/stripe-js` or any Stripe.js client library — the frontend's only Stripe interaction is redirecting to a server-generated Checkout URL; no client-side Stripe token creation
- Raw `window.posthog` — use shared `frontend/src/lib/analytics.ts` only
- Any in-memory state store other than React state/context for subscription data (no Zustand, Redux, etc. unless already established by S1-F)

---

##### Performance targets

From §1.9 (verbatim):

> **Stripe tier activation after Checkout redirect | <30 seconds | Monitoring target** | Stripe webhook handler + subscription update

This session is directly responsible for:
- Polling `GET /subscription` after Stripe Checkout redirect for up to **30 seconds** at a 2-second interval to detect tier change; displaying PendingState UI during this window
- Showing timeout/fallback messaging if the 30 s window elapses without a tier update

All other performance targets (dashboard load, canvas) are not owned by this session.

---

##### Owned files

```
frontend/src/pages/Subscription.tsx
frontend/src/features/subscription/TierCard.tsx
frontend/src/features/subscription/CheckoutRedirect.tsx
frontend/src/features/subscription/UpgradePrompt.tsx
frontend/src/features/subscription/PendingState.tsx
```

---

##### Read-only imports

| Owning Session | File | Named Exports Required |
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

##### Do not touch

- `frontend/src/main.tsx` — entry point, pre-stubbed by S0-A
- `frontend/src/App.tsx` — entry point, pre-stubbed by S0-A
- `frontend/src/router.tsx` — router, pre-stubbed by S0-A; routes for `/subscription` already stubbed
- `frontend/src/pages/_stubs.tsx` — stub registry, owned by S0-A
- `frontend/src/types/contracts.ts` — owned by S0-A; read-only
- `frontend/src/api/client.ts` — owned by S1-F
- `frontend/src/api/endpoints.ts` — owned by S1-F
- `frontend/src/auth/AuthContext.tsx` — owned by S1-F
- `frontend/src/auth/useAuth.ts` — owned by S1-F
- `frontend/src/auth/supabaseClient.ts` — owned by S1-F
- `frontend/src/hooks/useSSE.ts` — owned by S1-F
- `frontend/src/hooks/usePolling.ts` — owned by S1-F
- `frontend/src/components/Layout.tsx` — owned by S1-F
- `frontend/src/components/Nav.tsx` — owned by S1-F
- `frontend/src/components/GraceBanner.tsx` — owned by S1-F
- `frontend/src/components/ProtectedRoute.tsx` — owned by S1-F
- `frontend/src/lib/storage.ts` — owned by S1-F
- `frontend/src/lib/analytics.ts` — owned by S1-F
- `frontend/src/styles/globals.css` — owned by S1-F
- All backend files — owned by S2-E and other sessions
- All files owned by S3-A, S3-B, S3-C, S3-D, S3-E, S3-G, S3-H

---

##### Architecture context

From §1.3 — Subscription Billing State Transitions (verbatim):

```typescript
// Subscription Billing State Transitions
const BILLING_STATE_TRANSITIONS: Record<BillingState, BillingState[]> = {
  Active: ['Grace', 'Canceled'],
  Grace:  ['Active', 'Canceled'],   // → Active on payment resolved; → Canceled on grace expiry (downgrade to Free)
  Canceled: ['Active'],             // → Active on resubscribe
} as const;

// Grace period: 7 days from first invoice.payment_failed Stripe event
// Grace period day-1 email on entry; day-6 reminder email
```

From §1.3 — Feature-Tier Gate Matrix (verbatim):

```typescript
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

From §1.3 — Role-Permission Matrix (verbatim, billing_manage rows):

```typescript
const ROLE_PERMISSIONS = {
  user: {
    billing_manage: true,      // personal subscription
    ...
  },
  team_member: {
    billing_manage: false,
    ...
  },
  team_admin: {
    billing_manage: true,      // team subscription
    ...
  },
} as const;
```

From §1.4 — Critical Ordering Rules (verbatim):

> **Rule 8.** "The counter increment must occur at the point processing is initiated (job enqueued), not at job completion, to prevent race conditions from concurrent uploads."

> **Rule 9.** "The subscription state in the application database must be updated exclusively via Stripe webhook events (not inline after the payment redirect) to ensure consistency and idempotency."

> **Rule 10.** "Idempotency enforced via Stripe event ID stored in DB before any state mutation."

From §1.9 — Performance Targets (verbatim):

> **Stripe tier activation after Checkout redirect | <30 seconds | Monitoring target** | Stripe webhook handler + subscription update

From §1.10 — Analytics Event Contracts (verbatim):

> **`free_limit_reached`** | `{ event: 'free_limit_reached', timestamp: string, user_id: string, drawing_id: string, subscription_id: string }` | FastAPI — processing initiation handler | Free tier user attempts to initiate processing of drawing that would exceed 3/month limit | Processing job must not be queued | **Browser client; must fire before upgrade prompt is shown**

> **`subscription_upgraded`** | `{ event: 'subscription_upgraded', timestamp: string, user_id: string, subscription_id: string, previous_tier: TierId, new_tier: TierId }` | FastAPI — Stripe webhook handler (`customer.subscription.updated`) | ... | **Must NEVER fire from: Browser client; Stripe redirect handler inline**

> **`subscription_downgraded`** | `{ event: 'subscription_downgraded', timestamp: string, user_id: string, subscription_id: string, previous_tier: TierId, new_tier: TierId }` | FastAPI — Stripe webhook handler or downgrade confirmation handler | Subscription tier decreases (fires immediately at confirmation, not at period end) | None specified | **Browser client**

From §1.11 — Redis Cache Keys (verbatim):

> `subscription:flags:{user_id}` | Written By: FastAPI on login / Stripe webhook handler | Read By: FastAPI middleware (every authenticated request, feature-gate evaluation) | TTL: 5 minutes; invalidated on webhook receipt

> `graceBannerDismissed` | sessionStorage | GraceBanner component | Global nav component | Session-scoped suppression of grace period banner; resets on new session

From §1.1 — Shared Contracts (verbatim):

```typescript
// Subscription Billing State
type BillingState = 'Active' | 'Grace' | 'Canceled';

// Tier IDs
type TierId = 'free' | 'pro' | 'team';

// User Role
type UserRole = 'user' | 'team_member' | 'team_admin';
```

---

##### User stories and acceptance criteria

From §1.13 — Feature Scope P0 (verbatim):

> **US-018:** Free tier 3-drawing/month limit enforcement; upgrade prompt on limit hit; tier-gated features visible but inaccessible

> **US-019:** Stripe Checkout upgrade (Pro and Team tiers); downgrade deferred to period end; pending state with 30s webhook resolution timeout

> **US-020:** Grace period handling (7-day, day-1 and day-6 emails); Stripe cancellation (access until period end); idempotent webhook processing

**Derived acceptance criteria (from spec constraints):**

**US-018 — Free Tier Limit & Upgrade Prompt**
- AC-1: When a `free_limit_reached` signal is received (API 402/403 with appropriate error code from upload flow, or explicit prop from parent), `UpgradePrompt` is rendered and visible to the user
- AC-2: The `UpgradePrompt` contains a CTA that navigates to `/subscription`
- AC-3: On the `/subscription` page, revision_comparison and team_library feature rows for Free tier are rendered with a locked/disabled visual indicator (e.g., lock icon, greyed row)
- AC-4: Pro and Team tier cards each display an upgrade CTA that is interactive for a free-tier user
- AC-5: The monthly drawing limit (3) is shown in the Free tier card; Pro and Team cards show "Unlimited"

**US-019 — Stripe Checkout Upgrade Flow**
- AC-1: Clicking an upgrade CTA calls `POST /subscription/checkout` with the selected `tier_id`; on success the browser is redirected to the returned `checkout_url` (via `window.location.href`)
- AC-2: After Stripe redirects back to the app with `?checkout=pending` (or equivalent query param), `PendingState` is rendered immediately
- AC-3: `PendingState` polls `GET /subscription` every 2 seconds for up to 30 seconds
- AC-4: If `GET /subscription` returns a `tier_id` different from the pre-checkout value before 30 s elapses, `PendingState` transitions to a success confirmation showing the new tier name
- AC-5: If 30 seconds elapse without a tier change, `PendingState` renders a timeout message (e.g., "Your upgrade is being processed — check back in a moment") and stops polling
- AC-6: A downgrade CTA (e.g., "Switch to Free") displays confirmation text that the change will take effect at the end of the current billing period (`current_period_end`), not immediately; no `POST /subscription/checkout` is called immediately — [MANUAL] (downgrade initiation is a P1 Customer Portal redirect; this story covers the deferred-period-end messaging display only)
- AC-7: The currently active tier is visually distinguished in the tier cards (e.g., "Current Plan" badge, distinct border color); no upgrade CTA is shown for the active tier

**US-020 — Grace Period & Cancellation UI**
- AC-1: When `GET /subscription` returns `billing_state: 'Grace'`, the `/subscription` page renders a grace period notice prominently (distinct from the global `GraceBanner` in Nav) including the days remaining (derived from `grace_period_start + 7 days - now`)
- AC-2: The grace period notice includes a "Resolve payment" CTA (navigates to Stripe Customer Portal URL returned from `POST /subscription/checkout` with a manage-billing intent, or external Stripe link)
- AC-3: When `billing_state: 'Canceled'` and `current_period_end` is in the future, the subscription page shows messaging that access continues until `current_period_end` (formatted date)
- AC-4: When `billing_state: 'Canceled'` and `current_period_end` is in the past (or null), the subscription page renders the Free tier as the active plan
- AC-5: The subscription page never attempts to directly modify Stripe state (all mutations go through `POST /subscription/checkout`); it is a read + initiate-only surface

---

##### UX and design specification

**Page: `/subscription`**

Route: `/subscription` — protected route (requires authentication).

**Data fetching:**
- On mount, call `GET /subscription` to retrieve the current subscription record.
- The response drives all conditional rendering below.
- Re-fetch after `PendingState` resolves (success or timeout).

**Layout structure:**
```
<Layout>
  [GraceBanner — rendered by Nav/Layout from S1-F if billing_state = 'Grace']
  <SubscriptionPage>
    [Grace Period Section — conditional, billing_state = 'Grace']
    [Cancellation Notice — conditional, billing_state = 'Canceled']
    [PendingState — conditional, URL has ?checkout=pending]
    <TierCards row>
      <TierCard tier="free" />
      <TierCard tier="pro" />
      <TierCard tier="team" />
    </TierCards>
  </SubscriptionPage>
</Layout>
```

**TierCard component spec:**

Props:
```typescript
interface TierCardProps {
  tier: TierId;
  currentTierIdForUser: TierId;
  billingState: BillingState;
  currentPeriodEnd: string | null; // ISO 8601
  onUpgrade: (tierId: TierId) => void;
  isUpgrading: boolean; // loading state during checkout initiation
}
```

Content per tier card:
- **Header**: Tier name ("Free" / "Pro" / "Team")
- **Price**: Display pricing text (static copy — Free: "$0/month"; Pro: "$X/month"; Team: "$Y/month" — use placeholder copy `$29/month` for Pro, `$79/month` for Team since pricing is not in spec; mark with `// TODO: replace with dynamic pricing from API`)
- **Monthly drawing limit**: "3 drawings/month" (free) | "Unlimited" (pro, team)
- **Feature rows** (one per feature in TIER_FEATURE_GATES):
  - `export_csv_xlsx`: "CSV & XLSX Export" — available all tiers
  - `revision_comparison`: "Revision Comparison" — locked on Free (lock icon + greyed text), available Pro/Team
  - `team_library`: "Team Library" — locked on Free and Pro, available Team only
  - `api_access`: "API Access" — locked on all tiers with `/* P1: FR-11 */` comment
- **CTA button**:
  - If `tier === currentTierIdForUser` and `billingState === 'Active'`: render "Current Plan" badge (disabled button, no action)
  - If `tier === currentTierIdForUser` and `billingState === 'Grace'`: render "Current Plan (Payment Issue)" (disabled, styled warning)
  - If `tier === currentTierIdForUser` and `billingState === 'Canceled'`: render "Reactivate" button → calls `onUpgrade(tier)`
  - If `tier` is higher than `currentTierIdForUser` (free<pro<team): render "Upgrade to [Tier]" button → calls `onUpgrade(tier)`
  - If `tier` is lower than `currentTierIdForUser`: render "Downgrade" button → shows inline deferred-period-end copy ("Takes effect [current_period_end date]") — **does not call onUpgrade** — [MANUAL] for actual downgrade initiation (P1 Customer Portal); button may be disabled with tooltip explaining deferral

Tier ordering for comparison: `free = 0`, `pro = 1`, `team = 2`.

**CheckoutRedirect component spec:**

This is a thin handler, not a visible UI element. It:
1. Accepts `tierId: TierId` prop
2. On mount (or on explicit trigger), calls `POST /subscription/checkout` with `{ tier_id: tierId }`
3. Shows a loading spinner while the request is in flight
4. On success: sets `window.location.href = response.checkout_url`
5. On error: renders an error message with retry option

**UpgradePrompt component spec:**

Props:
```typescript
interface UpgradePromptProps {
  reason: 'free_limit_reached' | 'feature_gated';
  featureName?: string; // e.g., "Revision Comparison" for feature_gated
  onDismiss?: () => void;
}
```

Rendered as a modal overlay or inline callout (use a modal for `free_limit_reached`, inline callout for `feature_gated`).

Content:
- `free_limit_reached`: "You've reached your 3 drawing limit for this month. Upgrade to Pro for unlimited processing." + "Upgrade Now" CTA (navigates to `/subscription`) + "Dismiss" button
- `feature_gated`: "[featureName] is available on Pro and Team plans." + "See Plans" CTA (navigates to `/subscription`) + "Dismiss" button

Export `UpgradePrompt` for use by S3-C (Upload Flow) and S3-B (Drawing Library).

**PendingState component spec:**

Props:
```typescript
interface PendingStateProps {
  previousTierId: TierId;
  onResolved: (newTierId: TierId) => void;
  onTimeout: () => void;
}
```

Behavior:
- On mount: begin polling `GET /subscription` every 2000 ms
- Poll timeout: 30,000 ms total (15 polls maximum)
- If `response.tier_id !== previousTierId`: call `onResolved(response.tier_id)`, stop polling
- If 30 s elapsed without change: call `onTimeout()`, stop polling
- Must clean up polling interval on unmount (prevent memory leak / state updates on unmounted component)

UI states:
- **Polling**: spinner + "Activating your [tier] plan… this usually takes a few seconds"
- **Resolved**: success checkmark + "Your plan has been upgraded to [new tier]!" + "Continue" button (navigates to `/dashboard`)
- **Timeout**: warning icon + "Your upgrade is being processed. Check back in a moment — it may take up to a minute." + "Go to Dashboard" button

**Subscription page URL handling:**

On navigation to `/subscription?checkout=pending&tier=pro` (after Stripe redirect), the page:
1. Reads `?checkout=pending` query param
2. Reads `?tier=pro` (or whichever tier was being upgraded to) as `previousTierIdForUser` before checkout
3. Renders `PendingState` with those values, suppressing the TierCards until resolved

`?checkout=success` (after explicit success): show success banner, then render normal TierCards.

**Grace Period Section:**

Rendered when `subscription.billing_state === 'Grace'`, above the TierCards:
```
[Warning banner]
"Your payment could not be processed. Your account will be downgraded to Free on [grace_period_start + 7 days].
Update your payment method to maintain access."
[Button: "Update Payment Method"] → calls POST /subscription/checkout with intent=portal (or equivalent)
```

Days remaining computed client-side: `Math.max(0, Math.ceil((new Date(grace_period_start).getTime() + 7*24*3600*1000 - Date.now()) / (24*3600*1000)))`.

**Cancellation Notice:**

Rendered when `subscription.billing_state === 'Canceled'` and `current_period_end` is in the future:
```
[Info banner]
"Your subscription has been canceled. You have access to [current tier] features until [current_period_end formatted date]."
[Button: "Reactivate"] → opens TierCard upgrade flow
```

**State management rules:**
- All subscription data is fetched from `GET /subscription` on mount; no client-side optimistic mutation of tier/billing state
- `isUpgrading` boolean is local React state in `Subscription.tsx`, passed down to `TierCard`
- Polling state in `PendingState` uses `useRef` for interval ID and `useState` for UI phase
- No sessionStorage or localStorage writes in this session (graceBannerDismissed is owned by S1-F)

**Validation rules:**
- `POST /subscription/checkout` request body must include `tier_id: TierId` — validated client-side before call; if somehow called with current tier, button should be disabled so this path should not occur
- `checkout_url` from response must start with `https://` before `window.location.href` redirect (security check; reject and show error if not)

---

##### Critical implementation notes

- **Analytics events `subscription_upgraded` and `subscription_downgraded` must NEVER be fired from the browser client.** From §1.10: "Must NEVER fire from: Browser client; Stripe redirect handler inline." The frontend must not call `trackEvent('subscription_upgraded', ...)` or `trackEvent('subscription_downgraded', ...)` under any circumstance. These are server-side-only events.

- **Analytics event `free_limit_reached` must NEVER be fired from the browser client.** From §1.10: "Must NEVER fire from: Browser client; must fire before upgrade prompt is shown." The `UpgradePrompt` is shown as a reaction to an API error/signal, not as a trigger for the event. The server has already fired the event before the frontend shows the prompt.

- **`window.location.href` redirect for Stripe Checkout, never `router.push`.** Stripe Checkout is a full page navigation to an external URL. Using the SPA router would break this.

- **Validate `checkout_url` starts with `https://` before redirect.** Silent failure mode: if the API returns a relative URL or an HTTP URL, `window.location.href` assignment will silently navigate to the wrong place or expose an open redirect.

- **PendingState polling must use `setInterval` with cleanup on unmount.** Failure to clear the interval on unmount causes state updates on unmounted components (React warning) and continued network requests. Use `useRef` for the interval ID and clear in the `useEffect` cleanup.

- **PendingState `previousTierId` must be read from the URL query param at page load, not from `GET /subscription` after Checkout redirect.** By the time the user returns from Stripe, the subscription may already have been updated (fast webhook). The pre-checkout tier must have been encoded in the `?tier=` query param before redirect. Failure mode: if you read `GET /subscription` both as "previous" and poll for "new", you can never detect the change.

- **Billing state `'Canceled'` with future `current_period_end` ≠ no access.** From §1.13 US-020: "Stripe cancellation (access until period end)." Do not render the canceled user as a free-tier user until `current_period_end` has passed. Incorrect treatment silently removes Pro/Team UI affordances from a still-paying customer.

- **Downgrade is deferred to period end — no API call on downgrade CTA click for P0.** From §1.3 billing transitions and US-019: "downgrade deferred to period end." The downgrade CTA in TierCard must NOT call `POST /subscription/checkout` in P0. It must show informational messaging only. Stub with `/* P1: Customer Portal redirect for downgrade */`.

- **`team_member` role users must not see billing_manage affordances.** From §1.3: `team_member.billing_manage = false`. If the authenticated user's role is `team_member`, render the subscription page in read-only mode (no upgrade CTAs). Use `useAuth()` to check role.

- **Subscription state comes only from `GET /subscription` — never from JWT claims or local state.** The Redis cache key `subscription:flags:{user_id}` is invalidated on webhook receipt, meaning the API always reflects current state. JWT may be stale. Always re-fetch.

- **Grace period days-remaining calculation is client-side display only.** The server is authoritative for billing state. The frontend computes days remaining from `grace_period_start` for display purposes only; it does not determine gating decisions.

- **`POST /subscription/checkout` must not be called for the currently active tier.** The upgrade CTA must be disabled (or not rendered) for the active tier. Race condition silent failure: if the user somehow clicks twice before redirect, the second call is harmless (server returns a new URL), but the first redirect should have already fired.

- **HTTP status codes from backend (§1.5):** The subscription endpoints are not in the status code contract table. Treat any non-2xx from `POST /subscription/checkout` as an error and render an error state with retry.

---

##### Mocking contract

**Frontend session — mock API responses required:**

**`GET /subscription`**
```typescript
// Mock response shape — matches S2-E backend contract
interface SubscriptionResponse {
  id: string;                          // UUID
  tier_id: TierId;                     // 'free' | 'pro' | 'team'
  billing_state: BillingState;         // 'Active' | 'Grace' | 'Canceled'
  grace_period_start: string | null;   // ISO 8601 UTC, null if not in grace
  stripe_subscription_id: string | null;
  stripe_customer_id: string | null;
  current_period_end: string | null;   // ISO 8601 UTC
}

// Example mock — active free tier user:
{
  "id": "sub-uuid-1234",
  "tier_id": "free",
  "billing_state": "Active",
  "grace_period_start": null,
  "stripe_subscription_id": null,
  "stripe_customer_id": null,
  "current_period_end": null
}

// Example mock — active pro tier user:
{
  "id": "sub-uuid-5678",
  "tier_id": "pro",
  "billing_state": "Active",
  "grace_period_start": null,
  "stripe_subscription_id": "sub_stripe_abc",
  "stripe_customer_id": "cus_stripe_xyz",
  "current_period_end": "2025-02-15T00:00:00Z"
}

// Example mock — grace period user:
{
  "id": "sub-uuid-9999",
  "tier_id": "pro",
  "billing_state": "Grace",
  "grace_period_start": "2025-01-10T00:00:00Z",
  "stripe_subscription_id": "sub_stripe_abc",
  "stripe_customer_id": "cus_stripe_xyz",
  "current_period_end": "2025-02-15T00:00:00Z"
}

// Example mock — canceled with future period end:
{
  "id": "sub-uuid-7777",
  "tier_id": "pro",
  "billing_state": "Canceled",
  "grace_period_start": null,
  "stripe_subscription_id": "sub_stripe_abc",
  "stripe_customer_id": "cus_stripe_xyz",
  "current_period_end": "2025-02-15T00:00:00Z"
}
```

**`POST /subscription/checkout`**
```typescript
// Request body
interface CheckoutRequest {
  tier_id: TierId;  // 'pro' | 'team'
}

// Success response (200)
interface CheckoutResponse {
  checkout_url: string;  // e.g., "https://checkout.stripe.com/pay/cs_test_abc123"
}

// Example mock success:
{
  "checkout_url": "https://checkout.stripe.com/pay/cs_test_mockabc123"
}

// Error response (e.g., 400 or 500)
{
  "detail": "Failed to create checkout session"
}
```

**Polling scenario mock (PendingState test):**
- First N calls to `GET /subscription` return `tier_id: 'free'` (unchanged)
- Call N+1 returns `tier_id: 'pro'` (upgraded)
- Use MSW request handlers with call-count tracking to simulate this progression

---

##### Acceptance criteria checklist

- [ ] `UpgradePrompt` renders and is visible when `reason='free_limit_reached'` prop is passed [US-018 AC-1]
- [ ] `UpgradePrompt` contains a CTA button/link that navigates to `/subscription` [US-018 AC-2]
- [ ] Free tier TierCard renders `revision_comparison` row with a locked/disabled visual state [US-018 AC-3]
- [ ] Free tier TierCard renders `team_library` row with a locked/disabled visual state [US-018 AC-3]
- [ ] Pro and Team tier TierCards render enabled "Upgrade to [Tier]" CTAs for a free-tier authenticated user [US-018 AC-4]
- [ ] Free TierCard displays "3 drawings/month"; Pro and Team display "Unlimited" [US-018 AC-5]
- [ ] Clicking an upgrade CTA calls `POST /subscription/checkout` with the correct `tier_id` [US-019 AC-1]
- [ ] On `POST /subscription/checkout` success, `window.location.href` is set to the returned `checkout_url` [US-019 AC-1]
- [ ] Navigating to `/subscription?checkout=pending&tier=free` renders `PendingState` component [US-019 AC-2]
- [ ] `PendingState` makes polling calls to `GET /subscription` at ~2 s intervals [US-019 AC-3]
- [ ] `PendingState` transitions to success UI when `GET /subscription` returns a different `tier_id` before 30 s [US-019 AC-4]
- [ ] `PendingState` renders timeout message after 30 s without tier change and stops polling [US-019 AC-5]
- [ ] A downgrade CTA displays deferred-period-end copy including `current_period_end` date and does NOT call `POST /subscription/checkout` [US-019 AC-6] [MANUAL]
- [ ] The card for the user's current active tier displays a "Current Plan" indicator and no upgrade CTA [US-019 AC-7]
- [ ] When `billing_state: 'Grace'`, a grace period notice is rendered above TierCards including computed days remaining [US-020 AC-1]
- [ ] Grace period notice contains a "Resolve payment" / "Update Payment Method" CTA [US-020 AC-2]
- [ ] When `billing_state: 'Canceled'` and `current_period_end` is in the future, the page shows access-continues-until messaging with the formatted date [US-020 AC-3]
- [ ] When `billing_state: 'Canceled'` and `current_period_end` is in the past (or null), Free is shown as active plan [US-020 AC-4]
- [ ] `POST /subscription/checkout` is never called for the currently active tier (CTA is absent or disabled) [US-020 AC-5]
- [ ] `trackEvent('subscription_upgraded', ...)` is never called anywhere in this session's code [Technical — §1.10]
- [ ] `trackEvent('subscription_downgraded', ...)` is never called anywhere in this session's code [Technical — §1.10]
- [ ] `trackEvent('free_limit_reached', ...)` is never called anywhere in this session's code [Technical — §1.10]
- [ ] `checkout_url` is validated to start with `https://` before `window.location.href` assignment [Technical — security]
- [ ] `PendingState` clears its polling interval on component unmount [Technical — memory leak prevention]
- [ ] A `team_member` role user sees the subscription page in read-only mode (no upgrade CTAs rendered) [Technical — §1.3 role matrix]

---

##### Independent Test

**Test file path** (TDD — written first, must fail before implementation):
`tests/sessions/S3-F.test.tsx`

**Exact CI command:**
```
npm test -- tests/sessions/S3-F
```

**AC → assertion mapping:**

| AC | `it(...)` block |
|---|---|
| US-018 AC-1 | `it("renders UpgradePrompt when reason is free_limit_reached")` |
| US-018 AC-2 | `it("UpgradePrompt CTA navigates to /subscription")` |
| US-018 AC-3 | `it("TierCard locks revision_comparison for free tier")` |
| US-018 AC-3 | `it("TierCard locks team_library for free tier")` |
| US-018 AC-4 | `it("TierCard shows enabled upgrade CTA for non-current higher tiers")` |
| US-018 AC-5 | `it("free TierCard shows 3 drawings per month; pro and team show Unlimited")` |
| US-019 AC-1 (POST call) | `it("clicking upgrade CTA calls POST /subscription/checkout with correct tier_id")` |
| US-019 AC-1 (redirect) | `it("on checkout success sets window.location.href to checkout_url")` |
| US-019 AC-2 | `it("renders PendingState when URL has checkout=pending query param")` |
| US-019 AC-3 | `it("PendingState polls GET /subscription at 2s intervals")` |
| US-019 AC-4 | `it("PendingState transitions to success when tier changes before 30s")` |
| US-019 AC-5 | `it("PendingState shows timeout message after 30s without tier change")` |
| US-019 AC-6 | `[MANUAL]` |
| US-019 AC-7 | `it("active tier card shows Current Plan label with no upgrade CTA")` |
| US-020 AC-1 | `it("renders grace period notice with days remaining when billing_state is Grace")` |
| US-020 AC-2 | `it("grace period notice contains a resolve payment CTA")` |
| US-020 AC-3 | `it("shows access-continues-until messaging when Canceled with future period end")` |
| US-020 AC-4 | `it("shows Free as active plan when Canceled with past period end")` |
| US-020 AC-5 | `it("does not call POST checkout when active tier CTA is clicked (button is absent/disabled)")` |
| Technical §1.10 (upgraded) | `it("never calls trackEvent subscription_upgraded from any subscription component")` |
| Technical §1.10 (downgraded) | `it("never calls trackEvent subscription_downgraded from any subscription component")` |
| Technical §1.10 (limit) | `it("never calls trackEvent free_limit_reached from any subscription component")` |
| Technical security | `it("rejects checkout_url that does not start with https://")` |
| Technical memory leak | `it("PendingState clears polling interval on unmount")` |
| Technical role matrix | `it("hides upgrade CTAs and shows read-only view for team_member role")` |

**Fixtures / test doubles:**

```typescript
// MSW handlers (msw/node for Vitest)
import { rest } from 'msw';
import { setupServer } from 'msw/node';

// Fixture: active free-tier subscription
const subscriptionFreeActive = {
  id: 'sub-uuid-free',
  tier_id: 'free',
  billing_state: 'Active',
  grace_period_start: null,
  stripe_subscription_id: null,
  stripe_customer_id: null,
  current_period_end: null,
};

// Fixture: active pro subscription
const subscriptionProActive = {
  id: 'sub-uuid-pro',
  tier_id: 'pro',
  billing_state: 'Active',
  grace_period_start: null,
  stripe_subscription_id: 'sub_abc',
  stripe_customer_id: 'cus_xyz',
  current_period_end: '2025-02-15T00:00:00Z',
};

// Fixture: Grace period subscription (pro tier)
const subscriptionGrace = {
  id: 'sub-uuid-grace',
  tier_id: 'pro',
  billing_state: 'Grace',
  grace_period_start: new Date(Date.now() - 2 * 24 * 3600 * 1000).toISOString(), // 2 days ago
  stripe_subscription_id: 'sub_abc',
  stripe_customer_id: 'cus_xyz',
  current_period_end: '2025-02-15T00:00:00Z',
};

// Fixture: Canceled with future period end
const subscriptionCanceledFuture = {
  id: 'sub-uuid-canceled',
  tier_id: 'pro',
  billing_state: 'Canceled',
  grace_period_start: null,
  stripe_subscription_id: 'sub_abc',
  stripe_customer_id: 'cus_xyz',
  current_period_end: new Date(Date.now() + 10 * 24 * 3600 * 1000).toISOString(), // 10 days future
};

// Fixture: Canceled with past period end
const subscriptionCanceledPast = {
  id: 'sub-uuid-canceled-past',
  tier_id: 'free',
  billing_state: 'Canceled',
  grace_period_start: null,
  stripe_subscription_id: null,
  stripe_customer_id: null,
  current_period_end: new Date(Date.now() - 5 * 24 * 3600 * 1000).toISOString(), // 5 days past
};

// Fixture: checkout response
const checkoutResponse = {
  checkout_url: 'https://checkout.stripe.com/pay/cs_test_mock',
};

// Mock AuthContext factory
const mockAuthContextFreeUser = {
  user: { id: 'user-uuid-1', role: 'user', email: 'test@example.com' },
  isAuthenticated: true,
};
const mockAuthContextTeamMember = {
  user: { id: 'user-uuid-2', role: 'team_member', email: 'member@example.com' },
  isAuthenticated: true,
};

// Polling mock: first 2 calls return free, 3rd returns pro
let pollCount = 0;
const pollingHandlers = [
  rest.get('/subscription', (req, res, ctx) => {
    pollCount++;
    if (pollCount >= 3) return res(ctx.json(subscriptionProActive));
    return res(ctx.json(subscriptionFreeActive));
  }),
];
```

**Pre-conditions:**
- `vitest` and `@testing-library/react` installed in `frontend/package.json`
- `msw` installed for request interception
- `frontend/src/api/endpoints.ts` exports `ENDPOINTS.subscription` = `/subscription` and `ENDPOINTS.subscriptionCheckout` = `/subscription/checkout` (S1-F owned; assume available per contract)
- `frontend/src/auth/AuthContext.tsx` provides a `AuthContext` that can be overridden in tests via `AuthContext.Provider`
- `window.location.href` mocked via `vi.stubGlobal` or jsdom manipulation in the test setup
- `vi.useFakeTimers()` used for PendingState polling tests (allows advancing timers without real waits)
- No database, Redis, or backend services required — all mocked via MSW

**Isolation rule:**
This test file mocks all API endpoints via MSW and all auth context via React context override. It passes when this session's PR is the only one merged — it does not require S2-E, S1-F, or any other session to have merged (all imports from those sessions are mocked or stubbed in the test setup).

---

##### Checkpoint

- **One-sentence observable outcome:** Navigating to `/subscription` as a logged-in free-tier user displays three tier cards with Free highlighted as "Current Plan", Pro and Team showing "Upgrade" CTAs, locked feature rows for revision_comparison (Pro+) and team_library (Team only), and a working upgrade flow that redirects to `https://checkout.stripe.com/…` on CTA click.
- **Shippability claim:** This PR is independently mergeable to main even if no other session in the same wave (S3-A through S3-H) has merged. It depends on S1-F (frontend shared infrastructure) and S2-E (subscription + Stripe webhook backend) which are in prior phases and must already be merged; no sibling Phase 3 session is required.

---

##### Output and handoff

| Export | Kind | Consuming Session(s) | Load-bearing? |
|---|---|---|---|
| `UpgradePrompt` component | React component (`frontend/src/features/subscription/UpgradePrompt.tsx`) | S3-B (Drawing Library — shows prompt when free limit hit from library), S3-C (Upload Flow — shows prompt when upload blocked by free limit) | [LOAD-BEARING] — signature `{ reason: 'free_limit_reached' \| 'feature_gated'; featureName?: string; onDismiss?: () => void }` must not change after merge |
| `TierCard` component | React component (`frontend/src/features/subscription/TierCard.tsx`) | S3-F internal only; no other session imports TierCard directly | No |
| `CheckoutRedirect` component | React component (`frontend/src/features/subscription/CheckoutRedirect.tsx`) | S3-F internal only | No |
| `PendingState` component | React component (`frontend/src/features/subscription/PendingState.tsx`) | S3-F internal only | No |
| `Subscription` page | React page component (`frontend/src/pages/Subscription.tsx`) | `frontend/src/router.tsx` (S0-A, read-only — route already stubbed to this path) | No |

---

```json
{
  "test": {
    "cmd": "npm test -- tests/sessions/S3-F",
    "file": "tests/sessions/S3-F.test.tsx"
  },
  "checkpoint": "Navigating to /subscription as a logged-in free-tier user displays three tier cards with Free highlighted as 'Current Plan', Pro and Team showing 'Upgrade' CTAs, locked feature rows for revision_comparison and team_library, and a working upgrade flow that redirects to https://checkout.stripe.com/… on CTA click.",
  "manualAcs": [
    {
      "id": "US-019-AC-6",
      "text": "A downgrade CTA displays confirmation text that the change will take effect at the end of the current billing period (current_period_end), not immediately; no POST /subscription/checkout is called immediately — downgrade initiation is a P1 Customer Portal redirect; this story covers the deferred-period-end messaging display only."
    }
  ],
  "exports": [
    {
      "kind": "type",
      "name": "UpgradePromptProps",
      "shape": "{ reason: 'free_limit_reached' | 'feature_gated'; featureName?: string; onDismiss?: () => void }"
    },
    {
      "kind": "function",
      "name": "UpgradePrompt",
      "shape": "(props: UpgradePromptProps) => JSX.Element"
    },
    {
      "kind": "function",
      "name": "TierCard",
      "shape": "(props: { tier: TierId; currentTierIdForUser: TierId; billingState: BillingState; currentPeriodEnd: string | null; onUpgrade: (tierId: TierId) => void; isUpgrading: boolean }) => JSX.Element"
    },
    {
      "kind": "function",
      "name": "CheckoutRedirect",
      "shape": "(props: { tierId: TierId }) => JSX.Element"
    },
    {
      "kind": "function",
      "name": "PendingState",
      "shape": "(props: { previousTierId: TierId; onResolved: (newTierId: TierId) => void; onTimeout: () => void }) => JSX.Element"
    },
    {
      "kind": "module",
      "name": "frontend/src/features/subscription/UpgradePrompt",
      "shape": "frontend/src/features/subscription/UpgradePrompt.tsx"
    },
    {
      "kind": "module",
      "name": "frontend/src/pages/Subscription",
      "shape": "frontend/src/pages/Subscription.tsx"
    }
  ]
}
```