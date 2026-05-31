"""Integration tests for the S2-A auth endpoints (US-001, US-002).

SELF-CONTAINED re backing services. The authoritative ``session-tests`` CI gate
runs this file's ``test.cmd`` (``pytest tests/integration/test_auth_endpoints.py
-v``) WITHOUT booting the Docker fixture stack (Postgres/Redis/MinIO) — only the
separate ``integration`` workflow brings them up. So this suite never opens a
real DB/Redis/Supabase connection:

* **Database** — an in-process SQLite engine (``StaticPool``, shared connection)
  hosting the S1-A ORM models (``user`` / ``subscription`` / ``tier``) plus a
  portable ``audit_log`` table. ``get_db`` is overridden onto a single shared
  session so a handler's commit is visible to the test's assertions.
* **Redis brute-force counter** — ``fakeredis`` (in-process) via the S1-B
  ``brute_force._client`` patch seam.
* **Supabase Auth + Celery dispatch** — the ``app.services.auth_service``
  ``supabase_*`` coroutines, ``verify_token``, and ``enqueue_notification`` are
  patched wholesale; no live service or broker is touched.

``app.*`` modules are imported INSIDE fixtures/tests (never at module import
time) so the sibling S0-B smoke assertion ``test_smoke_does_not_import_app``
stays green when the whole ``tests/integration`` suite runs together.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

# Make `backend/app` importable. tests/integration/test_auth_endpoints.py
# -> parents[2] == repo root; the app package lives under repo_root/backend.
_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# S0-A's config marks ML_MODEL_S3_KEY / ODA_CONVERTER_PATH as REQUIRED, but the
# S0-B harness conftest only seeds the auth/storage subset. Seed the remainder
# here (at import time, before any app.config import) so settings can load.
os.environ.setdefault("ML_MODEL_S3_KEY", "models/test-model.onnx")
os.environ.setdefault("ODA_CONVERTER_PATH", "/usr/bin/ODAFileConverter")

SENTINEL = "<SUPABASE_MANAGED>"


def _run(coro):
    """Drive a coroutine to completion from a synchronous test."""
    import asyncio

    return asyncio.run(coro)


# --------------------------------------------------------------------------- #
# Database: in-memory SQLite hosting the real ORM models + a portable audit_log
# --------------------------------------------------------------------------- #
@pytest.fixture
def db():
    """A shared SQLite-backed Session, seeded with the ``free`` tier row."""
    import app.db.models.team  # noqa: F401 - FK target registered on metadata
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db.models.subscription import Subscription
    from app.db.models.tier import Tier
    from app.db.models.user import User

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Tier.__table__.create(engine)
    User.__table__.create(engine)
    Subscription.__table__.create(engine)
    # audit_log uses Postgres-only JSONB + RANGE partitioning in the ORM model;
    # create a portable equivalent so best-effort audit writes succeed quietly.
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE audit_log ("
                "id CHAR(32) NOT NULL, user_id CHAR(32), action_type VARCHAR NOT NULL, "
                "entity_id CHAR(32), entity_type VARCHAR, occurred_at TIMESTAMP NOT NULL, "
                "metadata TEXT, PRIMARY KEY (id, occurred_at))"
            )
        )

    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    session.add(
        Tier(
            id="free",
            name="Free",
            monthly_drawing_limit=3,
            team_features=False,
            api_access=False,
        )
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db):
    """A TestClient over a fresh app wiring ONLY the S2-A auth router.

    Isolated per test (no shared ``app.main`` singleton), with ``get_db``
    overridden onto the shared ``db`` session. ``raise_server_exceptions=False``
    so unexpected 500s surface as responses (used by the atomicity test).
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routers.auth import router as auth_router
    from app.db.session import get_db

    app = FastAPI()
    app.include_router(auth_router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


# --------------------------------------------------------------------------- #
# Brute-force lockout — fakeredis via the S1-B _client patch seam
# --------------------------------------------------------------------------- #
@pytest.fixture
def fake_redis(monkeypatch):
    """Patch ``brute_force._client`` to an in-process fakeredis server.

    Returns a synchronous client bound to the same server so tests can seed /
    assert counters and TTLs directly.
    """
    import fakeredis
    import fakeredis.aioredis

    from app.auth import brute_force

    server = fakeredis.FakeServer()

    def _client():
        return fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)

    monkeypatch.setattr(brute_force, "_client", _client)
    return fakeredis.FakeStrictRedis(server=server, decode_responses=True)


