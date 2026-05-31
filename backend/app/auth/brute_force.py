"""Redis-backed brute-force login lockout (§1.9, §1.11, US-002).

Contract (§1.11 / US-002 AC):

* Key pattern ``brute_force:{email}`` with the email **lowercased**.
* ``record_login_failure`` increments the counter and, on the *first* failure,
  sets a 900-second (15-minute) TTL. The TTL is preserved on subsequent
  failures — the lockout window does NOT slide.
* ``is_locked_out`` returns ``True`` once the counter reaches the threshold (5),
  so the 6th attempt is rejected *before* any credential verification.
* ``clear_failures`` deletes the counter. The caller (S2-A login handler) must
  only clear when the account is not locked out — see module note below.

This module talks to Redis **directly** via ``redis.asyncio`` using
``settings.REDIS_URL``. It deliberately does NOT import ``backend/app/redis/``
(owned by the parallel S1-D session); the two clients coexist.

NOTE on the "never clear while locked out" rule: the lockout primitives are
intentionally simple. The login flow checks ``is_locked_out`` first and returns
the lockout response without verifying credentials, so ``clear_failures`` is
only reached on a successful authentication while still below the threshold.
"""
from __future__ import annotations

import redis.asyncio as aioredis

from app.config import settings

# §1.9 / US-002: lock after 5 failed attempts for 15 minutes.
LOCKOUT_THRESHOLD = 5
LOCKOUT_TTL_SECONDS = 900


def _key(email: str) -> str:
    """Brute-force counter key for ``email`` (lowercased, §1.11)."""
    return f"brute_force:{email.lower()}"


def _client() -> "aioredis.Redis":
    """Construct a fresh async Redis client bound to ``settings.REDIS_URL``.

    A new client per call keeps connections from leaking across the short-lived
    login handler request and avoids sharing state with S1-D's wrapper.
    """
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def record_login_failure(email: str) -> int:
    """Increment the failed-login counter for ``email`` and return the new count.

    On the first failure (count == 1) a 900s TTL is set. The TTL is left
    untouched on later failures so the lockout window cannot be extended by
    additional attempts.
    """
    client = _client()
    try:
        count = await client.incr(_key(email))
        if count == 1:
            await client.expire(_key(email), LOCKOUT_TTL_SECONDS)
        return int(count)
    finally:
        await client.aclose()


async def is_locked_out(email: str) -> bool:
    """Return ``True`` when ``email`` has reached the lockout threshold.

    Reads the counter without mutating it — callers invoke this before verifying
    credentials so a locked-out attempt never touches Supabase.
    """
    client = _client()
    try:
        value = await client.get(_key(email))
        if value is None:
            return False
        return int(value) >= LOCKOUT_THRESHOLD
    finally:
        await client.aclose()


async def clear_failures(email: str) -> None:
    """Delete the failed-login counter for ``email``.

    Only call this for a successful login that is *not* locked out (the login
    handler guards on ``is_locked_out`` first).
    """
    client = _client()
    try:
        await client.delete(_key(email))
    finally:
        await client.aclose()


__all__ = [
    "record_login_failure",
    "is_locked_out",
    "clear_failures",
    "LOCKOUT_THRESHOLD",
    "LOCKOUT_TTL_SECONDS",
]
