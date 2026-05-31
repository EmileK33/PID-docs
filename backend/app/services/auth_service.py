"""Authentication service layer (S2-A — US-001, US-002).

This module is the single P0 authentication boundary's business logic. The
FastAPI handlers in ``app.api.routers.auth`` are thin: they parse the request,
delegate to :class:`AuthService`, and map the domain exceptions raised here onto
the §1.5 HTTP status contract.

Design notes / cross-session contracts
---------------------------------------
* **Supabase Auth is reached over GoTrue's REST API** via the module-level
  ``supabase_*`` coroutines below — consistent with S1-B's
  ``supabase_client.py`` (raw ``httpx`` against the self-hosted GoTrue service),
  since no Supabase Python SDK client is provided. Tests patch these coroutines.
* **Session revocation uses S1-B's** :func:`app.auth.supabase_client.admin_sign_out`
  exclusively (Rule #12) — see :mod:`app.services.password_reset`.
* **Notification email is dispatched onto the persistent Celery ``notification``
  queue** via :func:`enqueue_notification` (Rule #14 — never in-memory). The task
  payload shapes are a load-bearing contract consumed by S2-M; see
  :data:`SEND_VERIFICATION_EMAIL` / :data:`SEND_PASSWORD_RESET_EMAIL`.
* **``user.password_hash``** is a *flag*, never a real hash: the sentinel
  :data:`SUPABASE_MANAGED_SENTINEL` marks a password-based account (Supabase owns
  the credential); OAuth accounts leave it ``NULL``. The account-link conflict
  check in :meth:`AuthService.oauth_google` relies on this convention.
* **``user.id`` IS the Supabase Auth user id.** Registration persists the row
  under the Supabase-issued UUID, and the OAuth flow reads the ``sub`` claim, so
  ``admin_sign_out(user_id)`` and the ``token_invalidated_at`` middleware check
  (S1-B) line up without an extra lookup table.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import brute_force
from app.auth.jwt_verifier import TokenVerificationError, verify_token
from app.config import settings
from app.db.models.audit_log import AuditLog
from app.db.models.subscription import Subscription
from app.db.models.user import User

logger = logging.getLogger("pid.auth.service")

# ``password_hash`` sentinel marking a password-based (non-OAuth) account.
SUPABASE_MANAGED_SENTINEL = "<SUPABASE_MANAGED>"

# New registrations always land on the free tier in 'Active' billing state.
FREE_TIER_ID = "free"
DEFAULT_ROLE = "user"
ACTIVE_BILLING_STATE = "Active"

# Task names (the ``task_name`` field of the §Mocking-contract payloads).
SEND_VERIFICATION_EMAIL = "send_verification_email"
SEND_PASSWORD_RESET_EMAIL = "send_password_reset_email"

# GoTrue REST calls sit on the login / register hot path.
_GOTRUE_TIMEOUT_SECONDS = 10.0


# ===========================================================================
# Domain exceptions — mapped to §1.5 status codes by the router. The router is
# the ONLY place these become HTTP responses.
# ===========================================================================
class AuthError(Exception):
    """Base class for auth-domain failures."""


class EmailAlreadyRegistered(AuthError):
    """Registration with an email that already exists → 409."""


class InvalidCredentials(AuthError):
    """Login with bad credentials, or an invalid OAuth/access token → 401."""


class AccountLocked(AuthError):
    """Brute-force lockout active → 429 with ``retry_after_seconds``."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("account_locked")
        self.retry_after_seconds = retry_after_seconds


class AccountNotFound(AuthError):
    """Credentials verified but the app user is missing / soft-deleted → 401."""


class AccountLinkRequired(AuthError):
    """OAuth email collides with an existing password account → 409.

    Never a silent merge (§1.7). Carries the email for the link prompt.
    """

    def __init__(self, email: str) -> None:
        super().__init__("account_link_required")
        self.email = email


class InvalidRefreshToken(AuthError):
    """Refresh token expired or tampered → 401."""


class InvalidResetToken(AuthError):
    """Password-reset token expired or invalid → 400."""


class SignOutFailed(AuthError):
    """Supabase ``admin.signOut`` failed during password reset → 500.

    Raised BEFORE the ``token_invalidated_at`` DB write so that write never
    happens when revocation did not (Rule #12).
    """


