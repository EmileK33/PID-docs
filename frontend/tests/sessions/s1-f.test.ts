// S1-F session test — validates the shared frontend infrastructure.
//
// Runs in JSDOM with mocked fetch / EventSource / @supabase/supabase-js. No
// backend, Supabase, or PostHog network calls (manifest isolation rule).
//
// NOTE: this is a `.test.ts` (no JSX) per the manifest test path, so React
// trees are built with React.createElement (aliased `h`).
import { createElement as h, type ReactNode } from 'react';
import {
  act,
  cleanup,
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
} from '@testing-library/react';
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom';
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import type { DrawingStatusSSEEvent } from '../../src/types/contracts';

// --- Supabase mock ------------------------------------------------------------
// Hoisted shared state so each test can set the "current session".
const supa = vi.hoisted(() => ({
  state: { session: null as unknown }, // mutated per-test
}));

vi.mock('@supabase/supabase-js', () => {
  const auth = {
    getSession: vi.fn(async () => ({ data: { session: supa.state.session } })),
    onAuthStateChange: vi.fn(() => ({
      data: { subscription: { unsubscribe: vi.fn() } },
    })),
    signInWithPassword: vi.fn(async () => ({
      data: { session: supa.state.session },
      error: null,
    })),
    signOut: vi.fn(async () => {
      supa.state.session = null;
      return { error: null };
    }),
  };
  return { createClient: () => ({ auth }) };
});

// Imports AFTER the mock is declared (vi.mock is hoisted above all imports).
import { apiClient, ApiError } from '../../src/api/client';
import { endpoints, buildPath } from '../../src/api/endpoints';
import { AuthProvider } from '../../src/auth/AuthContext';
import { useAuth } from '../../src/auth/useAuth';
import { supabase } from '../../src/auth/supabaseClient';
import { useSSE } from '../../src/hooks/useSSE';
import { usePolling } from '../../src/hooks/usePolling';
import { ProtectedRoute } from '../../src/components/ProtectedRoute';
import { GraceBanner } from '../../src/components/GraceBanner';
import { Layout } from '../../src/components/Layout';
import { storage } from '../../src/lib/storage';
import * as analyticsModule from '../../src/lib/analytics';

// --- EventSource mock ---------------------------------------------------------
class MockEventSource {
  static instances: MockEventSource[] = [];
  static last(): MockEventSource {
    return MockEventSource.instances[MockEventSource.instances.length - 1];
  }

  url: string;
  closed = false;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  close(): void {
    this.closed = true;
  }

  emitOpen(): void {
    this.onopen?.(new Event('open'));
  }

  emitMessage(data: string): void {
    this.onmessage?.({ data } as MessageEvent);
  }

  emitError(): void {
    this.onerror?.(new Event('error'));
  }
}

// --- Fixtures -----------------------------------------------------------------
const AUTHED_SESSION = {
  access_token: 'test-token',
  user: {
    id: 'user-1',
    email: 'user@example.com',
    app_metadata: { role: 'user' },
  },
};

function jsonResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => (body === undefined ? '' : JSON.stringify(body)),
  };
}

function authProvider(children: ReactNode) {
  return h(AuthProvider, null, children);
}

const originalLocation = window.location;

beforeEach(() => {
  vi.clearAllMocks();
  supa.state.session = null;
  localStorage.clear();
  sessionStorage.clear();
  MockEventSource.instances = [];
  vi.unstubAllGlobals();
  vi.stubGlobal('EventSource', MockEventSource as unknown as typeof EventSource);
  // Controllable window.location for redirect assertions.
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: { pathname: '/', search: '', href: '', assign: vi.fn() },
  });
});

afterEach(() => {
  cleanup();
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: originalLocation,
  });
});

// =============================================================================
// API client
// =============================================================================
describe('apiClient', () => {
  it('attaches Bearer token for API host requests', async () => {
    supa.state.session = AUTHED_SESSION;
    const fetchMock = vi.fn(async () => jsonResponse(200, { ok: true }));
    vi.stubGlobal('fetch', fetchMock);

    await apiClient.get('/account');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('http://localhost:8000/account');
    expect((init.headers as Record<string, string>).Authorization).toBe(
      'Bearer test-token',
    );
  });

  it('does not attach Authorization header for non-API hosts', async () => {
    supa.state.session = AUTHED_SESSION;
    const fetchMock = vi.fn(async () => jsonResponse(200, {}));
    vi.stubGlobal('fetch', fetchMock);

    await apiClient.get('https://s3.amazonaws.com/bucket/presigned-key');

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('https://s3.amazonaws.com/bucket/presigned-key');
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it('exposes status code on error responses', async () => {
    supa.state.session = AUTHED_SESSION;
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse(409, { detail: 'hash blocked' })),
    );

    const err = await apiClient
      .post('/drawings/hash-check', { sha256_hash: 'x' })
      .catch((e) => e);

    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
  });

  it('clears session and redirects on 401', async () => {
    supa.state.session = AUTHED_SESSION;
    render(authProvider(h('div', null, 'app')));
    await waitFor(() => expect(supabase.auth.getSession).toHaveBeenCalled());

    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(401, undefined)));

    let err: unknown;
    await act(async () => {
      err = await apiClient.get('/account').catch((e) => e);
    });
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(401);

    await waitFor(() => expect(supabase.auth.signOut).toHaveBeenCalled());
    expect((window.location.assign as ReturnType<typeof vi.fn>)).toHaveBeenCalledWith(
      '/login',
    );
  });
});

