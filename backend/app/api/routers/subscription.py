"""Subscription API router (S2-E) — US-019.

Routes:

* ``GET  /subscription``          — current tier + billing state (AC-5/6).
* ``POST /subscription/checkout`` — create a Stripe Checkout session (AC-1..4).
* ``POST /subscription/manage``   — **P1 placeholder** (Stripe Customer Portal):
  a clearly-marked ``NotImplementedError`` per the session scope. Not in the P0
  route manifest.

``POST /subscription/checkout`` performs **no** subscription DB writes (§1.4
Rule 9) and never fires ``subscription_upgraded`` (§1.10 / US-019 AC-11): state
changes only via Stripe webhooks. The blocking Stripe SDK call runs in a thread
executor so the event loop is not blocked.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.config import settings
from app.db.session import get_db
from app.schemas.contracts import TierId
from app.services import stripe_client, subscription_service

router = APIRouter(tags=["subscription"])


# ---------------------------------------------------------------------------
# Response / request schemas (exported contract — consumed by S3-F)
# ---------------------------------------------------------------------------
class SubscriptionResponse(BaseModel):
    id: str
    tier_id: str
    billing_state: str
    current_period_end: Optional[datetime] = None
    grace_period_start: Optional[datetime] = None
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None


class CheckoutRequest(BaseModel):
    # Only paid tiers are checkout targets; 'free' is the absence of a paid plan.
    tier_id: TierId


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


def _checkout_urls() -> tuple[str, str]:
    """Success/cancel redirect URLs handed to Stripe Checkout.

    Frontend origin is environment-dependent; staging/prod inject it. The SPA
    subscription page (S3-F) polls ``GET /subscription`` after redirect.
    """
    base = getattr(settings, "FRONTEND_BASE_URL", None) or "https://app.pid.local"
    return (f"{base}/subscription?checkout=success", f"{base}/subscription?checkout=cancel")


@router.get("/subscription", response_model=SubscriptionResponse)
def get_subscription(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionResponse:
    """Return the authenticated user's current subscription state (AC-5).

    401 for unauthenticated requests is enforced by ``get_current_user`` (AC-6).
    """
    subscription = subscription_service.get_subscription_for_user(str(user.id), db)
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription for user",
        )
    return SubscriptionResponse(
        id=str(subscription.id),
        tier_id=subscription.tier_id,
        billing_state=subscription.billing_state,
        current_period_end=subscription.current_period_end,
        grace_period_start=subscription.grace_period_start,
        stripe_subscription_id=subscription.stripe_subscription_id,
        stripe_customer_id=subscription.stripe_customer_id,
    )


@router.post("/subscription/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    user: CurrentUser = Depends(get_current_user),
) -> CheckoutResponse:
    """Create a Stripe Checkout session for the requested paid tier (AC-1/2).

    Does NOT touch the ``subscription`` table (§1.4 Rule 9) and does NOT emit
    analytics (§1.10) — both happen only via the webhook. 401 for unauthenticated
    requests (AC-4) is enforced by ``get_current_user``.
    """
    if body.tier_id not in ("pro", "team"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tier_id must be a paid tier ('pro' or 'team')",
        )

    success_url, cancel_url = _checkout_urls()
    loop = asyncio.get_running_loop()
    try:
        session = await loop.run_in_executor(
            None,
            lambda: stripe_client.create_checkout_session(
                tier_id=body.tier_id,
                user_id=str(user.id),
                success_url=success_url,
                cancel_url=cancel_url,
                customer_email=user.email,
            ),
        )
    except stripe_client.ConfigurationError as exc:
        # Misconfigured Stripe price IDs — operator error, surface as 500.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    url = session.get("url")
    if not url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe did not return a checkout URL",
        )
    return CheckoutResponse(checkout_url=url, session_id=session.get("id", ""))


@router.post("/subscription/manage")
async def manage_subscription(
    user: CurrentUser = Depends(get_current_user),
) -> None:
    """P1 placeholder — Stripe Customer Portal redirect (downgrades / payment
    method management). Intentionally unimplemented in P0."""
    raise NotImplementedError(
        "POST /subscription/manage (Stripe Customer Portal) is a P1 feature; "
        "not implemented in the P0 build."
    )


__all__ = ["router", "SubscriptionResponse", "CheckoutResponse", "CheckoutRequest"]
