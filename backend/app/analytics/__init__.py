"""Analytics emission layer (§1.10).

Typed, non-blocking PostHog emitters plus a Redis dead-letter retry queue.
Importing this package configures the PostHog SDK once (logging a single
startup warning when ``POSTHOG_API_KEY`` is absent — analytics disabled).

Public API consumed by downstream sessions::

    from app.analytics.events import emit_drawing_uploaded, ...
    from app.analytics.dead_letter import retry_dead_letter
"""
from __future__ import annotations

from .dead_letter import retry_dead_letter
from .events import (
    emit_correction_action,
    emit_drawing_uploaded,
    emit_export_downloaded,
    emit_export_initiated,
    emit_free_limit_reached,
    emit_processing_complete,
    emit_processing_failed,
    emit_subscription_downgraded,
    emit_subscription_upgraded,
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
    "retry_dead_letter",
]
