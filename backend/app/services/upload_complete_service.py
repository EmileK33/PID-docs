"""Upload-complete + retry enqueue path (US-003, US-009, US-010, US-018).

This is the load-bearing junction of the upload flow. On ``POST
/drawings/{id}/upload-complete`` for a ``Pending`` drawing it:

1. Resolves the caller's tier; for free tier, atomically increments the monthly
   counter (``free_tier_counter``). If the cap (3/month) would be exceeded it
   fires ``free_limit_reached`` and returns ``402`` WITHOUT enqueuing (US-018
   AC-1, US-010 AC-4).
2. Transitions the drawing ``Pending -> Queued`` and writes the audit row
   (``drawing_state_machine.transition_drawing``), then COMMITS.
3. *After* the commit, enqueues the ingest Celery job on the ``ingest`` queue
   and fires ``drawing_uploaded`` (US-010 AC-1).

Ordering guarantees (§ critical implementation notes):

* The Celery dispatch happens only AFTER ``db.commit()`` so a rolled-back
  transaction never leaves a queued job (no in-memory dispatch — §1.4 rule 14).
* ``drawing_uploaded`` is emitted only after the commit so analytics never
  records a transition the DB rolled back.
* Idempotency (§1.4 rule 4): a drawing already in ``Queued`` or any later state
  returns ``200`` and does NOT re-enqueue or re-emit (silent duplicate-job
  prevention).

[LOAD-BEARING] The ingest job kwargs shape ``{drawing_id, user_id,
stored_file_id, storage_reference}`` and task name ``ingest.process_drawing``
are consumed verbatim by S2-H. ``user_id`` is written here, at enqueue time,
from authenticated session context (§1.4 rule 5) — never omitted, never None.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.events import emit_drawing_uploaded, emit_free_limit_reached
from app.auth.dependencies import CurrentUser
from app.db.models.drawing import Drawing
from app.db.models.stored_file import StoredFile
from app.db.models.subscription import Subscription
from app.db.models.tier import Tier
from app.services import free_tier_counter
from app.services.drawing_state_machine import transition_drawing
from app.workers.celery_app import celery_app
from app.workers.queues import QUEUE_INGEST

logger = logging.getLogger("pid.services.upload_complete")

# [LOAD-BEARING] task name consumed by S2-H ingest worker.
INGEST_TASK_NAME = "ingest.process_drawing"

# States at/after Queued — the idempotent set for upload-complete (§1.4 rule 4).
_QUEUED_OR_LATER = frozenset(
    {"Queued", "Scanning", "Processing", "Complete", "Under_Review", "Failed", "Scan_Failed"}
)

_TEAM_ROLES = ("team_member", "team_admin")


@dataclass(frozen=True)
class UploadCompleteResult:
    """HTTP-facing outcome of :func:`complete_upload`."""

    http_status: int
    enqueued: bool
    idempotent: bool = False
    limit_reached: bool = False


def _resolve_subscription(user: CurrentUser, db: Session) -> Optional[Subscription]:
    """The caller's governing subscription — team-scoped for team roles, else
    user-scoped. Returns ``None`` when no subscription row exists."""
    if user.role in _TEAM_ROLES and user.team_id is not None:
        stmt = select(Subscription).where(Subscription.team_id == user.team_id)
    else:
        stmt = select(Subscription).where(Subscription.user_id == user.id)
    return db.scalars(stmt.limit(1)).first()


def _monthly_limit(subscription: Optional[Subscription], db: Session) -> Optional[int]:
    """The tier's ``monthly_drawing_limit`` (``None`` == unlimited).

    A missing subscription falls back to the free-tier limit so an
    unprovisioned account cannot bypass the cap.
    """
    if subscription is None:
        return free_tier_counter.FREE_TIER_MONTHLY_LIMIT
    tier = db.get(Tier, subscription.tier_id)
    if tier is None:
        return free_tier_counter.FREE_TIER_MONTHLY_LIMIT
    return tier.monthly_drawing_limit


def _emit_safe(emit, *args) -> None:
    """Fire an analytics emitter, never letting a failure surface to the caller
    (US-010 AC-6). The emitters already swallow internally; this is belt-and-
    braces against a misbehaving double/override."""
    try:
        emit(*args)
    except Exception:  # noqa: BLE001 — analytics must never break the request
        logger.warning("analytics emit failed (suppressed)", exc_info=True)


def _enqueue_ingest(drawing: Drawing, stored_file: StoredFile, user_id: str) -> None:
    """Send the ingest job to the persistent ``ingest`` Celery queue (§1.4 rule
    14). ``user_id`` is mandatory and set here at enqueue time (§1.4 rule 5)."""
    celery_app.send_task(
        INGEST_TASK_NAME,
        kwargs={
            "drawing_id": str(drawing.id),
            "user_id": user_id,
            "stored_file_id": str(stored_file.id),
            "storage_reference": stored_file.object_key,
        },
        queue=QUEUE_INGEST,
    )


async def complete_upload(
    user: CurrentUser,
    drawing: Drawing,
    db: Session,
    redis: Any,
) -> UploadCompleteResult:
    """Idempotent upload-complete handler. See module docstring for ordering."""
    # Idempotency: already Queued or later → no enqueue, no analytics, 200.
    if drawing.processing_state in _QUEUED_OR_LATER:
        return UploadCompleteResult(http_status=200, enqueued=False, idempotent=True)

    stored_file = (
        db.get(StoredFile, drawing.stored_file_id) if drawing.stored_file_id else None
    )

    subscription = _resolve_subscription(user, db)
    limit = _monthly_limit(subscription, db)

    # Free-tier gate — increment at enqueue time (§1.4 rule 8). ``None`` limit ==
    # pro/team, which bypass the check entirely (US-018 AC-3).
    if limit is not None:
        result = await free_tier_counter.check_and_increment(
            str(user.id), db, redis, limit=limit
        )
        if not result.allowed:
            subscription_id = str(subscription.id) if subscription else ""
            # Fire before returning (and before any upgrade prompt) — US-010 AC-4.
            _emit_safe(
                emit_free_limit_reached, str(user.id), str(drawing.id), subscription_id
            )
            return UploadCompleteResult(
                http_status=402, enqueued=False, limit_reached=True
            )

    # Pending -> Queued (+ audit) in one transaction, then commit BEFORE dispatch.
    transition_drawing(drawing, "Queued", db, audit_user_id=str(user.id))
    db.commit()

    if stored_file is not None:
        _enqueue_ingest(drawing, stored_file, str(user.id))
    else:  # pragma: no cover — a Pending drawing always has a StoredFile
        logger.error(
            "drawing %s has no stored_file; cannot enqueue ingest job", drawing.id
        )

    _emit_safe(emit_drawing_uploaded, str(user.id), str(drawing.id))
    return UploadCompleteResult(http_status=202, enqueued=True)


def retry_drawing(user: CurrentUser, drawing: Drawing, db: Session) -> None:
    """Retry a ``Failed`` drawing: transition ``Failed -> Queued`` and re-enqueue
    the ingest job reusing the existing ``StoredFile`` (US-009 AC-1/AC-3 — no new
    S3 object). The router enforces that only ``Failed`` reaches here (``Complete``
    / ``Scan_Failed`` → ``422``)."""
    stored_file = (
        db.get(StoredFile, drawing.stored_file_id) if drawing.stored_file_id else None
    )
    transition_drawing(drawing, "Queued", db, audit_user_id=str(user.id))
    db.commit()
    if stored_file is not None:
        _enqueue_ingest(drawing, stored_file, str(user.id))


__all__ = [
    "INGEST_TASK_NAME",
    "UploadCompleteResult",
    "complete_upload",
    "retry_drawing",
]
