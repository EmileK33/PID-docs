"""``run_ml_inference`` Celery task — the ML worker entry point (US-008/010/011).

[LOAD-BEARING] The registered task name is ``app.workers.ml.tasks.run_ml_inference``
(the module-derived default — do NOT set a custom ``name=``). S2-B hard-codes this
exact string at enqueue time (``celery_app.send_task('app.workers.ml.tasks.run_ml_inference', ...)``).
Routing to the durable ``ml_inference`` queue is pinned via the ``queue=`` task
option (the auto name does not match the ``ml_inference.*`` route prefix), so the
job lands on the GPU queue regardless of the prefix router.

State machine leg (§1.3): ``Processing -> Complete | Failed``.

* Success path (task body): download → infer → atomically persist + transition
  ``Complete`` → publish SSE → emit ``processing_complete``.
* Failure path (:meth:`MLInferenceTask.on_failure`, fires once after the single
  automatic retry is exhausted): transition ``Failed`` → publish SSE → emit
  ``processing_failed``.

This split guarantees ``processing_complete`` and ``processing_failed`` are never
both emitted in one task execution (US-010 AC-3): the body only reaches the
complete-emit on success, and ``on_failure`` only runs when the body raised on
the final attempt.

§1.4 rule 5: ``user_id`` is read from the job payload ONLY. There is no DB/session
lookup for ``user_id`` anywhere in this module (or in ``inference`` /
``result_persistence``).
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from celery.signals import worker_process_init

from app.analytics.events import emit_processing_complete, emit_processing_failed
from app.config import settings
from app.db.models.drawing import Drawing
from app.db.session import SessionLocal
from app.redis.client import close_redis
from app.redis.pubsub import publish_drawing_status
from app.schemas.contracts import DrawingStatusSSEEvent
from app.workers.base import BaseTask
from app.workers.celery_app import celery_app
from app.workers.ml.inference import run_inference
from app.workers.ml.model_loader import download_s3_bytes, load_model, warm_model_cache
from app.workers.ml.result_persistence import persist_inference_results
# S1-D's queues module exports the queue constant as QUEUE_ML (string "ml_inference");
# re-export under the contract name so S2-B and tests can reference ML_INFERENCE_QUEUE.
from app.workers.queues import QUEUE_ML as ML_INFERENCE_QUEUE

logger = logging.getLogger("pid.workers.ml.tasks")

PROCESSING_STATE = "Processing"
COMPLETE_STATE = "Complete"
FAILED_STATE = "Failed"

# soft_time_limit raises SoftTimeLimitExceeded inside the task so cleanup/retry can
# run; the hard time_limit (soft + 60s) is the SIGKILL backstop (§1.9, US-008 AC-5).
_SOFT_TIME_LIMIT = settings.ML_JOB_TIMEOUT_SECONDS
_HARD_TIME_LIMIT = settings.ML_JOB_TIMEOUT_SECONDS + 60


class DrawingNotFoundError(Exception):
    """Raised when the job's ``drawing_id`` has no row (deleted mid-flight).

    Surfaced so the task fails loudly (US-008 AC-7) — ``on_failure`` re-checks the
    row and, finding it absent, emits no analytics and corrupts no state.
    """


# ---------------------------------------------------------------------------
# Payload helpers — user_id comes from the payload only (§1.4 rule 5).
# ---------------------------------------------------------------------------
def _as_dict(payload: Any) -> dict:
    if isinstance(payload, dict):
        return payload
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    return dict(payload)


def _coerce_uuid(value: Any) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _normalize_page_range(raw: Any) -> Optional[tuple[int, int]]:
    """JSON serialises the optional ``page_range`` as a 2-list; normalise to a tuple."""
    if not raw:
        return None
    return (int(raw[0]), int(raw[1]))


def _utc_now_iso() -> str:
    """ISO 8601 UTC timestamp for the SSE event (§1.11 DrawingStatusSSEEvent)."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Side-effect helpers (run only AFTER a durable commit).
