"""GDPR erasure Celery tasks (US-005, §1.11 ``gdpr_erasure`` queue).

Two tasks, both routed to the ``gdpr_erasure`` queue via the ``gdpr_erasure.*``
prefix in S1-D's ``task_routes`` (AC-7):

* ``scan_and_dispatch_erasure_jobs`` — Celery **beat** periodic task. Scans for
  users whose ``deleted_at`` is ≥ 30 days in the past and dispatches one
  ``erase_user_pii`` job per user. A beat scan (not a 30-day ETA countdown) is
  used because long-lived ETAs do not reliably survive broker restarts (NFR-7,
  §1.4 Rule 14 — durable persistent queue).
* ``erase_user_pii`` — per-user worker that performs the idempotent anonymize +
  PII purge (see ``anonymizer.purge_user_pii``). Consumed by S2-F's
  ``gdpr_init_service`` (which may also enqueue it directly) and S4-A's E2E test.

Job payload contract with S2-F: ``{"user_id": "<uuid-string>"}``.

Import-time safety: ``app.db.session`` is imported **lazily inside** the task
bodies, never at module top — importing it eagerly builds the engine against the
plain ``postgresql://`` URL and pulls in psycopg2, which fails under the bare
session-tests gate. Models, config and Celery infra import cleanly without a DB
or broker connection.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.workers.base import BaseTask
from app.workers.celery_app import celery_app
from app.workers.gdpr.anonymizer import compute_anonymous_id, purge_user_pii
from app.workers.queues import QUEUE_GDPR

# Importing queues applies the authoritative task_routes table (side effect);
# the explicit reference keeps the dependency visible and the import non-dead.
_ = QUEUE_GDPR

# §1.13 US-005: erasure runs 30 days after deletion is initiated.
ERASURE_DELAY_DAYS = 30

# Task names carry the ``gdpr_erasure.`` prefix so S1-D's task_routes
# (``"gdpr_erasure.*": {"queue": "gdpr_erasure"}``) route them to the right queue.
ERASE_TASK_NAME = "gdpr_erasure.erase_user_pii"
SCAN_TASK_NAME = "gdpr_erasure.scan_and_dispatch_erasure_jobs"


class GDPRErasureJobPayload(TypedDict):
    """Shape of the message S2-F enqueues onto ``gdpr_erasure`` (and we consume)."""

    user_id: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@celery_app.task(base=BaseTask, name=ERASE_TASK_NAME, queue=QUEUE_GDPR)
def erase_user_pii(user_id: str) -> None:
    """Anonymize + purge PII for ``user_id`` (idempotent; safe to retry).

    Opens its own DB session; the real work lives in ``purge_user_pii`` so tests
    and S4-A can drive it directly against a harness session.
    """
    # Lazy import — see module docstring (avoids eager psycopg2 import at load).
    from app.db.session import SessionLocal

    db: Session = SessionLocal()
    try:
        purge_user_pii(user_id, db)
    finally:
        db.close()


@celery_app.task(base=BaseTask, name=SCAN_TASK_NAME, queue=QUEUE_GDPR)
def scan_and_dispatch_erasure_jobs(db: Optional[Session] = None) -> None:
    """Beat task: dispatch ``erase_user_pii`` for every user deleted ≥ 30 days ago.

    Selects users with ``deleted_at IS NOT NULL AND deleted_at < NOW() - 30 days``
    (AC-3 excludes < 30 days; AC-4 excludes ``deleted_at IS NULL``) and enqueues
    one job each onto the durable ``gdpr_erasure`` queue.

    ``db`` is an optional injection point for tests (mirrors the repo's
    ``db=None`` lazy-session convention); beat invokes it with no arguments.
    """
    owns_session = db is None
    if owns_session:
        from app.db.session import SessionLocal  # lazy import (see module docstring)

        db = SessionLocal()
    try:
        cutoff = _utcnow() - timedelta(days=ERASURE_DELAY_DAYS)
        user_ids = (
            db.execute(
                select(User.id).where(
                    User.deleted_at.is_not(None),
                    User.deleted_at < cutoff,
                )
            )
            .scalars()
            .all()
        )
        for user_id in user_ids:
            erase_user_pii.apply_async(args=[str(user_id)])
    finally:
        if owns_session:
            db.close()


__all__ = [
    "erase_user_pii",
    "scan_and_dispatch_erasure_jobs",
    "GDPRErasureJobPayload",
    "ERASURE_DELAY_DAYS",
    "ERASE_TASK_NAME",
    "SCAN_TASK_NAME",
]
