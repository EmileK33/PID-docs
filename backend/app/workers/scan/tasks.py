"""Scan Worker Celery task — the Scanning leg of US-008 (§1.3 / §1.4 / §1.11).

Dequeues from the ``scan`` queue, streams the S3 object straight into clamd
(no disk write), and drives the ``Scanning → Processing | Scan_Failed | Failed``
branch of the drawing processing state machine, publishing a
``DrawingStatusSSEEvent`` on every transition and — on a clean result —
enqueueing the downstream ML inference job.

State-machine contract (§1.3):

* **clean** → ``Processing`` → publish SSE → ``send_task`` ML inference.
* **infected** → ``Scan_Failed`` → publish SSE. **Terminal** — no retry
  (``Scan_Failed: []``); the task commits and ACKs.
* **clamd unreachable** → Celery retry (``max_retries=3``, drawing stays
  ``Scanning``); on exhaustion → ``Failed`` → publish SSE.

Cross-session boundaries deliberately decoupled at runtime (no Python import):

* ML dispatch uses ``celery_app.send_task("backend.app.workers.ml.tasks.
  run_ml_inference", ...)`` — a *string* name (§1.4 rule 14) so there is no
  import cycle with S2-J.
* ``user_id`` flows straight from the inbound payload into the ML payload and is
  **never** looked up in the DB (§1.4 rule 5) — a deleted user must still yield
  the correct ``user_id`` in emitted events.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from celery.exceptions import MaxRetriesExceededError
from pydantic import BaseModel

from app.config import settings
from app.redis.client import close_redis
from app.redis.pubsub import publish_drawing_status
from app.schemas.contracts import DrawingStatusSSEEvent, MLInferenceJobPayload
from app.storage.s3_client import get_s3_client
from app.workers.base import BaseTask
from app.workers.celery_app import celery_app
from app.workers.queues import QUEUE_ML, QUEUE_SCAN
from app.workers.scan.clamav_client import ClamAVClient, ClamAVConnectionError

logger = logging.getLogger(__name__)

# Registered task name — LOAD-BEARING. S2-H enqueues against this exact string
# (see Output/handoff), so it must not change even though the import root is
# ``app.`` rather than ``backend.app.``.
SCAN_TASK_NAME = "backend.app.workers.scan.tasks.scan_drawing"
# ML inference task is dispatched by string name only (§1.4 rule 14) — importing
# S2-J's task function here would create a load-time circular import.
ML_TASK_NAME = "backend.app.workers.ml.tasks.run_ml_inference"

RETRY_COUNTDOWN_SECONDS = 30
MAX_RETRIES = 3

# State-machine literals (§1.3).
STATE_SCANNING = "Scanning"
STATE_PROCESSING = "Processing"
STATE_SCAN_FAILED = "Scan_Failed"
STATE_FAILED = "Failed"


class ScanJobPayload(BaseModel):
    """Inbound ``scan`` queue payload (written by S2-H, §1.4 rule 5).

    [LOAD-BEARING] Field names are a cross-session contract — S2-H enqueues with
    exactly these keys; do not rename ``drawing_id`` / ``storage_reference`` /
    ``user_id``.
    """

    drawing_id: str
    storage_reference: str
    user_id: str


def _session_factory():
    """Open a DB session.

    Imported lazily so module load never touches ``app.db.session`` — that
    module constructs the engine for the raw ``postgresql://`` URL, eagerly
    resolving the psycopg2 dialect, which is not installed in the bare-pytest
    gate. Tests patch this seam to a SQLite-backed session.
    """
    from app.db.session import SessionLocal

    return SessionLocal()


def _clamav_client() -> ClamAVClient:
    """Build a ClamAV client (host/port from env, defaults applied silently)."""
    return ClamAVClient()


def _utc_now_iso() -> str:
    # ISO 8601 UTC with an explicit offset — never naive utcnow() (§ critical
    # notes), which silently drops tz info for SSE consumers.
    return datetime.now(timezone.utc).isoformat()


def _emit_status(drawing_id: str, state: str) -> None:
    """Publish a ``DrawingStatusSSEEvent`` to ``drawing:status:{drawing_id}``.

    ``publish_drawing_status`` is async (S1-D); the sync Celery task drives it on
    a private event loop via ``asyncio.run``. The async Redis client (S1-D) is a
    singleton bound to the loop that created it, so we close it afterwards —
    otherwise the *next* task's fresh ``asyncio.run`` loop would reuse a client
    attached to this now-closed loop. Called only *after* the DB commit so a
    failed commit never produces phantom client state.
    """
    event = DrawingStatusSSEEvent(
        drawing_id=drawing_id, state=state, timestamp=_utc_now_iso()
    )

    async def _publish_then_close() -> None:
        try:
            await publish_drawing_status(drawing_id, event)
        finally:
            await close_redis()

    asyncio.run(_publish_then_close())


def _commit_state_and_publish(session, drawing, state: str) -> None:
    """Atomically persist ``state`` then publish the SSE event (commit first)."""
    drawing.processing_state = state
    session.commit()
    _emit_status(str(drawing.id), state)


@celery_app.task(bind=True, base=BaseTask, name=SCAN_TASK_NAME, queue=QUEUE_SCAN)
def scan_drawing(self, payload: dict) -> None:
    """Scan one drawing's stored file and advance the state machine.

    Idempotent: if the drawing is not in ``Scanning`` (duplicate delivery,
    re-queued after partial success) the task no-ops — no DB mutation, no SSE
    publish, no ML enqueue (AC-16).
    """
    data = ScanJobPayload(**payload)
    session = _session_factory()
    try:
        from app.db.models.drawing import Drawing

        drawing = session.get(Drawing, uuid.UUID(data.drawing_id))
        if drawing is None:
            logger.warning("scan_drawing: drawing %s not found; no-op", data.drawing_id)
            return
        if drawing.processing_state != STATE_SCANNING:
            logger.warning(
                "scan_drawing: drawing %s not in Scanning (state=%s); no-op",
                data.drawing_id,
                drawing.processing_state,
            )
            return

        # Stream the S3 object straight into clamd — never buffered to disk.
        s3 = get_s3_client()
        body = s3.get_object(
            Bucket=settings.S3_BUCKET_NAME, Key=data.storage_reference
        )["Body"]

        try:
            result = _clamav_client().scan_stream(body)
        except ClamAVConnectionError as exc:
            # Transient: drive Celery's retry. The drawing stays Scanning. On
            # the final attempt self.retry raises MaxRetriesExceededError, which
            # we catch to transition to Failed rather than letting it re-queue.
            try:
                raise self.retry(
                    exc=exc,
                    countdown=RETRY_COUNTDOWN_SECONDS,
                    max_retries=MAX_RETRIES,
                )
            except MaxRetriesExceededError:
                logger.error(
                    "scan_drawing: clamd unreachable after %d retries for %s",
                    MAX_RETRIES,
                    data.drawing_id,
                )
                _commit_state_and_publish(session, drawing, STATE_FAILED)
                return

        if result.clean:
            _commit_state_and_publish(session, drawing, STATE_PROCESSING)
            ml_payload = MLInferenceJobPayload(
                storage_reference=data.storage_reference,
                drawing_id=data.drawing_id,
                user_id=data.user_id,  # straight from the payload, never the DB
                page_range=None,
            )
            celery_app.send_task(
                ML_TASK_NAME,
                args=[ml_payload.model_dump()],
                queue=QUEUE_ML,
            )
        else:
            # Malware detected → terminal Scan_Failed. No retry of any kind.
            logger.warning(
                "scan_drawing: malware detected in drawing %s: %s",
                data.drawing_id,
                result.infection,
            )
            _commit_state_and_publish(session, drawing, STATE_SCAN_FAILED)
    finally:
        session.close()


__all__ = ["scan_drawing", "ScanJobPayload", "QUEUE_SCAN", "QUEUE_ML", "ClamAVConnectionError"]
