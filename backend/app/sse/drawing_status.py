"""Drawing-status SSE stream (US-008, §1.11).

``GET /drawings/{id}/status`` opens a ``text/event-stream`` that:

1. Immediately emits the drawing's *current* state as the first event, so a
   client connecting after the last transition still learns where the drawing
   is (silent-failure prevention — stale UI).
2. Forwards every ``DrawingStatusSSEEvent`` published to
   ``drawing:status:{drawing_id}`` by the Ingest/Scan/ML workers (S2-H/I/J) via
   S1-D's :func:`subscribe_drawing_status`.
3. Emits an SSE comment keepalive at least every
   :data:`SSE_KEEPALIVE_SECONDS` (10s) so proxied connections are not dropped
   and slow links fall back to ~10s polling cadence (§1.9).

The channel key format ``drawing:status:{drawing_id}`` is load-bearing and owned
by S1-D's pub/sub helper — this handler subscribes through that helper rather
than formatting the key itself, so the two can never drift.
"""
from __future__ import annotations

import asyncio
import datetime
from typing import AsyncIterator, Awaitable, Callable

from app.redis.pubsub import subscribe_drawing_status
from app.schemas.contracts import DrawingProcessingState, DrawingStatusSSEEvent

# §1.9 — max fallback interval is 10s. A comment frame at this cadence keeps
# proxied connections alive and bounds the worst-case staleness.
SSE_KEEPALIVE_SECONDS = 10

# Injectable subscription factory: an async iterator of DrawingStatusSSEEvent for
# a drawing. Defaults to the real Redis-backed S1-D helper; tests substitute a
# finite async generator.
SubscribeFn = Callable[[str], AsyncIterator[DrawingStatusSSEEvent]]


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def format_sse_event(event: DrawingStatusSSEEvent) -> str:
    """Serialise a ``DrawingStatusSSEEvent`` as an SSE ``data:`` frame.

    The payload is exactly the §1.1 field set (``drawing_id``, ``state``,
    ``timestamp``) — no extra fields — so it round-trips through the contract
    model on the client.
    """
    return f"data: {event.model_dump_json()}\n\n"


async def drawing_status_event_stream(
    drawing_id: str,
    current_state: str,
    *,
    subscribe: SubscribeFn = subscribe_drawing_status,
    keepalive_seconds: float = SSE_KEEPALIVE_SECONDS,
) -> AsyncIterator[str]:
    """Yield SSE frames for one drawing: current state first, then live updates
    interleaved with keepalive comments.

    The stream ends when the subscription is exhausted (in production
    :func:`subscribe_drawing_status` never ends, so the stream lives for the
    connection's lifetime; tests inject a finite generator so it terminates).
    """
    # 1. Current state as the very first event.
    yield format_sse_event(
        DrawingStatusSSEEvent(
            drawing_id=str(drawing_id),
            state=current_state,  # type: ignore[arg-type]
            timestamp=_now_iso(),
        )
    )

    agen = subscribe(drawing_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(
                    agen.__anext__(), timeout=keepalive_seconds
                )
            except asyncio.TimeoutError:
                # 3. Keepalive comment (ignored by EventSource, keeps proxies open).
                yield ": keepalive\n\n"
                continue
            except StopAsyncIteration:
                break
            # 2. Forward the published transition.
            yield format_sse_event(event)
    finally:
        aclose = getattr(agen, "aclose", None)
        if aclose is not None:
            await aclose()


__all__ = [
    "SSE_KEEPALIVE_SECONDS",
    "format_sse_event",
    "drawing_status_event_stream",
]
