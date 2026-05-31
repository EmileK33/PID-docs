"""Shared Redis layer (§1.8, §1.11).

A single Redis instance backs three concerns — the Celery broker (see
``app.workers``), the feature-flag / brute-force cache (``cache``), and the SSE
drawing-status pub/sub fan-out (``pubsub``). This package owns the async client
(`client`) and the typed helpers built on top of it.
"""
from __future__ import annotations

from app.redis.client import close_redis, get_redis

__all__ = ["get_redis", "close_redis"]
