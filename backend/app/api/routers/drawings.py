"""Drawing-lifecycle HTTP endpoints (US-003, US-006..US-010, US-018).

Implements the full drawing surface from §1.6: hash-check, create (+ pre-signed
URL), list (paginated/searchable), detail, update, delete, retry, upload-complete
and the SSE status stream. Registered ahead of ``stubs_router`` in
``app/api/routers/__init__.py`` (SWAP PROTOCOL) so these shadow the S2-B 501
stubs.

HTTP status contract (§1.5) is enforced here, not in the services:

* hash blocked → ``409`` (never ``200``/``400``)
* ``POST /drawings`` with no prior hash-check pass → ``400``
* ``upload-complete`` initial success → ``202``; idempotent replay → ``200``
* delete success → ``204``; retry success → ``202``; retry from a non-``Failed``
  state → ``422``
* unauthenticated → ``401`` (dependency); wrong owner → ``403``; missing → ``404``
"""
from __future__ import annotations

import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user, resolve_ownership
from app.auth.permissions import check_permission
from app.db.models.drawing import Drawing
from app.db.session import get_db
from app.redis import client as redis_client
from app.schemas.contracts import HashCheckRequest, HashCheckResponse
from app.services import drawing_service, hash_check_service, upload_complete_service
from app.sse.drawing_status import drawing_status_event_stream

router = APIRouter(tags=["drawings"])


# ---------------------------------------------------------------------------
# Request bodies (response shapes are plain dicts from drawing_service)
# ---------------------------------------------------------------------------
class DrawingCreateRequest(BaseModel):
    filename: str
    sha256_hash: str
    size_bytes: int
    file_type: str
    revision_label: Optional[str] = None


