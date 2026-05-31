"""Drawing CRUD + library query service (US-003, US-006, US-007).

Covers drawing creation (after a hash-check pass), the paginated/searchable
Drawing Library list, single-drawing fetch, revision-label update, and delete.
Ownership *enforcement* lives in the router (via S1-B's ``check_permission`` /
``resolve_ownership``); this module owns the *data* concerns — query shaping,
the owner-scope filter, FTS, and the canonical record serialisation consumed by
S3-B / S4-A.
"""
from __future__ import annotations

import datetime
import os
import uuid
from typing import Any, Optional

from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.config import settings
from app.db.models.drawing import Drawing
from app.db.models.stored_file import StoredFile
from app.schemas.contracts import DrawingProcessingState
from app.services.hash_check_service import has_passed_hash_check
from app.storage.presigned import drawing_object_key, generate_presigned_put_url

# Pagination contract (US-006 AC-1 / US-007 AC-5).
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100

_TEAM_ROLES = ("team_member", "team_admin")

# Minimal extension → MIME map for the signed PUT's Content-Type. The byte
# stream is opaque to us; anything unmapped is treated as a generic binary.
_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "dwg": "application/octet-stream",
    "dxf": "application/octet-stream",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "tif": "image/tiff",
    "tiff": "image/tiff",
}


class HashCheckRequiredError(Exception):
    """Raised by :func:`create_drawing` when no valid prior hash-check pass
    exists for the supplied hash (the endpoint maps this to ``400``)."""


def _normalize(sha256_hash: str) -> str:
    return sha256_hash.strip().lower()


def _extension(filename: str, file_type: str) -> str:
    ext = os.path.splitext(filename)[1].lstrip(".").lower()
    if ext:
        return ext
    return file_type.strip().lstrip(".").lower() or "bin"


def _content_type(ext: str) -> str:
    return _CONTENT_TYPES.get(ext, "application/octet-stream")


async def create_drawing(
    *,
    user: CurrentUser,
    filename: str,
    sha256_hash: str,
    size_bytes: int,
    file_type: str,
    revision_label: Optional[str],
    db: Session,
    redis: Any,
) -> tuple[Drawing, str]:
    """Create a ``Pending`` Drawing + its ``StoredFile`` and mint a pre-signed
    upload URL.

    Enforces §1.4 rule 1: a valid prior hash-check pass MUST exist (else
    :class:`HashCheckRequiredError`). The pre-signed URL expires in exactly
    ``PRESIGNED_URL_EXPIRY_SECONDS`` (S1-C bakes the TTL in; the caller cannot
    override it).
    """
    if not await has_passed_hash_check(str(user.id), sha256_hash, redis):
        raise HashCheckRequiredError(
            "POST /drawings requires a prior successful POST /drawings/hash-check"
        )

    drawing_id = uuid.uuid4()
    ext = _extension(filename, file_type)
    object_key = drawing_object_key(str(drawing_id), ext)

    stored_file = StoredFile(
        id=uuid.uuid4(),
        bucket=settings.S3_BUCKET_NAME,
        object_key=object_key,
        sha256_hash=_normalize(sha256_hash),
        file_type=file_type,
        size_bytes=size_bytes,
    )
    db.add(stored_file)
    db.flush()

    # Drawing ownership (drawing_owner XOR): team roles own at the team scope so
    # the whole team can see the upload (US-006 AC-3/4); solo users own it
    # individually (US-006 AC-2).
    if user.role in _TEAM_ROLES and user.team_id is not None:
        owner_user_id, owner_team_id = None, user.team_id
    else:
        owner_user_id, owner_team_id = user.id, None

    drawing = Drawing(
        id=drawing_id,
        owner_user_id=owner_user_id,
        owner_team_id=owner_team_id,
        filename=filename,
        revision_label=revision_label,
        processing_state="Pending",
        uploaded_at=datetime.datetime.now(datetime.timezone.utc),
        stored_file_id=stored_file.id,
    )
    db.add(drawing)
    db.commit()

    presigned_url = generate_presigned_put_url(
        settings.S3_BUCKET_NAME,
        object_key,
        size_bytes,
        _content_type(ext),
    )
    return drawing, presigned_url


def _owner_scope_clause(user: CurrentUser):
    """SQLAlchemy predicate restricting drawings to the caller's visible scope
    (US-006 AC-2/3/4): solo users see their own; team roles see team-owned."""
    if user.role in _TEAM_ROLES and user.team_id is not None:
        return Drawing.owner_team_id == user.team_id
    return Drawing.owner_user_id == user.id


