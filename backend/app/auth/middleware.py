"""Authentication middleware core (§1.4 Rule #12, §1.5, US-002, US-005).

This module holds the request-authentication logic shared by the FastAPI
dependencies. Resolving an authenticated identity is a two-stage process:

1. **Token stage** (:func:`app.auth.jwt_verifier.verify_token`) — RS256
   signature, ``exp``, ``iss``, ``aud``.
2. **User-state stage** (:func:`authenticate_request`) — a single indexed lookup
   on ``"user".id`` that enforces the *non-cacheable* checks mandated on every
   authenticated request:

   * ``deleted_at IS NOT NULL`` → reject (soft-deleted users, US-005).
   * ``token_invalidated_at`` set AND ``iat < token_invalidated_at`` → reject
     (Rule #12 — password reset / forced sign-out invalidates older tokens).

The ``"user"`` row is read with raw SQL against the ``"user"`` table rather than
importing the SQLAlchemy model: S1-A (models) is a parallel sibling that may not
have merged yet, so this session must not depend on it.

Any failure raises :class:`fastapi.HTTPException` with status ``401`` per the
§1.5 contract — unauthenticated / invalid-credential conditions never leak
detail to the client.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, TypedDict
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.jwt_verifier import TokenVerificationError, verify_token

# Mandatory, non-cacheable per-request user-state lookup (single indexed query).
_USER_SECURITY_SQL = text(
    'SELECT token_invalidated_at, deleted_at, team_id, role '
    'FROM "user" WHERE id = :id'
)

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


class ResolvedIdentity(TypedDict):
    """Identity fields resolved from the verified token + the ``"user"`` row."""

    id: UUID
    email: str
    role: str
    team_id: Optional[UUID]


def get_bearer_token(request: Request) -> Optional[str]:
    """Extract the bearer token from the ``Authorization`` header, or ``None``.

    Returns ``None`` when the header is missing or is not a well-formed
    ``Bearer <token>`` pair — the caller raises 401.
    """
    header = request.headers.get("Authorization")
    if not header:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _to_aware_utc(value: datetime) -> datetime:
    """Normalize a DB timestamp to a tz-aware UTC datetime for comparison."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def authenticate_request(request: Request, db: Session) -> ResolvedIdentity:
    """Resolve and validate the caller's identity, or raise ``401``.

    Performs token verification, then the mandatory ``token_invalidated_at`` /
    ``deleted_at`` user-state checks against the ``"user"`` table.
    """
    token = get_bearer_token(request)
    if token is None:
        raise _UNAUTHENTICATED

    try:
        claims = verify_token(token)
    except TokenVerificationError:
        raise _UNAUTHENTICATED

    sub = claims.get("sub")
    iat = claims.get("iat")
    if not sub or iat is None:
        raise _UNAUTHENTICATED

    try:
        user_id = UUID(str(sub))
    except (ValueError, TypeError):
        raise _UNAUTHENTICATED

    row = db.execute(_USER_SECURITY_SQL, {"id": user_id}).first()
    if row is None:
        # No such user — treat as unauthenticated, identical to a bad token.
        raise _UNAUTHENTICATED

    token_invalidated_at, deleted_at, team_id, role = row

    # Soft-deleted users are rejected identically to an invalid token (US-005).
    if deleted_at is not None:
        raise _UNAUTHENTICATED

    # Rule #12: tokens issued before token_invalidated_at are rejected (US-005).
    if token_invalidated_at is not None:
        token_issued_at = datetime.fromtimestamp(int(iat), tz=timezone.utc)
        if token_issued_at < _to_aware_utc(token_invalidated_at):
            raise _UNAUTHENTICATED

    return ResolvedIdentity(
        id=user_id,
        email=str(claims.get("email", "")),
        role=str(role),
        team_id=team_id if team_id is None else UUID(str(team_id)),
    )


class AuthMiddleware(BaseHTTPMiddleware):
    """Optional ASGI middleware that opportunistically populates
    ``request.state.user``.

    It NEVER short-circuits the request: routes opt into enforcement via
    ``Depends(get_current_user)``. When a valid token is present the resolved
    identity is attached; otherwise ``request.state.user`` is ``None``. A
    short-lived session from ``SessionLocal`` is used for the user-state lookup.

    Downstream apps may install this so non-dependency code (e.g. logging) can
    read ``request.state.user`` without re-verifying. The FastAPI dependencies do
    not require it.
    """

    async def dispatch(self, request: Request, call_next):
        request.state.user = None
        if get_bearer_token(request) is not None:
            # Imported lazily to avoid importing the DB engine at module load
            # and to keep this middleware optional.
            from app.db.session import SessionLocal

            db = SessionLocal()
            try:
                request.state.user = authenticate_request(request, db)
            except HTTPException:
                request.state.user = None
            finally:
                db.close()
        return await call_next(request)


__all__ = [
    "authenticate_request",
    "get_bearer_token",
    "AuthMiddleware",
    "ResolvedIdentity",
]
