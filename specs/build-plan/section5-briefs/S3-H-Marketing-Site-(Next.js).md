#### S3-H — Marketing Site (Next.js)

**Phase 3 | Frontend | Needs: S0-A**

---

##### Objective

Build the server-side-rendered Next.js marketing site (landing, pricing, about, contact pages) that serves as the public-facing entry point for PID Analyzer, satisfying SEO requirements and converting visitors to registered users via CTA links to the SPA.

---

##### Scope

**P0 MVP** — this session is entirely P0 (§1.13 lists the marketing/landing site under P0 scope as a required deployment). There is no P1 work in this session. All four pages, all three components, and both static files (`robots.txt`, `sitemap.xml`) must be fully implemented.

---

##### Technology constraints

From §1.8 Technology Stack:

| Layer | Selected Technology | Architecturally Irreversible Because |
|---|---|---|
| **Marketing/Landing** | Next.js (separate deployment) | SSR required for NFR-17 SEO; separate from SPA to avoid complexity bleed |

- **Must use**: Next.js App Router (the scaffold in S0-A sets up `marketing/app/layout.tsx` using App Router conventions). Use Next.js `14.x` or later.
- **Must use**: React Server Components for all four page routes (no `"use client"` at page level unless strictly required for interactivity; Hero, PricingTable, Footer are all static and must remain server components).
- **Must use**: `next/head` metadata API (App Router `metadata` export) for SEO meta tags — not `<Head>` from `next/head` (legacy Pages Router API).
- **Must NOT use**: the SPA's Vite/React setup or any imports from `frontend/src/**`.
- **Must NOT use**: any authenticated API calls — all page content is static or statically generated at build time; no `fetch()` to backend endpoints from marketing pages.
- **Must NOT use**: the Supabase client or any auth libraries from the SPA.
- CSS: use Tailwind CSS (configured in the scaffold via `marketing/next.config.js` and `tailwind.config.ts`). Do not introduce additional CSS frameworks.
- Testing: Jest + `@testing-library/react` with `next/jest` transformer.

---

##### Performance targets

From §1.8: "SSR required for NFR-17 SEO" — all four pages must render meaningful HTML on the server (no client-side-only content that would be invisible to crawlers). This is a hard architectural constraint, not a numeric SLA.

No latency SLA is directly owned by this session. The downstream NFR-17 SEO requirement (not numerically specified in the distilled spec) is met by using Next.js SSR/SSG — observable via `curl` returning full `<h1>` content without JavaScript execution.

None — see downstream sessions for runtime latency monitoring targets.

---

##### Owned files