def _bf_key(email: str) -> str:
    return f"brute_force:{email.lower()}"


# --------------------------------------------------------------------------- #
# Supabase / Celery mock seams
# --------------------------------------------------------------------------- #
@pytest.fixture
def mocks(monkeypatch):
    """Patch every external auth dependency with capturing test doubles."""
    from app.services import auth_service, password_reset

    ns = SimpleNamespace()

    ns.sign_up = AsyncMock(
        return_value={
            "user": {"id": str(uuid.uuid4()), "email": "x@example.com"},
            "session": {"access_token": "mock_access", "refresh_token": "mock_refresh"},
        }
    )
    monkeypatch.setattr(auth_service, "supabase_sign_up", ns.sign_up)

    ns.sign_in = AsyncMock(
        return_value={
            "access_token": "mock_access",
            "refresh_token": "mock_refresh",
            "user": {"id": str(uuid.uuid4()), "email": "test@example.com"},
        }
    )
    monkeypatch.setattr(auth_service, "supabase_sign_in_password", ns.sign_in)

    ns.refresh = AsyncMock(
        return_value={"access_token": "new_access", "refresh_token": "new_refresh"}
    )
    monkeypatch.setattr(auth_service, "supabase_refresh_session", ns.refresh)

    ns.sign_out = AsyncMock(return_value=None)
    monkeypatch.setattr(auth_service, "supabase_sign_out", ns.sign_out)

    ns.gen_link = AsyncMock(
        return_value="https://auth.example.com/verify?token=mock_token"
    )
    monkeypatch.setattr(auth_service, "supabase_generate_link", ns.gen_link)
    monkeypatch.setattr(password_reset, "supabase_generate_link", ns.gen_link)

    ns.reset_pw = AsyncMock(return_value={"user": {"id": str(uuid.uuid4())}})
    monkeypatch.setattr(password_reset, "supabase_reset_password", ns.reset_pw)

    ns.admin_sign_out = AsyncMock(return_value=None)
    monkeypatch.setattr(password_reset, "admin_sign_out", ns.admin_sign_out)

    ns.verify_token = MagicMock(
        return_value={
            "sub": str(uuid.uuid4()),
            "email": "oauth-new@example.com",
            "email_confirmed_at": "2024-01-01T00:00:00Z",
            "app_metadata": {"provider": "google"},
        }
    )
    monkeypatch.setattr(auth_service, "verify_token", ns.verify_token)

    ns.enqueue = MagicMock()
    monkeypatch.setattr(auth_service, "enqueue_notification", ns.enqueue)
    monkeypatch.setattr(password_reset, "enqueue_notification", ns.enqueue)

    # The real exception type, so tests can drive failure branches.
    ns.SupabaseAuthError = auth_service.SupabaseAuthError
    return ns


# --------------------------------------------------------------------------- #
# Seed helpers
# --------------------------------------------------------------------------- #
def _seed_user(
    db,
    *,
    email,
    password_hash=SENTINEL,
    email_verified=True,
    deleted_at=None,
    user_id=None,
    display_name="Seeded User",
    role="user",
):
    from app.db.models.user import User

    uid = user_id or uuid.uuid4()
    db.add(
        User(
            id=uid,
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            email_verified=email_verified,
            deleted_at=deleted_at,
            role=role,
        )
    )
    db.commit()
    return uid


