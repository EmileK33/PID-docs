"""Async export worker — CSV/XLSX generation Celery task (S2-K, US-017).

Generates CSV and XLSX exports for drawings whose symbol count crosses the
async threshold (the >1,000-symbol gate is evaluated upstream by S2-D at enqueue
time, §1.4 rule 15 — this worker generates whatever lands on the ``export``
queue). The task:

* transitions the ``ExportRecord`` ``Queued → Generating → Complete | Failed``,
* writes a CSV/XLSX file of the drawing's non-rejected symbols to S3,
* creates a ``StoredFile`` row and links it to the ``ExportRecord`` atomically,
* publishes an ``export_complete`` / ``export_failed`` event on the Redis
  channel ``export:status:{export_id}`` (the authoritative channel defined by
  this session for S3-G and S2-D's poll endpoint).

Self-containment constraints (§ Scope):

* CSV/XLSX generation lives *here*, NOT imported from S2-D's
  ``export_generators.py`` — S2-D is a Phase-2 sibling with no prerequisite
  relationship, and the test-isolation rule requires this session to stand
  alone. Any duplication with S2-D's sync generators is intentional.
* ``csv`` stdlib for CSV, ``openpyxl`` for XLSX — no ``pandas`` (ML-worker dep).
* No analytics emitter is imported or called here (§1.10): both
  ``export_initiated`` and ``export_downloaded`` fire from the FastAPI layer
  (S2-D). Firing them here would double-count.
* Workers never call the FastAPI server; they communicate only through the DB,
  the Celery queue, and Redis channels.

Redis publish note: S1-D's ``app.redis.pubsub`` is an *async* fan-out bound to
the ``DrawingStatusSSEEvent`` schema (``drawing:status:{drawing_id}``), so it is
not usable from this synchronous Celery worker for the export channel. The
worker therefore publishes via a synchronous Redis client built from
``settings.REDIS_URL`` (the same instance, separate logical use). Publishing is
fire-and-forget and logs on failure so a Redis hiccup never spuriously fails or
retries a completed export.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

import redis as redis_sync
from openpyxl import Workbook

from app.config import settings
from app.db.models import DetectedSymbol, ExportRecord, StoredFile
from app.db.session import SessionLocal
from app.storage.presigned import export_object_key
from app.storage.s3_client import put_object
from app.storage.hashing import compute_sha256_stream
from app.workers.celery_app import celery_app

logger = logging.getLogger("pid.workers.export")

# --- Contracts -------------------------------------------------------------

# §1.1 ExportStatus state machine values.
STATUS_QUEUED = "Queued"
STATUS_GENERATING = "Generating"
STATUS_COMPLETE = "Complete"
STATUS_FAILED = "Failed"

# AC-2 / AC-3: column order is identical for CSV and the XLSX ``Symbols`` sheet.
EXPORT_COLUMNS: tuple[str, ...] = (
    "id",
    "drawing_id",
    "page_number",
    "entity_class_id",
    "subtype",
    "tag_label",
    "confidence",
    "bbox_x",
    "bbox_y",
    "bbox_w",
    "bbox_h",
    "source",
)

CONTENT_TYPE_CSV = "text/csv"
CONTENT_TYPE_XLSX = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

XLSX_SYMBOLS_SHEET = "Symbols"

# Redis pub/sub channel pattern owned by this session (consumed by S3-G + S2-D).
EXPORT_STATUS_CHANNEL = "export:status:{export_id}"
EVENT_COMPLETE = "export_complete"
EVENT_FAILED = "export_failed"

# AC-5: exactly one automatic retry, 30 s before the retry attempt.
MAX_RETRIES = 1
RETRY_COUNTDOWN_SECONDS = 30
# Hard constraint (§ Performance targets): 1 hr task time limit.
EXPORT_TASK_TIME_LIMIT_SECONDS = 3600


def _channel(export_id: str) -> str:
    return EXPORT_STATUS_CHANNEL.format(export_id=export_id)


def _utcnow_iso() -> str:
    """UTC ISO-8601 timestamp with a trailing ``Z`` (matches the AC payloads)."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# --- Row / file generation -------------------------------------------------


