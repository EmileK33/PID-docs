"""Ingest Worker Celery task + orchestration (S2-H).

Pipeline for one uploaded drawing (§1.4 rule 3, §1.3, §1.11, §1.13 P0):

1. **State-machine guard** — only a ``Queued`` drawing is processed; any other
   state is a no-op (prevents double-processing on redelivery / re-enqueue).
2. **Queued → Scanning** — DB write + Redis publish *before* any file op, so the
   drawing is never stuck in ``Queued`` with processing under way.
3. **Download** the stored object from S3.
4. **Re-verify** the SHA-256 (gate 1) and re-check the blocklist (gate 2). Either
   failure → ``Scanning → Scan_Failed`` (terminal; no scan job, no Celery retry).
5. **Detect format** from magic bytes. Unsupported → ``Scanning → Failed``.
6. **PDF** → read page count, keep the original key. **DWG** → convert via the
   ODA sandbox, upload the PDF to ``converted/{drawing_id}/drawing.pdf``, create
   a new ``StoredFile`` + repoint ``drawing.stored_file_id`` in one transaction,
   read the converted page count. ODA failure → ``Scanning → Failed``.
7. **Enqueue** the scan job on the ``scan`` queue via string-based dispatch,
   passing ``user_id`` through verbatim from the ingest payload (never a DB
   lookup — §1.4 rule 5).

State / retry discipline:

* Business failures (mismatch, blocked, unsupported, ODA failure on a valid DWG)
  set a terminal/failed state and ``return`` — they must NOT raise, so Celery's
  ``autoretry_for`` does not re-run them.
* Transient infra errors (S3 / DB / Docker daemon) propagate and are retried by
  ``BaseTask`` (S1-D).
* A Redis publish failure is logged and swallowed — it never fails the task
  (S2-B's SSE handler has a 10-second polling fallback).
"""
from __future__ import annotations

import asyncio
import io
import logging
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

from pypdf import PdfReader

from app.db.models.drawing import Drawing
from app.db.models.stored_file import StoredFile
from app.db.session import SessionLocal
from app.redis.client import close_redis
from app.redis.pubsub import publish_drawing_status
from app.schemas.contracts import DrawingStatusSSEEvent
from app.storage.hashing import compute_sha256_stream
from app.storage.s3_client import get_s3_client, put_object
from app.workers.base import BaseTask
from app.workers.celery_app import celery_app
from app.workers.ingest.format_detect import detect_format
from app.workers.ingest.hash_reverify import reverify_hash
from app.workers.ingest.oda_converter import ODAConversionError, convert_dwg_to_pdf
from app.workers.queues import QUEUE_SCAN

logger = logging.getLogger("pid.workers.ingest")

# [LOAD-BEARING] Celery task name string — S2-B (string-based enqueue fallback)
# and S4-A (E2E) depend on it. Must NOT change after merge.
INGEST_TASK_NAME = "workers.ingest.tasks.ingest_task"

# [LOAD-BEARING] Cross-session contract: the scan worker (S2-I) registers this
# task name; the queue name is the §1.11 constant from S1-D.
SCAN_TASK_NAME = "workers.scan.tasks.scan_task"

# Deterministic key for the converted PDF of a DWG (US-003-AC-6).
CONVERTED_KEY_TEMPLATE = "converted/{drawing_id}/drawing.pdf"


# ── Payload contract ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class IngestJobPayload:
    """Ingest job kwargs produced by S2-B's upload-complete handler.

    ``user_id`` is set at enqueue time by the authenticated API layer (§1.4
    rule 5) and is passed through to the scan job unchanged.
    """

    drawing_id: str
    user_id: str
    stored_file_id: str
    storage_reference: str


