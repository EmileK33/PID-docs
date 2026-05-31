"""GDPR account-deletion initiation service (S2-F, US-005).

Initiates the right-to-erasure pipeline. This session only *initiates*: it
soft-deletes the user, revokes sessions, invalidates cached feature flags, and
enqueues the long-running erasure job onto Celery's ``gdpr_erasure`` queue. The
actual PII purge / anonymisation runs in S2-L's worker; the only coupling is the
queue message contract (task name + queue + args) defined below.

Ordering guarantees (§1.4 rules 11, 12, 14 — applied to deletion):

* ``deleted_at`` and ``token_invalidated_at`` are set in a single DB transaction
  (both committed or neither) — analogous to the password-reset atomicity rule.
* Supabase ``admin_sign_out``, the Redis cache invalidation, and the Celery
  enqueue all happen **after** the transaction commits. Enqueuing before commit
  would risk a worker job for a user whose soft-delete never persisted.
* The erasure job is enqueued via the persistent Celery/Redis broker (never an
  in-memory structure) so it survives a server restart (NFR-7).

Failure policy: once the soft-delete is committed the endpoint must return 204.
A Supabase sign-out failure, a Redis failure, or a Celery broker failure are all
logged and swallowed — the committed ``deleted_at`` / ``token_invalidated_at``
are the durable enforcement guard (the auth middleware rejects the user on the
next request regardless).

NOTE on the session type / async: the merged infra is synchronous SQLAlchemy,
but the Supabase admin call and the Redis cache helper are async coroutines, so
this initiator is ``async`` and awaits them. ``send_task`` is synchronous.
"""
from __future__ import annotations

import datetime
import logging
import uuid

from sqlalchemy.orm import Session

from app.auth import supabase_client
from app.config import settings
from app.db.models.user import User
from app.redis import cache
from app.workers.celery_app import celery_app

logger = logging.getLogger("pid.services.gdpr_init")

# --- Queue message contract with S2-L (§1.11, build brief) — exact strings. ---
GDPR_ERASURE_TASK_NAME = "backend.app.workers.gdpr.tasks.gdpr_erasure_task"
GDPR_ERASURE_QUEUE = "gdpr_erasure"

# §US-005 AC-5: 30 days in production; immediate (0) everywhere else for testability.
_PRODUCTION_COUNTDOWN_SECONDS = 30 * 24 * 3600  # 2,592,000


def _coerce_uuid(value: "str | uuid.UUID") -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _erasure_countdown() -> int:
    """0 outside production (immediate, testable); 30 days in production."""
    return (
        _PRODUCTION_COUNTDOWN_SECONDS
        if settings.ENVIRONMENT == "production"
        else 0
    )


async def initiate_account_deletion(user_id: str, db: Session) -> None:
    """Initiate GDPR erasure for ``user_id``.

    Idempotent: if the user is already soft-deleted (or unknown) this is a no-op
    and the erasure job is NOT re-enqueued (US-005 AC-7 — enqueued exactly once
    per account).
    """
    uid = _coerce_uuid(user_id)
    user = db.get(User, uid)
    if user is None:
        # Unknown user — nothing to delete. The endpoint still returns 204.
        return
    if user.deleted_at is not None:
        # Already soft-deleted: do not re-commit timestamps or re-enqueue.
        return

    now = datetime.datetime.now(datetime.timezone.utc)
    # Atomic: both timestamps land in a single COMMIT (US-005 AC-2, TECHNICAL).
    user.deleted_at = now
    user.token_invalidated_at = now
    db.commit()

    # --- Post-commit side effects (never inside the transaction block) -------

    # Revoke all Supabase sessions. A failure here must not block the 204 — the
    # committed token_invalidated_at is the fallback guard (US-005 AC-2 / AC-8).
    try:
        await supabase_client.admin_sign_out(user.id)
    except Exception:  # noqa: BLE001 - log-and-continue is the documented policy
        logger.error(
            "Supabase admin sign_out failed for user %s; "
            "token_invalidated_at is the fallback guard",
            user.id,
            exc_info=True,
        )

    # Drop stale subscription feature-gate cache (§1.11). Redis is fail-soft: a
    # stale entry expires within its 5-minute TTL, so only warn.
    try:
        await cache.invalidate_subscription_flags(str(user.id))
    except Exception:  # noqa: BLE001
        logger.warning(
            "invalidate_subscription_flags failed for user %s; "
            "stale flags expire within the 5-minute TTL",
            user.id,
            exc_info=True,
        )

    # Enqueue the persistent erasure job. A broker failure is logged and
    # swallowed so the (already committed) soft-delete stands (US-005 AC-8); a
    # manual re-enqueue is a P1 concern.
    try:
        celery_app.send_task(
            GDPR_ERASURE_TASK_NAME,
            args=[str(user.id)],
            queue=GDPR_ERASURE_QUEUE,
            countdown=_erasure_countdown(),
        )
    except Exception:  # noqa: BLE001
        logger.error(
            "GDPR erasure enqueue failed for user %s; soft-delete remains "
            "committed (manual re-enqueue required — P1)",
            user.id,
            exc_info=True,
        )


__all__ = [
    "initiate_account_deletion",
    "GDPR_ERASURE_TASK_NAME",
    "GDPR_ERASURE_QUEUE",
]
