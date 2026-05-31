"""REVISION_COMPARISON model (§1.2). FKs do NOT cascade (P1 surface, stubbed)."""
from __future__ import annotations

import datetime
import uuid
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RevisionComparison(Base):
    __tablename__ = "revision_comparison"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    drawing_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drawing.id"), nullable=False
    )
    drawing_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drawing.id"), nullable=False
    )
    match_result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    computed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    last_correction_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True)
    )
