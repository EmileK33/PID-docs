"""Shared fixtures for the S2-C session test (``test_s2c.py``).

This suite is the authoritative ``session-tests`` PR gate, which runs the
manifest's ``pytest tests/sessions/test_s2c.py -v`` with **bare pytest and NO
Docker backing services** (see memory: session-tests gate has no Postgres). So
every fixture here is fully self-contained: the symbols/corrections endpoints
are exercised against an in-memory SQLite database that mirrors the §1.2 schema
of the five tables S2-C touches.

To run the real S1-A ORM models (which use Postgres-only ``JSONB`` / ``UUID``
column types and ``gen_random_uuid()`` / ``now()`` server defaults) on SQLite we:

* register ``@compiles`` adapters so ``JSONB`` -> ``JSON`` and ``UUID`` ->
  ``CHAR(36)`` at DDL-compile time, and
* register the missing ``gen_random_uuid()`` / ``now()`` SQL functions on each
  SQLite connection.

A single in-memory DB is shared across the seeding session and the request
sessions via ``StaticPool`` (one connection), recreated per test for isolation.
"""
from __future__ import annotations

import datetime
import os
import sys
import uuid
from pathlib import Path

# --- import bootstrap ------------------------------------------------------
# The ``app`` package is rooted at ``backend/``. Make both roots importable so
# ``from app... import`` resolves, and set every §1.12 "Refuse to start" env var
# (incl. the two the integration conftest omits and the format-checked Stripe
# keys) BEFORE any ``app.config`` import constructs the settings singleton.
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
for _p in (str(BACKEND), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_TEST_ENV = {
    "DATABASE_URL": "postgresql://u:p@localhost:5432/pid",
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_BUCKET_NAME": "pid-test-bucket",
    "S3_REGION": "us-east-1",
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
    "JWT_RS256_PUBLIC_KEY": "-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----",
    "STRIPE_SECRET_KEY": "sk_test_dummy",
    "STRIPE_WEBHOOK_SECRET": "whsec_dummy",
    "SENDGRID_API_KEY": "SG.test_dummy",
    "HMAC_SERVER_SECRET": "test-secret-do-not-use",
    "ML_MODEL_S3_KEY": "models/test-model.onnx",
    "ODA_CONVERTER_PATH": "/usr/bin/ODAFileConverter",
    "ENVIRONMENT": "development",
}
for _k, _v in _TEST_ENV.items():
    os.environ.setdefault(_k, _v)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB  # noqa: E402
from sqlalchemy.dialects.postgresql import UUID as PG_UUID  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402


# --- Postgres-type -> SQLite adapters (registered once, process-wide) ------
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):  # noqa: ANN001, ANN201
    return "JSON"


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):  # noqa: ANN001, ANN201
    return "CHAR(36)"


def _register_sqlite_functions(dbapi_connection, _record):
    """Supply the Postgres server-default functions SQLite lacks.

    ``gen_random_uuid`` returns the 32-char hyphenless hex form to match how
    SQLAlchemy's non-native ``UUID(as_uuid=True)`` stores and binds UUIDs on
    SQLite — otherwise server-default-generated ids never match ``WHERE id = ?``.
    """
    dbapi_connection.create_function(
        "gen_random_uuid", 0, lambda: uuid.uuid4().hex
    )
    dbapi_connection.create_function(
        "now",
        0,
        lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )


# --- engine / session fixtures --------------------------------------------
@pytest.fixture()
def engine():
    """Function-scoped in-memory SQLite engine with the five S2-C tables.

    Imports the real S1-A ORM models (via the canonical ``app.`` root so they
    attach to the one ``app.db.base.Base`` metadata) and creates only the tables
    S2-C reads/writes. FK targets it does not create (``user``/``team``/
    ``table_cell``/``stored_file``) are unenforced by SQLite, which is fine for
    these endpoint tests.
    """
    from app.db.base import Base
    from app.db.models.detected_symbol import DetectedSymbol
    from app.db.models.drawing import Drawing
    from app.db.models.entity_class import EntityClass
    from app.db.models.ml_training_consent import MLTrainingConsent
    from app.db.models.user_correction import UserCorrection

    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    event.listen(eng, "connect", _register_sqlite_functions)

    tables = [
        EntityClass.__table__,
        Drawing.__table__,
        DetectedSymbol.__table__,
        UserCorrection.__table__,
        MLTrainingConsent.__table__,
    ]
    Base.metadata.create_all(eng, tables=tables)

    # Seed the eight §1.1 entity classes so reclassify/manual-add FKs resolve.
    sm = sessionmaker(bind=eng, future=True)
    with sm() as s:
        for cid in (
            "pipe",
            "valve_gate",
            "valve_globe",
            "valve_ball",
            "valve_butterfly",
            "valve_check",
            "valve_control",
            "instrument",
        ):
            s.add(EntityClass(id=cid, name=cid, color_hex="#abcdef"))
        s.commit()

    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture()
