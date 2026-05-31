"""STRIPE_EVENT model (§1.4 rule 10 — webhook idempotency).

``id`` is the Stripe-supplied string event ID (``evt_*``) and is the PRIMARY KEY,
so concurrent INSERTs rely on PK-conflict for atomic idempotency (a plain UNIQUE
is insufficient). Index ``idx_stripe_event_received`` is created in migration
``0001_initial_schema``.
"""
from __future__ import annotations

import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StripeEvent(Base):
    __tablename__ = "stripe_event"
    __table_args__ = (
        Index("idx_stripe_event_received", text("received_at DESC")),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)  # Stripe event ID (evt_*)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    received_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    processed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
