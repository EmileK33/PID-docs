"""S1-A — DB Models & Migrations: schema/structural integration tests.

These tests run against a real Postgres 15 instance (the S0-B fixture compose,
``tests/integration/docker-compose.fixtures.yml``) and verify the §1.2 schema
exactly: tables, columns, named constraints, indexes, partitioning, RLS, seed
data and FK cascade behaviour.

Harness note: the S0-B harness exposes the session-scoped ``db_engine`` and the
function-scoped transactional ``db_session`` (see ``tests/integration/conftest.py``).
It does NOT ship the ``migrate_to_head()`` / ``drop_all()`` helpers referenced in
some early planning docs, so this module drives Alembic directly via the
``alembic.command`` API and resets the schema itself.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

# --- import bootstrap ------------------------------------------------------
# Make both import roots resolvable in-process:
#   * ``app.*``          — the root Alembic's env.py imports (backend/ on path)
#   * ``backend.app.*``  — the cross-session contract downstream code imports
# tests/integration/test_db_schema.py -> parents[2] == repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
for _p in (str(REPO_ROOT), str(BACKEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# The S0-B harness exports DATABASE_URL as a driver-agnostic ``postgresql://``
# URI. SQLAlchemy/Alembic must use psycopg v3 explicitly (psycopg2 is not
# installed), and Alembic's env.py rebuilds the engine URL from
# ``settings.DATABASE_URL`` — so the env var itself must name the driver. Rewrite
# it BEFORE any ``app`` import triggers the ``settings`` singleton.
_db_url = os.environ.get(
    "DATABASE_URL", "postgresql://pidtest:pidtest@localhost:55432/pidtest"
)
if "+psycopg" not in _db_url and _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+psycopg://", 1)
os.environ["DATABASE_URL"] = _db_url

# Alembic's env.py imports ``app.config``, whose §1.12 contract marks
# ML_MODEL_S3_KEY and ODA_CONVERTER_PATH as REQUIRED ("refuse to start"). The
# S0-B harness conftest only seeds the subset its smoke suite needs, so supply
# test-safe values here before the ``settings`` singleton is constructed.
os.environ.setdefault("ML_MODEL_S3_KEY", "models/test-model.onnx")
os.environ.setdefault("ODA_CONVERTER_PATH", "/usr/bin/ODAFileConverter")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402


def _postgres_available() -> bool:
    """True iff the Postgres fixture is reachable.

    The authoritative ``session-tests`` PR gate runs this file with bare pytest
    and NO Docker backing services, whereas ``integration.yml`` (and local dev)
    bring up the fixture stack. These schema tests exercise Postgres-only
    features (pgcrypto, JSONB, GIN tsvector, partial indexes, RANGE partitioning,
    RLS) that cannot be emulated on SQLite, so when Postgres is absent the whole
    module skips cleanly rather than failing the gate. The real validation runs
    under integration.yml where Postgres is live.
    """
    try:
        from sqlalchemy import create_engine
        from sqlalchemy import text as _text

        eng = create_engine(
            os.environ["DATABASE_URL"], connect_args={"connect_timeout": 3}
        )
        try:
            with eng.connect() as conn:
                conn.execute(_text("SELECT 1"))
        finally:
            eng.dispose()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_available(),
    reason="Postgres fixture unreachable (session-tests gate runs bare pytest "
    "with no Docker); integration.yml / local runs execute these for real.",
)


# ---------------------------------------------------------------------------
# Alembic / schema lifecycle helpers
# ---------------------------------------------------------------------------
def _alembic_config() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    # env.py overrides sqlalchemy.url from settings.DATABASE_URL (already a
    # +psycopg URL via the rewrite above); this line is belt-and-suspenders.
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    return cfg


def _reset_schema(engine) -> None:
    """Drop everything to simulate a pristine, empty database."""
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()


def _upgrade_head() -> None:
    command.upgrade(_alembic_config(), "head")


def _table_names(engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        ).scalars()
        return set(rows)


@pytest.fixture(scope="module")
def migrated_db(db_engine):
    """Reset the schema and apply all migrations once for the module."""
    _reset_schema(db_engine)
    _upgrade_head()
    yield db_engine


# ---------------------------------------------------------------------------
# Expected schema descriptors (from §1.2 + stripe_event)
# ---------------------------------------------------------------------------
EXPECTED_TABLES = [
    "tier",
    "team",
    "user",
    "subscription",
    "stored_file",
    "file_hash_blocklist",
    "drawing",
    "entity_class",
    "detected_symbol",
    "table_cell",
    "user_correction",
    "export_record",
    "ml_training_consent",
    "revision_comparison",
    "audit_log",
    "stripe_event",
]

EXPECTED_NAMED_CHECK_CONSTRAINTS = [
    "subscription_user_or_team",
    "drawing_owner",
    "consent_user_or_team",
    "correction_symbol_or_cell",
    "detected_symbol_confidence_range",
]

EXPECTED_INDEXES = [
    "idx_user_team",
    "idx_user_email",
    "idx_subscription_user",
    "idx_subscription_team",
    "idx_stored_file_hash",
    "idx_drawing_team_state_date",
    "idx_drawing_user",
    "idx_drawing_fts",
    "idx_detected_symbol_drawing_rejected_class",
    "idx_detected_symbol_drawing_page",
    "idx_table_cell_drawing_page",
    "idx_user_correction_symbol",
    "idx_user_correction_cell",
    "idx_user_correction_consent",
    "idx_audit_log_user_date",
]


# ---------------------------------------------------------------------------
# Migration lifecycle
# ---------------------------------------------------------------------------
def test_alembic_upgrade_head_clean(db_engine):
    """`alembic upgrade head` from an empty database creates every table."""
    _reset_schema(db_engine)
    _upgrade_head()
    tables = _table_names(db_engine)
    for expected in EXPECTED_TABLES:
        assert expected in tables, f"missing table after upgrade: {expected}"


def test_alembic_downgrade_base(db_engine):
    """`alembic downgrade base` removes all session-owned tables, then re-upgrade."""
    _reset_schema(db_engine)
    _upgrade_head()
    cfg = _alembic_config()
    try:
        command.downgrade(cfg, "base")
        tables = _table_names(db_engine)
        for t in EXPECTED_TABLES:
            assert t not in tables, f"table survived downgrade base: {t}"
    finally:
        command.upgrade(cfg, "head")


def test_pgcrypto_extension_present(migrated_db):
    with migrated_db.connect() as conn:
        present = conn.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto'")
        ).scalar()
    assert present == 1


# ---------------------------------------------------------------------------
# Tables / columns
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("table", EXPECTED_TABLES)
def test_all_tables_present(migrated_db, table):
    assert table in _table_names(migrated_db)


def test_user_anonymous_id_nullable_no_default(migrated_db):
    with migrated_db.connect() as conn:
        row = conn.execute(
            text(
                "SELECT is_nullable, column_default, data_type "
                "FROM information_schema.columns "
                "WHERE table_name = 'user' AND column_name = 'anonymous_id'"
            )
        ).one()
    is_nullable, column_default, data_type = row
    assert is_nullable == "YES"
    assert column_default is None
    assert data_type == "character varying"


def test_stripe_event_id_is_primary_key(migrated_db):
    with migrated_db.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT a.attname, format_type(a.atttypid, a.atttypmod)
                FROM pg_index i
                JOIN pg_attribute a
                  ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = 'stripe_event'::regclass AND i.indisprimary
                """
            )
        ).all()
    cols = {name: typ for name, typ in row}
    assert list(cols.keys()) == ["id"], f"stripe_event PK should be (id), got {cols}"
    assert cols["id"].startswith("character varying")


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("constraint", EXPECTED_NAMED_CHECK_CONSTRAINTS)
def test_named_check_constraints_present(migrated_db, constraint):
    with migrated_db.connect() as conn:
        present = conn.execute(
            text(
                "SELECT 1 FROM pg_constraint WHERE conname = :n AND contype = 'c'"
            ),
            {"n": constraint},
        ).scalar()
    assert present == 1, f"missing CHECK constraint: {constraint}"


