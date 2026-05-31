"""S2-F — Account, Consent & GDPR-init endpoints: integration tests.

SELF-CONTAINED re backing services. The authoritative ``session-tests`` PR gate
runs this file with bare pytest and NO Docker (no Postgres/Redis), so the suite
stands the real S1-A ORM schema up on in-memory SQLite — PG-only column types
(``UUID``) get a DDL shim and the ``gen_random_uuid()`` / ``now()`` server
defaults are registered as SQLite functions (the same pattern S2-D/S2-G use).
The full ``tests/integration`` run under ``integration.yml`` uses the same
SQLite engine, so the tests pass identically with or without Docker.

Auth is exercised end-to-end against the REAL S1-B middleware: every
authenticated request carries a real RS256 token verified against an injected
test public key, and ``get_db`` is overridden onto the shared SQLite session so
the middleware's raw-SQL user-state lookup and the handlers see one DB. (A
sqlite3 adapter maps ``uuid.UUID`` bind params to the same hex form the ORM
persists, so the middleware's ``WHERE id = :id`` raw query matches.) External
effects (Supabase sign-out, Redis cache invalidation, the Celery erasure
enqueue) are mocked.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# --- import bootstrap (before any `app` import) ----------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
for _p in (str(REPO_ROOT), str(BACKEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# §1.12 marks these REQUIRED ("refuse to start"); the harness conftest seeds only
# the auth/storage subset, so supply the rest before the settings singleton loads.
os.environ.setdefault("ML_MODEL_S3_KEY", "models/test-model.onnx")
os.environ.setdefault("ODA_CONVERTER_PATH", "/usr/bin/ODAFileConverter")

import jwt  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB, UUID as _PGUUID  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

# Must match the harness SUPABASE_URL (tests/integration/conftest.py default) so
# the JWT issuer check passes.
SUPABASE_URL = "https://test.supabase.co"
SERVICE_ROLE_KEY = "test-service-role-key-do-not-use"


# --- SQLite shims for the PG-only ORM types / server defaults --------------
@compiles(_PGUUID, "sqlite")
def _compile_uuid_sqlite(element, compiler, **kw):  # noqa: ANN001, ANN201
    return "CHAR(36)"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):  # noqa: ANN001, ANN201
    return "JSON"


# The PG ``UUID(as_uuid=True)`` column persists values as 32-char hex under
# SQLite. The S1-B auth middleware looks the user up with a raw ``text()`` query
# binding a ``uuid.UUID`` — pysqlite can't bind that natively, so adapt it to the
# SAME hex form the ORM stores, otherwise the lookup misses and every authed
# request would 401.
sqlite3.register_adapter(uuid.UUID, lambda u: u.hex)


# --------------------------------------------------------------------------- #
# Key material + settings injection
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def rsa_keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


@pytest.fixture(scope="session", autouse=True)
def _configure_settings(rsa_keypair):
    from app.config import settings

    _, public_pem = rsa_keypair
    object.__setattr__(settings, "JWT_RS256_PUBLIC_KEY", public_pem)
    object.__setattr__(settings, "SUPABASE_URL", SUPABASE_URL)
    object.__setattr__(settings, "SUPABASE_SERVICE_ROLE_KEY", SERVICE_ROLE_KEY)
    yield


# --------------------------------------------------------------------------- #
# In-memory SQLite schema + session
# --------------------------------------------------------------------------- #
@pytest.fixture
def engine():
    """Fresh in-memory SQLite DB per test holding the team / user /
    ml_training_consent tables from the real S1-A models.

    ``StaticPool`` + ``check_same_thread=False`` share one connection across the
    TestClient threadpool and the test. The ``gen_random_uuid()`` / ``now()``
    functions back the server defaults (e.g. the consent insert lets the PK
    default fire)."""
    from app.db.models import Base, MLTrainingConsent, Team, User

    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(eng, "connect")
    def _register_fns(dbapi_conn, _record):  # noqa: ANN001
        # Return hex (not str(uuid)) so server-default-generated PKs match the
        # 32-char hex form the PG UUID type binds in WHERE/UPDATE clauses —
        # otherwise a later UPDATE on a default-PK row matches 0 rows.
        dbapi_conn.create_function("gen_random_uuid", 0, lambda: uuid.uuid4().hex)
        dbapi_conn.create_function(
            "now", 0, lambda: datetime.now(timezone.utc).isoformat(sep=" ")
        )

    Base.metadata.create_all(
        eng, tables=[Team.__table__, User.__table__, MLTrainingConsent.__table__]
    )
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def db(engine):
    """Shared session: setup writes, handler ``commit()``s, and the middleware
    user-state lookup all run against this one in-memory DB."""
    session = Session(bind=engine, future=True, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    """TestClient over the real app with ``get_db`` pinned to the test session
    (the override must NOT close it — the ``db`` fixture owns its lifecycle)."""
    from app.db.session import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Row + token factories
# --------------------------------------------------------------------------- #
@pytest.fixture
def make_team(db):
    from app.db.models import Team

    def _make(*, name: str = "Acme Engineering", seats: int = 5):
        team = Team(id=uuid.uuid4(), name=name, licensed_seats=seats)
        db.add(team)
        db.flush()
        return team

    return _make


@pytest.fixture
def make_user(db):
    from app.db.models import User

    def _make(
        *,
        email: str | None = None,
        display_name: str = "Test User",
        role: str = "user",
        team_id: uuid.UUID | None = None,
        email_verified: bool = True,
        deleted_at: datetime | None = None,
        token_invalidated_at: datetime | None = None,
    ):
        uid = uuid.uuid4()
        user = User(
            id=uid,
            email=email or f"user-{uid.hex[:8]}@example.com",
            display_name=display_name,
            role=role,
            team_id=team_id,
            email_verified=email_verified,
            deleted_at=deleted_at,
            token_invalidated_at=token_invalidated_at,
        )
        db.add(user)
        db.flush()
        return user

    return _make


@pytest.fixture
def make_consent(db):
    from app.db.models import MLTrainingConsent

    def _make(*, user_id=None, team_id=None, opted_in: bool = False):
        rec = MLTrainingConsent(
            id=uuid.uuid4(),
            user_id=user_id,
            team_id=team_id,
            opted_in=opted_in,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(rec)
        db.flush()
        return rec

    return _make


@pytest.fixture
def auth_headers_for(rsa_keypair):
    """Factory: a real ``Authorization: Bearer`` header (RS256) for a user."""
    private_pem, _ = rsa_keypair

    def _headers(user, *, iat: datetime | None = None) -> dict[str, str]:
        now = datetime.now(timezone.utc)
        iat = iat or now
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "iss": SUPABASE_URL,
            "aud": "authenticated",
            "iat": int(iat.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        }
        token = jwt.encode(payload, private_pem, algorithm="RS256")
        return {"Authorization": f"Bearer {token}"}

    return _headers


# --------------------------------------------------------------------------- #
# Mocked external effects (DELETE path)
# --------------------------------------------------------------------------- #
@pytest.fixture
def mock_supabase_sign_out(monkeypatch) -> AsyncMock:
    from app.auth import supabase_client

    mock = AsyncMock(return_value=None)
    monkeypatch.setattr(supabase_client, "admin_sign_out", mock)
    return mock


@pytest.fixture
def mock_celery_send_task(monkeypatch) -> MagicMock:
    from app.workers.celery_app import celery_app

    mock = MagicMock(return_value=None)
    monkeypatch.setattr(celery_app, "send_task", mock)
    return mock


@pytest.fixture
def mock_celery_send_task_raises(monkeypatch) -> MagicMock:
    from app.workers.celery_app import celery_app

    mock = MagicMock(side_effect=ConnectionError("broker down"))
    monkeypatch.setattr(celery_app, "send_task", mock)
    return mock


@pytest.fixture
def mock_invalidate_flags(monkeypatch) -> AsyncMock:
    from app.redis import cache

    mock = AsyncMock(return_value=None)
    monkeypatch.setattr(cache, "invalidate_subscription_flags", mock)
    return mock


# =========================================================================== #
# US-004 — Profile management
# =========================================================================== #
def test_get_account_returns_profile_for_authenticated_user(client, make_user, auth_headers_for):
    user = make_user(email="alice@example.com", display_name="Alice", role="user")
    resp = client.get("/account", headers=auth_headers_for(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == str(user.id)
    assert body["email"] == "alice@example.com"
    assert body["display_name"] == "Alice"
    assert body["email_verified"] is True
    assert body["role"] == "user"
    assert body["team_id"] is None


def test_get_account_returns_401_when_unauthenticated(client):
    assert client.get("/account").status_code == 401


def test_patch_account_updates_display_name(client, db, make_user, auth_headers_for):
    from app.db.models import User

    user = make_user(display_name="Old Name")
    resp = client.patch(
        "/account", json={"display_name": "New Name"}, headers=auth_headers_for(user)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["display_name"] == "New Name"
    # Durably persisted.
    assert db.get(User, user.id).display_name == "New Name"


def test_patch_account_updates_email_and_clears_email_verified(client, db, make_user, auth_headers_for):
    from app.db.models import User

    user = make_user(email="old@example.com", email_verified=True)
    resp = client.patch(
        "/account", json={"email": "new@example.com"}, headers=auth_headers_for(user)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == "new@example.com"
    assert body["email_verified"] is False
    row = db.get(User, user.id)
    assert row.email == "new@example.com"
    assert row.email_verified is False


def test_patch_account_invalid_email_returns_422(client, db, make_user, auth_headers_for):
    from app.db.models import User

    user = make_user(email="keep@example.com")
    resp = client.patch(
        "/account", json={"email": "not-a-valid-email"}, headers=auth_headers_for(user)
    )
    assert resp.status_code == 422
    # No DB write occurred.
    assert db.get(User, user.id).email == "keep@example.com"


def test_patch_account_empty_body_is_noop(client, make_user, auth_headers_for):
    user = make_user(display_name="Unchanged", email="unchanged@example.com")
    resp = client.patch("/account", json={}, headers=auth_headers_for(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["display_name"] == "Unchanged"
    assert body["email"] == "unchanged@example.com"


def test_patch_account_ignores_role_field(client, db, make_user, auth_headers_for):
    from app.db.models import User

    user = make_user(role="user")
    resp = client.patch(
        "/account",
        json={"role": "team_admin", "team_id": str(uuid.uuid4()), "display_name": "X"},
        headers=auth_headers_for(user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "user"  # not escalated
    assert resp.json()["display_name"] == "X"  # allowed field applied
    row = db.get(User, user.id)
    assert row.role == "user"
    assert row.team_id is None


def test_patch_account_unauthenticated_returns_401(client):
    assert client.patch("/account", json={"display_name": "X"}).status_code == 401


# =========================================================================== #
# US-004 — Consent retrieval / update
# =========================================================================== #
def test_get_consent_no_record_returns_default_false_user_source(client, make_user, auth_headers_for):
    user = make_user()  # solo, no consent record
    resp = client.get("/account/consent", headers=auth_headers_for(user))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"opted_in": False, "source": "user"}


def test_get_consent_solo_user_opted_in_returns_true(client, make_user, make_consent, auth_headers_for):
    user = make_user()
    make_consent(user_id=user.id, opted_in=True)
    resp = client.get("/account/consent", headers=auth_headers_for(user))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"opted_in": True, "source": "user"}


def test_get_consent_team_member_team_consent_overrides_user(
    client, make_team, make_user, make_consent, auth_headers_for
):
    team = make_team()
    user = make_user(role="team_member", team_id=team.id)
    # Personal record says False, team record says True → team wins.
    make_consent(user_id=user.id, opted_in=False)
    make_consent(team_id=team.id, opted_in=True)
    resp = client.get("/account/consent", headers=auth_headers_for(user))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"opted_in": True, "source": "team"}


def test_get_consent_team_member_no_team_record_falls_back_to_user(
    client, make_team, make_user, make_consent, auth_headers_for
):
    team = make_team()
    user = make_user(role="team_member", team_id=team.id)
    make_consent(user_id=user.id, opted_in=True)  # no team record
    resp = client.get("/account/consent", headers=auth_headers_for(user))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"opted_in": True, "source": "user"}


def test_get_consent_unauthenticated_returns_401(client):
    assert client.get("/account/consent").status_code == 401


def test_patch_consent_creates_new_record(client, db, make_user, auth_headers_for):
    from app.db.models import MLTrainingConsent
    from sqlalchemy import select

    user = make_user()
    resp = client.patch(
        "/account/consent", json={"opted_in": True}, headers=auth_headers_for(user)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"opted_in": True, "source": "user"}
    rows = db.execute(
        select(MLTrainingConsent).where(MLTrainingConsent.user_id == user.id)
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].opted_in is True
    assert rows[0].updated_at is not None


def test_patch_consent_updates_existing_record_no_duplicate(
    client, db, make_user, make_consent, auth_headers_for
):
    from app.db.models import MLTrainingConsent
    from sqlalchemy import select

    user = make_user()
    make_consent(user_id=user.id, opted_in=False)
    resp = client.patch(
        "/account/consent", json={"opted_in": True}, headers=auth_headers_for(user)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["opted_in"] is True
    rows = db.execute(
        select(MLTrainingConsent).where(MLTrainingConsent.user_id == user.id)
    ).scalars().all()
    assert len(rows) == 1  # updated, not duplicated
    assert rows[0].opted_in is True


def test_patch_consent_unauthenticated_returns_401(client):
    assert client.patch("/account/consent", json={"opted_in": True}).status_code == 401


def test_patch_consent_source_field_not_accepted(client, make_user, auth_headers_for):
    """A client-supplied ``source`` is silently dropped; the response source is
    computed server-side (solo user → "user")."""
    user = make_user()
    resp = client.patch(
        "/account/consent",
        json={"opted_in": True, "source": "team", "resolved": True},
        headers=auth_headers_for(user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"opted_in": True, "source": "user"}


def test_patch_consent_is_idempotent_no_duplicate_rows(client, db, make_user, auth_headers_for):
    from app.db.models import MLTrainingConsent
    from sqlalchemy import select

    user = make_user()
    headers = auth_headers_for(user)
    client.patch("/account/consent", json={"opted_in": True}, headers=headers)
    client.patch("/account/consent", json={"opted_in": False}, headers=headers)
    rows = db.execute(
        select(MLTrainingConsent).where(MLTrainingConsent.user_id == user.id)
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].opted_in is False


# =========================================================================== #
# US-004 — resolve_training_consent (LOAD-BEARING, tested directly)
# =========================================================================== #
def test_resolve_training_consent_team_takes_precedence_over_user(
    db, make_team, make_user, make_consent
):
    from app.services.consent_service import resolve_training_consent

    team = make_team()
    user = make_user(role="team_member", team_id=team.id)
    make_consent(user_id=user.id, opted_in=False)
    make_consent(team_id=team.id, opted_in=True)
    assert resolve_training_consent(str(user.id), db) is True


def test_resolve_training_consent_solo_user_false(db, make_user, make_consent):
    from app.services.consent_service import resolve_training_consent

    user = make_user()
    make_consent(user_id=user.id, opted_in=False)
    assert resolve_training_consent(str(user.id), db) is False


def test_resolve_training_consent_default_false_no_record(db, make_user):
    from app.services.consent_service import resolve_training_consent

    user = make_user()
    assert resolve_training_consent(str(user.id), db) is False


def test_resolve_training_consent_signature_is_user_id_str_and_session():
    """The LOAD-BEARING signature consumed by S2-C must be ``(user_id, db)``."""
    import inspect

    from app.services.consent_service import resolve_training_consent

    params = list(inspect.signature(resolve_training_consent).parameters)
    assert params == ["user_id", "db"]


# =========================================================================== #
# US-005 — Account deletion
# =========================================================================== #
def test_delete_account_returns_204_sets_deleted_at_enqueues_job(
    client, db, make_user, auth_headers_for,
    mock_supabase_sign_out, mock_celery_send_task, mock_invalidate_flags,
):
    from app.db.models import User

    user = make_user()
    resp = client.delete("/account", headers=auth_headers_for(user))
    assert resp.status_code == 204
    assert resp.content == b""  # no body
    assert db.get(User, user.id).deleted_at is not None

    assert mock_celery_send_task.call_count == 1
    _, kwargs = mock_celery_send_task.call_args
    name = mock_celery_send_task.call_args.args[0]
    assert name == "backend.app.workers.gdpr.tasks.gdpr_erasure_task"
    assert kwargs["queue"] == "gdpr_erasure"
    assert kwargs["args"] == [str(user.id)]


def test_delete_account_sets_token_invalidated_at_and_calls_sign_out(
    client, db, make_user, auth_headers_for,
    mock_supabase_sign_out, mock_celery_send_task, mock_invalidate_flags,
):
    from app.db.models import User

    user = make_user()
    resp = client.delete("/account", headers=auth_headers_for(user))
    assert resp.status_code == 204
    row = db.get(User, user.id)
    assert row.token_invalidated_at is not None
    mock_supabase_sign_out.assert_awaited_once()
    # Called with the user's id.
    (called_arg,) = mock_supabase_sign_out.await_args.args
    assert str(called_arg) == str(user.id)


def test_delete_account_subsequent_request_returns_401(
    client, make_user, auth_headers_for,
    mock_supabase_sign_out, mock_celery_send_task, mock_invalidate_flags,
):
    """After soft-delete the same token is rejected by the real S1-B middleware
    (it reads ``deleted_at`` from the shared session)."""
    user = make_user()
    headers = auth_headers_for(user)
    assert client.delete("/account", headers=headers).status_code == 204
    # Same previously-valid token, now soft-deleted → 401.
    assert client.get("/account", headers=headers).status_code == 401


def test_delete_account_unauthenticated_returns_401(client):
    assert client.delete("/account").status_code == 401


def test_delete_account_gdpr_task_payload_and_countdown(
    client, make_user, auth_headers_for,
    mock_supabase_sign_out, mock_celery_send_task, mock_invalidate_flags,
):
    user = make_user()
    resp = client.delete("/account", headers=auth_headers_for(user))
    assert resp.status_code == 204
    _, kwargs = mock_celery_send_task.call_args
    assert kwargs["args"] == [str(user.id)]
    assert kwargs["queue"] == "gdpr_erasure"
    # ENVIRONMENT is "development" under test → immediate execution.
    assert kwargs["countdown"] == 0


def test_delete_account_invalidates_subscription_flags_cache(
    client, make_user, auth_headers_for,
    mock_supabase_sign_out, mock_celery_send_task, mock_invalidate_flags,
):
    user = make_user()
    assert client.delete("/account", headers=auth_headers_for(user)).status_code == 204
    mock_invalidate_flags.assert_awaited_once()
    (called_arg,) = mock_invalidate_flags.await_args.args
    assert called_arg == str(user.id)


def test_delete_account_idempotent_no_double_enqueue(
    client, db, make_user, auth_headers_for,
    mock_supabase_sign_out, mock_celery_send_task, mock_invalidate_flags,
):
    """A second DELETE on an already-soft-deleted account returns 204 without
    re-enqueuing the erasure job (US-005 AC-7 — enqueued exactly once)."""
    from app.auth.dependencies import CurrentUser, get_current_user
    from app.db.models import User
    from app.main import app

    user = make_user()
    assert client.delete("/account", headers=auth_headers_for(user)).status_code == 204
    first_deleted_at = db.get(User, user.id).deleted_at
    assert mock_celery_send_task.call_count == 1

    # The soft-deleted user's real token now 401s at the middleware, so to drive
    # the endpoint's idempotency guard we substitute the resolved identity.
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id, email=user.email, role=user.role, team_id=user.team_id
    )
    try:
        resp = client.delete("/account")  # no header needed: identity overridden
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 204
    assert mock_celery_send_task.call_count == 1  # NOT re-enqueued
    assert db.get(User, user.id).deleted_at == first_deleted_at  # unchanged


def test_delete_account_celery_failure_still_returns_204(
    client, db, make_user, auth_headers_for,
    mock_supabase_sign_out, mock_celery_send_task_raises, mock_invalidate_flags,
):
    from app.db.models import User

    user = make_user()
    resp = client.delete("/account", headers=auth_headers_for(user))
    # Broker raised, but the soft-delete already committed → still 204.
    assert resp.status_code == 204
    assert db.get(User, user.id).deleted_at is not None
    assert mock_celery_send_task_raises.call_count == 1


def test_delete_account_both_timestamps_set_in_same_transaction(
    client, db, make_user, auth_headers_for,
    mock_supabase_sign_out, mock_celery_send_task, mock_invalidate_flags,
):
    from app.db.models import User

    user = make_user()
    assert client.delete("/account", headers=auth_headers_for(user)).status_code == 204
    row = db.get(User, user.id)
    assert row.deleted_at is not None
    assert row.token_invalidated_at is not None
    # Set together in one commit → identical timestamps.
    assert row.deleted_at == row.token_invalidated_at


def test_gdpr_countdown_is_30_days_in_production(monkeypatch):
    """The production branch of the countdown helper (US-005 AC-5)."""
    from app.config import settings
    from app.services import gdpr_init_service

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert gdpr_init_service._erasure_countdown() == 30 * 24 * 3600
