"""GDPR erasure core logic (US-005, §1.4 Rule 11).

This module owns the deterministic ``anonymous_id`` derivation and the idempotent
PII purge for a single user. It is deliberately Celery-agnostic — every function
takes a plain SQLAlchemy ``Session`` so it can be unit-tested with the S0-B
integration harness ``db_session`` fixture and reused directly by S4-A's E2E test.

Two load-bearing invariants from §1.4 Rule 11 ("anonymous_id written before any
records updated"):

1. ``anonymous_id`` is computed as ``HMAC-SHA256(user_id || HMAC_SERVER_SECRET)``
   and is **committed in its own transaction** before any PII field is touched.
2. Every subsequent retry **reads** ``USER.anonymous_id`` from the row and never
   recomputes the HMAC. Re-running after a full erase is a safe no-op.

``HMAC_SERVER_SECRET`` is REQUIRED (§1.12 — "Refuse to start" if absent). Importing
this module validates that the secret is configured and raises ``EnvironmentError``
otherwise (AC-8).
"""
from __future__ import annotations

import hashlib
import hmac
import uuid

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.audit_log import AuditLog
from app.db.models.ml_training_consent import MLTrainingConsent
from app.db.models.user import User

# Non-PII replacement values written during the purge (AC-1).
ERASED_EMAIL_DOMAIN = "erased.invalid"
ERASED_DISPLAY_NAME = "Deleted User"
# The placeholder embeds a 16-char slice of the (already non-PII) anonymous_id so
# every erased user gets a distinct address — preserving USER.email_unique on
# re-runs and across multiple erased users.
ERASED_EMAIL_ID_LEN = 16


def _validate_hmac_secret_configured() -> None:
    """Raise ``EnvironmentError`` if ``HMAC_SERVER_SECRET`` is absent/empty (AC-8).

    ``app.config`` already refuses to start without it, but the worker repeats the
    check explicitly so the failure surfaces as a clear startup-time
    ``EnvironmentError`` at the boundary that depends on the secret.
    """
    if not getattr(settings, "HMAC_SERVER_SECRET", None):
        raise EnvironmentError(
            "HMAC_SERVER_SECRET is absent or empty; the GDPR erasure worker refuses "
            "to start (anonymous_id derivation requires it). See §1.12."
        )


def compute_anonymous_id(user_id: str) -> str:
    """Return ``HMAC-SHA256(user_id || HMAC_SERVER_SECRET)`` as a hex digest.

    Deterministic for a fixed ``user_id`` + secret (AC-6). HMAC-SHA256 is the
    contractually required algorithm — do not substitute another.
    """
    _validate_hmac_secret_configured()
    return hmac.new(
        settings.HMAC_SERVER_SECRET.encode(),
        str(user_id).encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()


def erased_email(anonymous_id: str) -> str:
    """``erased_{anonymous_id[:16]}@erased.invalid`` — unique, non-PII placeholder."""
    return f"erased_{anonymous_id[:ERASED_EMAIL_ID_LEN]}@{ERASED_EMAIL_DOMAIN}"


def _coerce_uuid(user_id: str | uuid.UUID) -> uuid.UUID:
    """Accept a UUID or its string form; the models key on real ``UUID`` objects."""
    return user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))


def ensure_anonymous_id(user_id: str, db: Session) -> str:
    """Transaction 1 (§1.4 Rule 11): persist ``anonymous_id`` before any purge.

    Idempotency contract:
    * If the row already has an ``anonymous_id``, return it **without recomputing**
      the HMAC (AC-2 / AC-9 retry path).
    * Otherwise compute it, write it, and **commit** so it survives even if the
      subsequent PII purge crashes and the job is retried.

    Returns the persisted ``anonymous_id``.
    """
    user = db.get(User, _coerce_uuid(user_id))
    if user is None:
        raise ValueError(f"User {user_id!r} not found; cannot derive anonymous_id")

    if user.anonymous_id:
        # Retry / partial-run path: read the stored value, never recompute.
        return user.anonymous_id

    anonymous_id = compute_anonymous_id(str(user.id))
    user.anonymous_id = anonymous_id
    # Separate committed transaction — NEVER combined with the PII purge below.
    db.commit()
    return anonymous_id


def purge_user_pii(user_id: str, db: Session) -> None:
    """Idempotently anonymize ``user_id`` per US-005 AC-1.

    Step ordering (load-bearing):
      1. ``ensure_anonymous_id`` writes + commits ``anonymous_id`` (transaction 1).
      2. PII is cleared and related records updated, then committed (transaction 2).

    Safe to call any number of times: a fully-erased user is a no-op (AC-5), and a
    retry after a partial run reads the persisted ``anonymous_id`` (AC-2 / AC-9).
    Does NOT hard-delete the user and does NOT touch ``deleted_at``.
    """
    uid = _coerce_uuid(user_id)

    # --- Transaction 1: anonymous_id (committed before any record is updated) ---
    anonymous_id = ensure_anonymous_id(str(uid), db)

    # --- Transaction 2: PII purge -------------------------------------------
    user = db.get(User, uid)
    if user is None:
        raise ValueError(f"User {user_id!r} not found; cannot purge PII")

    # Overwrite direct PII on the user row. Re-writing identical values on a
    # re-run is harmless (AC-5). The email placeholder is unique per user.
    user.email = erased_email(anonymous_id)
    user.display_name = ERASED_DISPLAY_NAME
    user.password_hash = None

    # audit_log.user_id is nullable — null it across all partitions in one
    # statement (Postgres routes the UPDATE to the right partitions).
    db.execute(
        update(AuditLog).where(AuditLog.user_id == uid).values(user_id=None)
    )

    # ml_training_consent.user_id cannot be nulled (consent_user_or_team CHECK):
    # delete the user-owned consent rows instead.
    db.execute(delete(MLTrainingConsent).where(MLTrainingConsent.user_id == uid))

    # NOTE: user_correction is intentionally untouched — user_correction.user_id is
    # NOT NULL with an FK to user, and the anonymized user row makes the retained
    # UUID non-PII. Modifying it here would be both unnecessary and constraint-unsafe.

    db.commit()


# Validate the secret at import time so the worker refuses to start without it.
_validate_hmac_secret_configured()


__all__ = [
    "compute_anonymous_id",
    "ensure_anonymous_id",
    "purge_user_pii",
    "erased_email",
    "ERASED_EMAIL_DOMAIN",
    "ERASED_DISPLAY_NAME",
]