// =============================================================================
// Endpoint manifest
// =============================================================================
describe('endpoints', () => {
  it('endpoints.ts includes every P0 route', () => {
    const present = Object.values(endpoints).map((e) => `${e.method} ${e.path}`);
    const requiredP0 = [
      'POST /auth/register',
      'POST /auth/login',
      'POST /auth/oauth/google',
      'POST /auth/refresh',
      'POST /auth/logout',
      'POST /auth/password-reset/request',
      'POST /auth/password-reset/confirm',
      'POST /drawings/hash-check',
      'GET /drawings',
      'POST /drawings',
      'GET /drawings/:id',
      'PATCH /drawings/:id',
      'DELETE /drawings/:id',
      'POST /drawings/:id/retry',
      'GET /drawings/:id/status',
      'GET /drawings/:id/symbols',
      'PATCH /symbols/:id',
      'POST /drawings/:id/symbols',
      'POST /drawings/:id/exports',
      'GET /exports/:id',
      'POST /drawings/:id/upload-complete',
      'GET /account',
      'PATCH /account',
      'DELETE /account',
      'GET /account/consent',
      'PATCH /account/consent',
      'GET /subscription',
      'POST /subscription/checkout',
      'POST /webhooks/stripe',
      'GET /entity-classes',
    ];
    for (const route of requiredP0) {
      expect(present).toContain(route);
    }
  });

  it('buildPath fills :id placeholders', () => {
    expect(buildPath(endpoints.drawingGet.path, { id: 'abc' })).toBe(
      '/drawings/abc',
    );
  });
});

// =============================================================================
// useSSE / usePolling
// =============================================================================
describe('useSSE', () => {
  it('useSSE emits DrawingStatusSSEEvent objects', () => {
    const { result } = renderHook(() =>
      useSSE<DrawingStatusSSEEvent>('/drawings/d1/status'),
    );
    const es = MockEventSource.last();
    expect(es.url).toBe('http://localhost:8000/drawings/d1/status');

    const event: DrawingStatusSSEEvent = {
      drawing_id: 'd1',
      state: 'Processing',
      timestamp: '2026-05-31T00:00:00Z',
    };
    act(() => es.emitOpen());
    act(() => es.emitMessage(JSON.stringify(event)));

    expect(result.current.data).toEqual(event);
    expect(result.current.isPolling).toBe(false);
  });

  it('useSSE falls back to polling within 10 seconds on error', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue({
      drawing_id: 'd1',
      state: 'Queued',
      timestamp: '2026-05-31T00:00:00Z',
    });
    const { result } = renderHook(() =>
      useSSE<DrawingStatusSSEEvent>('/drawings/d1/status'),
    );
    const es = MockEventSource.last();

    act(() => es.emitError());

    await waitFor(() => expect(result.current.isPolling).toBe(true));
  });
});

describe('usePolling', () => {
  it('usePolling polls every 10 seconds', async () => {
    vi.useFakeTimers();
    try {
      const getSpy = vi
        .spyOn(apiClient, 'get')
        .mockResolvedValue({ state: 'Queued' });
      renderHook(() => usePolling('/drawings/d1/status', 10_000));

      await act(async () => {
        await vi.advanceTimersByTimeAsync(0); // initial immediate poll
      });
      expect(getSpy).toHaveBeenCalledTimes(1);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(10_000);
      });
      expect(getSpy).toHaveBeenCalledTimes(2);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(10_000);
      });
      expect(getSpy).toHaveBeenCalledTimes(3);

      expect(getSpy).toHaveBeenLastCalledWith('/drawings/d1/status');
    } finally {
      vi.useRealTimers();
    }
  });
});

// =============================================================================
// storage
// =============================================================================
describe('storage', () => {
  it('storage rejects writes exceeding 2MB cap', () => {
    // > 1,048,576 chars → > 2MB at 2 bytes/char (UTF-16).
    const tooBig = 'x'.repeat(1024 * 1024 + 10);
    expect(storage.setCorrectionState('d1', tooBig)).toBe(false);
    // A small payload writes fine.
    expect(storage.setCorrectionState('d2', { a: 1 })).toBe(true);
  });

  it('reads/writes correction_state:{drawingId} key', () => {
    storage.setCorrectionState('abc', { foo: 'bar' });
    expect(localStorage.getItem('correction_state:abc')).toBe(
      JSON.stringify({ foo: 'bar' }),
    );
    expect(storage.getCorrectionState('abc')).toEqual({ foo: 'bar' });

    storage.clearCorrectionState('abc');
    expect(storage.getCorrectionState('abc')).toBeNull();
  });
});