# ── Small helpers (each is a test seam) ───────────────────────────────────────
def _utc_now_iso() -> str:
    """ISO 8601 UTC timestamp with a trailing ``Z`` (the §1.1 SSE contract)."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _publish_status(drawing_id: str, state: str) -> None:
    """Publish a ``DrawingStatusSSEEvent`` to ``drawing:status:{drawing_id}``.

    Bridges the async S1-D ``publish_drawing_status`` from this synchronous
    Celery task. A publish failure is logged and swallowed — it must never fail
    or retry the task (US-008-AC-2; §1.11).
    """
    event = DrawingStatusSSEEvent(
        drawing_id=drawing_id, state=state, timestamp=_utc_now_iso()
    )

    async def _run() -> None:
        try:
            await publish_drawing_status(drawing_id, event)
        finally:
            # The async Redis client is bound to the loop that created it; close
            # it so the next sync invocation gets a fresh client on a new loop.
            await close_redis()

    try:
        asyncio.run(_run())
    except Exception:  # noqa: BLE001 — pub/sub failure is non-fatal by contract.
        logger.exception(
            "Failed to publish drawing-status event (drawing_id=%s, state=%s); "
            "continuing — SSE has a polling fallback.",
            drawing_id,
            state,
        )


def _download_file_bytes(bucket: str, object_key: str) -> bytes:
    """Download the full object body from S3 into memory."""
    s3 = get_s3_client()
    response = s3.get_object(Bucket=bucket, Key=object_key)
    return response["Body"].read()


def _read_pdf_page_count(pdf_bytes: bytes) -> int:
    """Return the page count of a PDF using pypdf (the only allowed PDF lib)."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return len(reader.pages)


def _enqueue_scan_job(*, drawing_id: str, user_id: str, storage_reference: str) -> None:
    """Enqueue the scan job via string-based dispatch (no import of S2-I).

    ``user_id`` is forwarded verbatim from the ingest payload (§1.4 rule 5).
    """
    celery_app.send_task(
        SCAN_TASK_NAME,
        kwargs={
            "drawing_id": drawing_id,
            "user_id": user_id,
            "storage_reference": storage_reference,
        },
        queue=QUEUE_SCAN,
    )