class SupabaseAuthError(Exception):
    """Low-level failure from a GoTrue REST call.

    ``status_code`` / ``code`` carry GoTrue's response detail so callers can
    distinguish e.g. a duplicate-email signup from a generic failure.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        code: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


# ===========================================================================
# GoTrue REST wrappers. Patched wholesale in tests (no live Supabase needed).
# ===========================================================================
def _gotrue_client() -> httpx.AsyncClient:
    """Build an httpx client for the self-hosted GoTrue service.

    Mirrors S1-B's ``supabase_client._build_client`` so tests can inject an
    ``httpx.MockTransport`` by patching this factory if they exercise the real
    call path; most tests patch the ``supabase_*`` coroutines directly.
    """
    return httpx.AsyncClient(
        base_url=settings.SUPABASE_URL.rstrip("/"),
        headers={
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Content-Type": "application/json",
        },
        timeout=_GOTRUE_TIMEOUT_SECONDS,
    )


def _raise_for_gotrue(response: httpx.Response) -> dict:
    """Return JSON for a 2xx GoTrue response, else raise ``SupabaseAuthError``."""
    if 200 <= response.status_code < 300:
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()
    code: Optional[str] = None
    try:
        body = response.json()
        code = body.get("error_code") or body.get("code") or body.get("error")
    except Exception:  # noqa: BLE001 - non-JSON error body
        body = response.text
    raise SupabaseAuthError(
        f"GoTrue call failed: HTTP {response.status_code} {body!r}",
        status_code=response.status_code,
        code=code,
    )


async def supabase_sign_up(email: str, password: str) -> dict:
    """Create a Supabase Auth user. Raises ``SupabaseAuthError`` on failure
    (including duplicate email)."""
    async with _gotrue_client() as client:
        response = await client.post(
            "/auth/v1/signup", json={"email": email, "password": password}
        )
    return _raise_for_gotrue(response)


async def supabase_sign_in_password(email: str, password: str) -> dict:
    """Verify email/password credentials via GoTrue's password grant.

    Raises ``SupabaseAuthError`` on invalid credentials.
    """
    async with _gotrue_client() as client:
        response = await client.post(
            "/auth/v1/token",
            params={"grant_type": "password"},
            json={"email": email, "password": password},
        )
    return _raise_for_gotrue(response)


async def supabase_refresh_session(refresh_token: str) -> dict:
    """Exchange a refresh token for a fresh session. Raises on expiry/tamper."""
    async with _gotrue_client() as client:
        response = await client.post(
            "/auth/v1/token",
            params={"grant_type": "refresh_token"},
            json={"refresh_token": refresh_token},
        )
    return _raise_for_gotrue(response)


async def supabase_sign_out(access_token: str) -> None:
    """Revoke the caller's own session (user-scoped logout)."""
    async with _gotrue_client() as client:
        response = await client.post(
            "/auth/v1/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    _raise_for_gotrue(response)


async def supabase_generate_link(link_type: str, email: str) -> str:
    """Admin-generate a magic link (``signup`` verification / ``recovery``).

    Returns the ``action_link`` URL embedded in the transactional email.
    """
    async with _gotrue_client() as client:
        response = await client.post(
            "/auth/v1/admin/generate_link",
            json={"type": link_type, "email": email},
        )
    body = _raise_for_gotrue(response)
    return str(body.get("action_link", ""))


async def supabase_reset_password(token: str, new_password: str) -> dict:
    """Consume a recovery token and set a new password.

    Verifies the ``recovery`` token (yielding a short-lived session) then updates
    the user's password with it. Returns the user record (must include ``id``).
    Raises ``SupabaseAuthError`` on an invalid/expired token.
    """
    async with _gotrue_client() as client:
        verify = await client.post(
            "/auth/v1/verify", json={"type": "recovery", "token": token}
        )
        verified = _raise_for_gotrue(verify)
        access_token = verified.get("access_token", "")
        update = await client.put(
            "/auth/v1/user",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"password": new_password},
        )
    updated = _raise_for_gotrue(update)
    # GoTrue returns the user either at the top level (PUT /user) or nested.
    if "user" in updated:
        return updated
    if "user" in verified:
        return {"user": verified["user"]}
    return {"user": updated}


# ===========================================================================
# Persistent Celery notification dispatch (Rule #14).
# ===========================================================================
def enqueue_notification(payload: dict) -> None:
    """Dispatch a notification task onto the persistent ``notification`` queue.

    Uses ``celery_app.send_task`` (broker-backed) rather than importing S2-M's
    task object, which does not exist in this session. The task name is prefixed
    with ``notification.`` so the §1.11 routing table lands it on the right
    queue. ``payload`` is passed as the task's single argument and is the
    load-bearing cross-session contract consumed by S2-M.
    """
    from app.workers.celery_app import celery_app
    from app.workers.queues import QUEUE_NOTIFICATION

    celery_app.send_task(
        f"notification.{payload['task_name']}",
        args=[payload],
        queue=QUEUE_NOTIFICATION,
    )


def _looks_like_duplicate(error: SupabaseAuthError) -> bool:
    """True when a GoTrue signup error means 'email already registered'."""
    if error.status_code in (409, 422):
        return True
    code = (error.code or "").lower()
    return "already" in code or "exist" in code or "registered" in code