// =============================================================================
// GraceBanner
// =============================================================================
describe('GraceBanner', () => {
  it('shows banner only when billing_state=Grace and not dismissed', async () => {
    supa.state.session = AUTHED_SESSION;

    const { unmount } = render(
      authProvider(h(GraceBanner, { subscription: { billing_state: 'Active' } })),
    );
    // Active → no banner.
    expect(screen.queryByRole('alert')).toBeNull();
    unmount();

    render(
      authProvider(
        h(GraceBanner, {
          subscription: { billing_state: 'Grace', grace_period_end: '2026-06-30' },
        }),
      ),
    );
    const banner = await screen.findByRole('alert');
    expect(banner).toBeInTheDocument();
    expect(screen.getByText(/payment failed/i)).toBeInTheDocument();
    expect(screen.getByText(/2026-06-30/)).toBeInTheDocument();
  });

  it('dismissing sets sessionStorage and hides banner', async () => {
    supa.state.session = AUTHED_SESSION;
    render(
      authProvider(h(GraceBanner, { subscription: { billing_state: 'Grace' } })),
    );

    await screen.findByRole('alert');
    fireEvent.click(screen.getByLabelText('Dismiss'));

    expect(sessionStorage.getItem('graceBannerDismissed')).toBe('true');
    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull());
  });
});

// =============================================================================
// ProtectedRoute
// =============================================================================
describe('ProtectedRoute', () => {
  function LoginProbe() {
    const loc = useLocation();
    return h('div', null, `LOGIN ${loc.search}`);
  }

  function renderProtected(initialPath: string) {
    return render(
      h(
        MemoryRouter,
        { initialEntries: [initialPath] },
        authProvider(
          h(
            Routes,
            null,
            h(Route, {
              path: '/dashboard',
              element: h(ProtectedRoute, null, h('div', null, 'SECRET CONTENT')),
            }),
            h(Route, { path: '/login', element: h(LoginProbe) }),
          ),
        ),
      ),
    );
  }

  it('redirects to /login?next= when unauthenticated', async () => {
    supa.state.session = null;
    renderProtected('/dashboard');

    const login = await screen.findByText(/^LOGIN/);
    expect(login.textContent).toContain('next=%2Fdashboard');
  });

  it('renders children when authenticated', async () => {
    supa.state.session = AUTHED_SESSION;
    renderProtected('/dashboard');

    expect(await screen.findByText('SECRET CONTENT')).toBeInTheDocument();
  });
});

// =============================================================================
// AuthContext shape
// =============================================================================
describe('AuthContext', () => {
  it('exposes user, session, signIn, signOut, loading', async () => {
    supa.state.session = AUTHED_SESSION;
    let captured: ReturnType<typeof useAuth> | undefined;
    function Probe() {
      captured = useAuth();
      return null;
    }
    render(authProvider(h(Probe)));

    await waitFor(() => expect(captured?.loading).toBe(false));
    expect(captured).toHaveProperty('user');
    expect(captured).toHaveProperty('session');
    expect(typeof captured?.signIn).toBe('function');
    expect(typeof captured?.signOut).toBe('function');
    expect(typeof captured?.loading).toBe('boolean');
    expect(captured?.user?.email).toBe('user@example.com');
  });
});

// =============================================================================
// analytics
// =============================================================================
describe('analytics', () => {
  it('analytics is no-op without VITE_POSTHOG_API_KEY', () => {
    // VITE_POSTHOG_API_KEY is unset in the test env.
    expect(() => analyticsModule.track('page_view', { path: '/x' })).not.toThrow();
    expect(() => analyticsModule.identify('user-1')).not.toThrow();
  });

  it('analytics module does not export server event names', () => {
    const serverEvents = [
      'user_registered',
      'drawing_uploaded',
      'processing_complete',
      'processing_failed',
      'correction_made',
      'export_generated',
      'subscription_upgraded',
      'subscription_canceled',
      'account_deleted',
    ];
    const exportedNames = Object.keys(analyticsModule);
    for (const name of serverEvents) {
      expect(exportedNames).not.toContain(name);
    }
    // Only UI-telemetry primitives are exported.
    expect(exportedNames).toEqual(
      expect.arrayContaining(['track', 'identify']),
    );
  });
});

// =============================================================================
// Layout chrome (TECH-VISUAL-1: renders without runtime errors)
// =============================================================================
describe('Layout', () => {
  it('renders chrome around an empty page without crashing', async () => {
    supa.state.session = AUTHED_SESSION;
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse(200, { billing_state: 'Active' })),
    );

    render(
      h(
        MemoryRouter,
        null,
        authProvider(h(Layout, null, h('div', null, 'PAGE BODY'))),
      ),
    );

    expect(await screen.findByText('PAGE BODY')).toBeInTheDocument();
    expect(screen.getByText('P&ID Extractor')).toBeInTheDocument();
  });
});
