"""Shared async Redis client (§1.8 — single Redis instance, three concerns).

[LOAD-BEARING] ``get_redis()`` returns the process-wide ``redis.asyncio.Redis``
singleton consumed by S1-B (brute-force), S2-A/E (subscription flags), S2-B
(SSE), and S2-G (taxonomy). The connection URL is sourced from ``REDIS_URL``
(§1.12); ``app.config`` already refuses to start when it is absent, but
``get_redis`` re-checks so callers fail loudly rather than connecting to a
bogus endpoint.

Two clients are exposed:

* ``get_redis()`` — the general-purpose client used for writes, brute-force
  counters, and the long-lived pub/sub subscriptions. It deliberately uses no
  aggressive socket read timeout, because pub/sub ``listen()`` blocks for the
  lifetime of a subscription.
* ``get_cache_read_client()`` — a tight-timeout client used only by cache
  *reads* so a Redis outage fails open (returns ``None``) within ~250 ms
  instead of hanging an authenticated request (see ``cache``).
"""
from __future__ import annotations

import redis.asyncio as aioredis

from app.config import settings

# Fail-open budget for cache reads (§ silent-failure prevention).
CACHE_SOCKET_TIMEOUT_SECONDS = 0.25

_client: aioredis.Redis | None = None
_cache_read_client: aioredis.Redis | None = None


def _require_redis_url() -> str:
    """Return ``REDIS_URL`` or raise — refuse to operate without it (§1.12)."""
    url = getattr(settings, "REDIS_URL", None)
    if not url:
        raise RuntimeError(
            "REDIS_URL is not configured; refusing to start the Redis client "
            "(§1.12 Environment Variable Schema)."
        )
    return url


def get_redis() -> aioredis.Redis:
    """Return the process-wide async Redis client.

    Lazily constructed on first use and reused thereafter. ``decode_responses``
    is enabled so cache payloads and pub/sub messages arrive as ``str``.
    """
    global _client
    if _client is None:
        _client = aioredis.Redis.from_url(
            _require_redis_url(),
            decode_responses=True,
        )
    return _client


def get_cache_read_client() -> aioredis.Redis:
    """Return a short-timeout client for fail-open cache reads.

    A dead/slow Redis must not block authenticated requests, so this client
    caps connect + socket time at ``CACHE_SOCKET_TIMEOUT_SECONDS``. Cache read
    helpers additionally bound the whole operation with ``asyncio.wait_for``.
    """
    global _cache_read_client
    if _cache_read_client is None:
        _cache_read_client = aioredis.Redis.from_url(
            _require_redis_url(),
            decode_responses=True,
            socket_connect_timeout=CACHE_SOCKET_TIMEOUT_SECONDS,
            socket_timeout=CACHE_SOCKET_TIMEOUT_SECONDS,
        )
    return _cache_read_client


async def close_redis() -> None:
    """Close and drop the cached clients.

    Used by app shutdown and by tests that drive the async client across
    multiple event loops (a ``redis.asyncio`` client is bound to the loop that
    created it, so it must be recreated per loop).
    """
    global _client, _cache_read_client
    for existing in (_client, _cache_read_client):
        if existing is not None:
            try:
                await existing.aclose()
            except Exception:  # noqa: BLE001 — best-effort cleanup
                pass
    _client = None
    _cache_read_client = None


__all__ = ["get_redis", "get_cache_read_client", "close_redis", "CACHE_SOCKET_TIMEOUT_SECONDS"]
