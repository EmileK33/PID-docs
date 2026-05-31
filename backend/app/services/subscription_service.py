"""Subscription read + Stripe-webhook state-mutation logic (S2-E).

This module owns the *DB-facing* half of the billing flow:

* :func:`get_subscription_for_user` — the read used by ``GET /subscription`` and
  by the cache-flag builder.
* :func:`build_flags` — assembles the ``subscription:flags:{user_id}`` payload
  (§1.11) from the subscription + its tier row.
* :func:`process_event` — dispatches a verified Stripe event to the matching
  handler, applies the DB mutation (still uncommitted), and returns a
  :class:`WebhookOutcome` describing the side effects (cache write, analytics,
  Celery dispatch) that the router performs **after** ``db.commit()`` so analytics
  never fires before the tier change is durable (§1.10).

The handlers never commit and never fire side effects themselves — that keeps
the §1.4 ordering rules (event row first, commit, then analytics/cache/celery)
enforced in one place: the webhook router.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Union
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.db.models.subscription import Subscription
from app.db.models.tier import Tier
from app.schemas.contracts import BillingState, TierId
from app.services import stripe_client
from app.services.billing_state_machine import BillingStateMachine

# --- Celery task names (S2-M owns the implementations; we dispatch by name so
#     this session does not import the not-yet-existing notification package). --
GRACE_STARTED_TASK = "notification.send_grace_period_started_email"
GRACE_REMINDER_TASK = "notification.send_grace_period_reminder_email"

# §1.3 — grace period is 7 days; day-6 reminder.
GRACE_PERIOD_DAYS = 7
GRACE_REMINDER_DAY = 6

# free < pro < team — used to classify upgrade vs downgrade.
_TIER_RANK: dict[str, int] = {"free": 0, "pro": 1, "team": 2}


@dataclass
class CeleryDispatch:
    """A deferred Celery task dispatch, applied by the router after commit."""

    name: str
    args: List[Any]
    eta: Optional[datetime] = None


@dataclass
class WebhookOutcome:
    """Side effects to apply *after* the webhook transaction commits.

    ``flags`` is the fresh ``subscription:flags`` payload to (re)write; when set,
    the router invalidates then writes the cache. ``analytics`` is
    ``("upgraded" | "downgraded", previous_tier, new_tier)`` or ``None``.
    """

    user_id: Optional[str] = None
    subscription_id: Optional[str] = None
    flags: Optional[dict] = None
    analytics: Optional[tuple[str, str, str]] = None
    celery: List[CeleryDispatch] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------
def _as_uuid(value: Union[str, UUID]) -> UUID:
    """Coerce a user-id to ``UUID`` so the ``UUID`` column binds on every dialect.

    The ``client_reference_id`` / ``metadata.user_id`` arriving from Stripe are
    strings; the ``subscription.user_id`` column is ``UUID(as_uuid=True)`` whose
    bind processor requires a ``UUID`` (SQLite raises on a bare ``str``).
    """
    return value if isinstance(value, UUID) else UUID(str(value))


def get_subscription_for_user(user_id: Union[str, UUID], db: Session) -> Optional[Subscription]:
    """Return the user's subscription row, or ``None`` if absent."""
    return (
        db.query(Subscription)
        .filter(Subscription.user_id == _as_uuid(user_id))
        .one_or_none()
    )


def _get_subscription_by_customer(db: Session, customer_id: Optional[str]) -> Optional[Subscription]:
    if not customer_id:
        return None
    return (
        db.query(Subscription)
        .filter(Subscription.stripe_customer_id == customer_id)
        .one_or_none()
    )


def build_flags(db: Session, subscription: Subscription) -> dict:
    """Build the §1.11 ``subscription:flags`` payload for ``subscription``."""
    tier = db.get(Tier, subscription.tier_id)
    monthly_limit = tier.monthly_drawing_limit if tier is not None else None
    team_library = bool(tier.team_features) if tier is not None else False
    return {
        "tier_id": subscription.tier_id,
        "billing_state": subscription.billing_state,
        "monthly_drawing_limit": monthly_limit,
        # Pro/Team gain revision comparison; free does not (§1.3 feature gates).
        "revision_comparison": subscription.tier_id in ("pro", "team"),
        "team_library": team_library,
    }


# ---------------------------------------------------------------------------
# Small payload accessors (defensive against missing keys)
# ---------------------------------------------------------------------------
def _first_price_id(container: Optional[dict]) -> Optional[str]:
    """Pull ``items.data[0].price.id`` out of a subscription-like dict."""
    if not container:
        return None
    items = container.get("items") or {}
    data = items.get("data") or []
    if not data:
        return None
    price = (data[0] or {}).get("price") or {}
    return price.get("id")