def _user_by_email(db, email):
    from app.db.models.user import User

    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def _subscriptions_for(db, user_id):
    from app.db.models.subscription import Subscription

    return (
        db.execute(select(Subscription).where(Subscription.user_id == user_id))
        .scalars()
        .all()
    )


# =========================================================================== #
# US-001 — registration
# =========================================================================== #
def test_register_success_returns_201_with_tokens(client, mocks):
    uid = str(uuid.uuid4())
    mocks.sign_up.return_value = {
        "user": {"id": uid, "email": "new@example.com"},
        "session": {"access_token": "mock_access", "refresh_token": "mock_refresh"},
    }
    resp = client.post(
        "/auth/register",
        json={"email": "new@example.com", "password": "Sup3rSecret!", "display_name": "New User"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["access_token"] == "mock_access"
    assert body["refresh_token"] == "mock_refresh"
    assert body["user"]["id"] == uid
    assert body["user"]["email"] == "new@example.com"
    assert body["user"]["display_name"] == "New User"
    assert body["user"]["email_verified"] is False


def test_register_creates_user_in_db(client, db, mocks):
    client.post(
        "/auth/register",
        json={"email": "dbuser@example.com", "password": "Sup3rSecret!", "display_name": "DB User"},
    )
    user = _user_by_email(db, "dbuser@example.com")
    assert user is not None
    assert user.email_verified is False
    assert user.role == "user"
    assert user.deleted_at is None
    assert user.password_hash == SENTINEL


def test_register_creates_free_subscription(client, db, mocks):
    uid = str(uuid.uuid4())
    mocks.sign_up.return_value = {
        "user": {"id": uid, "email": "subuser@example.com"},
        "session": {"access_token": "a", "refresh_token": "r"},
    }
    client.post(
        "/auth/register",
        json={"email": "subuser@example.com", "password": "Sup3rSecret!", "display_name": "Sub User"},
    )
    subs = _subscriptions_for(db, uuid.UUID(uid))
    assert len(subs) == 1
    assert subs[0].tier_id == "free"
    assert subs[0].billing_state == "Active"


def test_register_enqueues_verification_email(client, mocks):
    uid = str(uuid.uuid4())
    mocks.sign_up.return_value = {
        "user": {"id": uid, "email": "verify@example.com"},
        "session": {"access_token": "a", "refresh_token": "r"},
    }
    client.post(
        "/auth/register",
        json={"email": "verify@example.com", "password": "Sup3rSecret!", "display_name": "Verify User"},
    )
    mocks.enqueue.assert_called_once()
    payload = mocks.enqueue.call_args.args[0]
    assert payload["task_name"] == "send_verification_email"
    assert payload["user_id"] == uid
    assert payload["email"] == "verify@example.com"
    assert payload["display_name"] == "Verify User"
    assert payload["verification_url"] == "https://auth.example.com/verify?token=mock_token"


def test_register_duplicate_email_returns_409(client, db, mocks):
    _seed_user(db, email="dupe@example.com")
    resp = client.post(
        "/auth/register",
        json={"email": "dupe@example.com", "password": "Sup3rSecret!", "display_name": "Dupe"},
    )
    assert resp.status_code == 409
    assert resp.json() == {"error": "email_already_registered"}


def test_register_duplicate_email_no_task_enqueued(client, db, mocks):
    _seed_user(db, email="dupe2@example.com")
    client.post(
        "/auth/register",
        json={"email": "dupe2@example.com", "password": "Sup3rSecret!", "display_name": "Dupe"},
    )
    mocks.enqueue.assert_not_called()
    mocks.sign_up.assert_not_called()


def test_register_invalid_email_returns_400(client, mocks):
    resp = client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "Sup3rSecret!", "display_name": "X"},
    )
    assert resp.status_code == 400


