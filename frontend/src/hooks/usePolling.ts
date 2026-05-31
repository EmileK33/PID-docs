// usePolling — poll an API endpoint on a fixed interval.
//
// Used directly and as the fallback transport behind useSSE (§1.9: ≤10s polling
// fallback for proxied connections). Pass `url = null` to disable polling
// (so the hook can be called unconditionally while inactive).
import { useEffect, useState } from 'react';

import { apiClient } from '../api/client';

export const DEFAULT_POLL_INTERVAL_MS = 10_000;

export interface PollingResult<T> {
  data: T | null;
  error: Error | null;
}

export function usePolling<T>(
  url: string | null,
  intervalMs: number = DEFAULT_POLL_INTERVAL_MS,
): PollingResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!url) return;
    let active = true;

    const poll = async () => {
      try {
        const result = await apiClient.get<T>(url);
        if (active) {
          setData(result);
          setError(null);
        }
      } catch (err) {
        if (active) setError(err as Error);
      }
    };

    void poll(); // fetch immediately, then on the interval
    const id = setInterval(() => {
      void poll();
    }, intervalMs);

    return () => {
      active = false;
      clearInterval(id);
    };
  }, [url, intervalMs]);

  return { data, error };
}

export default usePolling;