def _symbol_row(symbol: Any) -> list[Any]:
    """Flatten a ``DetectedSymbol`` into the export column order.

    ``bbox`` is the §1.2 JSONB shape ``{x, y, w, h}``; it is exploded into the
    four ``bbox_*`` columns.
    """
    bbox = symbol.bbox or {}
    return [
        str(symbol.id),
        str(symbol.drawing_id),
        symbol.page_number,
        symbol.entity_class_id,
        symbol.subtype,
        symbol.tag_label,
        symbol.confidence,
        bbox.get("x"),
        bbox.get("y"),
        bbox.get("w"),
        bbox.get("h"),
        symbol.source,
    ]


def generate_csv_bytes(symbols: Sequence[Any]) -> bytes:
    """Render symbols to CSV bytes: header row + one row per symbol (AC-2)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_COLUMNS)
    for symbol in symbols:
        writer.writerow(_symbol_row(symbol))
    return buffer.getvalue().encode("utf-8")


def generate_xlsx_bytes(symbols: Sequence[Any]) -> bytes:
    """Render symbols to an XLSX workbook with a ``Symbols`` sheet (AC-3)."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = XLSX_SYMBOLS_SHEET
    sheet.append(list(EXPORT_COLUMNS))
    for symbol in symbols:
        sheet.append(_symbol_row(symbol))

    # TODO P1 (US-022): add 'Tables' worksheet with table cell data
    # Expected: iterate table_cell rows for drawing_id, write to second sheet
    # Prerequisite: US-021 ML table extraction must be complete
    pass

    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


def _render(fmt: str, symbols: Sequence[Any]) -> tuple[bytes, str]:
    """Return ``(file_bytes, content_type)`` for the requested format."""
    if fmt == "csv":
        return generate_csv_bytes(symbols), CONTENT_TYPE_CSV
    if fmt == "xlsx":
        return generate_xlsx_bytes(symbols), CONTENT_TYPE_XLSX
    raise ValueError(f"unsupported export format: {fmt!r}")


# --- Redis pub/sub ---------------------------------------------------------


def _redis_client() -> Any:
    """Synchronous Redis client for export notifications (separate logical use
    of the same instance backing the Celery broker, §1.8)."""
    return redis_sync.Redis.from_url(settings.REDIS_URL)


def _event_payload(
    event: str, export_id: str, drawing_id: str, user_id: str, fmt: str
) -> dict[str, str]:
    """Build the AC-4 / AC-6 payload. ``user_id`` is the value from the task
    payload (§1.4 rule 5) — never read back from the DB."""
    return {
        "event": event,
        "export_id": str(export_id),
        "drawing_id": str(drawing_id),
        "user_id": str(user_id),
        "format": fmt,
        "timestamp": _utcnow_iso(),
    }


def publish_export_event(channel: str, payload: dict) -> None:
    """Publish ``payload`` (JSON) to ``channel``. Fire-and-forget: a publish
    failure is logged, never raised, so it cannot fail/retry a finished export
    (mirrors the S1-D ``publish_event`` contract)."""
    try:
        client = _redis_client()
        try:
            client.publish(channel, json.dumps(payload))
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()
    except Exception:  # noqa: BLE001 — notifications must not break the worker
        logger.exception("failed to publish export event to %s", channel)


# --- Persistence helpers ---------------------------------------------------


def _fetch_symbols(session: Any, drawing_id: str) -> list[Any]:
    """Non-rejected symbols for the drawing, ordered ``page_number ASC, id ASC``
    (AC-2 ordering + AC-9 ``rejected = FALSE`` filter)."""
    return (
        session.query(DetectedSymbol)
        .filter(
            DetectedSymbol.drawing_id == drawing_id,
            DetectedSymbol.rejected.is_(False),
        )
        .order_by(DetectedSymbol.page_number.asc(), DetectedSymbol.id.asc())
        .all()
    )


