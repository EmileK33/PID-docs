"""Drawing processing state machine (§1.3 ``DRAWING_STATE_TRANSITIONS``).

[LOAD-BEARING] Imported by S2-H (Ingest Worker), S2-I (Scan Worker) and S2-J
(ML Worker). The public surface is frozen by the handoff contract:

* :data:`DRAWING_STATE_TRANSITIONS` — verbatim mirror of the §1.3 transition map.
* :func:`is_valid_transition` — ``(from_state, to_state) -> bool``.
* :func:`transition_drawing` — ``(drawing, target_state, db, audit_user_id) ->
  Drawing``; mutates ``drawing.processing_state`` and writes an ``audit_log`` row
  in the SAME DB transaction (a failed audit write rolls back the state change).
* :class:`InvalidStateTransitionError` — raised on any transition not in the map.

``InvalidStateTransitionError`` subclasses :class:`ValueError` so callers that
expect the documented "raises ``ValueError`` on ``Scan_Failed``" behaviour and
callers that catch the named exception both succeed (``Scan_Failed`` has an empty
allowed-target list, so every transition out of it is invalid).

ML-job timeout note (§ performance): a drawing that has been ``Processing`` for
longer than ``ML_JOB_TIMEOUT_SECONDS`` (default 1200s / 20 min) is driven to
``Failed`` by the ML worker's Celery soft-time-limit handler (S2-J / S1-D base
task) — this module only validates the ``Processing -> Failed`` edge; it does
not own the timer.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.audit_log import AuditLog
from app.db.models.drawing import Drawing
from app.schemas.contracts import DrawingProcessingState

# §1.3 — verbatim mirror of the TypeScript ``DRAWING_STATE_TRANSITIONS`` constant.
# ``Scan_Failed`` is terminal (empty list → no retry permitted).
DRAWING_STATE_TRANSITIONS: dict[str, list[str]] = {
    "Pending": ["Queued", "Failed"],
    "Queued": ["Scanning", "Failed"],
    "Scanning": ["Processing", "Scan_Failed", "Failed"],
    "Processing": ["Complete", "Failed"],
    "Complete": ["Under_Review", "Queued"],
    "Under_Review": ["Queued"],
    "Failed": ["Queued"],
    "Scan_Failed": [],
}

# Action type recorded in audit_log for every state transition.
AUDIT_ACTION_STATE_TRANSITION = "drawing.state_transition"


class InvalidStateTransitionError(ValueError):
    """Raised when a state transition is not in ``DRAWING_STATE_TRANSITIONS``.

    Subclasses :class:`ValueError` so the documented "raises ``ValueError`` on
    ``Scan_Failed``" contract holds while AC-7/AC-8 (which expect this specific
    type) also pass.
    """


def is_valid_transition(from_state: str, to_state: str) -> bool:
    """Return ``True`` iff ``from_state -> to_state`` is permitted per §1.3.

    Unknown ``from_state`` values resolve to ``False`` (fail closed).
    """
    return to_state in DRAWING_STATE_TRANSITIONS.get(from_state, [])


def transition_drawing(
    drawing: Drawing,
    target_state: str,
    db: Session,
    audit_user_id: Optional[str] = None,
) -> Drawing:
    """Atomically transition ``drawing`` to ``target_state``.

    The new state and a matching ``audit_log`` row are written in the same DB
    transaction: the row is added and flushed, but the COMMIT is the caller's
    responsibility (so the enqueue-after-commit pattern in
    ``upload_complete_service`` can keep the Celery dispatch out of the DB
    transaction). A flush failure (e.g. the audit insert) propagates so the
    caller rolls back the state change too.

    Raises :class:`InvalidStateTransitionError` when the transition is not
    permitted — including any attempt to leave the terminal ``Scan_Failed``
    state.
    """
    from_state = drawing.processing_state
    if not is_valid_transition(from_state, target_state):
        raise InvalidStateTransitionError(
            f"Illegal drawing state transition {from_state!r} -> {target_state!r}"
        )

    drawing.processing_state = target_state

    audit = AuditLog(
        # Explicit id/occurred_at rather than relying on the Postgres
        # server_defaults (gen_random_uuid()/now()) so this writes cleanly under
        # any backing engine the caller hands us.
        id=uuid.uuid4(),
        user_id=uuid.UUID(audit_user_id) if audit_user_id else None,
        action_type=AUDIT_ACTION_STATE_TRANSITION,
        entity_id=drawing.id,
        entity_type="drawing",
        occurred_at=datetime.datetime.now(datetime.timezone.utc),
        event_metadata={"from_state": from_state, "to_state": target_state},
    )
    db.add(audit)
    db.flush()
    return drawing


__all__ = [
    "DRAWING_STATE_TRANSITIONS",
    "InvalidStateTransitionError",
    "is_valid_transition",
    "transition_drawing",
    "AUDIT_ACTION_STATE_TRANSITION",
]


# Keep the declared transition map aligned with the contract's Literal type at
# import time — a drift here is a silent cross-session break (S2-H/I/J).
assert set(DRAWING_STATE_TRANSITIONS) == set(DrawingProcessingState.__args__)
