"""S2-G — ``GET /entity-classes`` router (public reference taxonomy).

Serves the full entity-class taxonomy (id, name, parent hierarchy, color code)
to the React SPA and other backend services via S1-D's Redis-cached read path
(see ``app.services.entity_class_service``).

The endpoint is **unauthenticated by design**: the S2-G prerequisites (S1-A, S1-D)
deliberately exclude the S1-B auth layer — this is public reference data needed to
render the canvas before full auth context is established (S3-D bootstrap) and by
the symbol reclassification panel (S2-C). Do NOT add an auth dependency here.

Mounting: this router is registered ahead of ``stubs_router`` at the S2-G slot in
``app/api/routers/__init__.py`` (the SWAP PROTOCOL documented there), so it shadows
the ``GET /entity-classes`` 501 stub. ``main.py`` is never touched.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.entity_class_service import (
    EntityClassListResponse,
    get_entity_classes,
)

router = APIRouter(tags=["entity-classes"])


@router.get("/entity-classes", response_model=EntityClassListResponse)
async def list_entity_classes(db: Session = Depends(get_db)) -> EntityClassListResponse:
    """Return every entity class wrapped under the ``entity_classes`` key.

    Cache-aside: served from Redis on all non-first requests; a single DB query on
    a cold cache. Always ``200 OK`` — Redis outages fall back to the DB (EC-7).
    """
    records = await get_entity_classes(db)
    return EntityClassListResponse(entity_classes=records)