# ---------------------------------------------------------------------------
async def _apublish(drawing_id: str, event: DrawingStatusSSEEvent) -> None:
    # publish_drawing_status is async and the Celery task is sync; each invocation
    # runs on a fresh loop, so close the loop-bound Redis client afterwards (the
    # async client is bound to the loop that created it — see S1-D close_redis).
    try:
        await publish_drawing_status(str(drawing_id), event)
    finally:
        await close_redis()


def _publish_status_safe(drawing_id: str, state: str) -> None:
    """Publish the drawing-status SSE event; never undo a committed transition.

    The transition is already durable in the DB before this runs (§ critical
    notes: SSE after commit). A Redis hiccup here is logged, not raised — re-running
    the task would only no-op (the drawing is no longer ``Processing``) and would
    skip analytics, so swallowing keeps the committed state authoritative and lets
    clients recover via the status poll fallback.
    """
    event = DrawingStatusSSEEvent(
        drawing_id=str(drawing_id), state=state, timestamp=_utc_now_iso()
    )
    try:
        asyncio.run(_apublish(drawing_id, event))
    except Exception:  # noqa: BLE001 - SSE publish must not fail a committed job
        logger.exception(
            "Failed to publish SSE status=%s for drawing %s (state already committed)",
            state,
            drawing_id,
        )


def _emit_complete_safe(user_id: Optional[str], drawing_id: str) -> None:
    """Emit ``processing_complete`` — never surfaces a failure to the worker (US-010 AC-4)."""
    if not user_id:
        logger.error(
            "Skipping processing_complete analytics for drawing %s: no user_id in payload",
            drawing_id,
        )
        return
    try:
        emit_processing_complete(user_id=user_id, drawing_id=str(drawing_id))
    except Exception:  # noqa: BLE001 - analytics failure must never surface (§1.10)
        logger.exception("processing_complete analytics emit failed for drawing %s", drawing_id)


def _emit_failed_safe(user_id: Optional[str], drawing_id: str) -> None:
    """Emit ``processing_failed`` — never surfaces a failure to the worker (US-010 AC-4)."""
    if not user_id:
        logger.error(
            "Skipping processing_failed analytics for drawing %s: no user_id in payload",
            drawing_id,
        )
        return
    try:
        emit_processing_failed(user_id=user_id, drawing_id=str(drawing_id))
    except Exception:  # noqa: BLE001 - analytics failure must never surface (§1.10)
        logger.exception("processing_failed analytics emit failed for drawing %s", drawing_id)


