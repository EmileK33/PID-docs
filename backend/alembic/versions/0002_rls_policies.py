"""enable RLS (defense-in-depth) on owned tables — §1.2

Enables ROW LEVEL SECURITY on the five tables listed in §1.2 and applies
``FORCE ROW LEVEL SECURITY`` so the table owner is also subject (application
connections may run as the owner in some deploy configs). Per §1.2, ownership is
enforced server-side in middleware as the PRIMARY control, so NO ``CREATE POLICY``
statements are added here — RLS-enabled-without-policy denies all row access in a
non-superuser context, which is the intended defense-in-depth posture.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-31
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RLS_TABLES: list[str] = [
    "drawing",
    "detected_symbol",
    "table_cell",
    "user_correction",
    "export_record",
]


def upgrade() -> None:
    for table in _RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in _RLS_TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
