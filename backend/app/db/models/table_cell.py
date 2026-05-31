"""TABLE_CELL model (§1.2). ``drawing_id`` FK uses ``ON DELETE CASCADE``."""
from __future__ import annotations

import datetime
import uuid
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TableCell(Base):
    __tablename__ = "table_cell"
    __table_args__ = (
        Index("idx_table_cell_drawing_page", "drawing_id", "page_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    drawing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drawing.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    row_label: Mapped[str] = mapped_column(String, nullable=False)
    column_label: Mapped[str] = mapped_column(String, nullable=False)
    bbox: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    extracted_value: Mapped[Optional[str]] = mapped_column(String)
    corrected_value: Mapped[Optional[str]] = mapped_column(String)
    correction_training_consent: Mapped[Optional[bool]] = mapped_column(Boolean)
    corrected_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    corrected_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id")
    )