def test_value_set_check_constraints_present(migrated_db):
    """The value-set CHECKs (role, processing_state, ...) exist as CHECKs."""
    checks = {
        "user": "role",
        "drawing": "processing_state",
        "subscription": "billing_state",
        "detected_symbol": "source",
        "user_correction": "correction_type",
        "export_record": "format",
    }
    with migrated_db.connect() as conn:
        for table, col in checks.items():
            # Find CHECK constraints on the table whose definition references col.
            defs = conn.execute(
                text(
                    """
                    SELECT pg_get_constraintdef(c.oid)
                    FROM pg_constraint c
                    WHERE c.conrelid = (:t)::regclass AND c.contype = 'c'
                    """
                ),
                {"t": f'"{table}"'},
            ).scalars().all()
            assert any(col in d for d in defs), (
                f"no CHECK referencing {table}.{col}: {defs}"
            )
    # status CHECK lives on export_record too
    with migrated_db.connect() as conn:
        defs = conn.execute(
            text(
                "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
                "WHERE c.conrelid = 'export_record'::regclass AND c.contype = 'c'"
            )
        ).scalars().all()
    assert any("status" in d for d in defs)


def test_unique_constraints_present(migrated_db):
    with migrated_db.connect() as conn:
        names = set(
            conn.execute(
                text("SELECT conname FROM pg_constraint WHERE contype = 'u'")
            ).scalars()
        )
    assert "user_email_unique" in names
    assert "stored_file_object_key_unique" in names


# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("index", EXPECTED_INDEXES)
def test_indexes_present(migrated_db, index):
    with migrated_db.connect() as conn:
        present = conn.execute(
            text("SELECT 1 FROM pg_indexes WHERE indexname = :n"),
            {"n": index},
        ).scalar()
    assert present == 1, f"missing index: {index}"


def test_drawing_fts_index_definition(migrated_db):
    with migrated_db.connect() as conn:
        indexdef = conn.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'idx_drawing_fts'")
        ).scalar_one()
    lowered = indexdef.lower()
    assert "gin" in lowered
    assert "to_tsvector" in lowered
    assert "'english'" in lowered
    assert "coalesce" in lowered
    assert "revision_label" in lowered
    assert "filename" in lowered


def test_user_correction_consent_partial_index(migrated_db):
    with migrated_db.connect() as conn:
        indexdef = conn.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE indexname = 'idx_user_correction_consent'"
            )
        ).scalar_one()
    lowered = indexdef.lower()
    assert "where" in lowered
    assert "training_consent" in lowered
    assert "true" in lowered


# ---------------------------------------------------------------------------
# FK cascade behaviour
# ---------------------------------------------------------------------------
def _fk_delete_action(conn, table: str, constraint_cols: str) -> str:
    """Return confdeltype ('c' cascade, 'a' no action, ...) for an FK on `table`
    whose referencing column list contains `constraint_cols`."""
    rows = conn.execute(
        text(
            """
            SELECT pg_get_constraintdef(c.oid), c.confdeltype
            FROM pg_constraint c
            WHERE c.conrelid = (:t)::regclass AND c.contype = 'f'
            """
        ),
        {"t": f'"{table}"'},
    ).all()
    for definition, deltype in rows:
        if constraint_cols in definition:
            return deltype
    raise AssertionError(f"no FK on {table} referencing {constraint_cols}: {rows}")


def test_detected_symbol_drawing_fk_cascade(migrated_db):
    with migrated_db.connect() as conn:
        assert _fk_delete_action(conn, "detected_symbol", "drawing_id") == "c"


def test_table_cell_drawing_fk_cascade(migrated_db):
    with migrated_db.connect() as conn:
        assert _fk_delete_action(conn, "table_cell", "drawing_id") == "c"


def test_no_cascade_on_corrections_exports_revisions(migrated_db):
    with migrated_db.connect() as conn:
        # user_correction -> detected_symbol / user: no cascade
        assert _fk_delete_action(conn, "user_correction", "detected_symbol_id") == "a"
        # export_record -> drawing: no cascade
        assert _fk_delete_action(conn, "export_record", "drawing_id") == "a"
        # revision_comparison -> drawing: no cascade
        assert _fk_delete_action(conn, "revision_comparison", "drawing_a_id") == "a"


# --- behavioural cascade tests (run inside a rolled-back transaction) ------
def _seed_user(session, uid: str = None) -> str:
    uid = uid or "11111111-1111-1111-1111-111111111111"
    session.execute(
        text(
            "INSERT INTO \"user\" (id, email, display_name, role) "
            "VALUES (:id, :email, 'T', 'user')"
        ),
        {"id": uid, "email": f"{uid}@example.com"},
    )
    return uid


