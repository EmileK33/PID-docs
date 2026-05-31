"""Internal PostHog client wrapper (§1.7 / §1.8 / §1.10).

[INTERNAL] Not for direct downstream import — Phase 2 sessions import the typed
emitters from :mod:`app.analytics.events` and :func:`retry_dead_letter` from
:mod:`app.analytics.dead_letter`.

Responsibilities:

* Configure the module-level PostHog SDK from the §1.12 env contract
  (``POSTHOG_API_KEY`` / ``POSTHOG_HOST``), self-hosted-compatible.
* Provide :func:`send_event` — a single, non-blocking, never-raising capture
  attempt. PostHog's ``capture`` is already async-batched (a background consumer
  thread flushes), so issuing a capture returns without awaiting the network.
* Expose :func:`is_enabled` so emitters become silent no-ops when the API key is
  absent (analytics disabled per §1.12) without pushing to the dead-letter queue.

Disabled mode logs exactly one startup warning (emitted by :func:`configure`,
which runs once at import).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import posthog

# Relative so this package imports cleanly under both roots used in the repo:
# ``app.analytics`` (backend/ on path, the runtime convention) and
# ``backend.app.analytics`` (repo root on path, the documented export path).
from ..config import settings

logger = logging.getLogger("pid.analytics")

# Sentinel so callers (and tests) can distinguish "read from settings" from an
# explicit ``None``/empty override.
_UNSET: Any = object()

# Module state: whether analytics emission is active. Gated by API-key presence.
_enabled: bool = False


def configure(api_key: Optional[str] = _UNSET, host: Optional[str] = _UNSET) -> bool:
    """(Re)initialise the PostHog SDK and recompute the enabled flag.

    With no arguments, reads ``POSTHOG_API_KEY`` / ``POSTHOG_HOST`` from the
    settings singleton (the import-time call). Tests pass explicit overrides to
    toggle enabled/disabled without mutating the frozen settings object.

    Returns ``True`` when analytics is enabled. When the API key is absent or
    empty, logs a single warning, disables emission, and returns ``False``.
    """
    global _enabled

    key = settings.POSTHOG_API_KEY if api_key is _UNSET else api_key
    resolved_host = settings.POSTHOG_HOST if host is _UNSET else host

    if not key:
        _enabled = False
        # Best-effort: make the SDK itself inert too.
        try:
            posthog.api_key = None
            posthog.project_api_key = None
            posthog.disabled = True
        except Exception:  # pragma: no cover - defensive; SDK attr surface varies
            pass
        logger.warning(
            "POSTHOG_API_KEY absent or empty; analytics disabled; all emit_* "
            "calls are no-ops."
        )
        return False

    try:
        posthog.api_key = key
        # PostHog SDK 7.x reads ``project_api_key``; 3.x reads ``api_key``. Set
        # both so this works across the pinned range (``posthog>=3.0``).
        posthog.project_api_key = key
        if resolved_host:
            posthog.host = resolved_host
        posthog.disabled = False
    except Exception:  # pragma: no cover - defensive; SDK attr surface varies
        logger.warning("Failed to configure PostHog client attributes.", exc_info=True)

    _enabled = True
    return True


def is_enabled() -> bool:
    """Return whether analytics emission is currently active."""
    return _enabled


def send_event(event: str, distinct_id: str, properties: dict[str, Any]) -> bool:
    """Issue a single non-blocking PostHog capture.

    Returns ``True`` if the capture call was issued without raising, ``False``
    otherwise. Never re-raises — analytics failure must never surface to a user
    (§1.10). The caller routes ``False`` to the dead-letter queue.
    """
    if not _enabled:
        return False
    try:
        # ``user_id`` is the distinct_id for every MVP event (§1.10). Keyword
        # args keep the call unambiguous across SDK 3.x/7.x signatures.
        posthog.capture(distinct_id=distinct_id, event=event, properties=dict(properties))
        return True
    except Exception:
        logger.warning(
            "PostHog capture failed for event %r; routing to dead-letter queue.",
            event,
            exc_info=True,
        )
        return False


# Configure once at import from the environment-backed settings singleton. This
# is the single startup warning site when POSTHOG_API_KEY is absent (§1.12).
configure()
