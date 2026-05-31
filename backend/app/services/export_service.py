"""Export lifecycle orchestration (S2-D, US-016 / US-017).

Owns the request → ``ExportRecord`` → (sync generate | async enqueue) →
pre-signed download URL flow that ``api/routers/exports.py`` exposes.

Key invariants (session brief "Critical implementation notes"):

* **Server-side threshold.** The sync-vs-async decision counts ``detected_symbol``
  rows for the drawing (§1.4 rule 15). ``<= 1000`` → synchronous; ``> 1000`` →
  async enqueue. A client-supplied count is never trusted.
* **``export_initiated`` fires after the row commits, before generation / enqueue**
  (§1.10), for *both* paths, and never from the worker.
* **Sync atomicity.** S3 upload happens outside any DB transaction; the
  ``StoredFile`` INSERT + ``ExportRecord`` UPDATE (→ ``Complete``) are then
  committed together.
* **Re-export never overwrites.** Every call INSERTs a fresh ``ExportRecord``.
* **No import of S2-K.** The worker is enqueued purely by task-name string.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.detected_symbol import DetectedSymbol
from app.db.models.export_record import ExportRecord
from app.db.models.stored_file import StoredFile
from app.schemas.contracts import ExportFormat, ExportStatus
from app.services.export_generators import (
    CSV_CONTENT_TYPE,
    XLSX_CONTENT_TYPE,
    generate_csv,
    generate_xlsx,
)
from app.storage.presigned import generate_presigned_get_url
from app.storage.s3_client import put_object
from app.workers.celery_app import celery_app

# [LOAD-BEARING] Task-name contract with S2-K (Export Worker). S2-K MUST define
# its Celery task with exactly this name. Enqueued by string so this session
# never imports the worker module and stays independently deployable.
EXPORT_TASK_NAME = "pid_analyzer.workers.export.tasks.generate_export_task"

# §1.4 rule 15 / US-017 AC-3: ``<= 1000`` symbols → sync, ``> 1000`` → async.
ASYNC_SYMBOL_THRESHOLD = 1000

logger = logging.getLogger("pid.exports")

# Analytics emitters are imported as a module so tests can spy on the bound
# attributes and so a future re-wiring stays in one place.
from app.analytics import events as analytics_events  # noqa: E402


# ---------------------------------------------------------------------------
# Request / response contracts (handoff to S3-G, S2-K, S4-A)
# ---------------------------------------------------------------------------
class ExportCreateRequest(BaseModel):
    """Body of ``POST /drawings/{id}/exports``."""

    format: ExportFormat


class ExportRecordResponse(BaseModel):
    """Serialized ``export_record`` (response of both endpoints)."""

    id: str
    drawing_id: str
    user_id: str
    format: ExportFormat
    status: ExportStatus
    initiated_at: str
    completed_at: Optional[str] = None
    download_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def export_object_key(export_id: UUID, drawing_id: UUID, fmt: ExportFormat) -> str:
    """S3 object key for an export file.

    Pattern (US-016 AC-9): ``exports/{export_id}/{drawing_id}.{format}``. The new
    per-export UUID makes keys collision-proof across re-exports.
    """
    return f"exports/{export_id}/{drawing_id}.{fmt}"


def _content_type(fmt: ExportFormat) -> str:
    return CSV_CONTENT_TYPE if fmt == "csv" else XLSX_CONTENT_TYPE


def _serialize(
    record: ExportRecord, *, download_url: Optional[str] = None
) -> ExportRecordResponse:
    return ExportRecordResponse(
        id=str(record.id),
        drawing_id=str(record.drawing_id),
        user_id=str(record.user_id),
        format=record.format,  # type: ignore[arg-type]
        status=record.status,  # type: ignore[arg-type]
        initiated_at=record.initiated_at.isoformat(),
        completed_at=record.completed_at.isoformat()
        if record.completed_at is not None
        else None,
        download_url=download_url,
    )


def _emit_initiated(
    user_id: UUID, drawing_id: UUID, export_id: UUID, fmt: ExportFormat
) -> None:
    """Fire ``export_initiated`` — non-blocking, never raises (§1.10)."""
    try:
        analytics_events.emit_export_initiated(
            user_id=str(user_id),
            drawing_id=str(drawing_id),
            export_id=str(export_id),
            format=fmt,
        )
    except Exception:  # pragma: no cover - analytics must never block the request
        logger.warning("export_initiated emit failed", exc_info=True)


def _emit_downloaded(user_id: UUID, drawing_id: UUID, export_id: UUID) -> None:
    """Fire ``export_downloaded`` — non-blocking, never raises (§1.10)."""
    try:
        analytics_events.emit_export_downloaded(
            user_id=str(user_id),
            drawing_id=str(drawing_id),
            export_id=str(export_id),
        )
    except Exception:  # pragma: no cover - analytics must never block the request
        logger.warning("export_downloaded emit failed", exc_info=True)


def _generate_bytes(db: Session, drawing_id: UUID, fmt: ExportFormat) -> bytes:
    return generate_csv(db, drawing_id) if fmt == "csv" else generate_xlsx(db, drawing_id)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def create_export(
    drawing_id: UUID, user_id: UUID, format: ExportFormat, db: Session
) -> ExportRecordResponse:
    """Create an export job for ``drawing_id`` on behalf of ``user_id``.

    The caller (router) is responsible for authentication, the drawing's
    existence (404), and ownership (403). This function evaluates the
    server-side symbol-count threshold and runs either the synchronous
    generation path (≤1000 symbols → ``Complete`` + pre-signed URL) or the async
    enqueue path (>1000 symbols → ``Queued``, worker handled by S2-K).
    """
    # 1. Server-side count — never trust a client-supplied value (§1.4 rule 15).
    symbol_count = db.execute(
        select(func.count())
        .select_from(DetectedSymbol)
        .where(DetectedSymbol.drawing_id == drawing_id)
    ).scalar_one()

    # 2. INSERT the ExportRecord in Queued state and commit BEFORE generation /
    #    enqueue (US-017 AC-4). The id is generated app-side so it can key the S3
    #    object without a DB round-trip.
    export_id = uuid.uuid4()
    record = ExportRecord(
        id=export_id,
        drawing_id=drawing_id,
        user_id=user_id,
        format=format,
        status="Queued",
        initiated_at=_now(),
    )
    db.add(record)
    db.commit()

    # 3. Analytics: after the row commits, before any generation / send_task.
    _emit_initiated(user_id, drawing_id, export_id, format)

    # 4a. Async path (> 1000 symbols): enqueue and return Queued.
    if symbol_count > ASYNC_SYMBOL_THRESHOLD:
        celery_app.send_task(
            EXPORT_TASK_NAME, kwargs={"export_id": str(export_id)}
        )
        return _serialize(record)

    # 4b. Sync path (≤ 1000 symbols): generate → hash → upload → atomically
    #     persist StoredFile + flip ExportRecord to Complete.
    data = _generate_bytes(db, drawing_id, format)
    sha256_hash = hashlib.sha256(data).hexdigest()
    object_key = export_object_key(export_id, drawing_id, format)
    content_type = _content_type(format)
    bucket = settings.S3_BUCKET_NAME

    # S3 upload is external and cannot be inside the DB transaction. On failure
    # the record stays Queued (S2-K's retry can pick it up) and we surface a 500.
    put_object(bucket, object_key, data, content_type)

    stored_file = StoredFile(
        id=uuid.uuid4(),
        bucket=bucket,
        object_key=object_key,
        sha256_hash=sha256_hash,
        file_type=content_type,
        size_bytes=len(data),
    )
    db.add(stored_file)
    record.stored_file_id = stored_file.id
    record.status = "Complete"
    record.completed_at = _now()
    db.commit()

    download_url = generate_presigned_get_url(bucket, object_key)
    return _serialize(record, download_url=download_url)


def get_export(
    export_id: UUID, user_id: UUID, db: Session
) -> ExportRecordResponse:
    """Return the export's current state for the owning user.

    Raises 404 when unknown, 403 when it belongs to another user (ownership is
    on ``export_record.user_id`` — independent of drawing access). When the
    export is ``Complete`` a *fresh* pre-signed download URL is minted and the
    ``export_downloaded`` analytics event fires.
    """
    record = db.get(ExportRecord, export_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Export not found"
        )

    if record.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
        )

    download_url: Optional[str] = None
    if record.status == "Complete" and record.stored_file_id is not None:
        stored_file = db.get(StoredFile, record.stored_file_id)
        if stored_file is not None:
            download_url = generate_presigned_get_url(
                stored_file.bucket, stored_file.object_key
            )
            _emit_downloaded(record.user_id, record.drawing_id, record.id)

    return _serialize(record, download_url=download_url)


__all__ = [
    "EXPORT_TASK_NAME",
    "ASYNC_SYMBOL_THRESHOLD",
    "ExportCreateRequest",
    "ExportRecordResponse",
    "create_export",
    "get_export",
    "export_object_key",
]