def _seed_drawing(session, did: str, owner: str) -> str:
    session.execute(
        text(
            "INSERT INTO drawing (id, owner_user_id, filename, processing_state) "
            "VALUES (:id, :owner, 'f.pdf', 'Pending')"
        ),
        {"id": did, "owner": owner},
    )
    return did


def _seed_symbol(session, sid: str, did: str) -> str:
    session.execute(
        text(
            "INSERT INTO detected_symbol "
            "(id, drawing_id, entity_class_id, confidence, bbox, source, page_number) "
            "VALUES (:id, :did, 'pipe', 0.5, '{}'::jsonb, 'ml', 1)"
        ),
        {"id": sid, "did": did},
    )
    return sid


def test_drawing_cascade_to_symbols_and_cells(migrated_db, db_session):
    uid = _seed_user(db_session)
    did = "22222222-2222-2222-2222-222222222222"
    _seed_drawing(db_session, did, uid)
    sid = "33333333-3333-3333-3333-333333333333"
    _seed_symbol(db_session, sid, did)
    db_session.execute(
        text(
            "INSERT INTO table_cell (id, drawing_id, page_number, row_label, "
            "column_label, bbox) VALUES "
            "('44444444-4444-4444-4444-444444444444', :did, 1, 'r', 'c', '{}'::jsonb)"
        ),
        {"did": did},
    )
    db_session.flush()
    db_session.execute(text("DELETE FROM drawing WHERE id = :did"), {"did": did})
    db_session.flush()
    sym = db_session.execute(
        text("SELECT count(*) FROM detected_symbol WHERE drawing_id = :did"),
        {"did": did},
    ).scalar()
    cell = db_session.execute(
        text("SELECT count(*) FROM table_cell WHERE drawing_id = :did"),
        {"did": did},
    ).scalar()
    assert sym == 0 and cell == 0


def test_drawing_delete_blocked_by_export_record(migrated_db, db_session):
    """export_record FK does not cascade → deleting the drawing is RESTRICTed."""
    import sqlalchemy.exc

    uid = _seed_user(db_session)
    did = "55555555-5555-5555-5555-555555555555"
    _seed_drawing(db_session, did, uid)
    db_session.execute(
        text(
            "INSERT INTO export_record (id, drawing_id, user_id, format, status) "
            "VALUES ('66666666-6666-6666-6666-666666666666', :did, :uid, 'csv', 'Queued')"
        ),
        {"did": did, "uid": uid},
    )
    db_session.flush()
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        db_session.execute(text("DELETE FROM drawing WHERE id = :did"), {"did": did})
        db_session.flush()


# ---------------------------------------------------------------------------
# audit_log partitioning
# ---------------------------------------------------------------------------
def test_audit_log_is_partitioned(migrated_db):
    with migrated_db.connect() as conn:
        relkind = conn.execute(
            text("SELECT relkind FROM pg_class WHERE relname = 'audit_log'")
        ).scalar_one()
    assert relkind == "p", "audit_log must be a partitioned table (relkind 'p')"


def test_audit_log_pk_is_composite(migrated_db):
    with migrated_db.connect() as conn:
        cols = conn.execute(
            text(
                """
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a
                  ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = 'audit_log'::regclass AND i.indisprimary
                ORDER BY a.attnum
                """
            )
        ).scalars().all()
    assert set(cols) == {"id", "occurred_at"}, f"audit_log PK should be (id, occurred_at), got {cols}"


def test_audit_log_partitions_for_current_and_next_month_exist(migrated_db):
    from datetime import date

    today = date.today()
    cur = f"audit_log_{today.year:04d}_{today.month:02d}"
    if today.month == 12:
        ny, nm = today.year + 1, 1
    else:
        ny, nm = today.year, today.month + 1
    nxt = f"audit_log_{ny:04d}_{nm:02d}"
    tables = _table_names(migrated_db)
    assert cur in tables, f"missing current-month partition {cur}"
    assert nxt in tables, f"missing next-month partition {nxt}"


