"""Redis-backed dead-letter queue for failed analytics emissions (§1.10).

On a PostHog send failure the originating event is serialised to the Redis list
``analytics:dead_letter`` via ``RPUSH`` and the list is capped at 10,000 entries
via ``LTRIM`` to bound growth. :func:`retry_dead_letter` drains the list with
``LPOP`` and re-attempts emission; it is intentionally NOT auto-scheduled here (a
cron / Celery beat will invoke it — out of scope for this session).

Per the session plan this module talks to Redis through the raw ``REDIS_URL``
env var via ``redis-py`` directly — it must not import S1-D's client (which may
not exist when this session runs in isolation).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis

# Relative import — see the note in posthog_client.py (dual import-root support).
from ..config import settings
from . import posthog_client

logger = logging.getLogger("pid.analytics")

# Redis list key + growth cap (§1.10).
DEAD_LETTER_KEY = "analytics:dead_letter"
MAX_DEAD_LETTER_ENTRIES = 10_000

# Lazily-constructed, cached client. Tests substitute a fakeredis instance by
# assigning this module attribute before exercising the queue.
_redis_client: Optional["redis.Redis"] = None


def get_redis_client() -> "redis.Redis":
    """Return the cached Redis client, constructing it from ``REDIS_URL`` once.

    ``decode_responses=True`` mirrors the integration harness fixture so list
    members round-trip as ``str`` (JSON) rather than ``bytes``.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def push_to_dead_letter(envelope: dict[str, Any]) -> None:
    """Persist a failed emission envelope, capped at 10,000 entries.

    ``envelope`` is ``{"event", "distinct_id", "properties"}`` — everything
    needed to replay the capture. Never raises into the caller; a dead-letter
    write failure is logged at WARN and the event is dropped (analytics failure
    must not surface to a user).
    """
    try:
        client = get_redis_client()
        client.rpush(DEAD_LETTER_KEY, json.dumps(envelope, separators=(",", ":")))
        # Keep only the most recent MAX_DEAD_LETTER_ENTRIES (drop oldest).
        client.ltrim(DEAD_LETTER_KEY, -MAX_DEAD_LETTER_ENTRIES, -1)
    except Exception:
        logger.warning(
            "Failed to persist analytics event to dead-letter queue; event dropped.",
            exc_info=True,
        )


def retry_dead_letter() -> int:
    """Drain the dead-letter queue and re-attempt emission.

    Returns the number of events successfully re-sent. Each entry is processed
    at most once per call: failed re-sends are pushed back to the tail (and not
    retried again until the next invocation), so a persistently-failing entry
    can never spin this function. Returns ``0`` immediately when analytics is
    disabled or Redis is unreachable.
    """
    if not posthog_client.is_enabled():
        return 0

    try:
        client = get_redis_client()
        pending = client.llen(DEAD_LETTER_KEY)
    except Exception:
        logger.warning("Failed to access dead-letter queue for retry.", exc_info=True)
        return 0

    resent = 0
    for _ in range(pending):
        raw = client.lpop(DEAD_LETTER_KEY)
        if raw is None:
            break
        try:
            envelope = json.loads(raw)
            event = envelope["event"]
            distinct_id = envelope["distinct_id"]
            properties = envelope["properties"]
        except Exception:
            logger.warning("Discarding malformed dead-letter entry.", exc_info=True)
            continue

        if posthog_client.send_event(event, distinct_id, properties):
            resent += 1
        else:
            try:
                client.rpush(DEAD_LETTER_KEY, raw)
            except Exception:
                logger.warning(
                    "Failed to requeue dead-letter entry after failed retry.",
                    exc_info=True,
                )
    return resent