def session_factory(engine):
    """A sessionmaker bound to the per-test engine (``expire_on_commit=False``
    so seeded ORM objects stay usable after commit)."""
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@pytest.fixture()
def db(session_factory):
    """A seeding session. Tests insert rows and ``commit()`` before issuing
    requests so the request-side sessions (same StaticPool connection) see them."""
    s = session_factory()
    try:
        yield s
    finally:
        s.close()


# --- identity fixtures -----------------------------------------------------
@pytest.fixture()
def owner_id():
    return uuid.uuid4()


@pytest.fixture()
def other_id():
    return uuid.uuid4()


@pytest.fixture()
def current_user_owner(owner_id):
    return {
        "id": str(owner_id),
        "email": "owner@example.com",
        "role": "user",
        "team_id": None,
    }


@pytest.fixture()
def current_user_other(other_id):
    return {
        "id": str(other_id),
        "email": "other@example.com",
        "role": "user",
        "team_id": None,
    }


# --- HTTP client + auth override -------------------------------------------
@pytest.fixture()
def client(engine, session_factory):
    """A TestClient whose ``get_db`` dependency yields sessions on the per-test
    SQLite engine. Auth is left to the real dependency unless a test calls the
    ``login`` fixture (so unauthenticated requests correctly resolve to 401)."""
    from app.db.session import get_db
    from app.main import app

    def _override_get_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def login():
    """Return a callable that authenticates the TestClient as ``user`` (a dict
    shaped like the §S1-B ``CurrentUser`` handoff) by overriding
    ``get_current_user``. Not calling it leaves requests unauthenticated."""
    from app.auth.dependencies import CurrentUser, get_current_user
    from app.main import app

    def _login(user: dict):
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(**user)

    return _login


# --- data-seeding helpers --------------------------------------------------
@pytest.fixture()
def make_drawing(db):
    from app.db.models.drawing import Drawing

    def _make(
        *,
        drawing_id=None,
        owner_user_id=None,
        owner_team_id=None,
        state="Complete",
    ):
        drawing_id = drawing_id or uuid.uuid4()
        d = Drawing(
            id=drawing_id,
            owner_user_id=owner_user_id,
            owner_team_id=owner_team_id,
            filename="test.pdf",
            processing_state=state,
        )
        db.add(d)
        db.commit()
        return d

    return _make


@pytest.fixture()
def make_symbol(db):
    from app.db.models.detected_symbol import DetectedSymbol

    def _make(
        *,
        drawing_id,
        entity_class_id="valve_gate",
        subtype="gate",
        tag_label="V-101",
        confidence=0.92,
        bbox=None,
        source="ml",
        rejected=False,
        page_number=1,
    ):
        sym = DetectedSymbol(
            drawing_id=drawing_id,
            entity_class_id=entity_class_id,
            subtype=subtype,
            tag_label=tag_label,
            confidence=confidence,
            bbox=bbox or {"x": 10.0, "y": 20.0, "w": 5.0, "h": 5.0},
            source=source,
            rejected=rejected,
            page_number=page_number,
        )
        db.add(sym)
        db.commit()
        return sym

    return _make


@pytest.fixture()
def make_consent(db):
    from app.db.models.ml_training_consent import MLTrainingConsent

    def _make(*, user_id=None, team_id=None, opted_in=True):
        c = MLTrainingConsent(
            user_id=user_id, team_id=team_id, opted_in=opted_in
        )
        db.add(c)
        db.commit()
        return c

    return _make


@pytest.fixture()
def count_corrections(session_factory):
    from app.db.models.user_correction import UserCorrection
    from sqlalchemy import func, select

    def _count(symbol_id=None):
        with session_factory() as s:
            stmt = select(func.count()).select_from(UserCorrection)
            if symbol_id is not None:
                stmt = stmt.where(
                    UserCorrection.detected_symbol_id == symbol_id
                )
            return s.execute(stmt).scalar()

    return _count
