"""Thin wrapper over the Stripe SDK (S2-E).

Centralises every Stripe interaction so the routers/services never touch the SDK
directly:

* ``stripe.api_key`` is configured from ``settings.STRIPE_SECRET_KEY`` at module
  import time (§1.12 — the key is a "Refuse to start" variable; ``app.config``
  already gates startup, but we re-assert here and raise
  :class:`ConfigurationError` if it is blank so the SDK never silently runs
  unauthenticated).
* :func:`create_checkout_session` creates a Stripe Checkout session and returns
  its raw dict. It performs **no** DB writes (§1.4 Rule 9).
* :func:`construct_event` verifies the ``Stripe-Signature`` header via
  ``stripe.Webhook.construct_event`` (§1.7) before any payload is trusted.
* :func:`tier_for_price_id` / :func:`price_id_for_tier` translate between Stripe
  price IDs and :data:`TierId` using ``STRIPE_PRO_PRICE_ID`` /
  ``STRIPE_TEAM_PRICE_ID``.

The blocking, network-bound calls (``checkout.Session.create``,
``Subscription.retrieve``) are synchronous here; async route handlers wrap them
in ``run_in_executor`` so the event loop is never blocked.
"""
from __future__ import annotations

from typing import Any, Optional

import stripe

from app.config import settings
from app.schemas.contracts import TierId


class ConfigurationError(RuntimeError):
    """Raised when a required Stripe configuration value is missing/blank."""


# --- Module-init: configure the SDK (§1.12 / critical note) ----------------
if not settings.STRIPE_SECRET_KEY:
    # app.config already refuses to start without it; this is belt-and-braces so
    # the SDK is never used unauthenticated if config gating is ever relaxed.
    raise ConfigurationError("STRIPE_SECRET_KEY is blank; refusing to configure Stripe SDK.")

stripe.api_key = settings.STRIPE_SECRET_KEY


# ---------------------------------------------------------------------------
# Price <-> tier mapping
# ---------------------------------------------------------------------------
def _tier_price_map() -> dict[str, TierId]:
    """Build a {price_id: tier_id} map from the configured price IDs.

    Read lazily (not cached at import) so tests can monkeypatch ``settings``.
    ``free`` has no Stripe price — it is the absence of a paid subscription.
    """
    mapping: dict[str, TierId] = {}
    if settings.STRIPE_PRO_PRICE_ID:
        mapping[settings.STRIPE_PRO_PRICE_ID] = "pro"
    if settings.STRIPE_TEAM_PRICE_ID:
        mapping[settings.STRIPE_TEAM_PRICE_ID] = "team"
    return mapping


def tier_for_price_id(price_id: Optional[str]) -> Optional[TierId]:
    """Return the :data:`TierId` for a Stripe price ID, or ``None`` if unknown."""
    if not price_id:
        return None
    return _tier_price_map().get(price_id)


def price_id_for_tier(tier_id: str) -> str:
    """Return the configured Stripe price ID for a paid tier.

    Raises :class:`ConfigurationError` if the tier is not a paid tier or its
    price ID is unconfigured (surfaced as HTTP 500 by the checkout route).
    """
    if tier_id == "pro":
        price = settings.STRIPE_PRO_PRICE_ID
    elif tier_id == "team":
        price = settings.STRIPE_TEAM_PRICE_ID
    else:
        raise ConfigurationError(f"No Stripe price for tier {tier_id!r} (paid tiers: pro, team).")
    if not price:
        raise ConfigurationError(
            f"Stripe price ID for tier {tier_id!r} is not configured "
            f"(set STRIPE_{tier_id.upper()}_PRICE_ID)."
        )
    return price


# ---------------------------------------------------------------------------
# Checkout (§1.4 Rule 9 — NO DB writes here)
# ---------------------------------------------------------------------------
def create_checkout_session(
    *,
    tier_id: str,
    user_id: str,
    success_url: str,
    cancel_url: str,
    customer_email: Optional[str] = None,
) -> dict[str, Any]:
    """Create a Stripe Checkout session for ``tier_id`` and return its dict.

    The authenticated user's UUID is embedded via both ``client_reference_id``
    and ``metadata.user_id`` (so ``checkout.session.completed`` can resolve the
    user), and ``metadata.tier_id`` / ``subscription_data.metadata`` carry the
    target tier so the completion handler does not need a follow-up API call.
    """
    price_id = price_id_for_tier(tier_id)
    metadata = {"user_id": user_id, "tier_id": tier_id}
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        client_reference_id=user_id,
        metadata=metadata,
        subscription_data={"metadata": metadata},
        customer_email=customer_email,
        success_url=success_url,
        cancel_url=cancel_url,
    )
    # stripe-python returns a StripeObject; normalise to a plain dict.
    return dict(session)


def retrieve_subscription(subscription_id: str) -> dict[str, Any]:
    """Retrieve a Stripe Subscription (used to resolve tier on checkout completion)."""
    return dict(stripe.Subscription.retrieve(subscription_id))


# ---------------------------------------------------------------------------
# Webhook signature verification (§1.7, US-020 AC-9)
# ---------------------------------------------------------------------------
def construct_event(payload: bytes, sig_header: Optional[str]) -> dict[str, Any]:
    """Verify the signature and return the Stripe event as a dict.

    Raises ``stripe.error.SignatureVerificationError`` (or ``ValueError`` for a
    malformed body / missing header) — the caller maps either to HTTP 400.
    """
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise ConfigurationError("STRIPE_WEBHOOK_SECRET is blank; cannot verify webhooks.")
    if not sig_header:
        # construct_event would raise anyway, but be explicit: missing header → 400.
        raise ValueError("Missing Stripe-Signature header")
    event = stripe.Webhook.construct_event(
        payload=payload,
        sig_header=sig_header,
        secret=settings.STRIPE_WEBHOOK_SECRET,
    )
    return dict(event)


__all__ = [
    "ConfigurationError",
    "create_checkout_session",
    "retrieve_subscription",
    "construct_event",
    "tier_for_price_id",
    "price_id_for_tier",
]
