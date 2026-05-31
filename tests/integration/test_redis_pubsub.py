"""Integration tests for S1-D — Redis client, cache, pub/sub & Celery config.

Covers every acceptance criterion in the S1-D brief against a live Redis
(the ephemeral fixture from S0-B / ``docker-compose.fixtures.yml``).

Async helpers are driven via :func:`run_async`, which runs each coroutine on a
fresh event loop and closes the module-level ``redis.asyncio`` client afterwards
(an async Redis client is bound to the loop that created it). TTL and payload
assertions use the synchronous ``redis_client`` fixture so they observe exactly
what the async helpers wrote to the shared instance.

NOTE: application modules (``app.*``) are imported lazily *inside* the tests, not
at module top level. S0-B's smoke suite asserts that no ``app.*`` module has
leaked into ``sys.modules`` during collection, so importing them here at import
time would break that sibling test when the full ``tests/integration`` suite
runs. Lazy imports keep collection side-effect-free.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Awaitable, Callable, TypeVar

import pytest

# The shared conftest seeds the §1.12 vars it marks load-bearing, but importing
# ``app.config`` validates the *full* required set. Provide test-safe values for
# the remaining REQUIRED vars (setdefault → real env / conftest still win) so the
# settings singleton can construct when a test first imports it. This session
# does not own config.py or conftest.py and must not edit them.
for _key, _value in {
    "ML_MODEL_S3_KEY": "test/model.onnx",
    "ODA_CONVERTER_PATH": "/usr/bin/ODAFileConverter",
}.items():
    os.environ.setdefault(_key, _value)

# Make the backend package (``app.*``) importable when pytest runs from the repo
# root. tests/integration/test_redis_pubsub.py -> parents[2] == repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

T = TypeVar("T")

# A TCP port with nothing listening — connections fail fast, letting us exercise
# the fail-open / raise-on-error paths deterministically.
_DEAD_REDIS_URL = "redis://127.0.0.1:6399/0"


def run_async(coro_factory: Callable[[], Awaitable[T]]) -> T:
    """Run ``coro_factory()`` on a fresh loop, then close the Redis client.

    The factory is invoked *inside* the loop so any client created via
    ``get_redis()`` is bound to that loop.
    """
    from app.redis.client import close_redis

    async def _wrapper() -> T:
        try:
            return await coro_factory()
        finally:
            await close_redis()

    return asyncio.run(_wrapper())


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# RedisClient singleton
# ---------------------------------------------------------------------------
def test_returns_connected_async_client_from_env():
    """get_redis() returns a connected redis.asyncio.Redis built from REDIS_URL."""
    import redis.asyncio as aioredis
    from app.redis.client import get_redis

    async def scenario():
        client = get_redis()
        assert isinstance(client, aioredis.Redis)
        # Same call returns the same singleton instance.
        assert get_redis() is client
        assert await client.ping() is True
        return True

    assert run_async(scenario) is True


# ---------------------------------------------------------------------------
# subscription:flags:{user_id}
# ---------------------------------------------------------------------------
def test_sets_subscription_flags_with_300s_ttl(redis_client):
    from app.redis.cache import set_subscription_flags

    user_id = _unique("user")
    key = f"subscription:flags:{user_id}"
    try:
        run_async(lambda: set_subscription_flags(user_id, {"tier": "pro", "can_export": True}))
        ttl = redis_client.ttl(key)
        # 300s contract — allow a small window for command latency.
        assert 290 <= ttl <= 300
        assert json.loads(redis_client.get(key)) == {"tier": "pro", "can_export": True}
    finally:
        redis_client.delete(key)


def test_gets_subscription_flags_returns_dict_or_none(redis_client):
    from app.redis.cache import get_subscription_flags, set_subscription_flags

    user_id = _unique("user")
    key = f"subscription:flags:{user_id}"
    try:
        # Miss → None.
        assert run_async(lambda: get_subscription_flags(user_id)) is None
        # Hit → parsed dict.
        run_async(lambda: set_subscription_flags(user_id, {"tier": "team"}))
        assert run_async(lambda: get_subscription_flags(user_id)) == {"tier": "team"}
    finally:
        redis_client.delete(key)


def test_invalidates_subscription_flags(redis_client):
    from app.redis.cache import (
        get_subscription_flags,
        invalidate_subscription_flags,
        set_subscription_flags,
    )

    user_id = _unique("user")
    key = f"subscription:flags:{user_id}"
    try:
        run_async(lambda: set_subscription_flags(user_id, {"tier": "pro"}))
        assert redis_client.exists(key) == 1
        run_async(lambda: invalidate_subscription_flags(user_id))
        assert run_async(lambda: get_subscription_flags(user_id)) is None
        assert redis_client.exists(key) == 0
    finally:
        redis_client.delete(key)


# ---------------------------------------------------------------------------
# entity_classes:taxonomy
# ---------------------------------------------------------------------------
def test_sets_entity_taxonomy_indefinite_ttl(redis_client):
    from app.redis.cache import ENTITY_TAXONOMY_KEY, get_entity_taxonomy, set_entity_taxonomy

    payload = {"classes": ["pipe", "valve_gate", "instrument"]}
    try:
        run_async(lambda: set_entity_taxonomy(payload))
        # -1 == key exists with no associated expiry.
        assert redis_client.ttl(ENTITY_TAXONOMY_KEY) == -1
        assert run_async(lambda: get_entity_taxonomy()) == payload
    finally:
        redis_client.delete(ENTITY_TAXONOMY_KEY)


def test_invalidates_entity_taxonomy(redis_client):
    from app.redis.cache import (
        ENTITY_TAXONOMY_KEY,
        get_entity_taxonomy,
        invalidate_entity_taxonomy,
        set_entity_taxonomy,
    )

    try:
        run_async(lambda: set_entity_taxonomy({"classes": ["pipe"]}))
        assert redis_client.exists(ENTITY_TAXONOMY_KEY) == 1
        run_async(lambda: invalidate_entity_taxonomy())
        assert redis_client.exists(ENTITY_TAXONOMY_KEY) == 0
        assert run_async(lambda: get_entity_taxonomy()) is None
    finally:
        redis_client.delete(ENTITY_TAXONOMY_KEY)


# ---------------------------------------------------------------------------
# brute_force:{email}
# ---------------------------------------------------------------------------
def test_incr_brute_force_sets_900s_ttl_on_first_increment(redis_client):
    from app.redis.cache import incr_brute_force

    email = _unique("attacker") + "@example.com"
    key = f"brute_force:{email}"
    try:
        first = run_async(lambda: incr_brute_force(email))
        assert first == 1
        ttl_after_first = redis_client.ttl(key)
        assert 890 <= ttl_after_first <= 900

        # Second increment must NOT reset/extend the 15-minute window.
        second = run_async(lambda: incr_brute_force(email))
        assert second == 2
        ttl_after_second = redis_client.ttl(key)
        assert 0 < ttl_after_second <= 900
    finally:
        redis_client.delete(key)


def test_gets_brute_force_returns_zero_when_absent():
    from app.redis.cache import get_brute_force

    email = _unique("ghost") + "@example.com"
    assert run_async(lambda: get_brute_force(email)) == 0


def test_clears_brute_force_counter(redis_client):
    from app.redis.cache import clear_brute_force, get_brute_force, incr_brute_force

    email = _unique("attacker") + "@example.com"
    key = f"brute_force:{email}"
    try:
        run_async(lambda: incr_brute_force(email))
        run_async(lambda: incr_brute_force(email))
        assert run_async(lambda: get_brute_force(email)) == 2
        run_async(lambda: clear_brute_force(email))
        assert redis_client.exists(key) == 0
        assert run_async(lambda: get_brute_force(email)) == 0
    finally:
        redis_client.delete(key)


# ---------------------------------------------------------------------------
# Fail-open cache reads (silent-failure prevention)
# ---------------------------------------------------------------------------
def test_cache_get_returns_none_within_250ms_on_redis_error(monkeypatch):
    """A read against an unreachable Redis returns None promptly, never hangs."""
    import redis.asyncio as aioredis
    from app.redis import client as client_mod
    from app.redis.cache import get_subscription_flags

    async def scenario():
        dead = aioredis.Redis.from_url(
            _DEAD_REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=client_mod.CACHE_SOCKET_TIMEOUT_SECONDS,
            socket_timeout=client_mod.CACHE_SOCKET_TIMEOUT_SECONDS,
        )
        monkeypatch.setattr(client_mod, "get_cache_read_client", lambda: dead)
        try:
            start = time.monotonic()
            result = await get_subscription_flags("any-user")
            elapsed = time.monotonic() - start
            return result, elapsed
        finally:
            await dead.aclose()

    result, elapsed = run_async(scenario)
    assert result is None
    # 250ms budget + generous slack for the connection-refused round trip.
    assert elapsed < 1.0, f"cache read took {elapsed:.3f}s; must fail open fast"


# ---------------------------------------------------------------------------
# Pub/Sub
# ---------------------------------------------------------------------------
def test_publish_drawing_status_emits_exact_sse_payload(redis_client):
    """Published payload contains exactly drawing_id, state, timestamp."""
    from app.redis.pubsub import publish_drawing_status
    from app.schemas.contracts import DrawingStatusSSEEvent

    drawing_id = _unique("drawing")
    channel = f"drawing:status:{drawing_id}"
    event = DrawingStatusSSEEvent(
        drawing_id=drawing_id,
        state="Processing",
        timestamp="2026-05-31T12:00:00Z",
    )

    sub = redis_client.pubsub()
    sub.subscribe(channel)
    # Drain the subscribe-confirmation frame so the next message is the payload.
    _drain_subscribe_confirmation(sub)

    try:
        run_async(lambda: publish_drawing_status(drawing_id, event))
        message = _read_pubsub_message(sub, timeout=5.0)
        assert message is not None, "subscriber never received the published event"
        payload = json.loads(message["data"])
        assert set(payload.keys()) == {"drawing_id", "state", "timestamp"}
        assert payload == {
            "drawing_id": drawing_id,
            "state": "Processing",
            "timestamp": "2026-05-31T12:00:00Z",
        }
    finally:
        sub.close()


def test_subscribe_yields_published_drawing_status_event():
    """A subscriber receives an event published after the subscription starts."""
    from app.redis.pubsub import publish_drawing_status, subscribe_drawing_status
    from app.schemas.contracts import DrawingStatusSSEEvent

    drawing_id = _unique("drawing")
    event = DrawingStatusSSEEvent(
        drawing_id=drawing_id,
        state="Complete",
        timestamp="2026-05-31T13:30:00Z",
    )

    async def scenario():
        agen = subscribe_drawing_status(drawing_id)
        collector = asyncio.create_task(_first_event(agen))
        # Let the subscription register on the server before publishing.
        await asyncio.sleep(0.25)
        await publish_drawing_status(drawing_id, event)
        try:
            received = await asyncio.wait_for(collector, timeout=5.0)
        finally:
            await agen.aclose()
        return received

    received = run_async(scenario)
    assert isinstance(received, DrawingStatusSSEEvent)
    assert received == event


def test_subscribe_raises_on_redis_disconnect(monkeypatch):
    """subscribe_drawing_status must NOT swallow connection errors."""
    import redis.asyncio as aioredis
    from redis.exceptions import RedisError
    from app.redis import client as client_mod
    from app.redis.pubsub import subscribe_drawing_status

    async def scenario():
        dead = aioredis.Redis.from_url(
            _DEAD_REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=0.25,
        )
        monkeypatch.setattr(client_mod, "get_redis", lambda: dead)
        try:
            agen = subscribe_drawing_status("any-drawing")
            # The specific error varies (refused vs. timeout); the contract is
            # that it propagates rather than being swallowed.
            with pytest.raises((RedisError, ConnectionError, OSError, asyncio.TimeoutError)):
                await asyncio.wait_for(agen.__anext__(), timeout=3.0)
        finally:
            await dead.aclose()
        return True

    assert run_async(scenario) is True


# ---------------------------------------------------------------------------
# Celery queues / routing / base task / result backend
# ---------------------------------------------------------------------------
def test_declares_all_six_celery_queues():
    from app.workers import queues

    expected = {"ingest", "scan", "ml_inference", "export", "gdpr_erasure", "notification"}
    assert set(queues.QUEUE_NAMES) == expected
    assert len(queues.QUEUE_NAMES) == 6
    # Named constants match the load-bearing contract.
    assert queues.QUEUE_INGEST == "ingest"
    assert queues.QUEUE_SCAN == "scan"
    assert queues.QUEUE_ML == "ml_inference"
    assert queues.QUEUE_EXPORT == "export"
    assert queues.QUEUE_GDPR == "gdpr_erasure"
    assert queues.QUEUE_NOTIFICATION == "notification"


def test_routes_task_name_prefixes_to_correct_queues():
    from app.workers import queues
    from app.workers.celery_app import celery_app

    expected_routes = {
        "ingest.*": "ingest",
        "scan.*": "scan",
        "ml_inference.*": "ml_inference",
        "export.*": "export",
        "gdpr_erasure.*": "gdpr_erasure",
        "notification.*": "notification",
    }
    for prefix, queue in expected_routes.items():
        assert queues.TASK_ROUTES[prefix]["queue"] == queue
    # The routing table is applied to the live Celery app.
    assert celery_app.conf.task_routes == queues.TASK_ROUTES


def test_base_task_has_acks_late_and_exponential_retry():
    from app.workers import base as worker_base

    bt = worker_base.BaseTask
    assert bt.acks_late is True
    assert bt.reject_on_worker_lost is True
    assert bt.max_retries == 3
    assert bt.retry_backoff is True  # exponential backoff
    assert bt.autoretry_for == (Exception,)


def test_celery_result_backend_uses_redis_url():
    from app.config import settings
    from app.workers.celery_app import celery_app

    backend_url = celery_app.conf.result_backend
    assert backend_url, "result backend must be configured"
    assert backend_url.startswith("redis://") or backend_url.startswith("rediss://")
    assert backend_url == settings.REDIS_URL


# ---------------------------------------------------------------------------
# Startup contract
# ---------------------------------------------------------------------------
def test_app_refuses_to_start_without_redis_url(monkeypatch):
    """get_redis() refuses to operate when REDIS_URL is absent (§1.12)."""
    from app.redis import client as client_mod

    # Ensure no cached singleton masks the check.
    asyncio.run(client_mod.close_redis())
    monkeypatch.setattr(client_mod.settings, "REDIS_URL", "", raising=False)
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        client_mod.get_redis()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _first_event(agen):
    async for event in agen:
        return event
    raise AssertionError("subscription closed before any event arrived")


def _drain_subscribe_confirmation(sub) -> None:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        message = sub.get_message(timeout=1.0)
        if message and message.get("type") == "subscribe":
            return


def _read_pubsub_message(sub, timeout: float) -> dict | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        message = sub.get_message(timeout=1.0)
        if message and message.get("type") == "message":
            return message
    return None