def test_create_audit_log_partition_helper(migrated_db):
    # Package-level import (the cross-session contract). Importing the submodule
    # directly under the ``backend.`` root would re-execute the model class body
    # against the canonical ``app.db.base.Base`` metadata and raise a duplicate-
    # table error — downstream code imports from the package, which re-exports it.
    from backend.app.db.models import create_audit_log_partition

    # A far-future partition that the migration would not have created.
    create_audit_log_partition(2099, 7)
    assert "audit_log_2099_07" in _table_names(migrated_db)
    # idempotent: a second call must not raise.
    create_audit_log_partition(2099, 7)


# ---------------------------------------------------------------------------
# RLS
# ---------------------------------------------------------------------------
RLS_TABLES = ["drawing", "detected_symbol", "table_cell", "user_correction", "export_record"]


@pytest.mark.parametrize("table", RLS_TABLES)
def test_rls_enabled_on_required_tables(migrated_db, table):
    with migrated_db.connect() as conn:
        row = conn.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity "
                "FROM pg_class WHERE relname = :n"
            ),
            {"n": table},
        ).one()
    relrowsecurity, relforce = row
    assert relrowsecurity is True, f"RLS not enabled on {table}"
    assert relforce is True, f"FORCE RLS not set on {table}"


def test_no_row_policies_defined(migrated_db):
    with migrated_db.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM pg_policy")).scalar()
    assert count == 0, "no CREATE POLICY statements should exist in S1-A"


def test_rls_migration_downgrade_reversible(db_engine):
    """0002 downgrade disables RLS without error, then restore head."""
    cfg = _alembic_config()
    _reset_schema(db_engine)
    _upgrade_head()
    try:
        command.downgrade(cfg, "0001")
        with db_engine.connect() as conn:
            relforce = conn.execute(
                text("SELECT relforcerowsecurity FROM pg_class WHERE relname = 'drawing'")
            ).scalar_one()
        assert relforce is False
    finally:
        command.upgrade(cfg, "head")


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------
def test_tier_seed_rows(migrated_db):
    with migrated_db.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, monthly_drawing_limit, team_features, api_access "
                "FROM tier ORDER BY id"
            )
        ).all()
    by_id = {r[0]: r for r in rows}
    assert set(by_id) == {"free", "pro", "team"}
    assert by_id["free"][1] == 3
    assert by_id["pro"][1] is None
    assert by_id["team"][1] is None
    assert by_id["team"][2] is True
    assert by_id["free"][2] is False
    assert all(r[3] is False for r in rows)  # api_access false for all three


def test_entity_class_seed_rows(migrated_db):
    expected = {
        "pipe",
        "valve_gate",
        "valve_globe",
        "valve_ball",
        "valve_butterfly",
        "valve_check",
        "valve_control",
        "instrument",
    }
    with migrated_db.connect() as conn:
        rows = conn.execute(text("SELECT id, color_hex FROM entity_class")).all()
    ids = {r[0] for r in rows}
    assert ids == expected
    assert all(r[1] for r in rows), "every entity_class needs a non-empty color_hex"


def test_valve_parent_class_relationships(migrated_db):
    with migrated_db.connect() as conn:
        rows = conn.execute(text("SELECT id, parent_class FROM entity_class")).all()
    parent = dict(rows)
    for vid in (
        "valve_gate",
        "valve_globe",
        "valve_ball",
        "valve_butterfly",
        "valve_check",
        "valve_control",
    ):
        assert parent[vid] == "valve", f"{vid} parent_class should be 'valve'"
    assert parent["pipe"] is None
    assert parent["instrument"] is None


# ---------------------------------------------------------------------------
# Constraint enforcement (behavioural, rolled back)
# ---------------------------------------------------------------------------
def _expect_integrity_error(session, sql, params=None):
    import sqlalchemy.exc

    with pytest.raises(sqlalchemy.exc.IntegrityError):
        session.execute(text(sql), params or {})
        session.flush()


def test_drawing_owner_xor_rejects_both_null(migrated_db, db_session):
    _expect_integrity_error(
        db_session,
        "INSERT INTO drawing (id, filename, processing_state) "
        "VALUES (gen_random_uuid(), 'f', 'Pending')",
    )


