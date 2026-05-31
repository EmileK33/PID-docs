"""CSV / XLSX export file generators (S2-D, US-016).

Pure, side-effect-free byte generation: each ``generate_*`` reads the drawing's
symbols (and corrections) from the DB and returns the encoded file as ``bytes``.
No S3, no analytics, no ``ExportRecord`` mutation — that orchestration lives in
``export_service``.

Technology constraints (§1.8 / session brief):

* **CSV** — Python stdlib :mod:`csv` only (no pandas).
* **XLSX** — :mod:`openpyxl` only (pure-Python; no C extension on Fargate).

Symbol-row semantics (session brief "Critical implementation notes"):

* The **CSV** contains *every* symbol — including ``rejected=True`` rows — with a
  ``rejected`` boolean column so downstream tooling can filter (do NOT silently
  drop rejected symbols).
* The **XLSX** ``Symbols`` worksheet contains only *non-rejected* symbols; a
  second ``Corrections`` worksheet lists every correction for the drawing.
* The effective ``entity_class_id`` of a symbol reflects the most recent
  ``reclassify`` correction (by ``created_at``) when one exists; otherwise it is
  the symbol's stored ``entity_class_id``.
"""
from __future__ import annotations

import csv
import io
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.detected_symbol import DetectedSymbol
from app.db.models.user_correction import UserCorrection

# Column order is a LOAD-BEARING contract (US-016 AC-3 / AC-4) — the CSV header
# and the XLSX ``Symbols`` header row are both built from this tuple.
SYMBOL_COLUMNS: tuple[str, ...] = (
    "symbol_id",
    "entity_class_id",
    "subtype",
    "tag_label",
    "confidence",
    "page_number",
    "bbox_x",
    "bbox_y",
    "bbox_w",
    "bbox_h",
    "source",
    "rejected",
)

CORRECTION_COLUMNS: tuple[str, ...] = (
    "correction_id",
    "detected_symbol_id",
    "user_id",
    "correction_type",
    "new_class_id",
    "training_consent",
    "created_at",
)

# §1.9 / AC-9 — exact MIME types stored on the ``stored_file`` record.
CSV_CONTENT_TYPE = "text/csv"
XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def _latest_reclassify_by_symbol(db: Session, drawing_id: UUID) -> dict[UUID, str]:
    """Map ``detected_symbol_id`` → ``new_class_id`` of its most recent
    ``reclassify`` correction (the effective class override).

    Only ``reclassify`` corrections with a non-null ``new_class_id`` participate.
    Ordered by ``created_at`` so the last writer wins per symbol.
    """
    rows = db.execute(
        select(
            UserCorrection.detected_symbol_id,
            UserCorrection.new_class_id,
        )
        .join(
            DetectedSymbol,
            DetectedSymbol.id == UserCorrection.detected_symbol_id,
        )
        .where(
            DetectedSymbol.drawing_id == drawing_id,
            UserCorrection.correction_type == "reclassify",
            UserCorrection.new_class_id.is_not(None),
        )
        .order_by(UserCorrection.created_at.asc())
    ).all()

    # Iterating ascending then overwriting means the latest correction wins.
    latest: dict[UUID, str] = {}
    for symbol_id, new_class_id in rows:
        latest[symbol_id] = new_class_id
    return latest


def _bbox_component(bbox: Any, key: str) -> Any:
    """Safely pull ``x``/``y``/``w``/``h`` out of the JSONB ``bbox`` mapping."""
    if isinstance(bbox, dict):
        return bbox.get(key, "")
    return ""


