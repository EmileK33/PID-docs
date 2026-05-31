"""AUDIT_LOG model (§1.2) — RANGE-partitioned by ``occurred_at``.

Partitioning notes:
* The parent table is declared ``PARTITION BY RANGE (occurred_at)``. Postgres
  requires the partition key to be part of any unique constraint, so the PK is
  the composite ``(id, occurred_at)``.
* Monthly partitions are named ``audit_log_YYYY_MM`` (2-year retention policy is
  operational, not enforced here). Migration ``0003_audit_partitions`` creates
  the parent table and the current + next month partitions.
* ``create_audit_log_partition(year, month)`` is exported for operational tooling
  and reused by the migration so partition DDL has a single source of truth.

The ``metadata`` column maps to the Python attribute ``event_metadata`` because
``metadata`` is reserved on the SQLAlchemy declarative base.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("idx_audit_log_user_date", "user_id", text("occurred_at DESC")),
        {"postgresql_partition_by": "RANGE (occurred_at)"},
    )

    # Composite PK (id, occurred_at) — partition key must be part of the PK.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id")
    )
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    entity_type: Mapped[Optional[str]] = mapped_column(String)
    occurred_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        nullable=False,
        server_default=text("now()"),
    )
    # DB column name is "metadata"; attribute is event_metadata (reserved word).
    event_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB)


# ---------------------------------------------------------------------------
# Partition management (single source of truth, reused by migration 0003)
# ---------------------------------------------------------------------------
def partition_name(year: int, month: int) -> str:
    """``audit_log_YYYY_MM`` partition name for the given month."""
    return f"audit_log_{year:04d}_{month:02d}"


def _partition_bounds(year: int, month: int) -> tuple[datetime.date, datetime.date]:
    start = datetime.date(year, month, 1)
    if month == 12:
        end = datetime.date(year + 1, 1, 1)
    else:
        end = datetime.date(year, month + 1, 1)
    return start, end


def partition_ddl(year: int, month: int) -> str:
    """Return idempotent ``CREATE TABLE ... PARTITION OF audit_log`` DDL."""
    start, end = _partition_bounds(year, month)
    name = partition_name(year, month)
    return (
        f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF audit_log "
        f"FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')"
    )


def create_audit_log_partition(year: int, month: int) -> None:
    """Create the ``audit_log_YYYY_MM`` partition for ``year``/``month``.

    Idempotent (``CREATE TABLE IF NOT EXISTS``). Uses the application engine
    (``app.db.session.engine``) so operational tooling can call it directly.
    """
    from app.db.session import engine

    with engine.begin() as conn:
        conn.execute(text(partition_ddl(year, month)))
