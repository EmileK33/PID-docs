"""DETECTED_SYMBOL model (§1.2).

``drawing_id`` FK uses ``ON DELETE CASCADE``. Confidence range CHECK is named
``detected_symbol_confidence_range`` for traceability.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DetectedSymbol(Base):
    __tablename__ = "detected_symbol"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="detected_symbol_confidence_range",
        ),
        CheckConstraint(
            "source IN ('ml','manual')", name="detected_symbol_source_check"
        ),
        Index(
            "idx_detected_symbol_drawing_rejected_class",
            "drawing_id",
            "rejected",
            "entity_class_id",
        ),
        Index("idx_detected_symbol_drawing_page", "drawing_id", "page_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    drawing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drawing.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_class_id: Mapped[str] = mapped_column(
        String, ForeignKey("entity_class.id"), nullable=False
    )
    subtype: Mapped[Optional[str]] = mapped_column(String)
    tag_label: Mapped[Optional[str]] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    bbox: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    rejected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
