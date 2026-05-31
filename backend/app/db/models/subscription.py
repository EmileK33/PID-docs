"""SUBSCRIPTION model (§1.2).

``subscription_user_or_team`` is a load-bearing XOR constraint name (§1.4).
"""
from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Subscription(Base):
    __tablename__ = "subscription"
    __table_args__ = (
        CheckConstraint(
            "billing_state IN ('Active','Grace','Canceled')",
            name="subscription_billing_state_check",
        ),
        CheckConstraint(
            "(user_id IS NOT NULL AND team_id IS NULL) OR "
            "(user_id IS NULL AND team_id IS NOT NULL)",
            name="subscription_user_or_team",
        ),
        Index("idx_subscription_user", "user_id"),
        Index("idx_subscription_team", "team_id"),
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
    tier_id: Mapped[str] = mapped_column(String, ForeignKey("tier.id"), nullable=False)
    billing_state: Mapped[str] = mapped_column(String, nullable=False)
    grace_period_start: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String)
    current_period_end: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True)
    )
