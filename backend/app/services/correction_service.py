"""Correction write path (S2-C) — the core of the drawing review workflow.

[LOAD-BEARING] Exports ``create_correction`` (PATCH /symbols/{id}) and
``create_manual_symbol`` (POST /drawings/{id}/symbols), consumed by S4-A's
``test_correction_flow.py``.

Each write is a single atomic unit of work (§ atomicity requirements):

  symbol mutation / insert  +  user_correction insert  +  conditional
  ``UPDATE drawing SET processing_state='Under_Review' WHERE ... = 'Complete'``

are committed together. ``training_consent`` is resolved server-side and
snapshotted INSIDE the transaction (§1.4 rules 6 & 7), never lazily nor from a
client-supplied field. The ``correction_action`` analytics event fires AFTER the
commit and never affects the response (§1.10 / US-010 AC-4).

Per the brief: the ``Under_Review`` transition and consent resolution are
implemented inline here — NOT via ``drawing_state_machine.py`` (S2-B) or
``consent_service.py`` (S2-F), which are sibling sessions and must not be
imported.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.analytics.events import emit_correction_action
from app.auth.dependencies import CurrentUser
from app.db.models.detected_symbol import DetectedSymbol
from app.db.models.drawing import Drawing
from app.db.models.ml_training_consent import MLTrainingConsent
from app.db.models.user_correction import UserCorrection
from app.schemas.contracts import SymbolRecord
from app.services.symbol_service import (
    assert_drawing_access,
    get_drawing_or_404,
    to_symbol_record,
)

if TYPE_CHECKING:  # avoid a router<-service import cycle at runtime
    from app.api.routers.symbols import (
        ManualSymbolCreateRequest,
        SymbolCorrectionRequest,
    )

logger = logging.getLogger("pid.corrections")


# ---------------------------------------------------------------------------
# Inline helpers (consent resolution + state transition)
# ---------------------------------------------------------------------------
def _resolve_training_consent(drawing: Drawing, db: Session) -> bool:
    """Resolve ML training consent server-side at correction time (§1.4 rules
    6 & 7). Team-owned drawings resolve from the team's consent record; personal
    drawings from the owning user's. Absent record defaults to ``False``."""
    if drawing.owner_team_id is not None:
        opted_in = db.execute(
            select(MLTrainingConsent.opted_in).where(
                MLTrainingConsent.team_id == drawing.owner_team_id
            )
        ).scalar()
    else:
        opted_in = db.execute(
            select(MLTrainingConsent.opted_in).where(
                MLTrainingConsent.user_id == drawing.owner_user_id
            )
        ).scalar()
    return bool(opted_in) if opted_in is not None else False


def _transition_to_under_review(db: Session, drawing_id: UUID) -> None:
    """Conditional UPDATE: ``Complete`` -> ``Under_Review`` on first correction.

    The ``WHERE processing_state = 'Complete'`` guard makes this idempotent and
    concurrency-safe (§1.4 rule 13 / US-012 AC-4): a drawing already in
    ``Under_Review`` simply matches zero rows — no error, no duplicate
    transition. Executed inside the caller's transaction.
    """
    db.execute(
        update(Drawing)
        .where(Drawing.id == drawing_id, Drawing.processing_state == "Complete")
        .values(processing_state="Under_Review")
    )


def _get_symbol_or_404(symbol_id: str, db: Session) -> DetectedSymbol:
    try:
        pk = UUID(str(symbol_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Symbol not found"
        )
    symbol = db.get(DetectedSymbol, pk)
    if symbol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Symbol not found"
        )
    return symbol


# ---------------------------------------------------------------------------
# PATCH /symbols/{id} — reclassify / reject / restore
# ---------------------------------------------------------------------------
def create_correction(
    symbol_id: str,
    payload: "SymbolCorrectionRequest",
    user: CurrentUser,
    db: Session,
) -> SymbolRecord:
    """Apply a reclassify/reject/restore correction to an existing symbol.

    Mutates the symbol, inserts the ``user_correction`` audit row (with the
    snapshotted consent), and conditionally transitions the drawing to
    ``Under_Review`` — all in one transaction. Emits ``correction_action`` after
    commit.
    """
    # P1-STUB: table_cell corrections — US-022
    if getattr(payload, "table_cell_id", None) is not None:
        raise NotImplementedError(
            "P1: table_cell_id corrections not yet implemented"
        )

    symbol = _get_symbol_or_404(symbol_id, db)
    drawing = db.get(Drawing, symbol.drawing_id)
    if drawing is None:  # orphaned symbol; treat as missing
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Symbol not found"
        )
    assert_drawing_access(user, drawing, db, action="symbol_correct")

    correction_type = payload.correction_type
    new_class_id: Optional[str] = None

    try:
        if correction_type == "reclassify":
            new_class_id = payload.new_class_id
            symbol.entity_class_id = new_class_id
        elif correction_type == "reject":
            symbol.rejected = True
        elif correction_type == "restore":
            symbol.rejected = False

        db.add(
            UserCorrection(
                detected_symbol_id=symbol.id,
                user_id=user.id,
                correction_type=correction_type,
                new_class_id=new_class_id,
                training_consent=_resolve_training_consent(drawing, db),
            )
        )
        _transition_to_under_review(db, drawing.id)

        db.flush()
        # Build the response while the session is live, before commit.
        record = to_symbol_record(symbol)
        ids = (str(user.id), str(drawing.id), str(symbol.id))
        db.commit()
    except Exception:
        db.rollback()
        raise

    _emit_correction_action(*ids)
    return record


# ---------------------------------------------------------------------------
# POST /drawings/{id}/symbols — manual annotation
# ---------------------------------------------------------------------------
def create_manual_symbol(
    drawing_id: str,
    payload: "ManualSymbolCreateRequest",
    user: CurrentUser,
    db: Session,
) -> SymbolRecord:
    """Create a manual symbol (``source='manual'``, ``confidence=1.0``) plus its
    ``manual_add`` correction row, transitioning the drawing to ``Under_Review``
    — all atomically. Emits ``correction_action`` after commit."""
    drawing = get_drawing_or_404(drawing_id, db)
    assert_drawing_access(user, drawing, db, action="symbol_correct")

    try:
        symbol = DetectedSymbol(
            drawing_id=drawing.id,
            entity_class_id=payload.entity_class_id,
            subtype=payload.subtype,
            tag_label=payload.tag_label,
            confidence=1.0,
            bbox=payload.bbox.model_dump(),
            source="manual",
            rejected=False,
            page_number=payload.page_number,
        )
        db.add(symbol)
        db.flush()  # populate symbol.id for the correction FK + analytics

        db.add(
            UserCorrection(
                detected_symbol_id=symbol.id,
                user_id=user.id,
                correction_type="manual_add",
                new_class_id=None,
                training_consent=_resolve_training_consent(drawing, db),
            )
        )
        _transition_to_under_review(db, drawing.id)

        db.flush()
        record = to_symbol_record(symbol)
        ids = (str(user.id), str(drawing.id), str(symbol.id))
        db.commit()
    except Exception:
        db.rollback()
        raise

    _emit_correction_action(*ids)
    return record


# ---------------------------------------------------------------------------
# Analytics (post-commit, never fails the response — §1.10 / US-010 AC-4)
# ---------------------------------------------------------------------------
def _emit_correction_action(user_id: str, drawing_id: str, symbol_id: str) -> None:
    try:
        emit_correction_action(user_id, drawing_id, symbol_id)
    except Exception:  # pragma: no cover - defense in depth
        logger.exception("correction_action analytics emission failed")


__all__ = ["create_correction", "create_manual_symbol"]
