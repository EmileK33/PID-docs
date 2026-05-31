"""Account, consent & GDPR-init HTTP endpoints (S2-F, US-004 / US-005).

Routes (mounted at prefix ``/account``):

* ``GET    /account``         — profile retrieval (US-004 AC-1/2)
* ``PATCH  /account``         — profile update: display_name / email (AC-3..8)
* ``GET    /account/consent`` — effective ML-training consent (AC-9..13)
* ``PATCH  /account/consent`` — upsert personal consent (AC-14..17)
* ``DELETE /account``         — GDPR erasure initiation (US-005)

The handlers are thin: authentication is delegated to S1-B's
``get_current_user`` (which returns id/email/role/team_id only, so the full row
is loaded here), persistence to the S2-F services, and transaction commit to the
handlers. No analytics events are fired from this router (§1.10).

The handlers are ``async`` so the deletion path can ``await`` the async Supabase
sign-out and Redis cache helpers; the synchronous ``get_db`` session composes
fine as a dependency of an async route.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.db.session import get_db
from app.services import account_service, consent_service, gdpr_init_service

router = APIRouter(prefix="/account", tags=["account"])


# ---------------------------------------------------------------------------
# Schemas (exported shapes consumed by S3-E frontend)
# ---------------------------------------------------------------------------
class AccountProfileResponse(BaseModel):
    """Profile payload returned by ``GET``/``PATCH`` ``/account`` (US-004 AC-1)."""

    id: str
    email: str
    display_name: str
    email_verified: bool
    role: str
    team_id: Optional[str] = None


class PatchAccountRequest(BaseModel):
    """Profile patch body. Only ``display_name`` and ``email`` are mutable;
    every other field (``role``, ``team_id``, ``deleted_at``, ...) is silently
    dropped (``extra='ignore'``) so it can never escalate privilege (AC-7)."""

    model_config = ConfigDict(extra="ignore")

    display_name: Optional[str] = None
    email: Optional[EmailStr] = None


class ConsentResponse(BaseModel):
    """Effective consent payload. ``source`` is computed server-side only
    (§1.4 rule 7) — never accepted from the client."""

    opted_in: bool
    source: Literal["user", "team"]


class PatchConsentRequest(BaseModel):
    """Consent patch body. Only ``opted_in`` is accepted; ``source`` / any other
    field is silently dropped so the resolution stays server-authoritative
    (AC-17)."""

    model_config = ConfigDict(extra="ignore")

    opted_in: bool


def _profile(user) -> AccountProfileResponse:
    return AccountProfileResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        email_verified=user.email_verified,
        role=user.role,
        team_id=str(user.team_id) if user.team_id is not None else None,
    )


# ---------------------------------------------------------------------------
# Profile (US-004)
# ---------------------------------------------------------------------------
@router.get("", response_model=AccountProfileResponse)
async def get_account(
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountProfileResponse:
    """Return the authenticated user's current profile (US-004 AC-1)."""
    user = account_service.get_user(current.id, db)
    return _profile(user)


@router.patch("", response_model=AccountProfileResponse)
async def patch_account(
    body: PatchAccountRequest,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountProfileResponse:
    """Update display_name and/or email. Empty body is a valid no-op (AC-6);
    changing email clears ``email_verified`` in the same transaction (AC-4)."""
    user = account_service.get_user(current.id, db)
    # exclude_unset → only fields the client actually sent; unknown fields were
    # already dropped by the schema's extra='ignore'.
    account_service.apply_profile_update(user, body.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(user)
    return _profile(user)


# ---------------------------------------------------------------------------
# Consent (US-004)
# ---------------------------------------------------------------------------
@router.get("/consent", response_model=ConsentResponse)
async def get_consent(
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConsentResponse:
    """Return the effective consent + its server-computed ``source``
    (AC-9..12). Team consent takes precedence over the personal record."""
    user = account_service.get_user(current.id, db)
    opted_in, source = consent_service.resolve_consent_with_source(user, db)
    return ConsentResponse(opted_in=opted_in, source=source)


@router.patch("/consent", response_model=ConsentResponse)
async def patch_consent(
    body: PatchConsentRequest,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConsentResponse:
    """Create or update the caller's personal consent record (AC-14/15), then
    return the re-resolved effective consent."""
    user = account_service.get_user(current.id, db)
    consent_service.set_user_consent(user.id, db, body.opted_in)
    db.commit()
    opted_in, source = consent_service.resolve_consent_with_source(user, db)
    return ConsentResponse(opted_in=opted_in, source=source)


# ---------------------------------------------------------------------------
# GDPR erasure initiation (US-005)
# ---------------------------------------------------------------------------
@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Initiate GDPR erasure. Returns 204 with no body (US-005 AC-1).

    Idempotent: if the account is already soft-deleted, returns 204 immediately
    without any DB write, Supabase call, cache invalidation, or re-enqueue
    (AC-7). The 204 stands even if the Celery broker is unavailable (AC-8).
    """
    user = account_service.get_user(current.id, db)
    if user is not None and user.deleted_at is not None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    await gdpr_init_service.initiate_account_deletion(str(current.id), db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = [
    "router",
    "AccountProfileResponse",
    "PatchAccountRequest",
    "ConsentResponse",
    "PatchConsentRequest",
]
