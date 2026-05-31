"""Drawing-status pub/sub fan-out (§1.11 Redis Pub/Sub Channels).

A single channel pattern carries every drawing state transition to connected
SSE clients:

    drawing:status:{drawing_id}

[LOAD-BEARING]

* ``publish_drawing_status(drawing_id, event)`` — called by the Ingest, Scan,
  and ML workers (S2-H/I/J) on each state transition. The payload is the §1.1
  ``DrawingStatusSSEEvent`` shape exactly (``drawing_id``, ``state``,
  ``timestamp``) — no extra fields.
* ``subscribe_drawing_status(drawing_id)`` — consumed by the SSE handler
  (S2-B), yielding deserialized events for one drawing.

Silent-failure prevention (§): neither helper swallows Redis connection errors.
A failed publish must raise so the calling worker can retry (otherwise status
updates silently stop reaching clients); a subscriber whose connection drops
must raise so the SSE handler tears the stream down rather than hanging.
"""
from __future__ import annotations

from typing import AsyncIterator

from app.redis import client as redis_client
from app.schemas.contracts import DrawingStatusSSEEvent

_CHANNEL_PREFIX = "drawing:status:"


def _channel(drawing_id: str) -> str:
    return f"{_CHANNEL_PREFIX}{drawing_id}"


async def publish_drawing_status(drawing_id: str, event: DrawingStatusSSEEvent) -> None:
    """Publish a drawing-status event to ``drawing:status:{drawing_id}``.

    Serializes ``event`` with the exact §1.1 field set. Raises on Redis error
    (does NOT swallow) so the calling worker can retry.
    """
    client = redis_client.get_redis()
    # model_dump_json emits exactly drawing_id / state / timestamp — the §1.1
    # contract S2-B deserializes with DrawingStatusSSEEvent.model_validate_json.
    await client.publish(_channel(drawing_id), event.model_dump_json())


async def subscribe_drawing_status(drawing_id: str) -> AsyncIterator[DrawingStatusSSEEvent]:
    """Yield ``DrawingStatusSSEEvent`` objects published for ``drawing_id``.

    The subscription is established before the first event is awaited.
    Subscription-confirmation frames are skipped; only ``message`` frames are
    deserialized and yielded. A dropped connection propagates as an exception
    (errors are NOT swallowed) so the SSE handler can close the stream.
    """
    client = redis_client.get_redis()
    pubsub = client.pubsub()
    await pubsub.subscribe(_channel(drawing_id))
    try:
        async for message in pubsub.listen():
            if message is None or message.get("type") != "message":
                continue
            yield DrawingStatusSSEEvent.model_validate_json(message["data"])
    finally:
        try:
            await pubsub.unsubscribe(_channel(drawing_id))
        finally:
            await pubsub.aclose()


__all__ = ["publish_drawing_status", "subscribe_drawing_status"]
