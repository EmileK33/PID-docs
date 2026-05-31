"""Symbols & corrections router (S2-C) — §1.6 routes:

    GET    /drawings/{drawing_id}/symbols   -> SymbolsPageResponse  (200)
    PATCH  /symbols/{symbol_id}             -> SymbolRecord          (200)
    POST   /drawings/{drawing_id}/symbols   -> SymbolRecord          (201)

[LOAD-BEARING] ``router`` is registered ahead of ``stubs_router`` in
``app/api/routers/__init__.py`` (SWAP PROTOCOL); its route names/prefixes are a
cross-session contract (S3-D mirrors the request schemas). Authentication is via
``Depends(get_current_user)`` (missing/invalid token -> 401, §1.5). Ownership
(-> 403) and existence (-> 404) are enforced in the service layer.

All request schemas use ``extra='ignore'`` so a client-supplied
``training_consent`` is silently discarded — that value is derived server-side
exclusively (§1.4 rule 7 / US-015 AC-3).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.contracts import (
    BoundingBox,
    CorrectionType,
    EntityClassId,
    SymbolRecord,
    SymbolsPageResponse,
)
from app.services import correction_service, symbol_service

router = APIRouter(tags=["symbols"])


# ---------------------------------------------------------------------------
# Request schemas (defined here per the brief — no separate schema module)
# ---------------------------------------------------------------------------
class SymbolCorrectionRequest(BaseModel):
    """Body for ``PATCH /symbols/{id}``.

    [LOAD-BEARING] Shape mirrored by the S3-D API client:
    ``{ correction_type, new_class_id }``. ``table_cell_id`` is accepted only to
    route P1 table-cell corrections to their NotImplementedError stub.
    ``manual_add`` is rejected here (it is only valid via POST).
    """

    model_config = ConfigDict(extra="ignore")

    correction_type: CorrectionType
    new_class_id: Optional[EntityClassId] = None
    table_cell_id: Optional[str] = None

    @model_validator(mode="after")
    def _validate_correction(self) -> "SymbolCorrectionRequest":
        if self.correction_type == "manual_add":
            raise ValueError(
                "manual_add is only valid via POST /drawings/{id}/symbols"
            )
        if self.correction_type == "reclassify" and self.new_class_id is None:
            raise ValueError("new_class_id is required for reclassify")
        return self


class ManualSymbolCreateRequest(BaseModel):
    """Body for ``POST /drawings/{id}/symbols``.

    [LOAD-BEARING] Shape mirrored by the S3-D API client:
    ``{ entity_class_id, subtype, tag_label, bbox, page_number }``.
    """

    model_config = ConfigDict(extra="ignore")

    entity_class_id: EntityClassId
    subtype: str
    tag_label: Optional[str] = None
    bbox: BoundingBox
    page_number: int = Field(ge=1)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/drawings/{drawing_id}/symbols", response_model=SymbolsPageResponse)
def list_symbols(
    drawing_id: str = Path(...),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    page_number: Optional[int] = Query(None, ge=1),
    entity_class_id: Optional[EntityClassId] = Query(None),
    rejected: Optional[bool] = Query(None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SymbolsPageResponse:
    """Canvas load: all detected symbols for the drawing + co-loaded correction
    history. No state mutation (§1.4 rule 13)."""
    return symbol_service.get_symbols_page(
        drawing_id=drawing_id,
        user=user,
        db=db,
        limit=limit,
        offset=offset,
        page_number=page_number,
        entity_class_id=entity_class_id,
        rejected=rejected,
    )


@router.patch("/symbols/{symbol_id}", response_model=SymbolRecord)
def patch_symbol(
    payload: SymbolCorrectionRequest,
    symbol_id: str = Path(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SymbolRecord:
    """Reclassify / reject / restore a symbol; persists the correction,
    transitions the drawing to ``Under_Review``, fires ``correction_action``."""
    return correction_service.create_correction(
        symbol_id=symbol_id, payload=payload, user=user, db=db
    )


@router.post(
    "/drawings/{drawing_id}/symbols",
    response_model=SymbolRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_symbol(
    payload: ManualSymbolCreateRequest,
    drawing_id: str = Path(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SymbolRecord:
    """Manual annotation: create a ``source='manual'`` symbol (confidence 1.0)
    plus its ``manual_add`` correction; transitions to ``Under_Review``."""
    return correction_service.create_manual_symbol(
        drawing_id=drawing_id, payload=payload, user=user, db=db
    )


__all__ = ["router", "SymbolCorrectionRequest", "ManualSymbolCreateRequest"]