def _session_tokens(result: dict) -> tuple[Optional[str], Optional[str]]:
    """Pull ``(access_token, refresh_token)`` from a GoTrue auth response.

    GoTrue returns tokens nested under ``session`` (signup) or at the top level
    (token grant); handle both.
    """
    session = result.get("session") if isinstance(result.get("session"), dict) else result
    return session.get("access_token"), session.get("refresh_token")


# ===========================================================================
# AuthService — orchestrates Supabase Auth + the application database.
# ===========================================================================
class AuthService:
    """Auth operations for the seven ``/auth`` endpoints.

    Imported by S2-F's account-deletion flow. All Supabase calls go through the
    module-level ``supabase_*`` coroutines; the DB session is synchronous (S0-A's
    ``get_db`` yields a sync ``Session``).
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- internal helpers -------------------------------------------------
    def _active_user_by_email(self, email: str) -> Optional[User]:
        """Return the non-deleted user with ``email``, or ``None``."""
        return self.db.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        ).scalar_one_or_none()

    @staticmethod
    def _user_public(user: User) -> dict:
        """The public ``user`` object shape returned in auth responses."""
        return {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "email_verified": bool(user.email_verified),
        }

    @staticmethod
    def _oauth_display_name(claims: dict, email: str) -> str:
        """Derive a non-null display name from OAuth claims (NOT NULL column)."""
        meta = claims.get("user_metadata") or {}
        for key in ("full_name", "name", "display_name"):
            value = meta.get(key)
            if value:
                return str(value)
        return email.split("@", 1)[0] or "user"

    def _write_audit(
        self,
        action_type: str,
        *,
        user_id: Optional[UUID] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Best-effort security audit write (§ critical notes).

        Committed independently so a failure here never fails the request. The
        AC set requires the audit semantics but asserts no audit row content.
        """
        try:
            self.db.add(
                AuditLog(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    action_type=action_type,
                    occurred_at=datetime.now(timezone.utc),
                    event_metadata=metadata,
                )
            )
            self.db.commit()
        except Exception:  # noqa: BLE001 - audit is best-effort
            self.db.rollback()
            logger.warning("audit write failed: %s", action_type, exc_info=True)

    # ---- US-001: registration --------------------------------------------
    async def register(self, email: str, password: str, display_name: str) -> dict:
        """Register a new password-based user (US-001 AC-1..AC-5).

        Raises :class:`EmailAlreadyRegistered` on a duplicate. On success creates
        the ``user`` (``email_verified=False``, ``role='user'``, password sentinel)
        and a free ``subscription`` atomically, then best-effort enqueues the
        verification email after commit.
        """
        if self._active_user_by_email(email) is not None:
            raise EmailAlreadyRegistered()

        try:
            result = await supabase_sign_up(email, password)
        except SupabaseAuthError as exc:
            if _looks_like_duplicate(exc):
                raise EmailAlreadyRegistered() from exc
            raise

        supabase_user = result.get("user") or {}
        user_id = UUID(str(supabase_user["id"]))
        access_token, refresh_token = _session_tokens(result)

        user = User(
            id=user_id,
            email=email,
            display_name=display_name,
            password_hash=SUPABASE_MANAGED_SENTINEL,
            email_verified=False,
            role=DEFAULT_ROLE,
        )
        subscription = Subscription(
            id=uuid.uuid4(),
            user_id=user_id,
            tier_id=FREE_TIER_ID,
            billing_state=ACTIVE_BILLING_STATE,
        )
        try:
            self.db.add(user)
            self.db.add(subscription)
            self.db.commit()
        except Exception:
            # Atomicity: the free subscription must never persist without the
            # user (and vice versa).
            self.db.rollback()
            raise

        # Verification email is eventually-consistent: a dispatch failure must
        # NOT fail registration (US-001 AC-4).
        try:
            verification_url = await supabase_generate_link("signup", email)
            enqueue_notification(
                {
                    "task_name": SEND_VERIFICATION_EMAIL,
                    "user_id": str(user_id),
                    "email": email,
                    "display_name": display_name,
                    "verification_url": verification_url,
                }
            )
        except Exception:  # noqa: BLE001 - email delivery is eventual
            logger.error(
                "failed to enqueue verification email for %s", email, exc_info=True
            )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": self._user_public(user),
        }

    # ---- US-002: email/password login ------------------------------------
    async def login(self, email: str, password: str) -> dict:
        """Authenticate email/password with brute-force lockout (US-002 AC-1..5,18).

        Order is load-bearing: the lockout check precedes ANY Supabase call so a
        locked account never reaches credential verification.
        """
        if await brute_force.is_locked_out(email):
            self._write_audit("login_locked", metadata={"email": email})
            raise AccountLocked(await self._lockout_ttl(email))

        try:
            result = await supabase_sign_in_password(email, password)
        except SupabaseAuthError:
            count = await brute_force.record_login_failure(email)
            action = (
                "login_locked"
                if count >= brute_force.LOCKOUT_THRESHOLD
                else "login_failed"
            )
            self._write_audit(action, metadata={"email": email})
            raise InvalidCredentials()

        # Supabase may still authenticate a row we soft-deleted (US-002 AC-18):
        # ``deleted_at`` is application-level, so re-check it here.
        user = self._active_user_by_email(email)
        if user is None:
            raise AccountNotFound()

        await brute_force.clear_failures(email)
        self._write_audit("login_success", user_id=user.id)

        access_token, refresh_token = _session_tokens(result)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": self._user_public(user),
        }

    @staticmethod
    async def _lockout_ttl(email: str) -> int:
        """Remaining TTL (seconds) of the ``brute_force:{email}`` key.

        Reuses S1-B's client/key seam so it honours the same fakeredis patch the
        brute-force primitives use under test.
        """
        client = brute_force._client()
        try:
            ttl = await client.ttl(brute_force._key(email))
        finally:
            await client.aclose()
        return max(int(ttl), 0)

    # ---- US-002: Google OAuth --------------------------------------------
    async def oauth_google(self, access_token: str, refresh_token: str) -> dict:
        """Log in / register via a verified Supabase Google OAuth token.

        * invalid token → :class:`InvalidCredentials` (401)
        * email matches an existing password account → :class:`AccountLinkRequired`
          (409, never merged — §1.7)
        * existing OAuth user → returned as-is
        * new email → new ``email_verified=true`` user + free subscription
        """
        try:
            claims = verify_token(access_token)
        except TokenVerificationError:
            raise InvalidCredentials()

        email = claims.get("email")
        sub = claims.get("sub")
        if not email or not sub:
            raise InvalidCredentials()

        existing = self._active_user_by_email(email)
        if existing is not None:
            if existing.password_hash is not None:
                # Password account already owns this email — prompt to link,
                # never silently merge. No session is created.
                raise AccountLinkRequired(email)
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": self._user_public(existing),
            }

        user_id = UUID(str(sub))
        user = User(
            id=user_id,
            email=email,
            display_name=self._oauth_display_name(claims, email),
            password_hash=None,  # OAuth account — no password flag
            email_verified=True,  # Google guarantees a verified email
            role=DEFAULT_ROLE,
        )
        subscription = Subscription(
            id=uuid.uuid4(),
            user_id=user_id,
            tier_id=FREE_TIER_ID,
            billing_state=ACTIVE_BILLING_STATE,
        )
        try:
            self.db.add(user)
            self.db.add(subscription)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self._write_audit("login_success", user_id=user_id)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": self._user_public(user),
        }

    # ---- US-002: token refresh -------------------------------------------
    async def refresh(self, refresh_token: str) -> dict:
        """Exchange a refresh token for a new session (US-002 AC-9/10).

        Does not touch brute-force counters — refresh is a separate flow.
        """
        try:
            result = await supabase_refresh_session(refresh_token)
        except SupabaseAuthError:
            raise InvalidRefreshToken()
        access_token, new_refresh = _session_tokens(result)
        return {"access_token": access_token, "refresh_token": new_refresh}

    # ---- US-002: logout ---------------------------------------------------
    async def logout(self, access_token: str, user_id: UUID) -> None:
        """Revoke the caller's session (US-002 AC-11).

        The Supabase call is best-effort: a downstream failure must not leave the
        client unable to log out. The endpoint always returns 204.
        """
        try:
            await supabase_sign_out(access_token)
        except Exception:  # noqa: BLE001 - revocation is best-effort here
            logger.warning("supabase sign_out failed", exc_info=True)
        self._write_audit("logout", user_id=user_id)


__all__ = [
    "AuthService",
    "AuthError",
    "EmailAlreadyRegistered",
    "InvalidCredentials",
    "AccountLocked",
    "AccountNotFound",
    "AccountLinkRequired",
    "InvalidRefreshToken",
    "InvalidResetToken",
    "SignOutFailed",
    "SupabaseAuthError",
    "enqueue_notification",
    "supabase_sign_up",
    "supabase_sign_in_password",
    "supabase_refresh_session",
    "supabase_sign_out",
    "supabase_generate_link",
    "supabase_reset_password",
    "SUPABASE_MANAGED_SENTINEL",
    "FREE_TIER_ID",
    "SEND_VERIFICATION_EMAIL",
    "SEND_PASSWORD_RESET_EMAIL",
]