```
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

##### Read-only imports

| Owning Session | File | Named Exports Required |
|---|---|---|
| S0-A | `marketing/app/layout.tsx` | Default layout wrapper (consumed implicitly by Next.js App Router — not imported directly, but must not conflict) |
| S0-A | `marketing/next.config.js` | Consumed by Next.js build system — not imported in code |
| S0-A | `marketing/tsconfig.json` | Consumed by TypeScript compiler — not imported in code |

No runtime imports from other sessions are required. This session is self-contained.

---

##### Do not touch

- `marketing/app/layout.tsx` — owned by S0-A (root layout, pre-stubbed)
- `marketing/app/page.tsx` — owned by S0-A (root page stub; see Critical Implementation Notes for resolution)
- `marketing/next.config.js` — owned by S0-A
- `marketing/tsconfig.json` — owned by S0-A
- `frontend/src/**` — all SPA files, owned by S1-F, S3-A through S3-G
- `backend/**` — all backend files, owned by S1-A through S2-M
- `docker-compose.yml`, `docker-compose.test.yml` — owned by S0-A
- `.env.example` — owned by S0-A

---

##### Architecture context

From §1.8 Technology Stack (verbatim):

> **Marketing/Landing** | Next.js (separate deployment) | SSR required for NFR-17 SEO; separate from SPA to avoid complexity bleed

From §1.6 Route Manifest — Frontend Page Routes (verbatim):

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

Note: `/register`, `/login`, `/dashboard`, `/upload`, `/drawings/{id}/review`, `/account`, `/subscription` are SPA routes served by the Vite React app (S3-A through S3-G), not by this Next.js deployment. The marketing site's CTA buttons and nav links that point to `/register` or `/login` must link to the SPA's deployment URL (environment-variable-configured), not to Next.js routes.

From §1.3 Feature-Tier Gate Matrix (verbatim):

```typescript
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

From §1.7 Third-Party Dependencies (verbatim, relevant to this session):

> **AWS CloudFront** | Standard CDN | N/A | Static SPA assets only; content-hash cache busting

The marketing site is a separate Next.js deployment. CloudFront CDN configuration (if any) is an ops concern outside this session's scope.

From §1.12 Environment Variable Schema — relevant to marketing site:

> `ENVIRONMENT` | string | `development` \| `staging` \| `production` | `production` | Log warning | Use `production`

The marketing site must read `NEXT_PUBLIC_APP_URL` (the SPA deployment URL) to construct CTA links — this is a convention not in the root env schema (which covers backend only), so it must be documented in the marketing `.env.local.example` generated by this session (not touching `.env.example` owned by S0-A).

---

##### User stories and acceptance criteria

The distilled spec contains no dedicated US-XXX user stories for the marketing site. The following acceptance criteria are derived from the architectural constraints in §1.8 (SSR/SEO requirement), §1.3 (tier feature gates for the pricing table), §1.6 (route manifest), and the P0 scope declaration in §1.13.

**SITE-1: Landing page (home)**
- AC-1: `GET /` returns a 200 HTTP response with a non-empty `<h1>` element in the server-rendered HTML (no JavaScript execution required to see headline content).
- AC-2: The page includes an `<meta name="description">` tag with non-empty content.
- AC-3: The page contains at least one CTA link pointing to the SPA `/register` URL (value of `NEXT_PUBLIC_APP_URL` + `/register`).
- AC-4: The Hero component is rendered on the landing page.
- AC-5: The Footer component is rendered on the landing page.
- AC-6: Nav includes links to `/pricing`, `/about`, `/contact`, and CTA to `/register`.

**SITE-2: Pricing page**
- AC-1: `GET /pricing` returns a 200 HTTP response with the PricingTable component rendered server-side.
- AC-2: The pricing table displays exactly three tier columns: Free, Pro, and Team.
- AC-3: Free tier shows monthly drawing limit of 3; Pro and Team show "Unlimited".
- AC-4: Revision Comparison feature is marked unavailable (e.g., "—" or ✗) for Free tier and available for Pro and Team.
- AC-5: Team Library feature is marked unavailable for Free and Pro tiers and available for Team tier.
- AC-6: CSV/XLSX export is marked available for all three tiers.
- AC-7: API Access is marked unavailable for all three tiers (it is P1 per §1.3 `api_access: false` for all tiers including team).
- AC-8: Each tier card contains a CTA link to the SPA `/register` URL.
- AC-9: The page `<title>` contains "Pricing".

**SITE-3: About page**
- AC-1: `GET /about` returns 200 with non-empty body content rendered server-side.
- AC-2: Page includes a `<meta name="description">` tag.
- AC-3: Footer is rendered.

**SITE-4: Contact page**
- AC-1: `GET /contact` returns 200 with non-empty body content rendered server-side.
- AC-2: Page includes a `<meta name="description">` tag.
- AC-3: Footer is rendered.
- AC-4: Contact page contains at minimum a contact email address or contact form (static; no API submission required for P0).

**SITE-5: SEO static files**
- AC-1: `GET /robots.txt` returns 200 with content that includes `User-agent: *` and `Sitemap:` directive pointing to `/sitemap.xml`.
- AC-2: `GET /sitemap.xml` returns 200 with valid XML containing `<urlset>` root element and `<url>` entries for `/`, `/pricing`, `/about`, and `/contact`.
- AC-3: `sitemap.xml` entries include `<loc>` elements with absolute URLs.

**SITE-6: Server-side rendering (SEO gate)**
- AC-1: All four page routes (`/`, `/pricing`, `/about`, `/contact`) render complete meaningful HTML in a `curl` request (no "Loading…" placeholder as the only body content).
- AC-2: All four pages export a `metadata` object (Next.js App Router `Metadata` type) with at minimum `title` and `description` fields.

**SITE-7: Navigation integrity**
- AC-1: All internal marketing links (`/pricing`, `/about`, `/contact`) use Next.js `<Link>` component (not `<a href>`).
- AC-2: External SPA links (to `/register`, `/login`) use standard `<a href>` with the configured `NEXT_PUBLIC_APP_URL` prefix, not Next.js `<Link>` (which would resolve within the Next.js deployment).

---

##### UX and design specification

The distilled spec does not include a dedicated UX/design specification section for the marketing site beyond the architectural constraints above. The following design requirements are derived from the spec's tier data and general web conventions for SaaS marketing sites:

**Hero component (`marketing/components/Hero.tsx`)**
- Contains: headline (H1), sub-headline, primary CTA button ("Get started free" → SPA `/register`), secondary CTA link ("See pricing" → `/pricing`).
- Must be a React Server Component (no `"use client"`).
- All text content is static (no API fetch).

**PricingTable component (`marketing/components/PricingTable.tsx`)**
- Displays three tier columns: **Free**, **Pro**, **Team** in that order (left to right).
- Feature rows must include (in any order):
  - Monthly drawings: "3 drawings/month" | "Unlimited" | "Unlimited"
  - CSV & XLSX Export: ✓ | ✓ | ✓
  - Revision Comparison: ✗ | ✓ | ✓
  - Team Library: ✗ | ✗ | ✓
  - API Access: "Coming soon" | "Coming soon" | "Coming soon" (P1; all false per §1.3)
- Each tier column has a CTA button linking to `${NEXT_PUBLIC_APP_URL}/register`.
- The Pro tier column is visually distinguished (e.g., "Most popular" badge or highlighted border) to guide conversion.
- Must be a React Server Component.
- Tier data must be defined as a static constant within the component file (no runtime fetch).

**Footer component (`marketing/components/Footer.tsx`)**
- Contains: site name, links to `/pricing`, `/about`, `/contact`, and an external link to the SPA (`${NEXT_PUBLIC_APP_URL}/register`).
- Contains: copyright notice with current year (can be static string; no dynamic `new Date()` in a Server Component is fine).
- Must be a React Server Component.

**Page-level layout integration**
- All four pages use the root layout (`marketing/app/layout.tsx`, owned by S0-A) which provides `<html>` and `<body>` wrapper. Pages must not redeclare these.
- The `(marketing)` route group may define its own `layout.tsx` that wraps only marketing pages with shared nav — **this file is not in the owned files list**, so if a group layout is needed, it must be created as an additional file and its creation must be flagged in the handoff. However, since only `marketing/app/(marketing)/page.tsx` is in the owned files, shared nav and footer should be composed directly in each page component rather than in a group layout.

**`robots.txt` content**:
```
User-agent: *
Allow: /
Sitemap: https://<SITE_DOMAIN>/sitemap.xml
```
The domain in Sitemap must be configurable via `NEXT_PUBLIC_SITE_URL` environment variable; fall back to `https://www.pidanalyzer.com` as the default placeholder.

**`sitemap.xml` content**: Must contain `<url>` entries for `/`, `/pricing`, `/about`, `/contact` with `<changefreq>monthly</changefreq>` and `<priority>` values (1.0 for home, 0.8 for pricing, 0.6 for about/contact).

---

##### Critical implementation notes

- **Route group conflict with S0-A's `app/page.tsx`**: S0-A creates `marketing/app/page.tsx` as a stub. In Next.js App Router, `app/page.tsx` and `app/(marketing)/page.tsx` both resolve to the `/` route — having both is a build error. The resolution: `marketing/app/page.tsx` (S0-A, do not touch) must remain as a redirect stub that performs `redirect('/')` pointing to the App Router catch or must export a re-export of the marketing page. **Do not modify `app/page.tsx`.** Instead, treat `app/(marketing)/page.tsx` as the actual home page and verify at test time that the route resolves — if the S0-A stub causes a conflict, document it as a required one-line fix in `app/page.tsx` that the human reviewer must apply (mark as `[MANUAL]` AC). Preferred resolution: S0-A's stub should have been a `redirect()` — confirm at implementation time and, if it is a conflicting page export, raise the conflict visibly rather than silently breaking the build.

- **`NEXT_PUBLIC_APP_URL` environment variable**: All CTA links pointing to the SPA (e.g., `/register`, `/login`) must use `process.env.NEXT_PUBLIC_APP_URL` as a prefix (e.g., `${process.env.NEXT_PUBLIC_APP_URL}/register`). This variable is not in the root `.env.example` (which covers backend only). Create `marketing/.env.local.example` with `NEXT_PUBLIC_APP_URL=http://localhost:5173` and `NEXT_PUBLIC_SITE_URL=https://www.pidanalyzer.com`. Do NOT modify `backend/.env.example` or root `.env.example`.

- **No backend API calls**: Per the architecture, the marketing site has zero runtime dependency on the FastAPI backend. All tier data, page content, and pricing information is hardcoded as static TypeScript constants. Any future dynamic pricing would be a P1 concern. A `fetch()` call from a Server Component to the backend API in this session is explicitly forbidden.

- **Server Components only at page level**: Per §1.8, SSR is required. All four page files and all three component files must be React Server Components (no `"use client"` directive) unless an interactive element strictly requires it. Interactive elements in P0 are minimal (nav mobile toggle if any — acceptable to be a `"use client"` sub-component only). The PricingTable and Hero are fully static and must NOT be `"use client"`.

- **`sitemap.xml` absolute URLs**: The `<loc>` elements in `sitemap.xml` must contain absolute URLs (e.g., `https://www.pidanalyzer.com/pricing`), not relative paths. Use `NEXT_PUBLIC_SITE_URL` environment variable for the domain. Relative `<loc>` values are non-compliant with the sitemap protocol and would fail SEO validation.

- **`robots.txt` placement**: In Next.js App Router, static files in `public/` are served at the root. `marketing/public/robots.txt` is served at `/robots.txt`. Do not create a `app/robots.txt/route.ts` — the static file approach is correct and simpler.

- **Metadata export contract**: Each page must export a `metadata` const of type `import type { Metadata } from 'next'`. This is the App Router mechanism — it is not compatible with the legacy `<Head>` component from `next/head` (Pages Router). Using the wrong API is a silent failure that produces correct-looking pages but breaks Next.js metadata aggregation.

- **`next/link` vs `<a>` for SPA links**: Next.js `<Link>` performs client-side navigation within the Next.js app. Links pointing to the SPA (`NEXT_PUBLIC_APP_URL/register`) are cross-origin or cross-deployment and must use plain `<a href>` to force a full browser navigation. Using `<Link>` for these would silently result in a 404 within the Next.js deployment.

- **No shared code with SPA**: Do not import anything from `frontend/src/**`. The `marketing/` directory is an entirely separate Next.js project with its own `node_modules` (or workspace dependency set). Type definitions from `frontend/src/types/contracts.ts` are for the SPA only — if any tier types are needed in the pricing table, define them locally in the component file as a static constant.

- **P1 stub for API access row**: The API Access tier feature is `false` for all tiers in §1.3 (even Team), marked as "P1 (FR-11)". The pricing table must display this row as "Coming soon" for all three tiers with a clearly marked `{/* P1: FR-11 — API access not yet available */}` comment in the JSX.

---

##### Mocking contract

N/A — this session makes no API calls and has no backend dependencies. All content is static. No mock responses required.

The test file will use `@testing-library/react` to render components directly with static props. No MSW or fetch interceptors are needed.

---

##### Acceptance criteria checklist

- [ ] `GET /` returns 200 with `<h1>` in server-rendered HTML without JavaScript [SITE-1 AC-1]
- [ ] Landing page includes `<meta name="description">` with non-empty content [SITE-1 AC-2]
- [ ] Landing page contains at least one CTA link pointing to SPA `/register` [SITE-1 AC-3]
- [ ] Hero component is rendered on landing page [SITE-1 AC-4]
- [ ] Footer component is rendered on landing page [SITE-1 AC-5]
- [ ] Nav includes links to /pricing, /about, /contact, and CTA to /register [SITE-1 AC-6]
- [ ] `GET /pricing` returns 200 with PricingTable rendered server-side [SITE-2 AC-1]
- [ ] Pricing table displays exactly three columns: Free, Pro, Team [SITE-2 AC-2]
- [ ] Free tier shows 3 drawings/month; Pro and Team show Unlimited [SITE-2 AC-3]
- [ ] Revision Comparison is marked unavailable for Free, available for Pro and Team [SITE-2 AC-4]
- [ ] Team Library is marked unavailable for Free and Pro, available for Team [SITE-2 AC-5]
- [ ] CSV/XLSX export is marked available for all three tiers [SITE-2 AC-6]
- [ ] API Access is marked "Coming soon" / unavailable for all three tiers [SITE-2 AC-7]
- [ ] Each tier card on pricing page has a CTA link to SPA /register [SITE-2 AC-8]
- [ ] Pricing page `<title>` contains "Pricing" [SITE-2 AC-9]
- [ ] `GET /about` returns 200 with non-empty body content server-rendered [SITE-3 AC-1]
- [ ] About page includes `<meta name="description">` tag [SITE-3 AC-2]
- [ ] Footer is rendered on About page [SITE-3 AC-3]
- [ ] `GET /contact` returns 200 with non-empty body content server-rendered [SITE-4 AC-1]
- [ ] Contact page includes `<meta name="description">` tag [SITE-4 AC-2]
- [ ] Footer is rendered on Contact page [SITE-4 AC-3]
- [ ] Contact page contains a contact email address or contact form element [SITE-4 AC-4]
- [ ] `/robots.txt` contains `User-agent: *` and `Sitemap:` directive [SITE-5 AC-1]
- [ ] `/sitemap.xml` is valid XML with `<urlset>` root and `<url>` entries for /, /pricing, /about, /contact [SITE-5 AC-2]
- [ ] `sitemap.xml` `<url>` entries contain `<loc>` with absolute URLs [SITE-5 AC-3]
- [ ] All four pages export a `metadata` object with `title` and `description` fields [SITE-6 AC-2]
- [ ] All internal marketing nav links use Next.js `<Link>` component [SITE-7 AC-1]
- [ ] SPA CTA links (to /register, /login) use `<a href>` with `NEXT_PUBLIC_APP_URL` prefix, not `<Link>` [SITE-7 AC-2]
- [ ] `app/(marketing)/page.tsx` and `app/page.tsx` coexist without Next.js build conflict [MANUAL] [SITE-6 AC-1 route conflict]
- [ ] All four pages render meaningful HTML visible via `curl` (no JS-only content) [MANUAL] [SITE-6 AC-1]

---

##### Independent Test

**Test file path** (TDD — written first, must fail before implementation):
`tests/sessions/S3-H.test.tsx`

**Exact CI command**:
```
cd marketing && npx jest --config jest.config.ts tests/sessions/S3-H.test.tsx
```

**AC → assertion mapping**:

| AC | `it(...)` block name |
|---|---|
| SITE-1 AC-1 | `it("renders <h1> in Hero on landing page server component")` |
| SITE-1 AC-2 | `it("landing page metadata includes non-empty description")` |
| SITE-1 AC-3 | `it("landing page contains CTA link to SPA /register")` |
| SITE-1 AC-4 | `it("Hero component renders headline and sub-headline")` |
| SITE-1 AC-5 | `it("Footer renders on landing page")` |
| SITE-1 AC-6 | `it("nav contains links to /pricing, /about, /contact and register CTA")` |
| SITE-2 AC-1 | `it("pricing page renders PricingTable component")` |
| SITE-2 AC-2 | `it("PricingTable displays Free, Pro, Team columns")` |
| SITE-2 AC-3 | `it("Free tier shows 3 drawings/month limit; Pro and Team show Unlimited")` |
| SITE-2 AC-4 | `it("Revision Comparison is unavailable for Free and available for Pro and Team")` |
| SITE-2 AC-5 | `it("Team Library is unavailable for Free and Pro and available for Team")` |
| SITE-2 AC-6 | `it("CSV/XLSX export is marked available for all three tiers")` |
| SITE-2 AC-7 | `it("API Access is marked Coming soon for all three tiers")` |
| SITE-2 AC-8 | `it("each tier column on pricing page has a CTA link to /register")` |
| SITE-2 AC-9 | `it("pricing page metadata title contains Pricing")` |
| SITE-3 AC-1 | `it("about page renders non-empty body content")` |
| SITE-3 AC-2 | `it("about page metadata includes description")` |
| SITE-3 AC-3 | `it("Footer renders on about page")` |
| SITE-4 AC-1 | `it("contact page renders non-empty body content")` |
| SITE-4 AC-2 | `it("contact page metadata includes description")` |
| SITE-4 AC-3 | `it("Footer renders on contact page")` |
| SITE-4 AC-4 | `it("contact page contains contact email or form element")` |
| SITE-5 AC-1 | `it("robots.txt contains User-agent wildcard and Sitemap directive")` |
| SITE-5 AC-2 | `it("sitemap.xml is valid XML with urlset root and four url entries")` |
| SITE-5 AC-3 | `it("sitemap.xml loc elements contain absolute URLs")` |
| SITE-6 AC-2 | `it("all four pages export metadata with title and description")` |
| SITE-7 AC-1 | `it("internal nav links use Next.js Link component")` |
| SITE-7 AC-2 | `it("SPA register/login links use plain anchor tags not Next.js Link")` |

`[MANUAL]` ACs are exempt from the mapping above and appear in `manualAcs[]` below.

**Fixtures / test doubles**:
- `NEXT_PUBLIC_APP_URL=http://localhost:5173` — set via `process.env` in test setup file (`jest.setup.ts`).
- `NEXT_PUBLIC_SITE_URL=https://www.pidanalyzer.com` — set via `process.env` in test setup file.
- No HTTP mocks required (no API calls).
- Static file tests (`robots.txt`, `sitemap.xml`) read directly from `marketing/public/` using `fs.readFileSync` in the test — no rendering required.
- Next.js App Router Server Components must be tested using `@testing-library/react`'s `render` with the `next/jest` transformer configured in `jest.config.ts`. For metadata export tests, import the page module and assert the exported `metadata` object directly (no render needed).