def build_symbol_rows(
    db: Session, drawing_id: UUID, *, include_rejected: bool
) -> list[dict[str, Any]]:
    """Return one ordered dict per symbol (keyed by :data:`SYMBOL_COLUMNS`).

    ``include_rejected`` controls whether ``rejected=True`` symbols are emitted
    (CSV: ``True``; XLSX ``Symbols`` sheet: ``False``). The effective
    ``entity_class_id`` reflects the latest ``reclassify`` correction.
    """
    overrides = _latest_reclassify_by_symbol(db, drawing_id)

    stmt = select(DetectedSymbol).where(DetectedSymbol.drawing_id == drawing_id)
    if not include_rejected:
        stmt = stmt.where(DetectedSymbol.rejected.is_(False))
    stmt = stmt.order_by(DetectedSymbol.page_number.asc(), DetectedSymbol.id.asc())

    symbols = db.execute(stmt).scalars().all()

    rows: list[dict[str, Any]] = []
    for s in symbols:
        effective_class = overrides.get(s.id, s.entity_class_id)
        rows.append(
            {
                "symbol_id": str(s.id),
                "entity_class_id": effective_class,
                "subtype": s.subtype if s.subtype is not None else "",
                "tag_label": s.tag_label if s.tag_label is not None else "",
                "confidence": s.confidence,
                "page_number": s.page_number,
                "bbox_x": _bbox_component(s.bbox, "x"),
                "bbox_y": _bbox_component(s.bbox, "y"),
                "bbox_w": _bbox_component(s.bbox, "w"),
                "bbox_h": _bbox_component(s.bbox, "h"),
                "source": s.source,
                "rejected": s.rejected,
            }
        )
    return rows


def build_correction_rows(db: Session, drawing_id: UUID) -> list[dict[str, Any]]:
    """Return every ``user_correction`` row attached to a symbol in the drawing.

    Includes corrections for both rejected and non-rejected symbols (session
    brief: the ``Corrections`` sheet lists all corrections for the drawing).
    """
    corrections = (
        db.execute(
            select(UserCorrection)
            .join(
                DetectedSymbol,
                DetectedSymbol.id == UserCorrection.detected_symbol_id,
            )
            .where(DetectedSymbol.drawing_id == drawing_id)
            .order_by(UserCorrection.created_at.asc())
        )
        .scalars()
        .all()
    )

    return [
        {
            "correction_id": str(c.id),
            "detected_symbol_id": str(c.detected_symbol_id)
            if c.detected_symbol_id is not None
            else "",
            "user_id": str(c.user_id),
            "correction_type": c.correction_type,
            "new_class_id": c.new_class_id if c.new_class_id is not None else "",
            "training_consent": c.training_consent,
            "created_at": c.created_at.isoformat() if c.created_at else "",
        }
        for c in corrections
    ]


def generate_csv(db: Session, drawing_id: UUID) -> bytes:
    """Encode the drawing's symbols as a UTF-8 CSV (all symbols, incl. rejected)."""
    rows = build_symbol_rows(db, drawing_id, include_rejected=True)

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(SYMBOL_COLUMNS))
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def generate_xlsx(db: Session, drawing_id: UUID) -> bytes:
    """Encode the drawing as an XLSX workbook with ``Symbols`` + ``Corrections``.

    ``Symbols`` holds the non-rejected symbols (same columns as the CSV);
    ``Corrections`` holds every correction for the drawing.
    """
    # Imported lazily so a missing openpyxl only breaks XLSX exports, not the
    # whole module / CSV path.
    from openpyxl import Workbook

    wb = Workbook()

    symbols_ws = wb.active
    symbols_ws.title = "Symbols"
    symbols_ws.append(list(SYMBOL_COLUMNS))
    for row in build_symbol_rows(db, drawing_id, include_rejected=False):
        symbols_ws.append([row[col] for col in SYMBOL_COLUMNS])

    corrections_ws = wb.create_sheet(title="Corrections")
    corrections_ws.append(list(CORRECTION_COLUMNS))
    for row in build_correction_rows(db, drawing_id):
        corrections_ws.append([row[col] for col in CORRECTION_COLUMNS])

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


__all__ = [
    "SYMBOL_COLUMNS",
    "CORRECTION_COLUMNS",
    "CSV_CONTENT_TYPE",
    "XLSX_CONTENT_TYPE",
    "build_symbol_rows",
    "build_correction_rows",
    "generate_csv",
    "generate_xlsx",
]
