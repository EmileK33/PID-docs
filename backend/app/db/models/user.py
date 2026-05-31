"""USER model (§1.2).

Notes:
* ``"user"`` is a reserved word in PostgreSQL; ``__tablename__ = "user"`` makes
  SQLAlchemy quote it in generated DDL.
* ``anonymous_id`` MUST be NULLable with no default (§1.4 rule 11 — the GDPR
  erasure job writes it on first run, then reads it on retries).
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
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "user"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user','team_member','team_admin')", name="user_role_check"
        ),
        UniqueConstraint("email", name="user_email_unique"),
        Index("idx_user_team", "team_id"),
        Index("idx_user_email", "email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String)
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("team.id")
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    deleted_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    # HMAC-SHA256(user_id||server_secret), set on first erasure run. NULLable, no default.
    anonymous_id: Mapped[Optional[str]] = mapped_column(String)
    token_invalidated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True)
    )
