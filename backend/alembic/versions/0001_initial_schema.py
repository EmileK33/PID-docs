"""initial schema — §1.2 tables, indexes, constraints + seed data

Creates ``pgcrypto`` first (needed for ``gen_random_uuid()``), then every §1.2
table EXCEPT ``audit_log`` (the partitioned ``audit_log`` is owned by migration
``0003_audit_partitions``), plus ``stripe_event`` (§1.4 rule 10). DDL is emitted
verbatim from §1.2 so column types, NULL/NOT NULL, DEFAULTs and constraint names
match the spec exactly. Tier and entity_class seed rows are INSERTed here so a
fresh ``alembic upgrade head`` is fully populated.

Revision ID: 0001
Revises:
Create Date: 2026-05-31
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db.seed_entity_classes import ENTITY_CLASS_SEED_DATA
from app.db.seed_tiers import TIER_SEED_DATA

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Verbatim §1.2 DDL (audit_log + RLS handled in 0003 / 0002). Statements are run
# in dependency order.
_CREATE_STATEMENTS: list[str] = [
    # EXTENSIONS — must precede any gen_random_uuid() default.
    'CREATE EXTENSION IF NOT EXISTS "pgcrypto"',
    # TIER
    """
    CREATE TABLE tier (
      id          VARCHAR PRIMARY KEY,
      name        VARCHAR NOT NULL,
      monthly_drawing_limit  INTEGER,
      team_features          BOOLEAN NOT NULL DEFAULT FALSE,
      api_access             BOOLEAN NOT NULL DEFAULT FALSE
    )
    """,
    # TEAM
    """
    CREATE TABLE team (
      id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      name            VARCHAR NOT NULL,
      licensed_seats  INTEGER NOT NULL
    )
    """,
    # USER
    """
    CREATE TABLE "user" (
      id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      email                  VARCHAR NOT NULL,
      display_name           VARCHAR NOT NULL,
      password_hash          VARCHAR,
      email_verified         BOOLEAN NOT NULL DEFAULT FALSE,
      team_id                UUID REFERENCES team(id),
      role                   VARCHAR NOT NULL CHECK (role IN ('user','team_member','team_admin')),
      deleted_at             TIMESTAMPTZ,
      anonymous_id           VARCHAR,
      token_invalidated_at   TIMESTAMPTZ,
      CONSTRAINT user_email_unique UNIQUE (email)
    )
    """,
    'CREATE INDEX idx_user_team ON "user"(team_id)',
    'CREATE INDEX idx_user_email ON "user"(email)',
    # SUBSCRIPTION
    """
    CREATE TABLE subscription (
      id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id                 UUID REFERENCES "user"(id),
      team_id                 UUID REFERENCES team(id),
      tier_id                 VARCHAR NOT NULL REFERENCES tier(id),
      billing_state           VARCHAR NOT NULL CHECK (billing_state IN ('Active','Grace','Canceled')),
      grace_period_start      TIMESTAMPTZ,
      stripe_subscription_id  VARCHAR,
      stripe_customer_id      VARCHAR,
      current_period_end      TIMESTAMPTZ,
      CONSTRAINT subscription_user_or_team CHECK (
        (user_id IS NOT NULL AND team_id IS NULL) OR
        (user_id IS NULL AND team_id IS NOT NULL)
      )
    )
    """,
    "CREATE INDEX idx_subscription_user ON subscription(user_id)",
    "CREATE INDEX idx_subscription_team ON subscription(team_id)",
    # STORED_FILE
    """
    CREATE TABLE stored_file (
      id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      bucket       VARCHAR NOT NULL,
      object_key   VARCHAR NOT NULL,
      sha256_hash  VARCHAR NOT NULL,
      file_type    VARCHAR NOT NULL,
      size_bytes   BIGINT NOT NULL,
      CONSTRAINT stored_file_object_key_unique UNIQUE (bucket, object_key)
    )
    """,
    "CREATE INDEX idx_stored_file_hash ON stored_file(sha256_hash)",
    # FILE_HASH_BLOCKLIST
    """
    CREATE TABLE file_hash_blocklist (
      sha256_hash  VARCHAR PRIMARY KEY,
      blocked_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      reason       VARCHAR NOT NULL
    )
    """,
    # DRAWING
    """
    CREATE TABLE drawing (
      id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      owner_user_id          UUID REFERENCES "user"(id),
      owner_team_id          UUID REFERENCES team(id),
      filename               VARCHAR NOT NULL,
      revision_label         VARCHAR,
      processing_state       VARCHAR NOT NULL CHECK (processing_state IN (
        'Pending','Queued','Scanning','Processing','Complete','Under_Review','Failed','Scan_Failed'
      )),
      page_count             INTEGER,
      estimated_symbol_count INTEGER,
      uploaded_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      processed_at           TIMESTAMPTZ,
      stored_file_id         UUID REFERENCES stored_file(id),
      CONSTRAINT drawing_owner CHECK (
        (owner_user_id IS NOT NULL AND owner_team_id IS NULL) OR
        (owner_user_id IS NULL AND owner_team_id IS NOT NULL)
      )
    )
    """,
    "CREATE INDEX idx_drawing_team_state_date ON drawing(owner_team_id, processing_state, uploaded_at DESC)",
    "CREATE INDEX idx_drawing_user ON drawing(owner_user_id)",
    "CREATE INDEX idx_drawing_fts ON drawing USING GIN "
    "(to_tsvector('english', filename || ' ' || COALESCE(revision_label, '')))",
    # ENTITY_CLASS
    """
    CREATE TABLE entity_class (
      id           VARCHAR PRIMARY KEY,
      name         VARCHAR NOT NULL,
      parent_class VARCHAR,
      color_hex    VARCHAR NOT NULL
    )
    """,
    # DETECTED_SYMBOL
    """
    CREATE TABLE detected_symbol (
      id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      drawing_id      UUID NOT NULL REFERENCES drawing(id) ON DELETE CASCADE,
      entity_class_id VARCHAR NOT NULL REFERENCES entity_class(id),
      subtype         VARCHAR,
      tag_label       VARCHAR,
      confidence      FLOAT NOT NULL CONSTRAINT detected_symbol_confidence_range CHECK (confidence >= 0 AND confidence <= 1),
      bbox            JSONB NOT NULL,
      source          VARCHAR NOT NULL CHECK (source IN ('ml','manual')),
      rejected        BOOLEAN NOT NULL DEFAULT FALSE,
      page_number     INTEGER NOT NULL
    )
    """,
    "CREATE INDEX idx_detected_symbol_drawing_rejected_class ON detected_symbol(drawing_id, rejected, entity_class_id)",
    "CREATE INDEX idx_detected_symbol_drawing_page ON detected_symbol(drawing_id, page_number)",
    # TABLE_CELL
    """
    CREATE TABLE table_cell (
      id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      drawing_id                  UUID NOT NULL REFERENCES drawing(id) ON DELETE CASCADE,
      page_number                 INTEGER NOT NULL,
      row_label                   VARCHAR NOT NULL,
      column_label                VARCHAR NOT NULL,
      bbox                        JSONB NOT NULL,
      extracted_value             VARCHAR,
      corrected_value             VARCHAR,
      correction_training_consent BOOLEAN,
      corrected_at                TIMESTAMPTZ,
      corrected_by_user_id        UUID REFERENCES "user"(id)
    )
    """,
    "CREATE INDEX idx_table_cell_drawing_page ON table_cell(drawing_id, page_number)",
    # USER_CORRECTION
    """
    CREATE TABLE user_correction (
      id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      detected_symbol_id  UUID REFERENCES detected_symbol(id),
      table_cell_id       UUID REFERENCES table_cell(id),
      user_id             UUID NOT NULL REFERENCES "user"(id),
      correction_type     VARCHAR NOT NULL CHECK (correction_type IN ('reclassify','reject','restore','manual_add')),
      new_class_id        VARCHAR REFERENCES entity_class(id),
      training_consent    BOOLEAN NOT NULL,
      created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      CONSTRAINT correction_symbol_or_cell CHECK (
        (detected_symbol_id IS NOT NULL AND table_cell_id IS NULL) OR
        (detected_symbol_id IS NULL AND table_cell_id IS NOT NULL)
      )
    )
    """,
    "CREATE INDEX idx_user_correction_symbol ON user_correction(detected_symbol_id)",
    "CREATE INDEX idx_user_correction_cell ON user_correction(table_cell_id)",
    "CREATE INDEX idx_user_correction_consent ON user_correction(training_consent) WHERE training_consent = TRUE",
    # EXPORT_RECORD
    """
    CREATE TABLE export_record (
      id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      drawing_id      UUID NOT NULL REFERENCES drawing(id),
      user_id         UUID NOT NULL REFERENCES "user"(id),
      format          VARCHAR NOT NULL CHECK (format IN ('csv','xlsx')),
      status          VARCHAR NOT NULL CHECK (status IN ('Queued','Generating','Complete','Failed')),
      stored_file_id  UUID REFERENCES stored_file(id),
      initiated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      completed_at    TIMESTAMPTZ
    )
    """,
    # ML_TRAINING_CONSENT
    """
    CREATE TABLE ml_training_consent (
      id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id     UUID REFERENCES "user"(id),
      team_id     UUID REFERENCES team(id),
      opted_in    BOOLEAN NOT NULL DEFAULT FALSE,
      updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      CONSTRAINT consent_user_or_team CHECK (
        (user_id IS NOT NULL AND team_id IS NULL) OR
        (user_id IS NULL AND team_id IS NOT NULL)
      )
    )
    """,
    # REVISION_COMPARISON
    """
    CREATE TABLE revision_comparison (
      id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      drawing_a_id        UUID NOT NULL REFERENCES drawing(id),
      drawing_b_id        UUID NOT NULL REFERENCES drawing(id),
      match_result        JSONB,
      computed_at         TIMESTAMPTZ,
      last_correction_at  TIMESTAMPTZ
    )
    """,
    # STRIPE_EVENT (§1.4 rule 10 — webhook idempotency; id = Stripe event ID PK)
    """
    CREATE TABLE stripe_event (
      id            VARCHAR PRIMARY KEY,
      event_type    VARCHAR NOT NULL,
      received_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      processed_at  TIMESTAMPTZ,
      payload       JSONB NOT NULL
    )
    """,
    "CREATE INDEX idx_stripe_event_received ON stripe_event(received_at DESC)",
]

# Drop order is the reverse of creation (children before parents).
_DROP_TABLES: list[str] = [
    "stripe_event",
    "revision_comparison",
    "ml_training_consent",
    "export_record",
    "user_correction",
    "table_cell",
    "detected_symbol",
    "entity_class",
    "drawing",
    "file_hash_blocklist",
    "stored_file",
    "subscription",
    '"user"',
    "team",
    "tier",
]


def upgrade() -> None:
    for stmt in _CREATE_STATEMENTS:
        op.execute(stmt)

    # Seed data — INSERTed in-migration so a fresh DB is fully populated.
    tier_table = sa.table(
        "tier",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("monthly_drawing_limit", sa.Integer),
        sa.column("team_features", sa.Boolean),
        sa.column("api_access", sa.Boolean),
    )
    op.bulk_insert(tier_table, [dict(r) for r in TIER_SEED_DATA])

    entity_class_table = sa.table(
        "entity_class",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("parent_class", sa.String),
        sa.column("color_hex", sa.String),
    )
    op.bulk_insert(entity_class_table, [dict(r) for r in ENTITY_CLASS_SEED_DATA])


def downgrade() -> None:
    for table in _DROP_TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    # pgcrypto is environment-level (also created by the fixture initdb); leave it.