# ---------------------------------------------------------------------------
# Task base with the terminal-failure callback.
# ---------------------------------------------------------------------------
class MLInferenceTask(BaseTask):
    """``BaseTask`` (durable queue + acks_late) plus the ``Failed`` transition.

    ``on_failure`` fires exactly once, *after* the single automatic retry is
    exhausted (Celery semantics; verified under eager mode). Emitting
    ``processing_failed`` only here — never in the task body — keeps the event to
    one fire-after-final-attempt (§1.10 / US-010 AC-2/AC-3).
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):  # noqa: D102
        payload = _as_dict(args[0]) if args else dict(kwargs.get("payload", {}))
        drawing_id = payload.get("drawing_id")
        user_id = payload.get("user_id")
        if drawing_id is None:
            logger.error("ML task failed with no drawing_id in payload; cannot transition (%s)", exc)
            return

        logger.error("ML inference failed for drawing %s after retries: %s", drawing_id, exc)

        committed = False
        session = SessionLocal()
        try:
            drawing = session.get(Drawing, _coerce_uuid(drawing_id))
            if drawing is None:
                # Deleted mid-flight (US-008 AC-7) — nothing to transition, no analytics.
                logger.warning("Drawing %s gone at failure time; no Failed transition", drawing_id)
                return
            if drawing.processing_state != PROCESSING_STATE:
                # Race / duplicate delivery — only Processing -> Failed is valid (§1.3).
                logger.warning(
                    "Drawing %s in state %s (not Processing) at failure; skipping Failed transition",
                    drawing_id,
                    drawing.processing_state,
                )
                return
            drawing.processing_state = FAILED_STATE
            session.commit()
            committed = True
        except Exception:  # noqa: BLE001 - failure-path DB error must not mask the original
            session.rollback()
            logger.exception("Failed to transition drawing %s to Failed", drawing_id)
        finally:
            session.close()

        if committed:
            _publish_status_safe(drawing_id, FAILED_STATE)
            _emit_failed_safe(user_id, drawing_id)


# ---------------------------------------------------------------------------
# The task.
# ---------------------------------------------------------------------------
@celery_app.task(
    bind=True,
    base=MLInferenceTask,
    queue=ML_INFERENCE_QUEUE,
    autoretry_for=(Exception,),
    max_retries=1,                      # 1 automatic retry => 2 attempts total (§1.9)
    retry_kwargs={"max_retries": 1},    # override BaseTask's default of 3
    retry_backoff=False,
    retry_jitter=False,
    soft_time_limit=_SOFT_TIME_LIMIT,   # 20 min default (US-008 AC-5)
    time_limit=_HARD_TIME_LIMIT,        # soft + 60s graceful window
)
def run_ml_inference(self, payload: dict) -> None:
    """Run ML inference for one drawing and drive the Processing->Complete leg.

    On any exception the task auto-retries once; if the retry also fails,
    :meth:`MLInferenceTask.on_failure` transitions the drawing to ``Failed``.
    """
    payload = _as_dict(payload)
    drawing_id = payload.get("drawing_id")
    storage_reference = payload.get("storage_reference")
    user_id = payload.get("user_id")
    page_range = _normalize_page_range(payload.get("page_range"))

    if drawing_id is None or storage_reference is None:
        raise ValueError("MLInferenceJobPayload requires drawing_id and storage_reference")
    if not user_id:
        # §1.4 rule 5 says user_id is mandatory at enqueue; handle its absence
        # defensively so the drawing still leaves Processing rather than wedging.
        logger.error(
            "MLInferenceJobPayload for drawing %s has no user_id; analytics will be skipped",
            drawing_id,
        )

    session = SessionLocal()
    try:
        drawing = session.get(Drawing, _coerce_uuid(drawing_id))
        if drawing is None:
            raise DrawingNotFoundError(f"Drawing {drawing_id} not found")

        state = drawing.processing_state
        if state != PROCESSING_STATE:
            # Wrong state (already Complete/Failed, or terminal Scan_Failed): no-op
            # without raising so duplicate delivery can't corrupt state (§1.3, US-008 AC-7).
            logger.warning(
                "Drawing %s in state %s (not Processing); ML task no-op", drawing_id, state
            )
            return

        model = load_model()
        file_bytes = download_s3_bytes(settings.S3_BUCKET_NAME, storage_reference)
        result = run_inference(model, file_bytes, drawing_id, page_range)
        count = persist_inference_results(session, drawing_id, result, page_range)
        logger.info("Drawing %s -> Complete with %d symbols", drawing_id, count)
    except Exception:
        # Roll back any pending (uncommitted) work; persist commits atomically, so a
        # failure before/within it leaves no partial rows. Re-raise into autoretry.
        session.rollback()
        raise
    finally:
        session.close()

    # Durable past this point: publish SSE, then emit analytics. Both best-effort
    # so neither can undo the committed Complete state (US-008 AC-2, US-010 AC-1/AC-4).
    _publish_status_safe(drawing_id, COMPLETE_STATE)
    _emit_complete_safe(user_id, drawing_id)


# Eagerly warm the model in each worker process at boot (US-011 AC-2). No-op under
# eager/test execution (no worker bootstrap), so tests are unaffected.
worker_process_init.connect(warm_model_cache)


__all__ = ["run_ml_inference", "MLInferenceTask", "DrawingNotFoundError", "ML_INFERENCE_QUEUE"]
