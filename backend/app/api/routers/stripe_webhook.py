"""Stripe webhook router (S2-E) — US-019/US-020.

``POST /webhooks/stripe`` is the single source of truth for subscription state
(§1.4 Rule 9). The handler enforces the §1.4 ordering rules end-to-end:

1. Read the **raw** body (bytes) and verify the ``Stripe-Signature`` header via
   the SDK *before* trusting any payload (US-020 AC-9 → 400 on failure).
2. Insert the ``stripe_event`` row FIRST (Rule 10 / AC-13). If the event ID is
   already present it is a duplicate → return 200 with no state mutation
   (AC-10/AC-12).
3. Apply the DB mutation (uncommitted), then ``commit()``.
4. ONLY after commit: invalidate + rewrite the ``subscription:flags`` cache
   (AC-9/AC-14), emit upgrade/downgrade analytics (so the tier change is durable
   before analytics fires — §1.10 / AC-10), and dispatch grace-period Celery
   tasks (AC-4/AC-5).

Every successfully processed event — including unrecognised types and duplicates
— returns 200 so Stripe never retries a handled delivery (§1.5).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session
from stripe.error import SignatureVerificationError

from app.analytics.events import (
    emit_subscription_downgraded,
    emit_subscription_upgraded,
)
from app.db.session import get_db
from app.redis.cache import invalidate_subscription_flags, set_subscription_flags
from app.services import stripe_client, subscription_service
from app.services.stripe_event_idempotency import check_and_store
from app.workers.celery_app import celery_app

router = APIRouter(tags=["stripe"])


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    # 1. Raw body + signature verification (must precede JSON parsing).
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    try:
        event = stripe_client.construct_event(payload, sig_header)
    except (SignatureVerificationError, ValueError):
        # Invalid/missing signature or malformed body → 400 (AC-9).
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    event_id = event.get("id")
    event_type = event.get("type", "")

    # 2. Idempotency: store the event ID FIRST (Rule 10 / AC-13). Duplicate → 200.
    if not event_id or not check_and_store(db, event_id, event_type, payload=event):
        db.rollback()
        return Response(status_code=status.HTTP_200_OK)

    # 3. Apply the state mutation (still uncommitted), then commit.
    outcome = subscription_service.process_event(db, event)
    db.commit()

    # 4. Post-commit side effects (tier change is now durable — §1.10 ordering).
    if outcome.flags is not None and outcome.user_id:
        await invalidate_subscription_flags(outcome.user_id)
        await set_subscription_flags(outcome.user_id, outcome.flags)

    if outcome.analytics is not None and outcome.user_id and outcome.subscription_id:
        direction, previous_tier, new_tier = outcome.analytics
        if direction == "upgraded":
            emit_subscription_upgraded(
                outcome.user_id, outcome.subscription_id, previous_tier, new_tier
            )
        else:
            emit_subscription_downgraded(
                outcome.user_id, outcome.subscription_id, previous_tier, new_tier
            )

    for task in outcome.celery:
        if task.eta is not None:
            celery_app.send_task(task.name, args=task.args, eta=task.eta)
        else:
            celery_app.send_task(task.name, args=task.args)

    return Response(status_code=status.HTTP_200_OK)


__all__ = ["router"]
