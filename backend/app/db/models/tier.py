"""TIER model (§1.2)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Tier(Base):
    __tablename__ = "tier"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # 'free'|'pro'|'team'
    name: Mapped[str] = mapped_column(String, nullable=False)
    monthly_drawing_limit: Mapped[Optional[int]] = mapped_column(Integer)  # NULL = unlimited
    team_features: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    api_access: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
