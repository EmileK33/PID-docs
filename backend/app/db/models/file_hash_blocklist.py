"""FILE_HASH_BLOCKLIST model (§1.2)."""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FileHashBlocklist(Base):
    __tablename__ = "file_hash_blocklist"

    sha256_hash: Mapped[str] = mapped_column(String, primary_key=True)
    blocked_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    reason: Mapped[str] = mapped_column(String, nullable=False)
