// GraceBanner — full-width banner shown during a subscription grace period.
//
// Shows ONLY when subscription.billing_state === 'Grace' AND
// sessionStorage.graceBannerDismissed !== 'true' (US-020). Dismissal is
// session-scoped (new tab/session → banner reappears).
//
// Subscription data: pass `subscription` explicitly (tests, or a parent that
// already has it), otherwise the banner fetches GET /subscription itself — but
// only when authenticated, to avoid a 401 logout loop on public pages.
import { useEffect, useState, type ReactElement } from 'react';

import type { BillingState } from '../types/contracts';
import { apiClient } from '../api/client';
import { endpoints } from '../api/endpoints';
import { useAuth } from '../auth/useAuth';
import { storage } from '../lib/storage';

export interface SubscriptionInfo {
  billing_state: BillingState;
  grace_period_end?: string;
}

export interface GraceBannerProps {
  subscription?: SubscriptionInfo;
}

export function GraceBanner({ subscription }: GraceBannerProps): ReactElement | null {
  const { user } = useAuth();
  const [sub, setSub] = useState<SubscriptionInfo | null>(subscription ?? null);
  const [dismissed, setDismissed] = useState<boolean>(() =>
    storage.isGraceBannerDismissed(),
  );

  useEffect(() => {
    if (subscription) {
      setSub(subscription);
      return;
    }
    if (!user) return;
    let active = true;
    apiClient
      .get<SubscriptionInfo>(endpoints.subscriptionGet.path)
      .then((result) => {
        if (active) setSub(result);
      })
      .catch(() => {
        /* banner simply stays hidden if we can't read the subscription */
      });
    return () => {
      active = false;
    };
  }, [user, subscription]);

  if (!sub || sub.billing_state !== 'Grace' || dismissed) return null;

  const handleDismiss = () => {
    storage.dismissGraceBanner();
    setDismissed(true);
  };

  return (
    <div className="grace-banner" role="alert">
      <span className="grace-banner__message">
        Your subscription payment failed. Resolve by{' '}
        {sub.grace_period_end ?? 'the end of your grace period'} to keep access.
      </span>
      <a className="grace-banner__action" href="/subscription">
        Update payment
      </a>
      <button
        type="button"
        className="grace-banner__dismiss"
        aria-label="Dismiss"
        onClick={handleDismiss}
      >
        ×
      </button>
    </div>
  );
}

export default GraceBanner;