def _apply_fts(stmt, db: Session, q: str):
    """Apply a filename/revision_label full-text filter.

    On PostgreSQL this uses the ``idx_drawing_fts`` GIN expression
    (``to_tsvector(filename || ' ' || COALESCE(revision_label,'')) @@
    plainto_tsquery``). On other engines (the self-contained test gate runs on
    SQLite) it falls back to a case-insensitive substring match so the same
    query path returns correct results everywhere.
    """
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        # Build the SAME expression the idx_drawing_fts GIN index was created on
        # (``filename || ' ' || COALESCE(revision_label, '')``) so the planner
        # can use the index rather than a seq scan.
        document = Drawing.filename.op("||")(text("' '")).op("||")(
            func.coalesce(Drawing.revision_label, text("''"))
        )
        ts_vector = func.to_tsvector(text("'english'"), document)
        return stmt.where(ts_vector.op("@@")(func.plainto_tsquery(text("'english'"), q)))

    like = f"%{q}%"
    return stmt.where(
        func.lower(Drawing.filename).like(func.lower(like))
        | func.lower(func.coalesce(Drawing.revision_label, "")).like(func.lower(like))
    )


def list_drawings(
    user: CurrentUser,
    db: Session,
    *,
    q: Optional[str] = None,
    state: Optional[str] = None,
    uploaded_after: Optional[datetime.datetime] = None,
    uploaded_before: Optional[datetime.datetime] = None,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> tuple[list[Drawing], int]:
    """Return ``(drawings, total)`` for the Drawing Library, newest first.

    Filters (FTS ``q``, ``state``, ``uploaded_after``/``uploaded_before``) are
    combined with AND (US-007 AC-4). ``limit`` is clamped to ``[1, 100]`` and
    ``offset`` to ``>= 0``.
    """
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, offset)

    conditions = [_owner_scope_clause(user)]
    if state is not None:
        conditions.append(Drawing.processing_state == state)
    if uploaded_after is not None:
        conditions.append(Drawing.uploaded_at >= uploaded_after)
    if uploaded_before is not None:
        conditions.append(Drawing.uploaded_at <= uploaded_before)

    base = select(Drawing).where(and_(*conditions))
    if q:
        base = _apply_fts(base, db, q)

    total = db.scalar(
        select(func.count()).select_from(base.order_by(None).subquery())
    )

    rows = (
        db.execute(
            base.order_by(Drawing.uploaded_at.desc(), Drawing.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return list(rows), int(total or 0)


def get_drawing(drawing_id: uuid.UUID, db: Session) -> Optional[Drawing]:
    """Fetch a single drawing by id, or ``None`` if it does not exist."""
    return db.get(Drawing, drawing_id)


def update_drawing(
    drawing: Drawing,
    db: Session,
    *,
    revision_label: Optional[str] = None,
    filename: Optional[str] = None,
) -> Drawing:
    """Update mutable drawing metadata (revision label / filename) and commit."""
    if revision_label is not None:
        drawing.revision_label = revision_label
    if filename is not None:
        drawing.filename = filename
    db.commit()
    db.refresh(drawing)
    return drawing


def delete_drawing(drawing: Drawing, db: Session) -> None:
    """Delete a drawing. Child rows (detected_symbol, table_cell,
    user_correction, export_record) are removed by the DB's ``ON DELETE
    CASCADE`` (migration 0001). A delete mid-processing is allowed — the running
    worker aborts gracefully when it finds the drawing gone (US-009 AC-8)."""
    db.delete(drawing)
    db.commit()


def serialize_drawing(drawing: Drawing) -> dict:
    """Canonical Drawing record shape (US-006 AC-5) — consumed by S3-B / S4-A."""
    return {
        "id": str(drawing.id),
        "filename": drawing.filename,
        "revision_label": drawing.revision_label,
        "processing_state": drawing.processing_state,
        "page_count": drawing.page_count,
        "estimated_symbol_count": drawing.estimated_symbol_count,
        "owner_user_id": str(drawing.owner_user_id) if drawing.owner_user_id else None,
        "owner_team_id": str(drawing.owner_team_id) if drawing.owner_team_id else None,
        "uploaded_at": drawing.uploaded_at.isoformat() if drawing.uploaded_at else None,
        "processed_at": drawing.processed_at.isoformat() if drawing.processed_at else None,
    }


def valid_state(state: str) -> bool:
    """Whether ``state`` is one of the §1.1 ``DrawingProcessingState`` literals."""
    return state in DrawingProcessingState.__args__


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "HashCheckRequiredError",
    "create_drawing",
    "list_drawings",
    "get_drawing",
    "update_drawing",
    "delete_drawing",
    "serialize_drawing",
    "valid_state",
]
