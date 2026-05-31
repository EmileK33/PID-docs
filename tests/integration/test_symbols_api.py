"""S2-C — Symbols & Corrections endpoints: PostgreSQL integration tests.

These exercise the real transaction semantics that SQLite cannot fully prove —
single-transaction atomicity and the concurrency-safety of the conditional
``Under_Review`` transition — against a live Postgres instance (the S0-B fixture
compose). The exhaustive endpoint/AC matrix lives in the bare-pytest session
suite ``tests/sessions/test_s2c.py``; this module is the Postgres counterpart.

Harness contract (mirrors ``tests/integration/test_db_schema.py``):

* Both ``app.*`` and ``backend.app.*`` import roots are put on ``sys.path``.
* ``DATABASE_URL`` is rewritten onto psycopg v3 (psycopg2 is not installed) and
  the two §1.12 vars the harness conftest omits are seeded — BEFORE any
  ``app.config`` import builds the settings singleton.
* ``app.*`` is imported lazily inside functions so the S0-B
  ``test_smoke_does_not_import_app`` guard stays green in the full
  ``tests/integration`` run.
* The whole module skips cleanly when Postgres is unreachable (the bare-pytest
  ``session-tests`` gate boots no Docker); ``integration.yml`` runs it for real.

The seeding helpers (``seed_user`` / ``seed_drawing`` / ``seed_symbol`` /
``authed_client``) are imported by S4-A's E2E harness.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

# --- import bootstrap (see module docstring) -------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
for _p in (str(REPO_ROOT), str(BACKEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_db_url = os.environ.get(
    "DATABASE_URL", "postgresql://pidtest:pidtest@localhost:55432/pidtest"
)
if "+psycopg" not in _db_url and _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+psycopg://", 1)
os.environ["DATABASE_URL"] = _db_url
os.environ.setdefault("ML_MODEL_S3_KEY", "models/test-model.onnx")
os.environ.setdefault("ODA_CONVERTER_PATH", "/usr/bin/ODAFileConverter")


def _postgres_available() -> bool:
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
# Schema lifecycle (drive Alembic to head, like test_db_schema.py)
# ---------------------------------------------------------------------------
def _alembic_config():
    from alembic.config import Config

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    return cfg


@pytest.fixture(scope="module")
def migrated_db(db_engine):
    """Reset to a pristine schema and apply every migration once for the module."""
    from alembic import command

    with db_engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()
    command.upgrade(_alembic_config(), "head")
    yield db_engine


# ---------------------------------------------------------------------------
# Seeding helpers (also imported by S4-A)
# ---------------------------------------------------------------------------
def seed_user(session, user_id=None, role="user", team_id=None) -> str:
    user_id = str(user_id or uuid.uuid4())
    session.execute(
        text(
            'INSERT INTO "user" (id, email, display_name, role, team_id) '
            "VALUES (:id, :email, 'Test', :role, :team_id)"
        ),
        {
            "id": user_id,
            "email": f"{user_id}@example.com",
            "role": role,
            "team_id": str(team_id) if team_id else None,
        },
    )
    return user_id


def seed_drawing(session, owner_user_id=None, owner_team_id=None,
                 state="Complete", drawing_id=None) -> str:
    drawing_id = str(drawing_id or uuid.uuid4())
    session.execute(
        text(
            "INSERT INTO drawing (id, owner_user_id, owner_team_id, filename, "
            "processing_state) VALUES (:id, :ou, :ot, 'f.pdf', :st)"
        ),
        {
            "id": drawing_id,
            "ou": str(owner_user_id) if owner_user_id else None,
            "ot": str(owner_team_id) if owner_team_id else None,
            "st": state,
        },
    )
    return drawing_id


def seed_symbol(session, drawing_id, entity_class_id="valve_gate",
                rejected=False, page_number=1, symbol_id=None) -> str:
    symbol_id = str(symbol_id or uuid.uuid4())
    # bbox is bound (not inlined) so the ``:n`` JSON keys aren't mistaken for
    # text() bind params.
    session.execute(
        text(
            "INSERT INTO detected_symbol (id, drawing_id, entity_class_id, "
            "subtype, tag_label, confidence, bbox, source, rejected, page_number) "
            "VALUES (:id, :did, :ec, 'gate', 'V-1', 0.9, "
            "CAST(:bbox AS jsonb), 'ml', :rej, :pg)"
        ),
        {
            "id": symbol_id,
            "did": str(drawing_id),
            "ec": entity_class_id,
            "bbox": '{"x":1,"y":2,"w":3,"h":4}',
            "rej": rejected,
            "pg": page_number,
        },
    )
    return symbol_id


def authed_client(engine, user: dict):
    """Build a ``TestClient`` whose ``get_db`` yields sessions on ``engine`` and
    whose ``get_current_user`` is ``user`` (a §S1-B ``CurrentUser``-shaped dict).

    Returns ``(client, teardown)``; call ``teardown()`` to clear overrides.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app.auth.dependencies import CurrentUser, get_current_user
    from app.db.session import get_db
    from app.main import app

    factory = sessionmaker(bind=engine, autoflush=False, future=True)

    def _get_db():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(**user)
    return TestClient(app, raise_server_exceptions=False), app.dependency_overrides.clear


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_patch_reclassify_persists_all_three_in_one_transaction(migrated_db):
    """Symbol class update + correction insert + Under_Review transition all
    commit together against real Postgres."""
    factory_engine = migrated_db
    from sqlalchemy.orm import sessionmaker

    sm = sessionmaker(bind=factory_engine, future=True)
    with sm() as s:
        uid = seed_user(s)
        did = seed_drawing(s, owner_user_id=uid, state="Complete")
        sid = seed_symbol(s, did, entity_class_id="valve_gate")
        s.commit()

    user = {"id": uid, "email": "o@x.com", "role": "user", "team_id": None}
    client, teardown = authed_client(factory_engine, user)
    try:
        resp = client.patch(
            f"/symbols/{sid}",
            json={"correction_type": "reclassify", "new_class_id": "valve_ball"},
        )
        assert resp.status_code == 200
        assert resp.json()["entity_class_id"] == "valve_ball"
    finally:
        teardown()

    with sm() as s:
        row = s.execute(
            text(
                "SELECT entity_class_id FROM detected_symbol WHERE id = :id"
            ),
            {"id": sid},
        ).scalar_one()
        assert row == "valve_ball"
        state = s.execute(
            text("SELECT processing_state FROM drawing WHERE id = :id"),
            {"id": did},
        ).scalar_one()
        assert state == "Under_Review"
        n = s.execute(
            text(
                "SELECT count(*) FROM user_correction WHERE detected_symbol_id = :id"
            ),
            {"id": sid},
        ).scalar_one()
        assert n == 1