def test_register_succeeds_when_celery_broker_unavailable(client, mocks):
    mocks.enqueue.side_effect = Exception("broker unreachable")
    resp = client.post(
        "/auth/register",
        json={"email": "resilient@example.com", "password": "Sup3rSecret!", "display_name": "R"},
    )
    assert resp.status_code == 201, resp.text


def test_register_subscription_rolled_back_if_user_insert_fails(client, db, mocks):
    # Seed a user under a known id, then force the new registration to collide on
    # that primary key — the commit must roll back BOTH the user and the
    # free subscription (atomicity).
    existing_id = uuid.uuid4()
    _seed_user(db, email="existing@example.com", user_id=existing_id)
    mocks.sign_up.return_value = {
        "user": {"id": str(existing_id), "email": "collision@example.com"},
        "session": {"access_token": "a", "refresh_token": "r"},
    }
    resp = client.post(
        "/auth/register",
        json={"email": "collision@example.com", "password": "Sup3rSecret!", "display_name": "C"},
    )
    assert resp.status_code >= 500
    # No user under the colliding email and no orphaned subscription.
    assert _user_by_email(db, "collision@example.com") is None
    assert _subscriptions_for(db, existing_id) == []


# =========================================================================== #
# US-002 — email/password login + brute-force lockout
# =========================================================================== #
def test_login_success_returns_200_with_tokens(client, db, mocks, fake_redis):
    _seed_user(db, email="test@example.com", display_name="Login User")
    resp = client.post(
        "/auth/login", json={"email": "test@example.com", "password": "Sup3rSecret!"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"] == "mock_access"
    assert body["refresh_token"] == "mock_refresh"
    assert body["user"]["email"] == "test@example.com"
    assert body["user"]["display_name"] == "Login User"


def test_login_success_resets_brute_force_counter(client, db, mocks, fake_redis):
    _seed_user(db, email="test@example.com")
    fake_redis.set(_bf_key("test@example.com"), 3)
    fake_redis.expire(_bf_key("test@example.com"), 900)
    resp = client.post(
        "/auth/login", json={"email": "test@example.com", "password": "Sup3rSecret!"}
    )
    assert resp.status_code == 200
    assert fake_redis.exists(_bf_key("test@example.com")) == 0


def test_login_wrong_password_returns_401(client, db, mocks, fake_redis):
    _seed_user(db, email="test@example.com")
    mocks.sign_in.side_effect = mocks.SupabaseAuthError("Invalid login credentials")
    resp = client.post(
        "/auth/login", json={"email": "test@example.com", "password": "wrong"}
    )
    assert resp.status_code == 401
    assert resp.json() == {"error": "invalid_credentials"}


def test_login_wrong_password_increments_counter(client, db, mocks, fake_redis):
    _seed_user(db, email="test@example.com")
    mocks.sign_in.side_effect = mocks.SupabaseAuthError("Invalid login credentials")
    client.post("/auth/login", json={"email": "test@example.com", "password": "wrong"})
    assert fake_redis.get(_bf_key("test@example.com")) == "1"


def test_login_locked_after_5_failures_returns_429(client, db, mocks, fake_redis):
    _seed_user(db, email="test@example.com")
    fake_redis.set(_bf_key("test@example.com"), 5)
    fake_redis.expire(_bf_key("test@example.com"), 850)
    resp = client.post(
        "/auth/login", json={"email": "test@example.com", "password": "Sup3rSecret!"}
    )
    assert resp.status_code == 429
    body = resp.json()
    assert body["error"] == "account_locked"
    assert 0 < body["retry_after_seconds"] <= 900


def test_login_locked_skips_supabase_check(client, db, mocks, fake_redis):
    _seed_user(db, email="test@example.com")
    fake_redis.set(_bf_key("test@example.com"), 5)
    fake_redis.expire(_bf_key("test@example.com"), 850)
    client.post("/auth/login", json={"email": "test@example.com", "password": "Sup3rSecret!"})
    mocks.sign_in.assert_not_called()


def test_login_correct_creds_returns_429_during_lockout(client, db, mocks, fake_redis):
    _seed_user(db, email="test@example.com")
    fake_redis.set(_bf_key("test@example.com"), 5)
    fake_redis.expire(_bf_key("test@example.com"), 850)
    # Even with the *correct* password the lockout wins (US-002 AC-4).
    resp = client.post(
        "/auth/login", json={"email": "test@example.com", "password": "Sup3rSecret!"}
    )
    assert resp.status_code == 429


def test_login_deleted_user_returns_401(client, db, mocks, fake_redis):
    _seed_user(
        db, email="deleted@example.com", deleted_at=datetime.now(timezone.utc)
    )
    # Supabase authenticates fine (mock), but the app row is soft-deleted.
    resp = client.post(
        "/auth/login", json={"email": "deleted@example.com", "password": "Sup3rSecret!"}
    )
    assert resp.status_code == 401
    assert resp.json() == {"error": "account_not_found"}


# =========================================================================== #
# US-002 — Google OAuth
# =========================================================================== #
def test_oauth_google_new_user_returns_200(client, db, mocks):
    sub = str(uuid.uuid4())
    mocks.verify_token.return_value = {
        "sub": sub,
        "email": "brandnew@example.com",
        "email_confirmed_at": "2024-01-01T00:00:00Z",
        "app_metadata": {"provider": "google"},
    }
    resp = client.post(
        "/auth/oauth/google",
        json={"supabase_access_token": "tok", "supabase_refresh_token": "rtok"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"] == "tok"
    assert body["refresh_token"] == "rtok"
    assert body["user"]["email"] == "brandnew@example.com"
    assert body["user"]["email_verified"] is True

    user = _user_by_email(db, "brandnew@example.com")
    assert user is not None
    assert user.password_hash is None
    assert user.email_verified is True


def test_oauth_google_existing_oauth_user_returns_200(client, db, mocks):
    uid = _seed_user(db, email="oauth@example.com", password_hash=None)
    mocks.verify_token.return_value = {
        "sub": str(uid),
        "email": "oauth@example.com",
        "app_metadata": {"provider": "google"},
    }
    resp = client.post(
        "/auth/oauth/google",
        json={"supabase_access_token": "tok", "supabase_refresh_token": "rtok"},
    )
    assert resp.status_code == 200, resp.text
    # No duplicate user created.
    from app.db.models.user import User

    count = len(
        db.execute(select(User).where(User.email == "oauth@example.com")).scalars().all()
    )
    assert count == 1


def test_oauth_google_password_account_conflict_returns_409(client, db, mocks):
    _seed_user(db, email="haspw@example.com", password_hash=SENTINEL)
    mocks.verify_token.return_value = {
        "sub": str(uuid.uuid4()),
        "email": "haspw@example.com",
        "app_metadata": {"provider": "google"},
    }
    resp = client.post(
        "/auth/oauth/google",
        json={"supabase_access_token": "tok", "supabase_refresh_token": "rtok"},
    )
    assert resp.status_code == 409
    assert resp.json() == {"error": "account_link_required", "email": "haspw@example.com"}


def test_oauth_google_conflict_no_user_created(client, db, mocks):
    _seed_user(db, email="haspw2@example.com", password_hash=SENTINEL)
    sub = str(uuid.uuid4())
    mocks.verify_token.return_value = {
        "sub": sub,
        "email": "haspw2@example.com",
        "app_metadata": {"provider": "google"},
    }
    client.post(
        "/auth/oauth/google",
        json={"supabase_access_token": "tok", "supabase_refresh_token": "rtok"},
    )
    from app.db.models.user import User

    # Only the original password account exists; no OAuth record + no session.
    rows = db.execute(select(User).where(User.email == "haspw2@example.com")).scalars().all()
    assert len(rows) == 1
    assert rows[0].password_hash == SENTINEL
    assert _subscriptions_for(db, uuid.UUID(sub)) == []


def test_oauth_google_invalid_token_returns_401(client, db, mocks):
    from app.auth.jwt_verifier import TokenVerificationError

    mocks.verify_token.side_effect = TokenVerificationError("bad token")
    resp = client.post(
        "/auth/oauth/google",
        json={"supabase_access_token": "bad", "supabase_refresh_token": "rtok"},
    )
    assert resp.status_code == 401


# =========================================================================== #
# US-002 — token refresh
# =========================================================================== #
def test_refresh_valid_token_returns_200(client, mocks):
    resp = client.post("/auth/refresh", json={"refresh_token": "valid_refresh"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"] == "new_access"
    assert body["refresh_token"] == "new_refresh"


def test_refresh_expired_token_returns_401(client, mocks):
    mocks.refresh.side_effect = mocks.SupabaseAuthError("invalid refresh token")
    resp = client.post("/auth/refresh", json={"refresh_token": "expired"})
    assert resp.status_code == 401
    assert resp.json() == {"error": "invalid_or_expired_refresh_token"}


# =========================================================================== #
# US-002 — logout
# =========================================================================== #
def _override_current_user(client):
    """Override get_current_user on the test app to a fixed authenticated user."""
    from app.auth.dependencies import CurrentUser, get_current_user

    user = CurrentUser(id=uuid.uuid4(), email="loggedin@example.com", role="user", team_id=None)
    client.app.dependency_overrides[get_current_user] = lambda: user
    return user


def test_logout_returns_204(client, mocks):
    _override_current_user(client)
    resp = client.post("/auth/logout", headers={"Authorization": "Bearer abc123"})
    assert resp.status_code == 204
    assert resp.content == b""
    mocks.sign_out.assert_awaited_once()
    assert mocks.sign_out.await_args.args[0] == "abc123"


def test_logout_status_code_is_204_not_200(client, mocks):
    _override_current_user(client)
    resp = client.post("/auth/logout", headers={"Authorization": "Bearer abc123"})
    assert resp.status_code == 204
    assert resp.status_code != 200


def test_logout_unauthenticated_returns_401(client, mocks):
    # No get_current_user override and no Authorization header → 401.
    resp = client.post("/auth/logout")
    assert resp.status_code == 401


# =========================================================================== #
# US-002 — password reset request
# =========================================================================== #
def test_password_reset_request_registered_email_returns_204(client, db, mocks):
    _seed_user(db, email="reset@example.com")
    resp = client.post("/auth/password-reset/request", json={"email": "reset@example.com"})
    assert resp.status_code == 204
    assert resp.content == b""


def test_password_reset_request_enqueues_task(client, db, mocks):
    uid = _seed_user(db, email="reset2@example.com", display_name="Reset User")
    client.post("/auth/password-reset/request", json={"email": "reset2@example.com"})
    mocks.enqueue.assert_called_once()
    payload = mocks.enqueue.call_args.args[0]
    assert payload["task_name"] == "send_password_reset_email"
    assert payload["user_id"] == str(uid)
    assert payload["email"] == "reset2@example.com"
    assert payload["display_name"] == "Reset User"
    assert payload["reset_url"] == "https://auth.example.com/verify?token=mock_token"


def test_password_reset_request_unregistered_email_returns_204(client, mocks):
    resp = client.post(
        "/auth/password-reset/request", json={"email": "ghost@example.com"}
    )
    assert resp.status_code == 204


def test_password_reset_request_unregistered_no_task(client, mocks):
    client.post("/auth/password-reset/request", json={"email": "ghost@example.com"})
    mocks.enqueue.assert_not_called()


def test_password_reset_request_response_identical_for_known_and_unknown(client, db, mocks):
    _seed_user(db, email="known@example.com")
    known = client.post("/auth/password-reset/request", json={"email": "known@example.com"})
    unknown = client.post("/auth/password-reset/request", json={"email": "unknown@example.com"})
    assert known.status_code == unknown.status_code == 204
    assert known.content == unknown.content == b""


def test_password_reset_request_status_code_is_204_not_200(client, db, mocks):
    _seed_user(db, email="exact@example.com")
    resp = client.post("/auth/password-reset/request", json={"email": "exact@example.com"})
    assert resp.status_code == 204
    assert resp.status_code != 200


# =========================================================================== #
# US-002 — password reset confirm (Rule #12 ordering)
# =========================================================================== #
def test_password_reset_confirm_valid_token_returns_204(client, db, mocks):
    uid = _seed_user(db, email="confirm@example.com")
    mocks.reset_pw.return_value = {"user": {"id": str(uid)}}
    resp = client.post(
        "/auth/password-reset/confirm",
        json={"token": "valid_token", "new_password": "Br4ndNewSecret!"},
    )
    assert resp.status_code == 204
    assert resp.content == b""


def test_password_reset_confirm_signout_before_db_update(client, db, mocks):
    uid = _seed_user(db, email="order@example.com")
    mocks.reset_pw.return_value = {"user": {"id": str(uid)}}

    order = []
    mocks.admin_sign_out.side_effect = lambda *a, **k: order.append("signout")

    real_commit = db.commit

    def _tracked_commit():
        order.append("commit")
        return real_commit()

    # Track the token-invalidation commit ordering relative to admin_sign_out.
    db.commit = _tracked_commit  # type: ignore[method-assign]
    try:
        client.post(
            "/auth/password-reset/confirm",
            json={"token": "valid_token", "new_password": "Br4ndNewSecret!"},
        )
    finally:
        db.commit = real_commit  # type: ignore[method-assign]

    assert "signout" in order and "commit" in order
    assert order.index("signout") < order.index("commit")


def test_password_reset_confirm_updates_token_invalidated_at(client, db, mocks):
    uid = _seed_user(db, email="invalidate@example.com")
    mocks.reset_pw.return_value = {"user": {"id": str(uid)}}
    before = datetime.now(timezone.utc)
    client.post(
        "/auth/password-reset/confirm",
        json={"token": "valid_token", "new_password": "Br4ndNewSecret!"},
    )
    user = _user_by_email(db, "invalidate@example.com")
    assert user.token_invalidated_at is not None
    tia = user.token_invalidated_at
    if tia.tzinfo is None:
        tia = tia.replace(tzinfo=timezone.utc)
    assert tia >= before - timedelta(seconds=2)


def test_password_reset_confirm_returns_500_if_signout_fails(client, db, mocks):
    uid = _seed_user(db, email="signoutfail@example.com")
    mocks.reset_pw.return_value = {"user": {"id": str(uid)}}
    mocks.admin_sign_out.side_effect = Exception("Supabase signout failed")
    resp = client.post(
        "/auth/password-reset/confirm",
        json={"token": "valid_token", "new_password": "Br4ndNewSecret!"},
    )
    assert resp.status_code == 500


def test_password_reset_confirm_no_db_update_if_signout_fails(client, db, mocks):
    uid = _seed_user(db, email="nodbupdate@example.com")
    mocks.reset_pw.return_value = {"user": {"id": str(uid)}}
    mocks.admin_sign_out.side_effect = Exception("Supabase signout failed")
    client.post(
        "/auth/password-reset/confirm",
        json={"token": "valid_token", "new_password": "Br4ndNewSecret!"},
    )
    user = _user_by_email(db, "nodbupdate@example.com")
    assert user.token_invalidated_at is None


def test_password_reset_confirm_invalid_token_returns_400(client, db, mocks):
    mocks.reset_pw.side_effect = mocks.SupabaseAuthError("invalid recovery token")
    resp = client.post(
        "/auth/password-reset/confirm",
        json={"token": "bad", "new_password": "Br4ndNewSecret!"},
    )
    assert resp.status_code == 400
    assert resp.json() == {"error": "invalid_or_expired_reset_token"}


def test_password_reset_confirm_invalid_token_no_signout(client, db, mocks):
    mocks.reset_pw.side_effect = mocks.SupabaseAuthError("invalid recovery token")
    client.post(
        "/auth/password-reset/confirm",
        json={"token": "bad", "new_password": "Br4ndNewSecret!"},
    )
    mocks.admin_sign_out.assert_not_called()


def test_password_reset_confirm_token_invalidated_at_is_after_signout(client, db, mocks):
    uid = _seed_user(db, email="afterso@example.com")
    mocks.reset_pw.return_value = {"user": {"id": str(uid)}}

    signout_times = []
    mocks.admin_sign_out.side_effect = lambda *a, **k: signout_times.append(
        datetime.now(timezone.utc)
    )
    client.post(
        "/auth/password-reset/confirm",
        json={"token": "valid_token", "new_password": "Br4ndNewSecret!"},
    )
    user = _user_by_email(db, "afterso@example.com")
    tia = user.token_invalidated_at
    if tia.tzinfo is None:
        tia = tia.replace(tzinfo=timezone.utc)
    assert signout_times, "admin_sign_out was not called"
    assert tia >= signout_times[0]


def test_password_reset_confirm_status_code_is_204_not_200(client, db, mocks):
    uid = _seed_user(db, email="exact-confirm@example.com")
    mocks.reset_pw.return_value = {"user": {"id": str(uid)}}
    resp = client.post(
        "/auth/password-reset/confirm",
        json={"token": "valid_token", "new_password": "Br4ndNewSecret!"},
    )
    assert resp.status_code == 204
    assert resp.status_code != 200


# =========================================================================== #
# Wiring — all seven endpoints registered under /auth, shadowing the stubs
# =========================================================================== #
def test_all_auth_endpoints_registered_under_auth_prefix():
    from app.api.routers.auth import router as auth_router

    paths = {route.path for route in auth_router.routes}
    expected = {
        "/auth/register",
        "/auth/login",
        "/auth/oauth/google",
        "/auth/refresh",
        "/auth/logout",
        "/auth/password-reset/request",
        "/auth/password-reset/confirm",
    }
    assert expected <= paths


def test_enqueue_notification_uses_persistent_notification_queue(monkeypatch):
    # Rule #14: notification tasks must be dispatched onto the persistent Celery
    # broker (never in-memory), routed to the `notification` queue, carrying the
    # exact payload shape S2-M consumes.
    import app.workers.celery_app as celery_mod
    from app.services import auth_service
    from app.workers import queues

    sent = {}

    def _send_task(name, args=None, queue=None, **kwargs):
        sent.update(name=name, args=args, queue=queue)

    monkeypatch.setattr(celery_mod.celery_app, "send_task", _send_task)

    payload = {
        "task_name": "send_verification_email",
        "user_id": "u",
        "email": "e@example.com",
        "display_name": "d",
        "verification_url": "https://auth.example.com/verify?token=x",
    }
    auth_service.enqueue_notification(payload)

    assert sent["name"] == "notification.send_verification_email"
    assert sent["queue"] == queues.QUEUE_NOTIFICATION
    assert sent["args"] == [payload]


def test_auth_router_shadows_stubs_in_app_main():
    import app.main as main

    by_path = {}
    for route in main.app.routes:
        path = getattr(route, "path", None)
        if path and path.startswith("/auth") and path not in by_path:
            by_path[path] = route
    # The real router is included ahead of the 501 stubs, so /auth/* resolves to
    # the S2-A handlers.
    register = by_path.get("/auth/register")
    assert register is not None
    assert register.endpoint.__module__ == "app.api.routers.auth"