def test_drawing_owner_xor_rejects_both_set(migrated_db, db_session):
    uid = _seed_user(db_session)
    db_session.execute(
        text("INSERT INTO team (id, name, licensed_seats) "
             "VALUES ('77777777-7777-7777-7777-777777777777', 'T', 1)")
    )
    db_session.flush()
    _expect_integrity_error(
        db_session,
        "INSERT INTO drawing (id, owner_user_id, owner_team_id, filename, processing_state) "
        "VALUES (gen_random_uuid(), :u, '77777777-7777-7777-7777-777777777777', 'f', 'Pending')",
        {"u": uid},
    )


def test_subscription_xor(migrated_db, db_session):
    uid = _seed_user(db_session)
    db_session.execute(
        text("INSERT INTO team (id, name, licensed_seats) "
             "VALUES ('88888888-8888-8888-8888-888888888888', 'T', 1)")
    )
    db_session.flush()
    # both set -> reject
    _expect_integrity_error(
        db_session,
        "INSERT INTO subscription (id, user_id, team_id, tier_id, billing_state) "
        "VALUES (gen_random_uuid(), :u, '88888888-8888-8888-8888-888888888888', 'free', 'Active')",
        {"u": uid},
    )


def test_subscription_xor_both_null(migrated_db, db_session):
    _expect_integrity_error(
        db_session,
        "INSERT INTO subscription (id, tier_id, billing_state) "
        "VALUES (gen_random_uuid(), 'free', 'Active')",
    )


def test_user_correction_xor(migrated_db, db_session):
    uid = _seed_user(db_session)
    # both null -> reject
    _expect_integrity_error(
        db_session,
        "INSERT INTO user_correction (id, user_id, correction_type, training_consent) "
        "VALUES (gen_random_uuid(), :u, 'reject', false)",
        {"u": uid},
    )


def test_detected_symbol_confidence_range_check(migrated_db, db_session):
    uid = _seed_user(db_session)
    did = "99999999-9999-9999-9999-999999999999"
    _seed_drawing(db_session, did, uid)
    _expect_integrity_error(
        db_session,
        "INSERT INTO detected_symbol "
        "(id, drawing_id, entity_class_id, confidence, bbox, source, page_number) "
        "VALUES (gen_random_uuid(), :did, 'pipe', 1.5, '{}'::jsonb, 'ml', 1)",
        {"did": did},
    )


def test_detected_symbol_entity_class_fk(migrated_db, db_session):
    uid = _seed_user(db_session)
    did = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _seed_drawing(db_session, did, uid)
    _expect_integrity_error(
        db_session,
        "INSERT INTO detected_symbol "
        "(id, drawing_id, entity_class_id, confidence, bbox, source, page_number) "
        "VALUES (gen_random_uuid(), :did, 'not_a_class', 0.5, '{}'::jsonb, 'ml', 1)",
        {"did": did},
    )


# ---------------------------------------------------------------------------
# Cross-session import contracts
# ---------------------------------------------------------------------------
def test_all_models_importable_from_db_models():
    from backend.app.db.models import (  # noqa: F401
        AuditLog,
        DetectedSymbol,
        Drawing,
        EntityClass,
        ExportRecord,
        FileHashBlocklist,
        MLTrainingConsent,
        RevisionComparison,
        StoredFile,
        StripeEvent,
        Subscription,
        TableCell,
        Team,
        Tier,
        User,
        UserCorrection,
    )

    # Every model attaches to the same declarative Base / metadata. The models
    # package re-exports the canonical ``app.db.base.Base`` (the one Alembic
    # also targets), so downstream code imports Base from the package.
    from backend.app.db.models import Base

    assert User.__tablename__ == "user"
    assert User.__table__.metadata is Base.metadata


def test_seed_modules_export_constants():
    from backend.app.db.seed_tiers import TIER_SEED_DATA
    from backend.app.db.seed_entity_classes import ENTITY_CLASS_SEED_DATA

    assert isinstance(TIER_SEED_DATA, list) and len(TIER_SEED_DATA) == 3
    assert isinstance(ENTITY_CLASS_SEED_DATA, list) and len(ENTITY_CLASS_SEED_DATA) == 8
    assert {t["id"] for t in TIER_SEED_DATA} == {"free", "pro", "team"}
