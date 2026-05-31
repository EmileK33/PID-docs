"""USER_CORRECTION model (§1.2).

``correction_symbol_or_cell`` is a load-bearing XOR constraint name. The
partial index ``idx_user_correction_consent`` (WHERE training_consent = TRUE) is
created in migration ``0001_initial_schema`` (partial-index predicates are not
expressible as a plain ORM ``Index`` here). FKs do NOT cascade — corrections are
retained for ML/audit data.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserCorrection(Base):
    __tablename__ = "user_correction"
    __table_args__ = (
        CheckConstraint(
            "correction_type IN ('reclassify','reject','restore','manual_add')",
            name="user_correction_type_check",
        ),
        CheckConstraint(
            "(detected_symbol_id IS NOT NULL AND table_cell_id IS NULL) OR "
            "(detected_symbol_id IS NULL AND table_cell_id IS NOT NULL)",
            name="correction_symbol_or_cell",
        ),
        Index("idx_user_correction_symbol", "detected_symbol_id"),
        Index("idx_user_correction_cell", "table_cell_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    detected_symbol_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("detected_symbol.id")
    )
    table_cell_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("table_cell.id")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    correction_type: Mapped[str] = mapped_column(String, nullable=False)
    new_class_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("entity_class.id")
    )
    training_consent: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
