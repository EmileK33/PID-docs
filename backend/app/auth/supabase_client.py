"""Supabase Auth Admin API wrapper (§1.7, Rule #12).

Two sanctioned operations:

* :func:`admin_sign_out` — the ONLY supported session-revocation path. Used by
  S2-A (password reset, Rule #12) and S2-F (account deletion). Calls
  ``POST {SUPABASE_URL}/auth/v1/admin/users/{id}/logout``.
* :func:`find_user_by_email` — used by S2-A's OAuth account-link flow to detect
  an existing password account. It **returns** the matching record (or ``None``)
  and never merges identities; the linking prompt is implemented in S2-A.

Both authenticate with the service-role key via the ``Authorization: Bearer``
and ``apikey`` headers Supabase's GoTrue admin API requires.
"""
from __future__ import annotations

from uuid import UUID

import httpx

from app.config import settings

# Network timeout for admin calls — these sit on the login / reset hot path.
_TIMEOUT_SECONDS = 10.0


class SupabaseAdminError(Exception):
    """Raised when the Supabase Admin API returns an unexpected status."""


def _admin_headers() -> dict[str, str]:
    """Service-role auth headers for the GoTrue admin API."""
    return {
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Content-Type": "application/json",
    }


def _build_client() -> httpx.AsyncClient:
    """Build the HTTP client used for admin calls.

    Tests monkeypatch this to inject an ``httpx.MockTransport`` (or respx),
    keeping the call-site code identical between tests and production.
    """
    return httpx.AsyncClient(
        base_url=settings.SUPABASE_URL.rstrip("/"),
        headers=_admin_headers(),
        timeout=_TIMEOUT_SECONDS,
    )


async def admin_sign_out(user_id: UUID) -> None:
    """Revoke all sessions for ``user_id`` via Supabase ``admin`` logout.

    Issues ``POST /auth/v1/admin/users/{user_id}/logout``. This is the only
    sanctioned revocation path (Rule #12); the caller is responsible for the
    simultaneous ``USER.token_invalidated_at`` update.
    """
    async with _build_client() as client:
        response = await client.post(f"/auth/v1/admin/users/{user_id}/logout")
    if response.status_code not in (200, 204):
        raise SupabaseAdminError(
            f"admin sign-out failed for {user_id}: HTTP {response.status_code}"
        )


async def find_user_by_email(email: str) -> dict | None:
    """Return the Supabase user record matching ``email``, or ``None``.

    Used by the S2-A OAuth account-link flow to detect an existing password
    account. This NEVER merges identities — it only reports existence so the
    caller can prompt for linking (§1.7: "never silent merge").
    """
    async with _build_client() as client:
        response = await client.get(
            "/auth/v1/admin/users", params={"email": email}
        )
    if response.status_code != 200:
        raise SupabaseAdminError(
            f"user lookup failed for {email!r}: HTTP {response.status_code}"
        )

    users = response.json().get("users", [])
    if not users:
        return None
    return users[0]


__all__ = ["admin_sign_out", "find_user_by_email", "SupabaseAdminError"]
