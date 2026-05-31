"""RS256 JWT verification for Supabase Auth tokens (§1.7, §1.8).

[INTERNAL but exposed for testability] ``verify_token`` is imported by
``middleware.py`` only. It enforces the irreversible §1.8 constraint: **RS256
only**. Any token presenting ``alg=none`` or a symmetric algorithm (HS256) is
rejected — there is no HS256 / custom-signing fallback in any environment.

Verification covers, in order:

* signature against ``settings.JWT_RS256_PUBLIC_KEY`` using RS256,
* ``exp`` (expiry),
* ``iss`` == ``settings.SUPABASE_URL``,
* ``aud`` == ``"authenticated"`` (Supabase's access-token audience).

The ``token_invalidated_at`` / ``deleted_at`` user-state checks are NOT done
here — they require a DB row and live in ``middleware.authenticate_request``.
"""
from __future__ import annotations

import jwt
from jwt import InvalidTokenError, PyJWTError

from app.config import settings

# Supabase signs access tokens with audience "authenticated". This is fixed by
# Supabase Auth and is not environment-configurable.
_EXPECTED_AUDIENCE = "authenticated"

# RS256 is the only accepted algorithm. Listing exactly one algorithm makes PyJWT
# reject `alg=none` and any HS* token before signature verification.
_ALLOWED_ALGORITHMS = ["RS256"]


class TokenVerificationError(Exception):
    """Raised when a token fails any verification step. The middleware maps this
    to HTTP 401. The message is for logging only — never surfaced to clients."""


def verify_token(token: str) -> dict:
    """Verify an RS256 Supabase access token and return its decoded claims.

    Raises :class:`TokenVerificationError` on any failure (bad signature,
    expired, wrong issuer/audience, malformed, or a disallowed algorithm such as
    ``none`` / HS256).
    """
    if not token:
        raise TokenVerificationError("empty token")

    try:
        claims = jwt.decode(
            token,
            settings.JWT_RS256_PUBLIC_KEY,
            algorithms=_ALLOWED_ALGORITHMS,
            issuer=settings.SUPABASE_URL,
            audience=_EXPECTED_AUDIENCE,
            options={
                "require": ["exp", "iat", "iss", "sub"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": True,
            },
        )
    except (InvalidTokenError, PyJWTError) as exc:  # pragma: no cover - exact subclass varies
        raise TokenVerificationError(f"token verification failed: {exc}") from exc

    return claims


__all__ = ["verify_token", "TokenVerificationError"]
