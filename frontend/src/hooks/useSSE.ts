// useSSE — subscribe to a server-sent-events endpoint with a polling fallback.
//
// [LOAD-BEARING] Consumed by S3-B/S3-D for live drawing status (US-008).
//
// Contract (§1.9, S1-F manifest):
//  - Opens a native EventSource (no 3rd-party SSE library) to the given URL and
//    emits parsed JSON payloads (e.g. DrawingStatusSSEEvent) to consumers.
//  - Falls back to usePolling within 10 seconds if the EventSource emits `error`
//    or never reaches `open`. Polling uses the same 10s cadence and same URL.
import { useEffect, useState } from 'react';

import { resolveUrl } from '../api/client';
import { DEFAULT_POLL_INTERVAL_MS, usePolling } from './usePolling';

export const SSE_FALLBACK_MS = 10_000;

export interface SSEResult<T> {
  data: T | null;
  error: Error | null;
  isPolling: boolean;
}

export function useSSE<T>(url: string): SSEResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  useEffect(() => {
    setIsPolling(false);
    setError(null);

    // No EventSource (SSR/old runtime) → go straight to polling.
    if (typeof EventSource === 'undefined') {
      setIsPolling(true);
      return;
    }

    let closed = false;
    let opened = false;
    const source = new EventSource(resolveUrl(url));

    const fallBackToPolling = () => {
      if (closed) return;
      closed = true;
      clearTimeout(timer);
      try {
        source.close();
      } catch {
        /* ignore */
      }
      setIsPolling(true);
    };

    // If we never reach `open` within the fallback window, switch to polling.
    const timer = setTimeout(() => {
      if (!opened) fallBackToPolling();
    }, SSE_FALLBACK_MS);

    source.onopen = () => {
      opened = true;
      clearTimeout(timer);
    };

    source.onmessage = (event: MessageEvent<string>) => {
      try {
        setData(JSON.parse(event.data) as T);
        setError(null);
      } catch (err) {
        setError(err as Error);
      }
    };

    source.onerror = () => {
      setError(new Error('SSE connection error'));
      fallBackToPolling();
    };

    return () => {
      closed = true;
      clearTimeout(timer);
      try {
        source.close();
      } catch {
        /* ignore */
      }
    };
  }, [url]);

  // Always called (hooks rule); inert until we flip to polling.
  const polling = usePolling<T>(isPolling ? url : null, DEFAULT_POLL_INTERVAL_MS);

  return {
    data: isPolling ? polling.data : data,
    error: isPolling ? polling.error : error,
    isPolling,
  };
}

export default useSSE;
