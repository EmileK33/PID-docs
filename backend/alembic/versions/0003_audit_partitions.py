"""partitioned audit_log + monthly partitions — §1.2

Creates the RANGE-partitioned ``audit_log`` parent table (partitioned by
``occurred_at``, composite PK ``(id, occurred_at)`` since the partition key must
be part of any unique constraint) and the rolling monthly partitions for the
current and next month. Partition DDL is sourced from
``app.db.models.audit_log.partition_ddl`` so it has a single definition.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-31
"""
from __future__ import annotations

import datetime
from typing import Sequence, Union

from alembic import op

from app.db.models.audit_log import partition_ddl

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _next_month(d: datetime.date) -> tuple[int, int]:
    if d.month == 12:
        return d.year + 1, 1
    return d.year, d.month + 1


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE audit_log (
          id            UUID NOT NULL DEFAULT gen_random_uuid(),
          user_id       UUID REFERENCES "user"(id),
          action_type   VARCHAR NOT NULL,
          entity_id     UUID,
          entity_type   VARCHAR,
          occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          metadata      JSONB,
          PRIMARY KEY (id, occurred_at)
        ) PARTITION BY RANGE (occurred_at)
        """
    )
    op.execute(
        "CREATE INDEX idx_audit_log_user_date ON audit_log(user_id, occurred_at DESC)"
    )

    # Rolling monthly partitions: current month + next month at migration time.
    today = datetime.date.today()
    op.execute(partition_ddl(today.year, today.month))
    ny, nm = _next_month(today)
    op.execute(partition_ddl(ny, nm))


def downgrade() -> None:
    # CASCADE drops the attached monthly partitions along with the parent.
    op.execute("DROP TABLE IF EXISTS audit_log CASCADE")
