"""S2-B — Drawing-status SSE acceptance tests (US-008).

Run:  pytest tests/integration/test_drawings_sse.py -v --tb=short

Self-contained at the infrastructure level (no Docker / live Redis): the
``GET /drawings/{id}/status`` HTTP concerns (auth, ownership, content-type, the
mandatory first event) reuse the SQLite + fakeredis + TestClient harness from
``test_drawings_api`` (the ``Harness`` / ``h`` fixture). The Redis-pub/sub
forwarding and keepalive behaviour are driven against the SSE async generator
directly via :func:`asyncio.run`, with an injected finite async iterator standing
in for S1-D's ``subscribe_drawing_status`` — so no real broker is needed.

``app.*`` stays out of sys.modules during collection: the shared harness imports
it lazily, and the SSE-generator imports live inside the test bodies.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import AsyncIterator

import pytest

# Ensure tests/integration is importable so the shared harness resolves, and the
# backend/repo roots are on the path (mirrors test_drawings_api's bootstrap).
_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parents[1]
for _p in (str(_HERE), str(REPO_ROOT), str(REPO_ROOT / "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Reuse the API harness (sets env, registers the SQLite type shims, exposes the
# `h` fixture + insert helpers). Importing this module does NOT import app.*.
from test_drawings_api import Harness, _ABC_SHA256, h  # noqa: E402,F401


async def _aiter(events) -> AsyncIterator:
    """Finite async iterator yielding the given events then completing."""
    for event in events:
        yield event


async def _never(_drawing_id) -> AsyncIterator:
    """A subscription that never yields (used to exercise the keepalive path)."""
    await asyncio.sleep(3600)
    yield  # pragma: no cover


def _sse(drawing_id):
    """Build a DrawingStatusSSEEvent the way a worker would publish one."""
    from app.schemas.contracts import DrawingStatusSSEEvent

    return DrawingStatusSSEEvent(
        drawing_id=str(drawing_id), state="Processing", timestamp="2024-01-15T10:30:00Z"
    )


# ===========================================================================
# US-008 AC-1 / AC-2 — stream established, first event = current state
# ===========================================================================
def test_sse_status_stream_established_with_initial_event(h):
    user = h.add_user(role="user")
    drawing = h.add_drawing(owner_user_id=user.id, state="Scanning")

    import app.sse.drawing_status as sse

    # Use an empty subscription so the stream terminates after the first event.
    def _empty_sub(_id):
        return _aiter([])

    async def _collect():
        frames = []
        async for frame in sse.drawing_status_event_stream(
            str(drawing.id), "Scanning", subscribe=_empty_sub
        ):
            frames.append(frame)
        return frames

    frames = asyncio.run(_collect())
    assert len(frames) == 1
    assert frames[0].startswith("data: ")
    payload = json.loads(frames[0][len("data: ") :].strip())
    assert payload["drawing_id"] == str(drawing.id)
    assert payload["state"] == "Scanning"  # current state delivered first
    assert "timestamp" in payload


def test_sse_event_shape_matches_contract(h):
    import app.sse.drawing_status as sse

    drawing_id = "550e8400-e29b-41d4-a716-446655440000"

    def _sub(_id):
        return _aiter([_sse(drawing_id)])

    async def _collect():
        return [
            frame
            async for frame in sse.drawing_status_event_stream(
                drawing_id, "Queued", subscribe=_sub
            )
        ]

    frames = asyncio.run(_collect())
    # First = current state, second = the forwarded worker event.
    forwarded = json.loads(frames[1][len("data: ") :].strip())
    assert set(forwarded.keys()) == {"drawing_id", "state", "timestamp"}
    assert forwarded == {
        "drawing_id": drawing_id,
        "state": "Processing",
        "timestamp": "2024-01-15T10:30:00Z",
    }


# ===========================================================================
# US-008 AC-3 — Redis pub/sub events are forwarded
# ===========================================================================
def test_sse_forwards_redis_pubsub_event(h):
    import app.sse.drawing_status as sse

    drawing_id = "11111111-1111-1111-1111-111111111111"
    published = [
        _sse(drawing_id),
        sse.DrawingStatusSSEEvent(
            drawing_id=drawing_id, state="Complete", timestamp="2024-01-15T10:31:00Z"
        ),
    ]

    def _sub(_id):
        assert _id == drawing_id  # subscribes to exactly this drawing's channel
        return _aiter(published)

    async def _collect():
        return [
            frame
            async for frame in sse.drawing_status_event_stream(
                drawing_id, "Scanning", subscribe=_sub
            )
        ]

    frames = asyncio.run(_collect())
    states = [json.loads(f[len("data: ") :].strip())["state"] for f in frames]
    # current state, then both forwarded transitions, in order.
    assert states == ["Scanning", "Processing", "Complete"]


# ===========================================================================
# US-008 AC-4 — keepalive within 10 seconds
# ===========================================================================
def test_sse_sends_keepalive_within_10_seconds():
    import app.sse.drawing_status as sse

    # Contract: the documented fallback interval is 10s.
    assert sse.SSE_KEEPALIVE_SECONDS == 10

    async def _collect():
        frames = []
        gen = sse.drawing_status_event_stream(
            "drawing-x", "Processing", subscribe=_never, keepalive_seconds=0.05
        )
        async for frame in gen:
            frames.append(frame)
            # First the initial event, then at least one keepalive comment.
            if len(frames) >= 2:
                await gen.aclose()
                break
        return frames

    frames = asyncio.run(_collect())
    assert frames[0].startswith("data: ")
    assert any(f.startswith(": ") for f in frames[1:]), "expected a keepalive comment"


# ===========================================================================
# US-008 AC-5 / AC-6 — auth & ownership over HTTP
# ===========================================================================
def test_sse_unauthenticated_returns_401(h):
    user = h.add_user(role="user")
    drawing = h.add_drawing(owner_user_id=user.id, state="Pending")
    resp = h.client.get(f"/drawings/{drawing.id}/status")
    assert resp.status_code == 401


def test_sse_wrong_owner_returns_403(h):
    owner = h.add_user(role="user")
    other = h.add_user(role="user")
    drawing = h.add_drawing(owner_user_id=owner.id, state="Pending")
    resp = h.client.get(
        f"/drawings/{drawing.id}/status", headers=h.auth(other)
    )
    assert resp.status_code == 403


def test_sse_status_content_type_and_first_event_over_http(h, monkeypatch):
    """End-to-end: the endpoint returns text/event-stream and the current state
    as the first event. The Redis subscription is patched to a finite iterator
    so the HTTP stream terminates for the test client."""
    import app.sse.drawing_status as sse

    user = h.add_user(role="user")
    drawing = h.add_drawing(owner_user_id=user.id, state="Processing")

    monkeypatch.setattr(sse, "subscribe_drawing_status", lambda _id: _aiter([]))

    with h.client.stream(
        "GET", f"/drawings/{drawing.id}/status", headers=h.auth(user)
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = "".join(resp.iter_text())

    first = body.split("\n\n")[0]
    assert first.startswith("data: ")
    payload = json.loads(first[len("data: ") :].strip())
    assert payload["drawing_id"] == str(drawing.id)
    assert payload["state"] == "Processing"


# ===========================================================================
# US-008 AC-7 / AC-8 — state machine validity (also covered in API suite)
# ===========================================================================
def test_state_machine_rejects_invalid_transition():
    from app.services.drawing_state_machine import (
        InvalidStateTransitionError,
        is_valid_transition,
    )

    assert is_valid_transition("Scanning", "Processing") is True
    assert is_valid_transition("Complete", "Processing") is False
    assert issubclass(InvalidStateTransitionError, ValueError)


def test_state_machine_scan_failed_terminal(h):
    from app.services.drawing_state_machine import (
        InvalidStateTransitionError,
        transition_drawing,
    )

    user = h.add_user(role="user")
    drawing = h.add_drawing(owner_user_id=user.id, state="Scan_Failed")
    with pytest.raises(InvalidStateTransitionError):
        transition_drawing(drawing, "Queued", h.session)
