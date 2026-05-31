// HTTP API client for the FastAPI backend.
//
// [LOAD-BEARING] `apiClient` is consumed by every S3-* page session.
//
// Critical contract notes (§1.4 rule 12, §1.5, S1-F manifest):
//  - Attaches the current Supabase JWT as `Authorization: Bearer` ONLY when the
//    request targets the API host. S3 pre-signed URLs (a different host) must be
//    sent WITHOUT an Authorization header or S3 rejects the signed request.
//  - Surfaces every non-2xx response as an `ApiError` carrying the HTTP status,
//    so callers can branch on 409 (hash blocked) vs 403 (forbidden) vs 400. The
//    client never auto-retries.
//  - On a 401 from the API host it notifies registered unauthorized handlers
//    (AuthContext clears the session + redirects to /login) and then throws. It
//    does NOT silently retry.

import { supabase } from '../auth/supabaseClient';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// Refuse to ship a production build that can't reach the API.
if (import.meta.env.PROD && !API_BASE_URL) {
  throw new Error(
    'VITE_API_BASE_URL must be set: the API client cannot be constructed without it in a production build.',
  );
}

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

export interface RequestOptions {
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

// --- 401 / unauthorized notification ------------------------------------------
// The client can't import AuthContext (that would be a cycle), so AuthContext
// registers a handler here. Handlers fire on any 401 from the API host.
type UnauthorizedHandler = () => void;
const unauthorizedHandlers = new Set<UnauthorizedHandler>();

export function onUnauthorized(handler: UnauthorizedHandler): () => void {
  unauthorizedHandlers.add(handler);
  return () => {
    unauthorizedHandlers.delete(handler);
  };
}

function notifyUnauthorized(): void {
  for (const handler of unauthorizedHandlers) {
    try {
      handler();
    } catch {
      /* a misbehaving handler must not break request handling */
    }
  }
}

// --- URL helpers --------------------------------------------------------------

/** Resolve a request path/URL against the API base. Absolute URLs pass through. */
export function resolveUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  const base = API_BASE_URL ?? '';
  if (!base) return path; // same-origin fallback (dev only)
  return base.replace(/\/+$/, '') + (path.startsWith('/') ? path : `/${path}`);
}

/** True when the (already-resolved) URL targets the API host. */
function isApiHost(absoluteUrl: string): boolean {
  if (!API_BASE_URL) return true; // same-origin: treat as API
  try {
    return new URL(absoluteUrl, API_BASE_URL).host === new URL(API_BASE_URL).host;
  } catch {
    return true;
  }
}

async function currentAccessToken(): Promise<string | null> {
  try {
    const { data } = await supabase.auth.getSession();
    return data?.session?.access_token ?? null;
  } catch {
    return null;
  }
}

function parseBody(text: string): unknown {
  if (!text) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function request<T>(
  method: HttpMethod,
  path: string,
  body?: unknown,
  opts?: RequestOptions,
): Promise<T> {
  const url = resolveUrl(path);
  const toApiHost = isApiHost(url);
  const headers: Record<string, string> = { ...(opts?.headers ?? {}) };

  // Attach the JWT only for API-host requests — never for S3 pre-signed URLs.
  if (toApiHost) {
    const token = await currentAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  let payload: string | undefined;
  if (body !== undefined && body !== null) {
    headers['Content-Type'] = headers['Content-Type'] ?? 'application/json';
    payload = JSON.stringify(body);
  }

  const response = await fetch(url, {
    method,
    headers,
    body: payload,
    signal: opts?.signal,
  });

  const parsed = parseBody(await response.text());

  // 401 from the API host: surface it AND notify (AuthContext logs out). Never retry.
  if (response.status === 401 && toApiHost) {
    notifyUnauthorized();
    throw new ApiError(401, 'Unauthorized', parsed);
  }

  if (!response.ok) {
    throw new ApiError(
      response.status,
      `Request failed with status ${response.status}`,
      parsed,
    );
  }

  // 204 No Content (logout, delete, etc.) → undefined.
  return parsed as T;
}

type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'DELETE';

export const apiClient = {
  get: <T>(path: string, opts?: RequestOptions): Promise<T> =>
    request<T>('GET', path, undefined, opts),
  post: <T>(path: string, body?: unknown, opts?: RequestOptions): Promise<T> =>
    request<T>('POST', path, body, opts),
  patch: <T>(path: string, body?: unknown, opts?: RequestOptions): Promise<T> =>
    request<T>('PATCH', path, body, opts),
  delete: <T>(path: string, opts?: RequestOptions): Promise<T> =>
    request<T>('DELETE', path, undefined, opts),
};

export default apiClient;
