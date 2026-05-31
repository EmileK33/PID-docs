"""ML_TRAINING_CONSENT model (§1.2). ``consent_user_or_team`` is a load-bearing
XOR constraint name."""
from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MLTrainingConsent(Base):
    __tablename__ = "ml_training_consent"
    __table_args__ = (
        CheckConstraint(
            "(user_id IS NOT NULL AND team_id IS NULL) OR "
            "(user_id IS NULL AND team_id IS NOT NULL)",
            name="consent_user_or_team",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id")
    )
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("team.id")
    )
    opted_in: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
