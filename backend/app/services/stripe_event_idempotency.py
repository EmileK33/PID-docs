"""Stripe webhook idempotency guard (§1.4 Rule 10, US-020 AC-10/AC-13).

:func:`check_and_store` records a Stripe event ID in the ``stripe_event`` table
*before any subscription state mutation*. It is the FIRST DB write in every
webhook transaction. If the event ID is already present the function returns
``False`` and the caller must return HTTP 200 without touching the
``subscription`` table (duplicate webhook → idempotent, §1.5).

The ``stripe_event`` PK is the Stripe event ID, so a concurrent duplicate
delivery collides on the primary key. We use a fast-path SELECT (covers the
common retry case portably across Postgres and the SQLite test DB) plus an
INSERT whose ``flush`` surfaces a PK conflict before any further work.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.stripe_event import StripeEvent


def check_and_store(
    db: Session,
    event_id: str,
    event_type: str,
    payload: Optional[dict[str, Any]] = None,
) -> bool:
    """Insert the event marker, returning ``True`` if new / ``False`` if duplicate.

    On ``True`` a ``stripe_event`` row has been added and flushed (so the
    insert precedes any subscription write in the same transaction). The caller
    commits the transaction once all state mutations succeed.

    ``payload`` is stored in the model's non-null ``payload`` JSONB column for
    audit/replay; callers pass the full verified event. ``received_at`` /
    ``processed_at`` are set explicitly (rather than relying on the Postgres
    ``now()`` server default) so the same code path works on the SQLite test DB.
    """
    # Fast path: already processed (the common Stripe-retry case).
    if db.get(StripeEvent, event_id) is not None:
        return False

    now = datetime.now(timezone.utc)
    db.add(
        StripeEvent(
            id=event_id,
            event_type=event_type,
            received_at=now,
            processed_at=now,
            payload=payload if payload is not None else {},
        )
    )
    try:
        # Surface a PK conflict now (race with a concurrent duplicate delivery),
        # before any subscription mutation runs.
        db.flush()
    except IntegrityError:
        db.rollback()
        return False
    return True


__all__ = ["check_and_store"]
