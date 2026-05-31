"""Atomic persistence of ML inference results (US-011 AC-3..AC-7, US-021 P1-STUB).

The single invariant this module enforces is **atomicity** (§1.2, US-011 AC-6):
the ``detected_symbol`` inserts and the ``drawing`` state/metadata update commit
together in exactly one :meth:`Session.commit` call. Either every symbol is
written and the drawing becomes ``Complete``, or nothing is written and the
exception propagates so the task retries / fails — never a partial result.

Order within the single transaction (§ critical notes):
1. insert all ``detected_symbol`` rows, then
2. update the ``drawing`` (``processing_state='Complete'``, ``processed_at``,
   ``estimated_symbol_count``, conditionally ``page_count``), then
3. one ``commit``.

``user_id`` is never read here — persistence is keyed entirely by ``drawing_id``
(§1.4 rule 5).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.detected_symbol import DetectedSymbol
from app.db.models.drawing import Drawing
from app.schemas.contracts import MLInferenceResult

logger = logging.getLogger("pid.workers.ml.result_persistence")

COMPLETE_STATE = "Complete"
ML_SOURCE = "ml"


def _coerce_uuid(value):
    """Return ``value`` as ``uuid.UUID`` (drawing_id arrives as a str from JSON)."""
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _in_page_range(page_number: int, page_range: Optional[tuple[int, int]]) -> bool:
    """Inclusive 1-based page-range membership (US-011 AC-5)."""
    if not page_range:
        return True
    low, high = page_range[0], page_range[1]
    return low <= page_number <= high


def persist_inference_results(
    session: Session,
    drawing_id: str,
    result: MLInferenceResult,
    page_range: Optional[tuple[int, int]] = None,
) -> int:
    """Atomically write detected symbols and transition the drawing to Complete.

    Returns the number of (non-rejected) detected symbols written — the value
    also stored as ``drawing.estimated_symbol_count`` (US-011 AC-7).

    Raises if the drawing row is missing; on any DB error the caller's
    transaction guarantees no partial state is visible (single commit).
    """
    drawing = session.get(Drawing, _coerce_uuid(drawing_id))
    if drawing is None:
        # tasks.py guards this first; defensive re-check keeps the contract.
        raise ValueError(f"Drawing {drawing_id} not found during result persistence")

    # 1) Build + insert all detected_symbol rows (filtered to page_range).
    symbols: list[DetectedSymbol] = []
    for sym in result.symbols:
        if not _in_page_range(sym.page_number, page_range):
            continue
        symbols.append(
            DetectedSymbol(
                drawing_id=drawing.id,
                entity_class_id=sym.entity_class_id,
                subtype=sym.subtype,
                tag_label=sym.tag_label,
                confidence=sym.confidence,
                bbox=sym.bbox.model_dump(),  # JSONB: {"x","y","w","h"}
                source=ML_SOURCE,
                rejected=False,
                page_number=sym.page_number,
            )
        )
    session.add_all(symbols)

    # 2) Update the drawing in the SAME transaction.
    count = len(symbols)
    drawing.processing_state = COMPLETE_STATE
    drawing.processed_at = datetime.now(timezone.utc)
    drawing.estimated_symbol_count = count

    # page_count: derive only when page_range is absent (full-document run) and we
    # actually detected symbols; with a page_range, ingest already set page_count
    # and we must not overwrite it (§ critical notes).
    if not page_range and symbols:
        drawing.page_count = max(sym.page_number for sym in symbols)

    # US-021 P1-STUB: Table cell persistence not implemented in P0.
    # Tables from the inference result are intentionally discarded.
    # See US-021 for P1 implementation requirements.
    if result.tables:
        logger.debug(
            "Received %d table regions for drawing %s; skipping persistence (P1-STUB)",
            len(result.tables),
            drawing_id,
        )

    # 3) Single atomic commit for inserts + drawing update.
    session.commit()
    logger.info(
        "Persisted %d detected symbols and set drawing %s -> %s",
        count,
        drawing_id,
        COMPLETE_STATE,
    )
    return count


__all__ = ["persist_inference_results"]