@contextmanager
def _session_scope() -> Iterator["object"]:
    """Yield a task-scoped SQLAlchemy session, always closed on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _transition(db, drawing: Drawing, drawing_id: str, state: str) -> None:
    """Persist a state transition then publish the SSE event (in that order)."""
    drawing.processing_state = state
    db.commit()
    _publish_status(drawing_id, state)


# ── Core orchestration (called by the Celery task; directly unit-tested) ──────
def _run_ingest(payload: IngestJobPayload, db) -> None:
    """Run the full ingest pipeline for one drawing against session ``db``."""
    drawing = db.get(Drawing, uuid.UUID(payload.drawing_id))
    if drawing is None:
        logger.warning("Ingest no-op: drawing %s not found.", payload.drawing_id)
        return

    # State-machine guard (§1.3): only a Queued drawing is processed. This makes
    # the task a no-op on redelivery, on a Scanning/later drawing, and on a
    # terminal Scan_Failed drawing (US-008-AC-3, US-009-AC-2).
    if drawing.processing_state != "Queued":
        logger.warning(
            "Ingest no-op: drawing %s is in state %s, not Queued.",
            payload.drawing_id,
            drawing.processing_state,
        )
        return

    # Queued → Scanning BEFORE any file operation (§1.4 rule 3, US-008-AC-1).
    _transition(db, drawing, payload.drawing_id, "Scanning")

    stored_file = db.get(StoredFile, uuid.UUID(payload.stored_file_id))
    if stored_file is None:
        # Data-integrity problem; transient/business boundary is unclear, so let
        # it propagate for a retry rather than silently failing.
        raise RuntimeError(
            f"stored_file {payload.stored_file_id} missing for drawing "
            f"{payload.drawing_id}"
        )

    bucket = stored_file.bucket
    object_key = payload.storage_reference

    # Download (transient errors here propagate → Celery retry).
    file_bytes = _download_file_bytes(bucket, object_key)

    # Gate 1 (integrity) + Gate 2 (blocklist) — both → Scan_Failed (terminal).
    verdict = reverify_hash(file_bytes, stored_file.sha256_hash, db)
    if verdict in ("mismatch", "blocked"):
        logger.warning(
            "Drawing %s failed hash re-verification (%s) → Scan_Failed.",
            payload.drawing_id,
            verdict,
        )
        _transition(db, drawing, payload.drawing_id, "Scan_Failed")
        # P1 STUB: emit ingest_failed analytics event here
        return  # Terminal: no scan job, no Celery retry.

    # Format detection from magic bytes (US-003-AC-3).
    file_format = detect_format(file_bytes)
    if file_format == "unsupported":
        logger.warning(
            "Drawing %s has an unsupported file format → Failed.",
            payload.drawing_id,
        )
        _transition(db, drawing, payload.drawing_id, "Failed")
        # P1 STUB: emit ingest_failed analytics event here
        return

    if file_format == "pdf":
        # No conversion: read page count, keep the original key.
        drawing.page_count = _read_pdf_page_count(file_bytes)
        db.commit()
        ready_storage_reference = object_key
    else:  # "dwg" — convert via the ODA sandbox.
        try:
            pdf_bytes = convert_dwg_to_pdf(file_bytes, payload.drawing_id)
        except ODAConversionError:
            logger.warning(
                "ODA conversion failed for drawing %s → Failed.",
                payload.drawing_id,
            )
            db.rollback()
            _transition(db, drawing, payload.drawing_id, "Failed")
            # P1 STUB: emit ingest_failed analytics event here
            return

        converted_key = CONVERTED_KEY_TEMPLATE.format(drawing_id=payload.drawing_id)
        # Upload first; if the DB transaction below fails the S3 object is an
        # orphan (acceptable — S3 lifecycle policy reclaims it).
        put_object(bucket, converted_key, pdf_bytes, "application/pdf")

        # Single transaction: new StoredFile + repoint drawing + page_count.
        new_stored_file = StoredFile(
            id=uuid.uuid4(),
            bucket=bucket,
            object_key=converted_key,
            sha256_hash=compute_sha256_stream(io.BytesIO(pdf_bytes)),
            file_type="pdf",
            size_bytes=len(pdf_bytes),
        )
        db.add(new_stored_file)
        db.flush()  # assign new_stored_file.id
        drawing.stored_file_id = new_stored_file.id
        drawing.page_count = _read_pdf_page_count(pdf_bytes)
        db.commit()
        ready_storage_reference = converted_key

    # Enqueue the scan job (user_id forwarded verbatim — §1.4 rule 5).
    _enqueue_scan_job(
        drawing_id=payload.drawing_id,
        user_id=payload.user_id,
        storage_reference=ready_storage_reference,
    )
    logger.info(
        "Ingest complete for drawing %s; scan job enqueued (ref=%s).",
        payload.drawing_id,
        ready_storage_reference,
    )


# ── Celery task ───────────────────────────────────────────────────────────────
@celery_app.task(name=INGEST_TASK_NAME, base=BaseTask, bind=True)
def ingest_task(  # noqa: D401 — Celery task.
    self,
    *,
    drawing_id: str,
    user_id: str,
    stored_file_id: str,
    storage_reference: str,
) -> None:
    """[LOAD-BEARING] Ingest one uploaded drawing. Routed to the ``ingest`` queue.

    Called by S2-B as ``ingest_task.apply_async(kwargs={...})``. Opens a
    task-scoped DB session and delegates to :func:`_run_ingest`.
    """
    payload = IngestJobPayload(
        drawing_id=drawing_id,
        user_id=user_id,
        stored_file_id=stored_file_id,
        storage_reference=storage_reference,
    )
    with _session_scope() as db:
        _run_ingest(payload, db)


__all__ = [
    "ingest_task",
    "INGEST_TASK_NAME",
    "SCAN_TASK_NAME",
    "IngestJobPayload",
    "CONVERTED_KEY_TEMPLATE",
]
