"""Export endpoints (S2-D).

Route manifest (§1.6):

* ``POST /drawings/{id}/exports`` — create an export (sync 201 / async 202).
* ``GET  /exports/{id}``          — poll status + mint a fresh download URL.
* ``GET  /exports/{id}/comparison-csv`` — P1, stubbed 501 (revision comparison).

Wiring: this module exposes ``exports_router``; it is included ahead of
``stubs_router`` in ``app/api/routers/__init__.py`` (SWAP PROTOCOL there) so it
shadows the S2-D 501 stubs. The endpoints enforce the §1.5 status contract
(401 unauth, 403 cross-owner, 404 missing) and delegate business logic to
``app.services.export_service``.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user, resolve_ownership
from app.auth.permissions import check_permission
from app.db.models.drawing import Drawing
from app.db.session import get_db
from app.services.export_service import (
    ExportCreateRequest,
    ExportRecordResponse,
    create_export,
    get_export,
)

exports_router = APIRouter(tags=["exports"])


@exports_router.post(
    "/drawings/{drawing_id}/exports",
    response_model=ExportRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_drawing_export(
    drawing_id: UUID,
    body: ExportCreateRequest,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExportRecordResponse:
    """Create a CSV/XLSX export for a drawing.

    Returns 201 + ``status=Complete`` + ``download_url`` for the synchronous path
    (≤1000 symbols), or 202 + ``status=Queued`` for the async path (>1000
    symbols). The symbol-count threshold is evaluated server-side.
    """
    drawing = db.get(Drawing, drawing_id)
    if drawing is None:
        # §1.5: a genuinely absent resource is a 404.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Drawing not found"
        )

    # §1.3 ``export_initiate`` gate over the drawing's ownership. §1.5: an
    # authenticated user lacking access gets 403 (never 404).
    ownership = resolve_ownership(user, drawing.owner_user_id, drawing.owner_team_id)
    if not check_permission(user.role, "export_initiate", ownership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
        )

    result = create_export(drawing_id, user.id, body.format, db)

    # Async jobs return 202 Accepted; completed sync exports return 201 Created.
    if result.status != "Complete":
        response.status_code = status.HTTP_202_ACCEPTED
    return result


@exports_router.get(
    "/exports/{export_id}",
    response_model=ExportRecordResponse,
)
def read_export(
    export_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExportRecordResponse:
    """Return the export's current status; mints a fresh download URL and fires
    ``export_downloaded`` when the export is ``Complete``."""
    return get_export(export_id, user.id, db)


@exports_router.get("/exports/{export_id}/comparison-csv")
def read_export_comparison_csv(export_id: UUID) -> None:
    """P1 — revision-comparison CSV. Not scheduled in the current build plan."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented — P1 endpoint (revision comparison)",
    )


__all__ = ["exports_router"]
