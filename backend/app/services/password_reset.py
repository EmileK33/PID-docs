"""Password-reset service (S2-A — US-002 AC-13..AC-17, §1.4 Rule #12).

Two operations, both returning ``204`` to the client:

* :meth:`PasswordResetService.request_reset` — enumeration-safe. Enqueues a
  ``send_password_reset_email`` task ONLY when the email maps to an active user,
  but returns nothing either way so the response can't reveal account existence.
* :meth:`PasswordResetService.confirm_reset` — enforces Rule #12's ordering:
  ``admin.signOut(userId)`` is called FIRST (the only sanctioned revocation path,
  S1-B :func:`app.auth.supabase_client.admin_sign_out`); only then is
  ``USER.token_invalidated_at`` written, in a single DB commit. If revocation
  fails the timestamp is never written and the caller surfaces ``500``.

The token-invalidation timestamp is what lets S1-B's middleware reject any JWT
issued before the reset (US-002 AC-17) — that middleware behaviour is tested in
S1-B; this session is responsible only for setting the column correctly.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.supabase_client import admin_sign_out
from app.db.models.user import User
from app.services.auth_service import (
    SEND_PASSWORD_RESET_EMAIL,
    InvalidResetToken,
    SignOutFailed,
    SupabaseAuthError,
    enqueue_notification,
    supabase_generate_link,
    supabase_reset_password,
)

logger = logging.getLogger("pid.auth.password_reset")


class PasswordResetService:
    """Reset-request and reset-confirm flows for ``/auth/password-reset/*``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    async def request_reset(self, email: str) -> None:
        """Enqueue a reset email iff ``email`` is a registered active user.

        Always returns ``None`` (router → 204). Unregistered emails enqueue
        nothing and are indistinguishable from registered ones in the response
        (US-002 AC-13/14 — no enumeration).
        """
        user = self.db.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        ).scalar_one_or_none()
        if user is None:
            return

        try:
            reset_url = await supabase_generate_link("recovery", email)
            enqueue_notification(
                {
                    "task_name": SEND_PASSWORD_RESET_EMAIL,
                    "user_id": str(user.id),
                    "email": email,
                    "display_name": user.display_name,
                    "reset_url": reset_url,
                }
            )
        except Exception:  # noqa: BLE001 - email delivery is eventual
            logger.error(
                "failed to enqueue password-reset email for %s", email, exc_info=True
            )

    async def confirm_reset(self, token: str, new_password: str) -> None:
        """Reset the password and atomically invalidate prior sessions.

        Ordering (Rule #12): reset password via Supabase → ``admin_sign_out`` →
        write ``token_invalidated_at``. Raises :class:`InvalidResetToken` (→ 400)
        on a bad token and :class:`SignOutFailed` (→ 500) if revocation fails,
        leaving ``token_invalidated_at`` untouched in the latter case.
        """
        try:
            result = await supabase_reset_password(token, new_password)
        except SupabaseAuthError:
            raise InvalidResetToken()

        supabase_user = result.get("user") or {}
        try:
            user_id = UUID(str(supabase_user["id"]))
        except (KeyError, ValueError, TypeError):
            raise InvalidResetToken()

        # Rule #12: revoke ALL sessions before touching the DB. If this raises we
        # must NOT write token_invalidated_at and must surface a 500.
        try:
            await admin_sign_out(user_id)
        except Exception as exc:  # noqa: BLE001 - any failure blocks the DB write
            logger.error("admin sign-out failed during password reset", exc_info=True)
            raise SignOutFailed() from exc

        # token_invalidated_at is set AT/AFTER the revocation call so the
        # middleware rejects every pre-reset JWT.
        invalidated_at = datetime.now(timezone.utc)
        user = self.db.get(User, user_id)
        if user is not None:
            user.token_invalidated_at = invalidated_at
            self.db.commit()

        self._write_audit_confirmed(user_id)

    def _write_audit_confirmed(self, user_id: UUID) -> None:
        """Best-effort ``password_reset_confirmed`` audit entry."""
        from app.db.models.audit_log import AuditLog
        import uuid as _uuid

        try:
            self.db.add(
                AuditLog(
                    id=_uuid.uuid4(),
                    user_id=user_id,
                    action_type="password_reset_confirmed",
                    occurred_at=datetime.now(timezone.utc),
                )
            )
            self.db.commit()
        except Exception:  # noqa: BLE001 - audit is best-effort
            self.db.rollback()
            logger.warning("audit write failed: password_reset_confirmed", exc_info=True)


__all__ = ["PasswordResetService", "InvalidResetToken", "SignOutFailed"]
