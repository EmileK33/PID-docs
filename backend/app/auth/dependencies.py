"""FastAPI auth dependencies (§1.3, §1.5).

[LOAD-BEARING] Imported by every Phase 2 router:

* :class:`CurrentUser` — the authenticated-identity model attached to requests.
* :func:`get_current_user` — guards a route with authentication; populates
  ``request.state.user`` and returns the :class:`CurrentUser`.
* :func:`require_role` — restricts a route to one or more roles (used by S2-F,
  S2-E, future teams API).
* :func:`require_permission` / :func:`resolve_ownership` — ownership-aware
  permission gates resolving through ``permissions.check_permission`` (§1.3).

§1.5 status contract: missing/invalid credentials → ``401``; an authenticated
user lacking the required role or ownership → ``403``.

NOTE on sync vs async: ``get_current_user`` is a synchronous dependency because
S0-A's ``get_db`` yields a synchronous ``Session`` and the mandatory
``token_invalidated_at`` lookup is a single synchronous query. FastAPI runs sync
dependencies in a threadpool, so this does not block the event loop. Downstream
routers consume it via ``Depends(...)`` and are unaffected by the call style.
"""
from __future__ import annotations

from typing import Callable, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.middleware import authenticate_request
from app.auth.permissions import Ownership, check_permission
from app.db.session import get_db
from app.schemas.contracts import UserRole


class CurrentUser(BaseModel):
    """Authenticated identity attached to ``request.state.user`` and returned by
    :func:`get_current_user`. Field set is fixed by the handoff contract."""

    id: UUID
    email: str
    role: UserRole
    team_id: Optional[UUID] = None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> CurrentUser:
    """Authenticate the request and return the :class:`CurrentUser`.

    Raises ``401`` when the token is missing, malformed, expired, has the wrong
    issuer/audience, uses a disallowed algorithm, was issued before
    ``token_invalidated_at``, or belongs to a soft-deleted / unknown user. On
    success ``request.state.user`` is populated.
    """
    identity = authenticate_request(request, db)
    user = CurrentUser(
        id=identity["id"],
        email=identity["email"],
        role=identity["role"],
        team_id=identity["team_id"],
    )
    request.state.user = user
    return user


def require_role(*roles: UserRole) -> Callable[..., CurrentUser]:
    """Dependency factory restricting a route to ``roles``.

    Returns ``403`` for an authenticated user whose role is not in ``roles``
    (``401`` is still raised first if the request is unauthenticated).
    """

    allowed = set(roles)

    def _require_role(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return user

    return _require_role


def resolve_ownership(
    user: CurrentUser,
    owner_user_id: Optional[UUID],
    owner_team_id: Optional[UUID],
) -> Optional[Ownership]:
    """Classify ``user``'s relationship to a resource as ``"own"``, ``"team"``
    or ``None``.

    A direct owner match takes precedence over a team match. Supports resources
    owned by an individual (``owner_user_id``) and team-owned resources
    (``owner_team_id``) per the spec's ownership-helper requirement.
    """
    if owner_user_id is not None and owner_user_id == user.id:
        return "own"
    if (
        owner_team_id is not None
        and user.team_id is not None
        and owner_team_id == user.team_id
    ):
        return "team"
    return None


# A resolver maps the incoming request to the target resource's owner fields:
# ``(owner_user_id, owner_team_id)``. Phase 2 routers supply a resolver that
# loads the resource (e.g. by path param) and returns its ownership columns.
ResourceOwnerResolver = Callable[[Request], tuple[Optional[UUID], Optional[UUID]]]


def require_permission(
    action: str,
    resolver: ResourceOwnerResolver,
) -> Callable[..., CurrentUser]:
    """Dependency factory enforcing ``action`` against the §1.3 matrix for the
    resource identified by ``resolver``.

    ``resolver`` receives the request and returns the resource's
    ``(owner_user_id, owner_team_id)``. Ownership is classified via
    :func:`resolve_ownership` and checked with
    :func:`app.auth.permissions.check_permission`. Returns ``403`` when denied.
    """

    def _require_permission(
        request: Request,
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        owner_user_id, owner_team_id = resolver(request)
        ownership = resolve_ownership(user, owner_user_id, owner_team_id)
        if not check_permission(user.role, action, ownership):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )
        return user

    return _require_permission


__all__ = [
    "CurrentUser",
    "get_current_user",
    "require_role",
    "require_permission",
    "resolve_ownership",
    "ResourceOwnerResolver",
]
