"""ML training-consent resolution + write service (S2-F, US-004).

[LOAD-BEARING] :func:`resolve_training_consent` is imported by S2-C's
``correction_service`` at correction-creation time to snapshot the resolved
``training_consent`` value into ``user_correction.training_consent`` (§1.4 rule
6). Its signature ``(user_id: str, db: Session) -> bool`` must not change after
merge.

Resolution is evaluated **server-side only** (§1.4 rule 7) and follows the exact
precedence ordered in the build brief:

1. Load the ``user`` row; read ``user.team_id``.
2. If ``team_id`` is set: look up ``ml_training_consent`` for that team; if a
   record exists, return its ``opted_in`` — team consent wins unconditionally.
3. Otherwise fall back to the user's personal ``ml_training_consent`` record.
4. Default to ``False`` (not consented) when neither record exists.

NOTE on the session type: the build brief's contract names ``AsyncSession``, but
the merged S1-A/S1-B infrastructure is synchronous (``app.db.session.get_db``
yields a SQLAlchemy ``Session``; ``get_current_user`` is a sync dependency).
This service therefore takes a sync ``Session`` so it composes with the actual
merged code. S2-C consumes it against the same sync session.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.ml_training_consent import MLTrainingConsent
from app.db.models.user import User

# The ``source`` value reported to the client / snapshotted server-side.
ConsentSource = str  # Literal["user", "team"] at the schema boundary.


def _coerce_uuid(value: "str | uuid.UUID") -> uuid.UUID:
    """Accept a str or UUID and return a UUID (the contract param is ``str``)."""
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _resolve(user: User, db: Session) -> Tuple[bool, ConsentSource]:
    """Resolve ``(opted_in, source)`` for ``user`` per the §1.4 precedence.

    Team consent (step 2) is evaluated before the personal record (step 3) so a
    team-level opt-in cannot be overridden by a stale personal record.
    """
    if user.team_id is not None:
        team_record = (
            db.execute(
                select(MLTrainingConsent)
                .where(MLTrainingConsent.team_id == user.team_id)
                .limit(1)
            )
            .scalars()
            .first()
        )
        if team_record is not None:
            return bool(team_record.opted_in), "team"

    user_record = (
        db.execute(
            select(MLTrainingConsent)
            .where(MLTrainingConsent.user_id == user.id)
            .limit(1)
        )
        .scalars()
        .first()
    )
    if user_record is not None:
        return bool(user_record.opted_in), "user"

    # Default: not consented. Source is "user" — a personal (absent) record.
    return False, "user"


def resolve_consent_with_source(user: User, db: Session) -> Tuple[bool, ConsentSource]:
    """Public helper used by ``GET /account/consent`` — returns the effective
    consent flag plus its computed ``source`` (``"team"`` or ``"user"``)."""
    return _resolve(user, db)


def resolve_training_consent(user_id: str, db: Session) -> bool:
    """[LOAD-BEARING — S2-C] Return the effective ML-training consent for a user.

    Loads the user, applies the team-before-user precedence, and returns the
    resolved ``opted_in`` boolean. Returns ``False`` for an unknown user or when
    no consent record exists anywhere (default: not consented).
    """
    user = db.get(User, _coerce_uuid(user_id))
    if user is None:
        return False
    opted_in, _ = _resolve(user, db)
    return opted_in


def set_user_consent(user_id: str, db: Session, opted_in: bool) -> MLTrainingConsent:
    """Create or update the caller's personal ``ml_training_consent`` record.

    The ``ml_training_consent`` table has no unique index on ``user_id`` (§1.2),
    so a bare ``INSERT ... ON CONFLICT`` is not available. Instead we use the
    read-then-write pattern with a row lock (``SELECT ... FOR UPDATE``) so two
    concurrent requests cannot both insert: the first locks/creates the row, the
    second blocks then updates it. Exactly one record per user is maintained.

    The row is flushed (not committed) — the caller owns the transaction
    boundary so the write composes with the request-scoped session.
    """
    uid = _coerce_uuid(user_id)
    now = datetime.datetime.now(datetime.timezone.utc)

    record = (
        db.execute(
            select(MLTrainingConsent)
            .where(MLTrainingConsent.user_id == uid)
            .with_for_update()
        )
        .scalars()
        .first()
    )
    if record is None:
        record = MLTrainingConsent(user_id=uid, opted_in=opted_in, updated_at=now)
        db.add(record)
    else:
        record.opted_in = opted_in
        record.updated_at = now

    db.flush()
    return record


# ---------------------------------------------------------------------------
# P1 STUBS — team-level consent WRITE surface (set/update via /teams/{id}/consent)
# ---------------------------------------------------------------------------
# Reading team consent for resolution is implemented above (P0) — see
# ``_resolve``. Only the team-admin-facing write operations are deferred to P1.

def set_team_consent(*args, **kwargs):  # noqa: ANN002, ANN003, ARG001
    """# P1 STUB — not implemented.

    Team-admin write of team-level ML-training consent (``PATCH
    /teams/{id}/consent``). Deferred to the P1 team-workspace feature; the
    stub router currently returns 501 for that path.
    """
    raise NotImplementedError(
        "P1 STUB — team-level consent write is not implemented in P0"
    )


def get_team_consent(*args, **kwargs):  # noqa: ANN002, ANN003, ARG001
    """# P1 STUB — not implemented.

    Team-admin read of the raw team consent record for the management UI
    (``GET /teams/{id}/consent``). Resolution-time team-consent reads are P0
    and live in ``_resolve``; this admin-facing surface is P1.
    """
    raise NotImplementedError(
        "P1 STUB — team-level consent management read is not implemented in P0"
    )


__all__ = [
    "resolve_training_consent",
    "resolve_consent_with_source",
    "set_user_consent",
    "set_team_consent",
    "get_team_consent",
]