**Pre-conditions**:
- `marketing/package.json` must include `jest`, `@testing-library/react`, `@testing-library/jest-dom`, `jest-environment-jsdom`, `next` (already present from S0-A scaffold).
- `marketing/jest.config.ts` must be created by this session (not in owned files list — needs to be added; see Critical Implementation Notes — raise if this is a gap).
- `marketing/jest.setup.ts` must be created by this session for env var injection and `@testing-library/jest-dom` import.
- No database, Redis, or S3 required — this session is fully static.
- No running Next.js server required for component-level tests.

> **Note on `jest.config.ts` and `jest.setup.ts`**: These files are not in the owned files list. Creating them is a required prerequisite for the test to run. This session must create them and flag them in the handoff as additional created files. They are isolated to `marketing/` and do not conflict with any other session.

**Isolation rule**: This test passes when S3-H is the only merged session beyond S0-A. It has zero dependency on any Phase 1 or Phase 2 session. All test content is static.

---

##### Checkpoint

- **One-sentence observable outcome**: Visiting `https://<marketing-domain>/`, `/pricing`, `/about`, and `/contact` in a browser (or via `curl`) returns fully server-rendered HTML pages with hero content, a three-tier pricing table, navigation, and footer — with `/robots.txt` and `/sitemap.xml` returning valid SEO files.
- **Shippability claim**: This PR is independently mergeable to main even if no other session in the same wave (Phase 3) has merged — it depends only on S0-A (Phase 0) which is a gate prerequisite and will have merged before any Phase 3 session begins.