def _epoch_to_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def _tier_rank(tier_id: Optional[str]) -> int:
    return _TIER_RANK.get(tier_id or "", -1)


# ---------------------------------------------------------------------------
# Event handlers — each mutates the subscription (uncommitted) and returns the
# side-effect plan. They never commit and never fire analytics/cache/celery.
# ---------------------------------------------------------------------------
def apply_checkout_session_completed(db: Session, obj: dict) -> WebhookOutcome:
    """``checkout.session.completed`` → activate the purchased tier (AC-7/8/9)."""
    user_id = obj.get("client_reference_id") or (obj.get("metadata") or {}).get("user_id")
    if not user_id:
        return WebhookOutcome()

    tier_id = _resolve_checkout_tier(obj)
    if tier_id is None:
        # Cannot determine the tier — leave state untouched; row is still recorded.
        return WebhookOutcome()

    subscription = get_subscription_for_user(user_id, db)
    if subscription is None:
        # Edge case: user predates subscription seeding — bootstrap a row.
        subscription = Subscription(
            id=uuid4(),
            user_id=_as_uuid(user_id),
            tier_id="free",
            billing_state="Active",
        )
        db.add(subscription)

    subscription.tier_id = tier_id
    subscription.billing_state = "Active"
    subscription.stripe_customer_id = obj.get("customer") or subscription.stripe_customer_id
    subscription.stripe_subscription_id = (
        obj.get("subscription") or subscription.stripe_subscription_id
    )
    db.flush()

    return WebhookOutcome(
        user_id=str(user_id),
        subscription_id=str(subscription.id),
        flags=build_flags(db, subscription),
        # Tier activation analytics is emitted from customer.subscription.updated
        # (which carries previous_attributes); checkout.completed only activates.
    )


def _resolve_checkout_tier(obj: dict) -> Optional[TierId]:
    """Determine the purchased tier from session metadata, falling back to a
    Stripe subscription retrieve to read the price."""
    meta_tier = (obj.get("metadata") or {}).get("tier_id")
    if meta_tier in ("pro", "team"):
        return meta_tier  # type: ignore[return-value]

    sub_id = obj.get("subscription")
    if sub_id:
        try:
            remote = stripe_client.retrieve_subscription(sub_id)
        except Exception:  # noqa: BLE001 — network/SDK error: tier stays unknown
            return None
        return stripe_client.tier_for_price_id(_first_price_id(remote))
    return None


def apply_subscription_updated(
    db: Session, obj: dict, previous_attributes: dict
) -> WebhookOutcome:
    """``customer.subscription.updated`` → upgrade/downgrade analytics (AC-10/AC-8).

    A scheduled cancellation (``cancel_at_period_end`` flipping to ``True``)
    fires ``subscription_downgraded`` immediately while retaining the tier until
    period end (§1.10 note). A price change up/down sets the new tier and fires
    the matching analytics event.
    """
    subscription = _get_subscription_by_customer(db, obj.get("customer"))
    if subscription is None:
        return WebhookOutcome()

    previous_tier = subscription.tier_id
    new_period_end = _epoch_to_dt(obj.get("current_period_end"))
    if new_period_end is not None:
        subscription.current_period_end = new_period_end
    if obj.get("id"):
        subscription.stripe_subscription_id = obj["id"]

    analytics: Optional[tuple[str, str, str]] = None

    cancel_now = (
        obj.get("cancel_at_period_end") is True
        and previous_attributes.get("cancel_at_period_end") is False
    )
    if cancel_now:
        # Scheduled cancellation: fire downgrade now, keep access until period end.
        analytics = ("downgraded", previous_tier, "free")
    else:
        new_tier = stripe_client.tier_for_price_id(_first_price_id(obj))
        # §1.10 / AC-10: the tier change is detected from previous_attributes
        # (Stripe's authoritative diff). An unconfigured/absent price → 'free'.
        prev_price = _first_price_id(previous_attributes)
        if prev_price is not None:
            previous_tier = stripe_client.tier_for_price_id(prev_price) or "free"
        if new_tier is not None and new_tier != previous_tier:
            if _tier_rank(new_tier) > _tier_rank(previous_tier):
                subscription.tier_id = new_tier
                if subscription.billing_state != "Active":
                    subscription.billing_state = "Active"
                analytics = ("upgraded", previous_tier, new_tier)
            else:
                subscription.tier_id = new_tier
                analytics = ("downgraded", previous_tier, new_tier)

    db.flush()
    return WebhookOutcome(
        user_id=str(subscription.user_id) if subscription.user_id else None,
        subscription_id=str(subscription.id),
        flags=build_flags(db, subscription),
        analytics=analytics,
    )