def _store_file(
    session: Any,
    *,
    bucket: str,
    object_key: str,
    sha256_hash: str,
    file_type: str,
    size_bytes: int,
) -> Any:
    """Create the ``StoredFile`` row, or reuse an existing one on the retry
    path (same ``export_id`` → same ``object_key``).

    The (bucket, object_key) unique constraint only fires when a prior attempt
    committed the ``StoredFile`` but failed before updating the
    ``ExportRecord``; in that case we adopt the existing row instead of
    re-inserting (AC-8 / § ``object_key`` unique-constraint note)."""
    existing = (
        session.query(StoredFile)
        .filter(
            StoredFile.bucket == bucket,
            StoredFile.object_key == object_key,
        )
        .one_or_none()
    )
    if existing is not None:
        existing.sha256_hash = sha256_hash
        existing.file_type = file_type
        existing.size_bytes = size_bytes
        return existing

    stored = StoredFile(
        bucket=bucket,
        object_key=object_key,
        sha256_hash=sha256_hash,
        file_type=file_type,
        size_bytes=size_bytes,
    )
    session.add(stored)
    session.flush()  # assign stored.id before linking it to the export record
    return stored


def _process_export(
    export_id: str,
    drawing_id: str,
    user_id: str,
    fmt: str,
    *,
    allow_generating: bool,
) -> bool:
    """Run one export attempt. Returns ``True`` if generation completed, or
    ``False`` if the task exited idempotently (duplicate delivery).

    The session is always closed in ``finally`` to avoid PgBouncer pool
    exhaustion under the Celery worker (§ silent-failure mode)."""
    session = SessionLocal()
    try:
        # AC-1: row-lock the record and inspect its status before doing work.
        record = (
            session.query(ExportRecord)
            .filter(ExportRecord.id == export_id)
            .with_for_update()
            .one_or_none()
        )
        if record is None:
            logger.warning("export %s: no export_record found; skipping", export_id)
            return False

        # Fresh delivery may only start from Queued (a Generating row is a
        # duplicate delivery → idempotent exit, AC-1). A retry of *this* task
        # (allow_generating=True) may resume a Generating row it set on the
        # prior attempt (§ status-reset-on-retry note).
        allowed_start = (
            {STATUS_QUEUED, STATUS_GENERATING} if allow_generating else {STATUS_QUEUED}
        )
        if record.status not in allowed_start:
            logger.info(
                "export %s already in status %s; skipping (idempotent)",
                export_id,
                record.status,
            )
            return False

        # AC-1: transition to Generating before any generation begins, and
        # commit so the state is observable during the retry window (AC-5).
        record.status = STATUS_GENERATING
        record.completed_at = None
        session.commit()

        # AC-9: only non-rejected symbols, in the AC-2 order.
        symbols = _fetch_symbols(session, drawing_id)
        data, content_type = _render(fmt, symbols)

        bucket = settings.S3_BUCKET_NAME
        object_key = export_object_key(str(export_id), fmt)
        # AC-2/AC-3 + AC-8: unique export_id-scoped key; put_object overwrites
        # the same key on retry (idempotent) and never touches prior exports.
        put_object(bucket, object_key, data, content_type)
        sha256_hash = compute_sha256_stream(io.BytesIO(data))

        # AC-2/AC-3 atomicity: the StoredFile INSERT and the ExportRecord
        # UPDATE (Complete + stored_file_id + completed_at) commit together.
        stored = _store_file(
            session,
            bucket=bucket,
            object_key=object_key,
            sha256_hash=sha256_hash,
            file_type=content_type,
            size_bytes=len(data),
        )
        record.stored_file_id = stored.id
        record.status = STATUS_COMPLETE
        record.completed_at = datetime.now(timezone.utc)
        session.commit()
        return True
    finally:
        session.close()


