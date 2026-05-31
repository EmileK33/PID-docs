"""Typed, non-blocking analytics event emitters — the nine MVP events (§1.10).

[LOAD-BEARING] Function signatures are consumed by Phase 2 sessions (S2-A..F,
S2-J). Each ``emit_*`` builds a payload with EXACTLY the field names mandated by
the §1.10 event-contract table, generates the server-side UTC timestamp, and
hands off to PostHog via the non-blocking, never-raising send path. On send
failure the event is routed to the Redis dead-letter queue.

Non-negotiable constraints (§1.10):

* Non-blocking — emitters return synchronously (PostHog capture is async-batched).
* Swallow all exceptions — analytics failure must never surface to a user.
* Server-side timestamps — emitters do NOT accept a ``timestamp`` parameter.
* ``user_id`` is supplied by the caller (the distinct_id); NO DB lookup is
  performed — mandatory for worker-emitted ``processing_*`` events (§1.4 rule 5).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

# Read-only import from S0-A contracts: the export-format Literal. Relative so
# this package imports cleanly under both roots (see posthog_client.py note).
from ..schemas.contracts import ExportFormat

from . import dead_letter, posthog_client

logger = logging.getLogger("pid.analytics")

_VALID_EXPORT_FORMATS: tuple[str, ...] = ("csv", "xlsx")


def _utc_timestamp() -> str:
    """ISO 8601 UTC timestamp with timezone suffix (``+00:00``), server-side."""
    return datetime.now(timezone.utc).isoformat()


def _emit(event: str, user_id: str, properties: dict[str, Any]) -> None:
    """Shared non-blocking emit path.

    Prepends the server-generated ``timestamp`` and ``user_id`` to the
    event-specific ``properties``, uses ``user_id`` as the PostHog distinct_id,
    and routes to the dead-letter queue if the capture call fails. When
    analytics is disabled this is a pure no-op (no dead-letter write — there is
    no recipient). Always returns ``None``.
    """
    if not posthog_client.is_enabled():
        return

    props: dict[str, Any] = {"timestamp": _utc_timestamp(), "user_id": user_id}
    props.update(properties)

    if not posthog_client.send_event(event, user_id, props):
        dead_letter.push_to_dead_letter(
            {"event": event, "distinct_id": user_id, "properties": props}
        )


# ---------------------------------------------------------------------------
# The nine MVP events (§1.10). Payload field names are verbatim from the spec.
# ---------------------------------------------------------------------------
def emit_drawing_uploaded(user_id: str, drawing_id: str) -> None:
    """Drawing transitioned to ``Queued`` after upload-complete."""
    _emit("drawing_uploaded", user_id, {"drawing_id": drawing_id})


def emit_processing_complete(user_id: str, drawing_id: str) -> None:
    """Drawing transitioned to ``Complete``. ``user_id`` comes from the job
    payload (§1.4 rule 5) — never a DB/session lookup in the worker."""
    _emit("processing_complete", user_id, {"drawing_id": drawing_id})


def emit_processing_failed(user_id: str, drawing_id: str) -> None:
    """Drawing transitioned to ``Failed`` (after the one automatic retry)."""
    _emit("processing_failed", user_id, {"drawing_id": drawing_id})


def emit_correction_action(user_id: str, drawing_id: str, symbol_id: str) -> None:
    """User submitted a reclassify/reject/restore/manual_add correction."""
    _emit(
        "correction_action",
        user_id,
        {"drawing_id": drawing_id, "symbol_id": symbol_id},
    )


def emit_export_initiated(
    user_id: str, drawing_id: str, export_id: str, format: ExportFormat
) -> None:
    """Export job created (sync or async).

    Rejects a ``format`` outside ``{"csv", "xlsx"}`` (§1.10 / contracts
    ``ExportFormat``) — a caller programming error surfaced eagerly, before any
    emission.
    """
    if format not in _VALID_EXPORT_FORMATS:
        raise ValueError(
            f"format must be one of {_VALID_EXPORT_FORMATS}, got {format!r}"
        )
    _emit(
        "export_initiated",
        user_id,
        {"drawing_id": drawing_id, "export_id": export_id, "format": format},
    )


def emit_export_downloaded(user_id: str, drawing_id: str, export_id: str) -> None:
    """User accessed the pre-signed download URL."""
    _emit(
        "export_downloaded",
        user_id,
        {"drawing_id": drawing_id, "export_id": export_id},
    )


def emit_free_limit_reached(
    user_id: str, drawing_id: str, subscription_id: str
) -> None:
    """Free-tier user hit the 3/month processing limit (before upgrade prompt)."""
    _emit(
        "free_limit_reached",
        user_id,
        {"drawing_id": drawing_id, "subscription_id": subscription_id},
    )


def emit_subscription_upgraded(
    user_id: str, subscription_id: str, previous_tier: str, new_tier: str
) -> None:
    """Subscription tier increased (after the tier change is applied)."""
    _emit(
        "subscription_upgraded",
        user_id,
        {
            "subscription_id": subscription_id,
            "previous_tier": previous_tier,
            "new_tier": new_tier,
        },
    )


def emit_subscription_downgraded(
    user_id: str, subscription_id: str, previous_tier: str, new_tier: str
) -> None:
    """Subscription tier decreased (fires immediately at confirmation)."""
    _emit(
        "subscription_downgraded",
        user_id,
        {
            "subscription_id": subscription_id,
            "previous_tier": previous_tier,
            "new_tier": new_tier,
        },
    )


__all__ = [
    "emit_drawing_uploaded",
    "emit_processing_complete",
    "emit_processing_failed",
    "emit_correction_action",
    "emit_export_initiated",
    "emit_export_downloaded",
    "emit_free_limit_reached",
    "emit_subscription_upgraded",
    "emit_subscription_downgraded",
]
