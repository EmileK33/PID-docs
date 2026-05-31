"""Symbol read path + shared correction/symbol serialization (S2-C).

[LOAD-BEARING] Exports ``get_symbols_page`` (the canvas-load query consumed by
S3-D / S4-A) plus the record-mapping helpers and ``assert_drawing_access``,
which ``correction_service`` re-uses.

Performance contract (§1.9):

* ``GET /drawings/{id}/symbols`` co-loads correction history in the SAME response
  (``corrections_by_symbol_id``) so the React panel-open SLA (<200ms P95,
  NFR-19) needs no second fetch.
* Corrections are fetched in ONE batched ``WHERE detected_symbol_id IN (...)``
  query after the symbol page — never one query per symbol (no N+1).

Note on ``assert_drawing_access``: §S2-C's brief lists this as an S1-B export,
but the merged ``app.auth.permissions`` ships the ownership primitives
(``resolve_ownership`` + ``check_permission``) rather than this exact helper. We
therefore compose it here from those sanctioned primitives — not a
re-implementation of ownership/team logic, which still lives in S1-B.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, resolve_ownership
from app.auth.permissions import check_permission
from app.db.models.detected_symbol import DetectedSymbol
from app.db.models.drawing import Drawing
from app.db.models.user_correction import UserCorrection
from app.schemas.contracts import (
    BoundingBox,
    CorrectionRecord,
    SymbolRecord,
    SymbolsPageResponse,
)


# ---------------------------------------------------------------------------
# Serialization helpers (shared with correction_service)
# ---------------------------------------------------------------------------
def to_symbol_record(symbol: DetectedSymbol) -> SymbolRecord:
    """Map a ``DetectedSymbol`` ORM row onto the §1.1 ``SymbolRecord`` contract."""
    return SymbolRecord(
        id=str(symbol.id),
        drawing_id=str(symbol.drawing_id),
        entity_class_id=symbol.entity_class_id,
        # §1.1 types subtype as a non-null string; coalesce a NULL DB value.
        subtype=symbol.subtype or "",
        tag_label=symbol.tag_label,
        confidence=symbol.confidence,
        bbox=BoundingBox(**symbol.bbox),
        source=symbol.source,
        rejected=symbol.rejected,
        page_number=symbol.page_number,
    )


def to_correction_record(correction: UserCorrection) -> CorrectionRecord:
    """Map a ``UserCorrection`` ORM row onto the §1.1 ``CorrectionRecord``."""
    created_at = correction.created_at
    return CorrectionRecord(
        id=str(correction.id),
        detected_symbol_id=(
            str(correction.detected_symbol_id)
            if correction.detected_symbol_id is not None
            else None
        ),
        table_cell_id=(
            str(correction.table_cell_id)
            if correction.table_cell_id is not None
            else None
        ),
        user_id=str(correction.user_id),
        correction_type=correction.correction_type,
        new_class_id=correction.new_class_id,
        training_consent=correction.training_consent,
        created_at=(
            created_at.isoformat()
            if hasattr(created_at, "isoformat")
            else str(created_at)
        ),
    )


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------
def get_drawing_or_404(drawing_id: str, db: Session) -> Drawing:
    """Load a drawing by id WITHOUT filtering by ownership, raising 404 if it
    does not exist.

    Loading independently of ownership is deliberate (§1.5): an authenticated
    user hitting a drawing they cannot access must get 403 — never 404 — so the
    access check happens separately, after the row is confirmed to exist.
    """
    try:
        pk = UUID(str(drawing_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Drawing not found"
        )
    drawing = db.get(Drawing, pk)
    if drawing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Drawing not found"
        )
    return drawing


def assert_drawing_access(
    user: CurrentUser,
    drawing: Drawing,
    db: Session,
    action: str = "symbol_correct",
) -> None:
    """Raise ``HTTPException(403)`` if ``user`` may not perform ``action`` on
    ``drawing`` per the §1.3 role-permission matrix.

    ``db`` is accepted for signature parity with the documented S1-B contract
    (and future team-membership lookups); ownership today is resolved purely
    from the drawing's owner columns and the caller's identity.
    """
    ownership = resolve_ownership(
        user, drawing.owner_user_id, drawing.owner_team_id
    )
    if not check_permission(user.role, action, ownership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
        )


# ---------------------------------------------------------------------------
# Read path — GET /drawings/{id}/symbols
# ---------------------------------------------------------------------------
def get_symbols_page(
    drawing_id: str,
    user: CurrentUser,
    db: Session,
    limit: int = 200,
    offset: int = 0,
    page_number: Optional[int] = None,
    entity_class_id: Optional[str] = None,
    rejected: Optional[bool] = None,
) -> SymbolsPageResponse:
    """Return one page of detected symbols for a drawing with their correction
    history co-loaded. Performs NO state mutation (canvas open must not trigger
    the ``Under_Review`` transition — §1.4 rule 13)."""
    drawing = get_drawing_or_404(drawing_id, db)
    assert_drawing_access(user, drawing, db, action="drawing_view")

    filters = [DetectedSymbol.drawing_id == drawing.id]
    if page_number is not None:
        filters.append(DetectedSymbol.page_number == page_number)
    if entity_class_id is not None:
        filters.append(DetectedSymbol.entity_class_id == entity_class_id)
    if rejected is not None:
        filters.append(DetectedSymbol.rejected == rejected)

    total = db.execute(
        select(func.count()).select_from(DetectedSymbol).where(*filters)
    ).scalar_one()

    symbols = (
        db.execute(
            select(DetectedSymbol)
            .where(*filters)
            .order_by(DetectedSymbol.page_number, DetectedSymbol.id)
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )

    # Single batched correction fetch for the whole page (no N+1).
    corrections_by_symbol_id: dict[str, list[CorrectionRecord]] = {}
    symbol_ids = [s.id for s in symbols]
    if symbol_ids:
        corrections = (
            db.execute(
                select(UserCorrection).where(
                    UserCorrection.detected_symbol_id.in_(symbol_ids)
                )
            )
            .scalars()
            .all()
        )
        for correction in corrections:
            key = str(correction.detected_symbol_id)
            corrections_by_symbol_id.setdefault(key, []).append(
                to_correction_record(correction)
            )

    return SymbolsPageResponse(
        symbols=[to_symbol_record(s) for s in symbols],
        corrections_by_symbol_id=corrections_by_symbol_id,
        total=total,
        limit=limit,
        offset=offset,
    )


__all__ = [
    "get_symbols_page",
    "to_symbol_record",
    "to_correction_record",
    "assert_drawing_access",
    "get_drawing_or_404",
]