class DrawingUpdateRequest(BaseModel):
    revision_label: Optional[str] = None
    filename: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse_uuid_or_404(drawing_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(drawing_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drawing not found")


def _load_drawing_for(action: str, drawing_id: str, user: CurrentUser, db: Session) -> Drawing:
    """Load a drawing and enforce ``action`` for ``user`` per §1.3.

    Missing → ``404`` (existence is not leaked for unknown ids). Found but the
    caller lacks ``action`` for it → ``403``.
    """
    parsed = _parse_uuid_or_404(drawing_id)
    drawing = drawing_service.get_drawing(parsed, db)
    if drawing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drawing not found")
    ownership = resolve_ownership(user, drawing.owner_user_id, drawing.owner_team_id)
    if not check_permission(user.role, action, ownership):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return drawing


# ---------------------------------------------------------------------------
# US-003 — hash-check
# ---------------------------------------------------------------------------
@router.post("/drawings/hash-check", response_model=HashCheckResponse)
async def hash_check(
    payload: HashCheckRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HashCheckResponse:
    """Blocklist gate. ``409`` when the hash is blocked (no Drawing/URL created),
    else ``200 {allowed: true}`` and a 30-minute Redis pass is recorded."""
    result = await hash_check_service.run_hash_check(
        str(user.id), payload, db, redis_client.get_redis()
    )
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="File hash is blocked",
        )
    return result


# ---------------------------------------------------------------------------
# US-003 — create drawing + pre-signed URL
# ---------------------------------------------------------------------------
@router.post("/drawings", status_code=status.HTTP_201_CREATED)
async def create_drawing(
    payload: DrawingCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Create a ``Pending`` Drawing + ``StoredFile`` and return ``{drawing_id,
    presigned_url}``. ``400`` if no valid prior hash-check pass exists."""
    try:
        drawing, presigned_url = await drawing_service.create_drawing(
            user=user,
            filename=payload.filename,
            sha256_hash=payload.sha256_hash,
            size_bytes=payload.size_bytes,
            file_type=payload.file_type,
            revision_label=payload.revision_label,
            db=db,
            redis=redis_client.get_redis(),
        )
    except drawing_service.HashCheckRequiredError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A successful POST /drawings/hash-check is required first",
        )
    return {"drawing_id": str(drawing.id), "presigned_url": presigned_url}


# ---------------------------------------------------------------------------
# US-006 / US-007 — list (paginated, searchable, filterable)
# ---------------------------------------------------------------------------
@router.get("/drawings")
def list_drawings(
    q: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    uploaded_after: Optional[datetime.datetime] = Query(default=None),
    uploaded_before: Optional[datetime.datetime] = Query(default=None),
    limit: int = Query(default=drawing_service.DEFAULT_PAGE_SIZE, ge=1),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Drawing Library list scoped to the caller (own / team), newest first."""
    if state is not None and not drawing_service.valid_state(state):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown processing_state filter: {state!r}",
        )
    drawings, total = drawing_service.list_drawings(
        user,
        db,
        q=q,
        state=state,
        uploaded_after=uploaded_after,
        uploaded_before=uploaded_before,
        limit=limit,
        offset=offset,
    )
    return {
        "drawings": [drawing_service.serialize_drawing(d) for d in drawings],
        "total": total,
        "limit": max(1, min(limit, drawing_service.MAX_PAGE_SIZE)),
        "offset": max(0, offset),
    }


# ---------------------------------------------------------------------------
# US-003 — detail
# ---------------------------------------------------------------------------
@router.get("/drawings/{drawing_id}")
def get_drawing(
    drawing_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    drawing = _load_drawing_for("drawing_view", drawing_id, user, db)
    return drawing_service.serialize_drawing(drawing)


# ---------------------------------------------------------------------------
# US-003 — update (revision label)
# ---------------------------------------------------------------------------
@router.patch("/drawings/{drawing_id}")
def update_drawing(
    drawing_id: str,
    payload: DrawingUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    drawing = _load_drawing_for("drawing_view", drawing_id, user, db)
    updated = drawing_service.update_drawing(
        drawing, db, revision_label=payload.revision_label, filename=payload.filename
    )
    return drawing_service.serialize_drawing(updated)


# ---------------------------------------------------------------------------
# US-009 — delete
# ---------------------------------------------------------------------------
@router.delete("/drawings/{drawing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_drawing(
    drawing_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    drawing = _load_drawing_for("drawing_delete", drawing_id, user, db)
    drawing_service.delete_drawing(drawing, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# US-009 — retry
# ---------------------------------------------------------------------------
@router.post("/drawings/{drawing_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_drawing(
    drawing_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Retry a ``Failed`` drawing (re-enqueue, reusing the existing StoredFile).

    Only ``Failed`` is retryable here: ``Scan_Failed`` is terminal and
    ``Complete`` must not be silently re-processed (both → ``422``)."""
    drawing = _load_drawing_for("drawing_retry", drawing_id, user, db)
    if drawing.processing_state != "Failed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot retry a drawing in state {drawing.processing_state!r}",
        )
    upload_complete_service.retry_drawing(user, drawing, db)
    return {"drawing_id": str(drawing.id), "processing_state": drawing.processing_state}


# ---------------------------------------------------------------------------
# US-008 — SSE status stream
# ---------------------------------------------------------------------------
@router.get("/drawings/{drawing_id}/status")
def drawing_status(
    drawing_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Live ``text/event-stream`` of the drawing's processing state."""
    drawing = _load_drawing_for("drawing_view", drawing_id, user, db)
    stream = drawing_status_event_stream(str(drawing.id), drawing.processing_state)
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# US-003 / US-010 / US-018 — upload-complete
# ---------------------------------------------------------------------------
@router.post("/drawings/{drawing_id}/upload-complete")
async def upload_complete(
    drawing_id: str,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Signal upload completion: enqueue ingest (``202``), or replay idempotently
    (``200``), or reject a free-tier over-limit request (``402``)."""
    drawing = _load_drawing_for("drawing_view", drawing_id, user, db)
    result = await upload_complete_service.complete_upload(
        user, drawing, db, redis_client.get_redis()
    )
    response.status_code = result.http_status
    return {
        "drawing_id": str(drawing.id),
        "processing_state": drawing.processing_state,
        "enqueued": result.enqueued,
        "limit_reached": result.limit_reached,
    }


__all__ = ["router"]
