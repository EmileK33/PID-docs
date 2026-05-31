// Endpoint manifest — method + path constants for every backend route the SPA
// talks to (§1.6).
//
// [LOAD-BEARING] Consumed by every S3-* page session via `endpoints`. Paths use
// `:param` placeholders; fill them with `buildPath(endpoints.X.path, { param })`.
//
// Scope: all P0 routes are required and exercised by the session test. P1 routes
// (teams, comparisons) are included as INERT constants so downstream P1 sessions
// don't have to extend this file — they are never called until a consumer wires
// them up.

export type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'DELETE';

export interface EndpointDef {
  readonly method: HttpMethod;
  readonly path: string;
}

const def = (method: HttpMethod, path: string): EndpointDef => ({ method, path });

export const endpoints = {
  // --- Auth (P0) ---
  authRegister: def('POST', '/auth/register'),
  authLogin: def('POST', '/auth/login'),
  authOauthGoogle: def('POST', '/auth/oauth/google'),
  authRefresh: def('POST', '/auth/refresh'),
  authLogout: def('POST', '/auth/logout'), // → 204
  authPasswordResetRequest: def('POST', '/auth/password-reset/request'), // → 204
  authPasswordResetConfirm: def('POST', '/auth/password-reset/confirm'), // → 204

  // --- Drawings (P0) ---
  drawingsHashCheck: def('POST', '/drawings/hash-check'), // 200 HashCheckResponse | 409
  drawingsList: def('GET', '/drawings'),
  drawingsCreate: def('POST', '/drawings'), // requires prior hash-check; 400 otherwise
  drawingGet: def('GET', '/drawings/:id'),
  drawingUpdate: def('PATCH', '/drawings/:id'),
  drawingDelete: def('DELETE', '/drawings/:id'), // → 204
  drawingRetry: def('POST', '/drawings/:id/retry'),
  drawingStatus: def('GET', '/drawings/:id/status'), // SSE
  drawingSymbols: def('GET', '/drawings/:id/symbols'), // → SymbolsPageResponse
  drawingSymbolCreate: def('POST', '/drawings/:id/symbols'),
  drawingExportCreate: def('POST', '/drawings/:id/exports'),
  drawingUploadComplete: def('POST', '/drawings/:id/upload-complete'), // 202 first time, 200 idempotent

  // --- Symbols / exports (P0) ---
  symbolUpdate: def('PATCH', '/symbols/:id'),
  exportGet: def('GET', '/exports/:id'),

  // --- Account (P0) ---
  accountGet: def('GET', '/account'),
  accountUpdate: def('PATCH', '/account'),
  accountDelete: def('DELETE', '/account'), // → 204
  accountConsentGet: def('GET', '/account/consent'),
  accountConsentUpdate: def('PATCH', '/account/consent'),

  // --- Subscription / billing (P0) ---
  subscriptionGet: def('GET', '/subscription'),
  subscriptionCheckout: def('POST', '/subscription/checkout'),
  webhooksStripe: def('POST', '/webhooks/stripe'), // NOT called from the client

  // --- Reference data (P0) ---
  entityClasses: def('GET', '/entity-classes'),

  // --- Teams / comparisons (P1, INERT) ---
  // Listed so P1 sessions consume rather than extend. Never called in P0.
  teamsList: def('GET', '/teams'),
  teamCreate: def('POST', '/teams'),
  teamMembers: def('GET', '/teams/:id/members'),
  teamInvite: def('POST', '/teams/:id/invites'),
  teamInviteAccept: def('POST', '/teams/invite/accept'),
  comparisonCreate: def('POST', '/comparisons'),
  comparisonGet: def('GET', '/comparisons/:id'),
} as const satisfies Record<string, EndpointDef>;

export type EndpointKey = keyof typeof endpoints;

/**
 * Fill `:param` placeholders in an endpoint path.
 *
 * @example buildPath(endpoints.drawingGet.path, { id }) // "/drawings/abc"
 */
export function buildPath(
  path: string,
  params: Record<string, string | number> = {},
): string {
  return path.replace(/:([A-Za-z0-9_]+)/g, (_match, key: string) => {
    if (!(key in params)) {
      throw new Error(`Missing path parameter ":${key}" for "${path}"`);
    }
    return encodeURIComponent(String(params[key]));
  });
}

export default endpoints;
