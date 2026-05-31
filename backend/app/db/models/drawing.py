"""DRAWING model (§1.2).

``drawing_owner`` is a load-bearing XOR constraint name (§1.4 rule 5 — worker /
consent code parses it). The FTS GIN index ``idx_drawing_fts`` and the
``idx_drawing_team_state_date`` / ``idx_drawing_user`` indexes are created in
migration ``0001_initial_schema`` (the functional GIN expression is not
expressible as a plain ORM ``Index``).
"""
from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_PROCESSING_STATES = (
    "Pending",
    "Queued",
    "Scanning",
    "Processing",
    "Complete",
    "Under_Review",
    "Failed",
    "Scan_Failed",
)


class Drawing(Base):
    __tablename__ = "drawing"
    __table_args__ = (
        CheckConstraint(
            "processing_state IN ("
            + ",".join(f"'{s}'" for s in _PROCESSING_STATES)
            + ")",
            name="drawing_processing_state_check",
        ),
        CheckConstraint(
            "(owner_user_id IS NOT NULL AND owner_team_id IS NULL) OR "
            "(owner_user_id IS NULL AND owner_team_id IS NOT NULL)",
            name="drawing_owner",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    owner_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id")
    )
    owner_team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("team.id")
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    revision_label: Mapped[Optional[str]] = mapped_column(String)
    processing_state: Mapped[str] = mapped_column(String, nullable=False)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    estimated_symbol_count: Mapped[Optional[int]] = mapped_column(Integer)
    uploaded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    processed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    stored_file_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stored_file.id")
    )
