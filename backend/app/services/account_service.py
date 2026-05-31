"""Account-profile read/update service (S2-F, US-004).

Pure DB helpers over the S1-A ``User`` model. The router owns the transaction
boundary (commit) and the HTTP shaping; this module never imports FastAPI or
touches the response schemas.

NOTE on the session type: see ``consent_service`` — the merged infrastructure is
synchronous, so these helpers take a SQLAlchemy ``Session``.
"""
from __future__ import annotations

import uuid
from typing import Mapping

from sqlalchemy.orm import Session

from app.db.models.user import User


def _coerce_uuid(value: "str | uuid.UUID") -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def get_user(user_id: "str | uuid.UUID", db: Session) -> "User | None":
    """Return the ``User`` row for ``user_id`` (the authenticated identity only
    carries id/email/role/team_id, so the full row is loaded here)."""
    return db.get(User, _coerce_uuid(user_id))


def apply_profile_update(user: User, fields: Mapping[str, object]) -> User:
    """Apply an allowed-field profile patch to ``user`` in place.

    ``fields`` is the request body's *set* fields only (``model_dump(
    exclude_unset=True)``), so an empty mapping is a valid no-op (US-004 AC-6)
    and unknown fields never reach here (the request schema drops them via
    ``extra='ignore'``, US-004 AC-7).

    Changing ``email`` clears ``email_verified`` in the same in-memory mutation
    (flushed in one ``UPDATE`` by the caller) so the row is never left with a
    new address still marked verified (US-004 AC-4).
    """
    if "display_name" in fields and fields["display_name"] is not None:
        user.display_name = str(fields["display_name"])

    if "email" in fields and fields["email"] is not None:
        user.email = str(fields["email"])
        user.email_verified = False

    return user


__all__ = ["get_user", "apply_profile_update"]
