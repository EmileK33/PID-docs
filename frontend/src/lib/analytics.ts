// Client analytics — UI telemetry ONLY (page views, button clicks).
//
// HARD BOUNDARY (§1.10, manifest): the 9 structured product events fire
// SERVER-SIDE. This browser helper must never emit them. `track()` refuses any
// reserved event name, and this module exports no constant named after them.
//
// No-op contract: if VITE_POSTHOG_API_KEY is absent, every call is a silent
// no-op (must not throw) — local/CI runs have no PostHog key.
import posthog from 'posthog-js';

const POSTHOG_API_KEY = import.meta.env.VITE_POSTHOG_API_KEY;
const POSTHOG_HOST = import.meta.env.VITE_POSTHOG_HOST ?? 'https://us.i.posthog.com';

// §1.10 server-side structured events. The browser must NOT emit these.
const SERVER_RESERVED_EVENTS: ReadonlySet<string> = new Set([
  'user_registered',
  'drawing_uploaded',
  'processing_complete',
  'processing_failed',
  'correction_made',
  'export_generated',
  'subscription_upgraded',
  'subscription_canceled',
  'account_deleted',
]);

let initialized = false;
if (POSTHOG_API_KEY) {
  try {
    posthog.init(POSTHOG_API_KEY, {
      api_host: POSTHOG_HOST,
      capture_pageview: false,
      autocapture: false,
    });
    initialized = true;
  } catch {
    initialized = false;
  }
}

/** Emit a UI telemetry event. No-op without a PostHog key; reserved server-side
 * event names are refused. */
export function track(event: string, props?: Record<string, unknown>): void {
  if (!initialized) return;
  if (SERVER_RESERVED_EVENTS.has(event)) {
    if (import.meta.env.DEV) {
      // eslint-disable-next-line no-console
      console.warn(
        `[analytics] refusing to emit server-side event "${event}" from the browser`,
      );
    }
    return;
  }
  try {
    posthog.capture(event, props);
  } catch {
    /* never let telemetry break the UI */
  }
}

export function identify(userId: string): void {
  if (!initialized) return;
  try {
    posthog.identify(userId);
  } catch {
    /* ignore */
  }
}

export const analytics = { track, identify };

export default analytics;