def _mark_failed(export_id: str) -> None:
    """AC-6: set the record to ``Failed`` with ``completed_at`` / stored_file
    cleared. Own session, own ``finally`` close."""
    session = SessionLocal()
    try:
        record = (
            session.query(ExportRecord)
            .filter(ExportRecord.id == export_id)
            .with_for_update()
            .one_or_none()
        )
        if record is None:
            logger.warning("export %s: no record to mark Failed", export_id)
            return
        record.status = STATUS_FAILED
        record.completed_at = None
        record.stored_file_id = None
        session.commit()
    finally:
        session.close()


# --- Celery task -----------------------------------------------------------


def _run_export(self: Any, export_id: str, drawing_id: str, user_id: str, format: str) -> None:
    """Core task body (separated from the Celery decorator so it is unit
    testable with a stand-in ``self``).

    Retry/failure policy (AC-5 / AC-6):

    * On the first failure (``request.retries < MAX_RETRIES``) call
      ``self.retry`` with a 30 s countdown and leave the record in
      ``Generating`` — do NOT mark Failed.
    * Once retries are exhausted, mark the record ``Failed``, publish the
      ``export_failed`` event, then re-raise so Celery records the failure.
    """
    retries = getattr(getattr(self, "request", None), "retries", 0) or 0
    try:
        completed = _process_export(
            export_id,
            drawing_id,
            user_id,
            format,
            allow_generating=retries > 0,
        )
    except Exception as exc:  # noqa: BLE001 — funnel every failure through retry/fail
        logger.exception(
            "export %s failed on attempt %s", export_id, retries
        )
        if retries < MAX_RETRIES:
            # AC-5: retry exactly once, 30 s delay; record stays Generating.
            raise self.retry(exc=exc, countdown=RETRY_COUNTDOWN_SECONDS)
        # AC-6: retries exhausted → Failed + export_failed notification.
        _mark_failed(export_id)
        publish_export_event(
            _channel(export_id),
            _event_payload(EVENT_FAILED, export_id, drawing_id, user_id, format),
        )
        raise

    if completed:
        # AC-4: notify completion only when this attempt actually generated.
        publish_export_event(
            _channel(export_id),
            _event_payload(EVENT_COMPLETE, export_id, drawing_id, user_id, format),
        )


@celery_app.task(
    bind=True,
    name="export.generate_export",
    acks_late=True,  # § crash-recovery: re-deliver if the worker dies mid-task
    max_retries=MAX_RETRIES,
    default_retry_delay=RETRY_COUNTDOWN_SECONDS,
    time_limit=EXPORT_TASK_TIME_LIMIT_SECONDS,
    # Manual retry handling (above) owns the policy; disable inherited
    # autoretry so a re-raised failure is not retried beyond MAX_RETRIES.
    autoretry_for=(),
)
def generate_export(
    self: Any,
    export_id: str,
    drawing_id: str,
    user_id: str,
    format: str,
) -> None:
    """Generate a CSV/XLSX export and notify on completion/failure.

    Routed to the ``export`` queue via the ``export.*`` task-name prefix in
    ``app.workers.queues`` (§1.11). Payload kwargs (``export_id``,
    ``drawing_id``, ``user_id``, ``format``) are a load-bearing contract with
    S2-D's enqueue call.
    """
    _run_export(self, export_id, drawing_id, user_id, format)


__all__ = [
    "generate_export",
    "generate_csv_bytes",
    "generate_xlsx_bytes",
    "publish_export_event",
    "EXPORT_COLUMNS",
    "EXPORT_STATUS_CHANNEL",
    "CONTENT_TYPE_CSV",
    "CONTENT_TYPE_XLSX",
    "MAX_RETRIES",
    "RETRY_COUNTDOWN_SECONDS",
    "EXPORT_TASK_TIME_LIMIT_SECONDS",
]