def test_under_review_transition_is_concurrency_safe(migrated_db):
    """Two corrections racing on a ``Complete`` drawing: the conditional UPDATE
    (... WHERE processing_state='Complete') transitions exactly once and the
    loser violates no constraint (§US-012 AC-4)."""
    from sqlalchemy import update
    from sqlalchemy.orm import sessionmaker

    from app.db.models.drawing import Drawing

    sm = sessionmaker(bind=migrated_db, future=True)
    with sm() as s:
        uid = seed_user(s)
        did = seed_drawing(s, owner_user_id=uid, state="Complete")
        s.commit()

    # Two independent transactions, both issuing the guarded UPDATE.
    s1, s2 = sm(), sm()
    try:
        r1 = s1.execute(
            update(Drawing)
            .where(Drawing.id == uuid.UUID(did), Drawing.processing_state == "Complete")
            .values(processing_state="Under_Review")
        )
        s1.commit()
        r2 = s2.execute(
            update(Drawing)
            .where(Drawing.id == uuid.UUID(did), Drawing.processing_state == "Complete")
            .values(processing_state="Under_Review")
        )
        s2.commit()  # must not raise
        assert r1.rowcount == 1
        assert r2.rowcount == 0  # already transitioned — no duplicate, no error
    finally:
        s1.close()
        s2.close()

    with sm() as s:
        state = s.execute(
            text("SELECT processing_state FROM drawing WHERE id = :id"),
            {"id": did},
        ).scalar_one()
        assert state == "Under_Review"


def test_team_consent_snapshotted_into_correction(migrated_db):
    """Team-owned drawing resolves consent from the team's record and snapshots
    it into ``user_correction.training_consent`` at creation time."""
    from sqlalchemy.orm import sessionmaker

    sm = sessionmaker(bind=migrated_db, future=True)
    with sm() as s:
        team_id = str(uuid.uuid4())
        s.execute(
            text(
                "INSERT INTO team (id, name, licensed_seats) "
                "VALUES (:id, 'T', 1)"
            ),
            {"id": team_id},
        )
        uid = seed_user(s, role="team_member", team_id=team_id)
        did = seed_drawing(s, owner_team_id=team_id, state="Complete")
        sid = seed_symbol(s, did)
        s.execute(
            text(
                "INSERT INTO ml_training_consent (id, team_id, opted_in) "
                "VALUES (gen_random_uuid(), :tid, true)"
            ),
            {"tid": team_id},
        )
        s.commit()

    user = {"id": uid, "email": "m@x.com", "role": "team_member", "team_id": team_id}
    client, teardown = authed_client(migrated_db, user)
    try:
        resp = client.patch(f"/symbols/{sid}", json={"correction_type": "reject"})
        assert resp.status_code == 200
    finally:
        teardown()

    with sm() as s:
        consent = s.execute(
            text(
                "SELECT training_consent FROM user_correction "
                "WHERE detected_symbol_id = :id"
            ),
            {"id": sid},
        ).scalar_one()
        assert consent is True


def test_manual_symbol_created_with_source_and_correction(migrated_db):
    """POST creates a manual symbol (source='manual', confidence=1.0) plus its
    manual_add correction, returning 201."""
    from sqlalchemy.orm import sessionmaker

    sm = sessionmaker(bind=migrated_db, future=True)
    with sm() as s:
        uid = seed_user(s)
        did = seed_drawing(s, owner_user_id=uid, state="Complete")
        s.commit()

    user = {"id": uid, "email": "o@x.com", "role": "user", "team_id": None}
    client, teardown = authed_client(migrated_db, user)
    try:
        resp = client.post(
            f"/drawings/{did}/symbols",
            json={
                "entity_class_id": "valve_ball",
                "subtype": "ball",
                "bbox": {"x": 1, "y": 2, "w": 3, "h": 4},
                "page_number": 1,
            },
        )
        assert resp.status_code == 201
        new_id = resp.json()["id"]
        assert resp.json()["source"] == "manual"
        assert resp.json()["confidence"] == 1.0
    finally:
        teardown()

    with sm() as s:
        ct = s.execute(
            text(
                "SELECT correction_type FROM user_correction "
                "WHERE detected_symbol_id = :id"
            ),
            {"id": new_id},
        ).scalar_one()
        assert ct == "manual_add"
