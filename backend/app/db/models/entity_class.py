"""ENTITY_CLASS model (§1.2). ``id`` values are the ``EntityClassId`` literals."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EntityClass(Base):
    __tablename__ = "entity_class"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # EntityClassId values
    name: Mapped[str] = mapped_column(String, nullable=False)
    parent_class: Mapped[Optional[str]] = mapped_column(String)
    color_hex: Mapped[str] = mapped_column(String, nullable=False)
