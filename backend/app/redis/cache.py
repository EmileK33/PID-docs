"""Typed Redis cache helpers (§1.11 Redis Cache Keys).

Three caches live here, each with a load-bearing key format and TTL contract:

* ``subscription:flags:{user_id}`` — 300 s TTL, read on every authenticated
  request (S1-B middleware, all Phase 2 routers); written on login / Stripe
  webhook (S2-A, S2-E) and invalidated on webhook receipt.
* ``entity_classes:taxonomy`` — no TTL (indefinite until admin update), written
  / invalidated by S2-G.
* ``brute_force:{email}`` — 900 s TTL security counter (§1.9), used by S1-B.

Key strings and TTLs are exact contracts (§1.11): downstream sessions format
these keys independently, so any drift here silently breaks them.

Fail-open reads (§ silent-failure prevention): every ``get_*`` returns ``None``
(or ``0`` for the brute-force counter) on a Redis error/timeout within
~250 ms instead of blocking the caller, who treats it as a cache miss.
"""
from __future__ import annotations

import asyncio
import json
import logging

from redis.exceptions import RedisError

from app.redis import client as redis_client

logger = logging.getLogger("pid.redis.cache")

# --- Key formats (§1.11 — exact strings, load-bearing) ---------------------
_SUBSCRIPTION_FLAGS_PREFIX = "subscription:flags:"
ENTITY_TAXONOMY_KEY = "entity_classes:taxonomy"
_BRUTE_FORCE_PREFIX = "brute_force:"

# --- TTL contracts (§1.11, §1.9 — seconds; hard-coded, not configurable) ---
SUBSCRIPTION_FLAGS_TTL_SECONDS = 300  # 5 minutes
BRUTE_FORCE_TTL_SECONDS = 900  # 15 minutes
# entity_classes:taxonomy intentionally has NO TTL (indefinite).

# Whole-operation budget for fail-open reads.
_READ_TIMEOUT_SECONDS = redis_client.CACHE_SOCKET_TIMEOUT_SECONDS


def _subscription_flags_key(user_id: str) -> str:
    return f"{_SUBSCRIPTION_FLAGS_PREFIX}{user_id}"


def _brute_force_key(email: str) -> str:
    return f"{_BRUTE_FORCE_PREFIX}{email}"


async def _read_raw(key: str) -> str | None:
    """Fail-open GET: return the raw string value, or ``None`` on miss/error.

    Bounded by ``_READ_TIMEOUT_SECONDS`` so a Redis outage never blocks the
    caller longer than the cache budget.
    """
    try:
        client = redis_client.get_cache_read_client()
        return await asyncio.wait_for(client.get(key), timeout=_READ_TIMEOUT_SECONDS)
    except (asyncio.TimeoutError, RedisError, OSError) as exc:
        logger.warning("cache read failed-open for key %r: %s", key, exc)
        return None


def _parse_json_dict(raw: str | None) -> dict | None:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        logger.warning("cached value is not valid JSON; treating as miss")
        return None
    return value if isinstance(value, dict) else None


# ---------------------------------------------------------------------------
# subscription:flags:{user_id}  (S2-A write, S2-E write/invalidate, all reads)
# ---------------------------------------------------------------------------
async def set_subscription_flags(user_id: str, flags: dict) -> None:
    """Cache a user's subscription feature flags for 300 s (§1.11)."""
    client = redis_client.get_redis()
    await client.set(
        _subscription_flags_key(user_id),
        json.dumps(flags),
        ex=SUBSCRIPTION_FLAGS_TTL_SECONDS,
    )


async def get_subscription_flags(user_id: str) -> dict | None:
    """Return cached subscription flags, or ``None`` on miss / Redis error."""
    return _parse_json_dict(await _read_raw(_subscription_flags_key(user_id)))


async def invalidate_subscription_flags(user_id: str) -> None:
    """Delete the cached flags (called by S2-E on Stripe webhook receipt)."""
    client = redis_client.get_redis()
    await client.delete(_subscription_flags_key(user_id))


# ---------------------------------------------------------------------------
# entity_classes:taxonomy  (S2-G write/invalidate; indefinite TTL)
# ---------------------------------------------------------------------------
async def set_entity_taxonomy(payload: dict) -> None:
    """Cache the entity-class taxonomy with NO expiry (§1.11)."""
    client = redis_client.get_redis()
    await client.set(ENTITY_TAXONOMY_KEY, json.dumps(payload))


async def get_entity_taxonomy() -> dict | None:
    """Return the cached taxonomy, or ``None`` on miss / Redis error."""
    return _parse_json_dict(await _read_raw(ENTITY_TAXONOMY_KEY))


async def invalidate_entity_taxonomy() -> None:
    """Delete the cached taxonomy (called by S2-G admin update)."""
    client = redis_client.get_redis()
    await client.delete(ENTITY_TAXONOMY_KEY)


# ---------------------------------------------------------------------------
# brute_force:{email}  (S1-B login handler; §1.9 security counter)
# ---------------------------------------------------------------------------
async def incr_brute_force(email: str) -> int:
    """Increment the failed-login counter, setting a 900 s TTL on first hit.

    Returns the new count. The TTL is applied only when the counter is created
    (count == 1) so the 15-minute window starts at the first failure and is not
    extended by subsequent failures within the window.
    """
    client = redis_client.get_redis()
    key = _brute_force_key(email)
    count = await client.incr(key)
    if count == 1:
        await client.expire(key, BRUTE_FORCE_TTL_SECONDS)
    return int(count)


async def get_brute_force(email: str) -> int:
    """Return the current failed-login count, or ``0`` if absent / on error."""
    raw = await _read_raw(_brute_force_key(email))
    if raw is None:
        return 0
    try:
        return int(raw)
    except (ValueError, TypeError):
        return 0


async def clear_brute_force(email: str) -> None:
    """Delete the counter (called by S1-B on successful login)."""
    client = redis_client.get_redis()
    await client.delete(_brute_force_key(email))


__all__ = [
    "set_subscription_flags",
    "get_subscription_flags",
    "invalidate_subscription_flags",
    "set_entity_taxonomy",
    "get_entity_taxonomy",
    "invalidate_entity_taxonomy",
    "incr_brute_force",
    "get_brute_force",
    "clear_brute_force",
    "ENTITY_TAXONOMY_KEY",
    "SUBSCRIPTION_FLAGS_TTL_SECONDS",
    "BRUTE_FORCE_TTL_SECONDS",
]