def apply_invoice_payment_failed(db: Session, obj: dict) -> WebhookOutcome:
    """``invoice.payment_failed`` → enter Grace + schedule emails (AC-1..5)."""
    subscription = _get_subscription_by_customer(db, obj.get("customer"))
    if subscription is None:
        return WebhookOutcome()

    celery: List[CeleryDispatch] = []

    # Only the FIRST failure (Active → Grace) sets grace_period_start and queues
    # the emails; a repeat failure while already in Grace is idempotent (AC-3).
    if subscription.billing_state == "Active":
        BillingStateMachine.transition(subscription, "Grace")
        if subscription.grace_period_start is None:
            subscription.grace_period_start = datetime.now(timezone.utc)
        grace_start = subscription.grace_period_start
        grace_end_iso = (grace_start + timedelta(days=GRACE_PERIOD_DAYS)).isoformat()
        user_id = str(subscription.user_id) if subscription.user_id else None
        if user_id:
            celery.append(CeleryDispatch(GRACE_STARTED_TASK, [user_id, grace_end_iso]))
            celery.append(
                CeleryDispatch(
                    GRACE_REMINDER_TASK,
                    [user_id, grace_end_iso],
                    eta=grace_start + timedelta(days=GRACE_REMINDER_DAY),
                )
            )

    db.flush()
    return WebhookOutcome(
        user_id=str(subscription.user_id) if subscription.user_id else None,
        subscription_id=str(subscription.id),
        flags=build_flags(db, subscription),
        celery=celery,
    )


def apply_invoice_payment_succeeded(db: Session, obj: dict) -> WebhookOutcome:
    """``invoice.payment_succeeded`` → recover from Grace to Active (AC-6)."""
    subscription = _get_subscription_by_customer(db, obj.get("customer"))
    if subscription is None:
        return WebhookOutcome()

    if subscription.billing_state == "Grace":
        BillingStateMachine.transition(subscription, "Active")
        subscription.grace_period_start = None

    db.flush()
    return WebhookOutcome(
        user_id=str(subscription.user_id) if subscription.user_id else None,
        subscription_id=str(subscription.id),
        flags=build_flags(db, subscription),
    )


def apply_subscription_deleted(db: Session, obj: dict) -> WebhookOutcome:
    """``customer.subscription.deleted`` → Canceled + downgrade to free (AC-7)."""
    subscription = _get_subscription_by_customer(db, obj.get("customer"))
    if subscription is None:
        return WebhookOutcome()

    if subscription.billing_state != "Canceled":
        BillingStateMachine.transition(subscription, "Canceled")
    subscription.tier_id = "free"

    db.flush()
    return WebhookOutcome(
        user_id=str(subscription.user_id) if subscription.user_id else None,
        subscription_id=str(subscription.id),
        flags=build_flags(db, subscription),
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
_HANDLERS = {
    "checkout.session.completed": lambda db, data: apply_checkout_session_completed(
        db, data.get("object") or {}
    ),
    "customer.subscription.updated": lambda db, data: apply_subscription_updated(
        db, data.get("object") or {}, data.get("previous_attributes") or {}
    ),
    "invoice.payment_failed": lambda db, data: apply_invoice_payment_failed(
        db, data.get("object") or {}
    ),
    "invoice.payment_succeeded": lambda db, data: apply_invoice_payment_succeeded(
        db, data.get("object") or {}
    ),
    "customer.subscription.deleted": lambda db, data: apply_subscription_deleted(
        db, data.get("object") or {}
    ),
}


def process_event(db: Session, event: dict) -> WebhookOutcome:
    """Dispatch a verified Stripe event to its handler.

    Unrecognised event types are a no-op (the event row is still recorded by the
    caller) and return an empty :class:`WebhookOutcome` so the router returns
    HTTP 200 (US-020 AC-15).
    """
    handler = _HANDLERS.get(event.get("type", ""))
    if handler is None:
        return WebhookOutcome()
    return handler(db, event.get("data") or {})


__all__ = [
    "WebhookOutcome",
    "CeleryDispatch",
    "get_subscription_for_user",
    "build_flags",
    "process_event",
    "apply_checkout_session_completed",
    "apply_subscription_updated",
    "apply_invoice_payment_failed",
    "apply_invoice_payment_succeeded",
    "apply_subscription_deleted",
    "GRACE_STARTED_TASK",
    "GRACE_REMINDER_TASK",
]
