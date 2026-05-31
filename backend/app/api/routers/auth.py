"""Authentication API router (S2-A) — the seven ``/auth`` endpoints.

This is the sole P0 authentication boundary (US-001, US-002). Handlers are thin:
they validate input, delegate to :class:`app.services.auth_service.AuthService` /
:class:`app.services.password_reset.PasswordResetService`, and translate the
service's domain exceptions onto the §1.5 HTTP status contract.

§1.5 contracts enforced here:

* ``logout`` / ``password-reset/request`` / ``password-reset/confirm`` success →
  ``204`` (NEVER ``200``).
* missing/invalid credentials → ``401``.
* brute-force lockout → ``429`` (NOT ``401``) with ``retry_after_seconds``.

Error bodies use the ``{"error": "<machine_code>"}`` shape the frontend (S3-A)
consumes, so handlers return :class:`fastapi.responses.JSONResponse` directly for
error cases rather than ``HTTPException`` (whose body is ``{"detail": ...}``).
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.auth.middleware import get_bearer_token
from app.db.session import get_db
from app.services.auth_service import (
    AccountLinkRequired,
    AccountLocked,
    AccountNotFound,
    AuthService,
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidRefreshToken,
)
from app.services.password_reset import (
    InvalidResetToken,
    PasswordResetService,
    SignOutFailed,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Pragmatic email-shape check. Real complexity/validity is enforced by Supabase
# Auth on signup; this only rejects obviously malformed input with a 400 (rather
# than FastAPI's default 422) per US-001 AC-3.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email or ""))


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class OAuthGoogleRequest(BaseModel):
    supabase_access_token: str
    supabase_refresh_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequestBody(BaseModel):
    email: str


class PasswordResetConfirmBody(BaseModel):
    token: str
    new_password: str


# ---------------------------------------------------------------------------
# US-001: registration
# ---------------------------------------------------------------------------
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if not _valid_email(body.email):
        return JSONResponse(status_code=400, content={"error": "invalid_email"})
    try:
        return await AuthService(db).register(
            body.email, body.password, body.display_name
        )
    except EmailAlreadyRegistered:
        return JSONResponse(
            status_code=409, content={"error": "email_already_registered"}
        )


# ---------------------------------------------------------------------------
# US-002: email/password login
# ---------------------------------------------------------------------------
@router.post("/login")
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    try:
        return await AuthService(db).login(body.email, body.password)
    except AccountLocked as exc:
        return JSONResponse(
            status_code=429,
            content={
                "error": "account_locked",
                "retry_after_seconds": exc.retry_after_seconds,
            },
        )
    except AccountNotFound:
        return JSONResponse(status_code=401, content={"error": "account_not_found"})
    except InvalidCredentials:
        return JSONResponse(status_code=401, content={"error": "invalid_credentials"})


# ---------------------------------------------------------------------------
# US-002: Google OAuth
# ---------------------------------------------------------------------------
@router.post("/oauth/google")
async def oauth_google(body: OAuthGoogleRequest, db: Session = Depends(get_db)):
    try:
        return await AuthService(db).oauth_google(
            body.supabase_access_token, body.supabase_refresh_token
        )
    except AccountLinkRequired as exc:
        return JSONResponse(
            status_code=409,
            content={"error": "account_link_required", "email": exc.email},
        )
    except InvalidCredentials:
        return JSONResponse(status_code=401, content={"error": "invalid_token"})


# ---------------------------------------------------------------------------
# US-002: token refresh
# ---------------------------------------------------------------------------
@router.post("/refresh")
async def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        return await AuthService(db).refresh(body.refresh_token)
    except InvalidRefreshToken:
        return JSONResponse(
            status_code=401, content={"error": "invalid_or_expired_refresh_token"}
        )


# ---------------------------------------------------------------------------
# US-002: logout (must return 204, never 200)
# ---------------------------------------------------------------------------
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    access_token = get_bearer_token(request) or ""
    await AuthService(db).logout(access_token, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# US-002: password reset (request + confirm; both 204, never 200)
# ---------------------------------------------------------------------------
@router.post("/password-reset/request", status_code=status.HTTP_204_NO_CONTENT)
async def password_reset_request(
    body: PasswordResetRequestBody, db: Session = Depends(get_db)
):
    await PasswordResetService(db).request_reset(body.email)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def password_reset_confirm(
    body: PasswordResetConfirmBody, db: Session = Depends(get_db)
):
    try:
        await PasswordResetService(db).confirm_reset(body.token, body.new_password)
    except InvalidResetToken:
        return JSONResponse(
            status_code=400, content={"error": "invalid_or_expired_reset_token"}
        )
    except SignOutFailed:
        return JSONResponse(
            status_code=500, content={"error": "session_revocation_failed"}
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