---

##### Output and handoff

| Export | Consuming Session | Load-bearing |
|---|---|---|
| `marketing/components/Hero.tsx` (default export: `Hero` React component) | S3-H internal only | No |
| `marketing/components/PricingTable.tsx` (default export: `PricingTable` React component) | S3-H internal only | No |
| `marketing/components/Footer.tsx` (default export: `Footer` React component) | S3-H internal only | No |
| `marketing/public/robots.txt` (static file) | Crawler/SEO — no code consumer | No |
| `marketing/public/sitemap.xml` (static file) | Crawler/SEO — no code consumer | No |
| `marketing/app/(marketing)/page.tsx` (default Next.js page export) | Next.js App Router build system | No |
| `marketing/app/pricing/page.tsx` (default Next.js page export) | Next.js App Router build system | No |
| `marketing/app/about/page.tsx` (default Next.js page export) | Next.js App Router build system | No |
| `marketing/app/contact/page.tsx` (default Next.js page export) | Next.js App Router build system | No |

No downstream session (S4-A E2E tests or others) imports directly from marketing site source files. The marketing site is a standalone deployment. S4-A may include smoke tests against the deployed marketing URL but does not import these modules.

---

```json
{
  "test": {
    "cmd": "cd marketing && npx jest --config jest.config.ts tests/sessions/S3-H.test.tsx",
    "file": "tests/sessions/S3-H.test.tsx"
  },
  "checkpoint": "Visiting /pricing via curl returns fully server-rendered HTML with a three-tier pricing table (Free/Pro/Team), and /robots.txt and /sitemap.xml return valid SEO files.",
  "manualAcs": [
    {
      "id": "SITE-6-AC-1-conflict",
      "text": "app/(marketing)/page.tsx and app/page.tsx (S0-A stub) coexist without a Next.js build error — verify that `next build` completes without duplicate-route conflict."
    },
    {
      "id": "SITE-6-AC-1-ssr",
      "text": "All four pages (/, /pricing, /about, /contact) render meaningful HTML visible via `curl` without executing JavaScript — confirmed by running `curl -s <url> | grep -c '<h'` returning a non-zero count."
    }
  ],
  "exports": [
    {
      "kind": "module",
      "name": "marketing/components/Hero",
      "shape": "marketing/components/Hero.tsx"
    },
    {
      "kind": "module",
      "name": "marketing/components/PricingTable",
      "shape": "marketing/components/PricingTable.tsx"
    },
    {
      "kind": "module",
      "name": "marketing/components/Footer",
      "shape": "marketing/components/Footer.tsx"
    },
    {
      "kind": "module",
      "name": "marketing/app/(marketing)/page",
      "shape": "marketing/app/(marketing)/page.tsx"
    },
    {
      "kind": "module",
      "name": "marketing/app/pricing/page",
      "shape": "marketing/app/pricing/page.tsx"
    },
    {
      "kind": "module",
      "name": "marketing/app/about/page",
      "shape": "marketing/app/about/page.tsx"
    },
    {
      "kind": "module",
      "name": "marketing/app/contact/page",
      "shape": "marketing/app/contact/page.tsx"
    }
  ]
}
```